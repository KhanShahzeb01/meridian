import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table

from ..agent.agent import Agent
from ..helpers import TokenCounter
from ..llm import LLMError
from ..storage import Storage
from . import data_provider as dp
from . import personas
from . import universe as uv

logger = logging.getLogger(__name__)

MAX_AGENT_CANDIDATES = 30
DEFAULT_FINAL_COUNT = 10

STYLE_KEYWORDS: dict[str, list[str]] = {
    "value": ["value", "undervalued", "cheap", "bargain", "low pe", "deep value"],
    "growth": ["growth", "growing", "high growth", "revenue growth", "earnings growth"],
    "quality": ["quality", "durable", "strong", "best in class", "stable"],
    "momentum": ["momentum", "trending", "breakout", "strong price", "relative strength"],
}

DEFAULT_PERSONAS = ["value", "growth", "quality", "momentum"]

Criteria = dict[str, Any]


def _agent_results_have_scores(agent_results: dict[str, dict[str, dict]]) -> bool:
    return any(scores for scores in agent_results.values())


def parse_intent(prompt: str) -> Criteria:
    text = prompt.lower().strip()

    criteria: Criteria = {
        "raw": prompt,
        "sector": None,
        "style": None,
        "personas": list(DEFAULT_PERSONAS),
        "tickers": None,
        "min_mcap": None,
        "max_pe": None,
        "min_rev_growth": None,
    }

    for token in re.split(r"[,;\s]+", text):
        if "=" in token:
            k, v = token.split("=", 1)
            k = k.strip()
            v = v.strip()
            if k == "sector":
                criteria["sector"] = v
            elif k == "style":
                criteria["style"] = v
            elif k == "min_mcap":
                try:
                    vn = float(v.upper().replace("B", "e9").replace("T", "e12").replace("M", "e6"))
                    criteria["min_mcap"] = vn
                except ValueError:
                    pass
            elif k == "max_pe":
                try:
                    criteria["max_pe"] = float(v)
                except ValueError:
                    pass

    if criteria["style"]:
        matched = [k for k in STYLE_KEYWORDS if criteria["style"] in STYLE_KEYWORDS[k] or k == criteria["style"]]
        if matched:
            criteria["personas"] = matched

    for token in re.split(r"[,;\s]+", text):
        token = token.strip().lower()
        for style, keywords in STYLE_KEYWORDS.items():
            if token in keywords or token == style:
                criteria["style"] = style
                criteria["personas"] = [style]
                break

    for token in re.split(r"[,;\s]+", text):
        token = token.strip().lower()
        group = uv.resolve_group(token)
        if group is not None:
            criteria["sector"] = token
            break

    if criteria["sector"] is None and criteria["tickers"] is None:
        tokens = [t.strip().upper() for t in re.split(r"[,;\s]+", text) if t.strip()]
        candidates = [t for t in tokens if re.match(r"^[A-Z]{1,5}$", t) and t not in {"ALL", "SCREEN", "STOCKS", "FIND", "SHOW", "LIST", "BEST", "TOP", "FOR", "THE", "AND", "WITH"}]
        if len(candidates) >= 2 and len(candidates) <= 20:
            criteria["tickers"] = candidates
            criteria["sector"] = None

    return criteria


class ScreenerOrchestrator:
    def __init__(self, agent: Agent, storage: Storage | None = None, final_count: int | None = None):
        self.agent = agent
        self.llm = agent.llm
        self.storage = storage
        self.final_count = final_count if final_count is not None else DEFAULT_FINAL_COUNT

    def screen(self, prompt: str, console: Console | None = None) -> str:
        c = parse_intent(prompt)

        if console:
            console.print(f"\n[yellow]🔍 Screening:[/yellow] [white]{prompt}[/white]")

        status = StatusPanel("Progress", console)
        try:
            tickers = self._resolve_tickers(c, status)
            if not tickers:
                return "[red]No tickers found matching your criteria.[/red]"

            if len(tickers) > 200:
                status.update(f"[yellow]Large universe ({len(tickers)} stocks). Fetching basic metrics...[/yellow]")

            basic = dp.fetch_basic(tickers, self.storage)
            if not basic:
                return "[red]Could not fetch data for any ticker. Check your yfinance installation or internet connection.[/red]"

            status.update(f"Basic data: {len(basic)}/{len(tickers)} tickers fetched")

            candidates = self._algo_filter(basic, c, status)

            if len(candidates) > MAX_AGENT_CANDIDATES:
                candidates = candidates[:MAX_AGENT_CANDIDATES]

            status.update(f"[green]Shortlisted {len(candidates)} candidates for analysis.[/green]")

            deep = dp.fetch_deep(candidates, self.storage)
            deep = self._hydrate_deep_from_basic(candidates, basic, deep, status)
            status.update(f"[green]Deep data fetched for {len(deep)} stocks.[/green]")

            agent_results, agent_errors = self._run_agents(deep, c, status)
            if not _agent_results_have_scores(agent_results):
                if agent_errors:
                    err_preview = "; ".join(agent_errors[:2])
                    status.update(
                        f"[yellow]LLM screening failed ({err_preview}). "
                        "Using data-only fallback ranking.[/yellow]"
                    )
                else:
                    status.update(
                        "[yellow]Agents returned no scores. Using data-only fallback ranking.[/yellow]"
                    )
                consensus = self._build_fallback_consensus(deep, c)
                if not consensus:
                    if agent_errors:
                        return (
                            f"{agent_errors[0]}\n\n"
                            "[dim]Tip: /screen tech value narrows the universe.[/dim]"
                        )
                    return "[red]Could not build screening results from available market data.[/red]"
                return self._format_results(consensus, {}, deep, None)

            consensus = self._build_consensus(agent_results, deep)
            status.update("[green]Consensus built. Generating thesis...[/green]")

            moderator = self._run_moderator(c, agent_results, deep, status)

            return self._format_results(consensus, agent_results, deep, moderator)
        finally:
            # Always close the Live panel so control returns to the CLI prompt.
            status.stop()

    def _resolve_tickers(self, c: Criteria, status: "StatusPanel") -> list[str]:
        if c.get("tickers"):
            status.update(f"[yellow]Custom tickers: {len(c['tickers'])}[/yellow]")
            return c["tickers"]

        sector = c.get("sector")
        if sector and sector != "all":
            group = uv.resolve_group(sector)
            if group:
                status.update(f"[yellow]Universe: {sector} ({len(group)} stocks)[/yellow]")
                return group
            status.update(f"[yellow]Unknown sector '{sector}', using full universe.[/yellow]")

        all_tickers = uv.get_all_tickers()
        status.update(f"[yellow]Full universe: {len(all_tickers)} stocks[/yellow]")
        return all_tickers

    def _algo_filter(self, basic: dp.BasicMetrics, c: Criteria, status: "StatusPanel") -> list[str]:
        scored: list[tuple[str, float]] = []
        for ticker, data in basic.items():
            price = data.get("price")
            mcap_raw = data.get("mcap")
            pe_raw = data.get("pe")
            if price is None or mcap_raw is None:
                continue
            mcap = float(mcap_raw)
            min_mcap = c.get("min_mcap")
            if min_mcap and mcap < min_mcap:
                continue
            max_pe = c.get("max_pe")
            pe_val = float(pe_raw) if isinstance(pe_raw, (int, float)) and pe_raw > 0 else None
            if max_pe and pe_val and pe_val > max_pe:
                continue

            score = 0.0
            style = c.get("style", "")
            mcap_score = min(mcap / 1e10, 10.0)

            if style == "value":
                if pe_val:
                    score += 50.0 / pe_val * 0.5
                score += mcap_score * 0.3
            elif style == "growth":
                score += mcap_score * 0.5
                if pe_val:
                    score += 10.0 / pe_val * 0.2
            elif style == "quality":
                score += mcap_score * 0.5
                if pe_val:
                    score += 20.0 / pe_val * 0.2
            elif style == "momentum":
                score += mcap_score * 0.3
            else:
                score += mcap_score * 0.4
                if pe_val:
                    score += 10.0 / pe_val * 0.3

            scored.append((ticker, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        result = [t for t, _ in scored]
        status.update(f"[green]Pre-filter: {len(result)} candidates remain[/green]")
        return result

    def _run_agents(
        self, deep: dp.DeepMetrics, c: Criteria, status: "StatusPanel"
    ) -> tuple[dict[str, dict[str, dict]], list[str]]:
        data_rows = list(deep.values())
        if not data_rows:
            return {}, []

        all_results: dict[str, dict[str, dict]] = {}
        errors: list[str] = []
        personas_to_run = c.get("personas", DEFAULT_PERSONAS)

        with ThreadPoolExecutor(max_workers=len(personas_to_run)) as ex:
            futures = {}
            for pk in personas_to_run:
                messages = personas.build_screener_prompt(pk, c.get("raw", ""), data_rows)
                status.update(f"Running {personas.PERSONAS[pk]['name']} agent...")
                futures[ex.submit(self._call_llm, messages)] = pk

            for f in as_completed(futures):
                pk = futures[f]
                try:
                    result, err = f.result()
                    if err:
                        errors.append(f"{personas.PERSONAS[pk]['short']}: {err}")
                    parsed = self._parse_agent_response(result)
                    all_results[pk] = parsed
                    count = len(parsed)
                    if count:
                        status.update(f"[green]{personas.PERSONAS[pk]['short']}: {count} stocks scored[/green]")
                    elif err:
                        short = err.split("\n", 1)[0].strip()
                        status.update(f"[red]{personas.PERSONAS[pk]['short']}: {short}[/red]")
                    else:
                        status.update(
                            f"[yellow]{personas.PERSONAS[pk]['short']}: 0 stocks scored[/yellow]"
                        )
                except Exception as e:
                    logger.warning("Agent %s failed: %s", pk, e)
                    errors.append(f"{personas.PERSONAS[pk]['short']}: {e}")
                    status.update(f"[red]{personas.PERSONAS[pk]['short']} agent failed[/red]")

        return all_results, errors

    def _hydrate_deep_from_basic(
        self,
        candidates: list[str],
        basic: dp.BasicMetrics,
        deep: dp.DeepMetrics,
        status: "StatusPanel",
    ) -> dp.DeepMetrics:
        """
        If deep fetch is empty/partial (e.g., yfinance rate limiting), backfill
        minimal rows from already-fetched basic metrics so screening can proceed.
        """
        hydrated: dp.DeepMetrics = dict(deep)
        added = 0
        for ticker in candidates:
            if ticker in hydrated:
                continue
            b = basic.get(ticker)
            if not b:
                continue
            hydrated[ticker] = {
                "ticker": ticker,
                "name": b.get("name", ticker),
                "price": b.get("price"),
                "mcap": b.get("mcap"),
                "pe": b.get("pe"),
                "sector": b.get("sector", "") or "",
                "industry": b.get("industry", "") or "",
                # Keep deep-only metrics empty; downstream logic handles missing values.
                "forward_pe": None,
                "pb": None,
                "ps": None,
                "peg": None,
                "div_yield": None,
                "payout": None,
                "eps": None,
                "roe": None,
                "roa": None,
                "de": None,
                "rev_growth": None,
                "earnings_growth": None,
                "gross_margin": None,
                "op_margin": None,
                "profit_margin": None,
                "beta": None,
                "free_cf": None,
                "rec_key": None,
                "target_mean": None,
                "target_high": None,
                "target_low": None,
                "fifty_two_high": None,
                "fifty_two_low": None,
                "avg_vol": None,
                "volume": None,
                "shares": None,
                "prev_close": None,
                "change_pct": None,
                "mom_3m_pct": None,
            }
            added += 1

        if added:
            status.update(f"[yellow]Deep data rate-limited. Backfilled {added} stocks from basic metrics.[/yellow]")
        return hydrated

    def _build_fallback_consensus(self, deep: dp.DeepMetrics, c: Criteria) -> list[dict]:
        """
        Deterministic ranking used when LLM screening agents fail/unavailable.
        """
        style = c.get("style")
        rows: list[dict] = []
        for ticker, d in deep.items():
            mcap = d.get("mcap")
            pe = d.get("pe")
            rev_growth = d.get("rev_growth")
            profit_margin = d.get("profit_margin")
            roe = d.get("roe")
            change_pct = d.get("change_pct")
            mom_3m = d.get("mom_3m_pct")

            score = 0.0
            if isinstance(mcap, (int, float)) and mcap > 0:
                score += min(float(mcap) / 1e11, 10.0) * 0.25
            if isinstance(pe, (int, float)) and pe > 0:
                score += min(50.0 / float(pe), 10.0) * 0.30
            if isinstance(rev_growth, (int, float)):
                score += max(min(float(rev_growth) * 100.0, 30.0), -30.0) * 0.03
            if isinstance(profit_margin, (int, float)):
                score += max(min(float(profit_margin) * 100.0, 40.0), -40.0) * 0.02
            if isinstance(roe, (int, float)):
                score += max(min(float(roe) * 100.0, 40.0), -40.0) * 0.015
            if isinstance(mom_3m, (int, float)):
                score += max(min(float(mom_3m), 50.0), -50.0) * 0.015
            elif isinstance(change_pct, (int, float)):
                score += max(min(float(change_pct), 20.0), -20.0) * 0.01

            if style == "value" and isinstance(pe, (int, float)) and pe > 0:
                score += min(30.0 / float(pe), 10.0) * 0.8
            elif style == "growth" and isinstance(rev_growth, (int, float)):
                score += max(min(float(rev_growth) * 100.0, 40.0), -40.0) * 0.04
            elif style == "quality":
                if isinstance(roe, (int, float)):
                    score += max(min(float(roe) * 100.0, 40.0), -40.0) * 0.04
                if isinstance(profit_margin, (int, float)):
                    score += max(min(float(profit_margin) * 100.0, 40.0), -40.0) * 0.03
            elif style == "momentum":
                if isinstance(mom_3m, (int, float)):
                    score += max(min(float(mom_3m), 50.0), -50.0) * 0.08
                elif isinstance(change_pct, (int, float)):
                    score += max(min(float(change_pct), 20.0), -20.0) * 0.04

            avg_score = max(1.0, min(10.0, round(score, 1)))
            rows.append(
                {
                    "ticker": ticker,
                    "avg_score": avg_score,
                    "std": 0.0,
                    "agent_count": 0,
                    "agent_scores": {},
                    "reasons": {},
                    "name": d.get("name", ticker),
                    "price": d.get("price"),
                    "mcap": d.get("mcap"),
                    "pe": d.get("pe"),
                    "sector": d.get("sector", ""),
                }
            )

        rows.sort(key=lambda x: (-x["avg_score"], -(x.get("mcap") or 0)))
        return rows[: self.final_count]

    def _call_llm(self, messages: list[dict]) -> tuple[str, str | None]:
        """Returns (raw_text, error_message). On total failure raw_text is '[]'."""
        models_to_try: list[str | None] = [None]
        for model in getattr(self.llm, "_fallback_models", []):
            if model and model not in models_to_try:
                models_to_try.append(model)

        last_error: str | None = None
        for force_model in models_to_try:
            try:
                result = self.llm.prompt(
                    messages,
                    task_type="action",
                    no_cache=force_model is not None,
                    force_model=force_model,
                )
                text = str(result) if not isinstance(result, str) else result
                if text.strip():
                    return text, None
                last_error = "empty response"
            except LLMError as e:
                model = force_model or getattr(self.llm, "last_model", None)
                last_error = e.user_message(model=model)
                logger.warning(
                    "Screener LLM failed (model=%s): %s",
                    force_model or "default",
                    e,
                )
                retryable = e.reason_code in ("rate_limit", "timeout", "network") or (
                    getattr(e, "http_status", None) in (429, 502, 503, 504)
                )
                if retryable and force_model != models_to_try[-1]:
                    continue
                if not retryable:
                    break

        return "[]", last_error

    def _parse_agent_response(self, raw: str) -> dict[str, dict]:
        text = raw.strip()
        if not text:
            return {}

        candidates = []
        seen = set()

        def add_candidate(s):
            s = (s or "").strip()
            if s and s not in seen:
                seen.add(s)
                candidates.append(s)

        add_candidate(text)
        start, end = text.find("["), text.rfind("]")
        if start != -1 and end != -1 and end > start:
            add_candidate(text[start : end + 1])

        for cand in candidates:
            try:
                data = json.loads(cand)
            except json.JSONDecodeError:
                continue
            if isinstance(data, list):
                result = {}
                for item in data:
                    if isinstance(item, dict) and "ticker" in item and "score" in item:
                        ticker = item["ticker"].upper().strip()
                        score = int(item["score"])
                        score = max(1, min(10, score))
                        result[ticker] = {
                            "score": score,
                            "reasoning": str(item.get("reasoning", ""))[:100],
                        }
                if result:
                    return result
                return result
            if isinstance(data, dict):
                result = {}
                if "ticker" in data and "score" in data:
                    t = data["ticker"].upper().strip()
                    s = int(data["score"])
                    result[t] = {"score": max(1, min(10, s)), "reasoning": str(data.get("reasoning", ""))[:100]}
                    return result
                for key, val in data.items():
                    if isinstance(val, dict) and "score" in val:
                        k = key.upper().strip()
                        s = int(val["score"])
                        result[k] = {"score": max(1, min(10, s)), "reasoning": str(val.get("reasoning", ""))[:100]}
                    elif isinstance(val, (int, float)):
                        k = key.upper().strip()
                        result[k] = {"score": max(1, min(10, int(val))), "reasoning": ""}
                if result:
                    return result

        return {}

    def _build_consensus(
        self, agent_results: dict[str, dict[str, dict]], deep: dp.DeepMetrics
    ) -> list[dict]:
        all_tickers: set[str] = set()
        for scores in agent_results.values():
            all_tickers.update(scores.keys())

        rows = []
        for ticker in all_tickers:
            all_scores = []
            reasons: dict[str, str] = {}
            for agent_key, scores in agent_results.items():
                entry = scores.get(ticker)
                if entry:
                    all_scores.append(entry["score"])
                    reasons[personas.PERSONAS.get(agent_key, {}).get("short", agent_key)] = entry.get("reasoning", "")
            if not all_scores:
                continue

            avg = sum(all_scores) / len(all_scores)
            std = (sum((s - avg) ** 2 for s in all_scores) / len(all_scores)) ** 0.5
            d = deep.get(ticker, {})
            rows.append({
                "ticker": ticker,
                "avg_score": round(avg, 1),
                "std": round(std, 1),
                "agent_count": len(all_scores),
                "agent_scores": {
                    agent_key: scores[ticker].get("score")
                    for agent_key, scores in agent_results.items()
                    if ticker in scores
                },
                "reasons": reasons,
                "name": d.get("name", ticker),
                "price": d.get("price"),
                "mcap": d.get("mcap"),
                "pe": d.get("pe"),
                "sector": d.get("sector", ""),
            })

        rows.sort(key=lambda x: (-x["avg_score"], x["std"]))

        return rows[:self.final_count]

    def _run_moderator(
        self,
        c: Criteria,
        agent_results: dict[str, dict[str, dict]],
        deep: dp.DeepMetrics,
        status: "StatusPanel",
    ) -> str | None:
        if len(agent_results) < 2:
            return None

        try:
            messages = personas.build_moderator_prompt(c.get("raw", ""), agent_results, len(deep))
            status.update("[yellow]Moderator synthesizing final thesis...[/yellow]")
            result = self.llm.prompt(messages, task_type="action", no_cache=True)
            return str(result) if not isinstance(result, str) else result
        except Exception:
            return None

    def _format_results(
        self,
        consensus: list[dict],
        agent_results: dict[str, dict[str, dict]],
        deep: dp.DeepMetrics,
        moderator: str | None,
    ) -> str:
        if not consensus:
            return (
                "[yellow]No stocks in the consensus list.[/yellow] "
                "Try narrowing criteria, e.g. [cyan]/screen tech value[/cyan] or "
                "[cyan]/screen sector=healthcare style=growth[/cyan]."
            )

        import io
        from rich.console import Console as RichConsole

        out = io.StringIO()
        rc = RichConsole(file=out, force_terminal=False, safe_box=True, width=140)

        agent_short_names = [
            personas.PERSONAS.get(k, {}).get("short", k) for k in agent_results.keys()
        ]

        table = Table(
            title=f"Screening Results — Top {len(consensus)} Stocks",
            title_style="bold cyan",
            header_style="bright_green",
        )
        table.add_column("Ticker", style="white", no_wrap=True)
        table.add_column("Name", style="dim")
        table.add_column("Score", justify="right")
        for an in agent_short_names:
            table.add_column(an, justify="center", style="dim")
        table.add_column("Disc.", style="yellow", justify="center")
        table.add_column("Price", justify="right")
        table.add_column("P/E", justify="right")
        table.add_column("Mkt Cap", justify="right")
        table.add_column("Sector", style="dim")

        for row in consensus:
            ticker = row["ticker"]
            parts = []
            for ax in agent_results.keys():
                s = row.get("agent_scores", {}).get(ax)
                if s is not None:
                    color = "green" if s >= 7 else "yellow" if s >= 5 else "red"
                    parts.append(f"[{color}]{s}[/{color}]")
                else:
                    parts.append("[dim]—[/dim]")

            disc = f"[red]{row['std']:.1f}[/red]" if row["std"] > 2.0 else "[dim]✓[/dim]"

            price = row.get("price")
            price_str = f"${float(price):.2f}" if price else "—"
            pe = row.get("pe")
            pe_str = f"{float(pe):.1f}" if pe else "—"
            mcap = row.get("mcap")
            if mcap:
                mcap_str = f"${float(mcap)/1e9:.1f}B" if mcap >= 1e9 else f"${float(mcap)/1e6:.0f}M"
            else:
                mcap_str = "—"

            table.add_row(
                ticker,
                str(row.get("name", ""))[:20],
                f"[bold]{row['avg_score']:.1f}[/bold]",
                *parts,
                disc,
                price_str,
                pe_str,
                mcap_str,
                str(row.get("sector", ""))[:15],
            )

        rc.print(table)
        table_str = out.getvalue()

        if moderator:
            table_str += "\n\n[bold]📋 Moderator Thesis:[/bold]\n"
            table_str += str(moderator)[:2000]

        table_str += self._format_detailed_scores(consensus, agent_results)

        return table_str

    def _format_detailed_scores(
        self, consensus: list[dict], agent_results: dict[str, dict[str, dict]]
    ) -> str:
        lines = ["\n\n[bold]Agent Scores Per Stock:[/bold]"]
        for row in consensus:
            ticker = row["ticker"]
            reasons = row.get("reasons", {})
            agent_parts = []
            for agent_key in agent_results:
                short = personas.PERSONAS.get(agent_key, {}).get("short", agent_key)
                score = row.get("agent_scores", {}).get(agent_key)
                note = reasons.get(short, reasons.get(agent_key, ""))
                if score is not None:
                    agent_parts.append(f"  {short}: [bold]{score}/10[/bold] — {note}")
            if agent_parts:
                lines.append(f"\n[white]{ticker}[/white] — Avg [bold]{row['avg_score']:.1f}[/bold]/10")
                lines.extend(agent_parts)
        return "\n".join(lines)


class StatusPanel:
    def __init__(self, title: str, console: Console | None = None):
        self.console = console
        self.title = title
        self._lines: list[str] = []
        self._live: Live | None = None

        if console:
            self._live = Live(
                Panel("Initializing...", title=title, style="magenta"),
                console=console,
                refresh_per_second=10,
            )
            self._live.__enter__()

    def update(self, msg: str):
        self._lines.append(msg)
        if self._live:
            content = "\n".join(self._lines[-8:])
            self._live.update(Panel(content, title=self.title, style="magenta"))

    def stop(self):
        if self._live:
            self._live.__exit__(None, None, None)
            self._live = None
