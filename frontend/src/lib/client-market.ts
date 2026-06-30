import type { MarketHeadline, MarketIndex } from "./api";
import { fetchYahooChart, fetchYahooJson } from "./yahoo-fetch";

const INDICES = [
  { id: "sp500", name: "S&P 500", symbol: "^GSPC", fallback: "SPY" },
  { id: "nasdaq", name: "NASDAQ", symbol: "^IXIC", fallback: "QQQ" },
  { id: "dow", name: "Dow Jones", symbol: "^DJI", fallback: "DIA" },
  { id: "gold", name: "Gold", symbol: "GC=F", fallback: "GLD" },
  { id: "crude", name: "Crude Oil", symbol: "CL=F", fallback: "USO" },
  { id: "vix", name: "VIX", symbol: "^VIX", fallback: "VIXY" },
] as const;

export interface SnapshotQuote {
  price: number;
  prev_close?: number | null;
  change_pct?: number | null;
}

interface MarketSnapshot {
  indices: MarketIndex[];
  headlines: MarketHeadline[];
  quotes?: Record<string, SnapshotQuote>;
  updated_at: string;
  source?: string;
}

function basePath(): string {
  if (typeof window !== "undefined") {
    const m = window.location.pathname.match(/^(\/[^/]+)\//);
    if (m) return m[1];
  }
  return process.env.NEXT_PUBLIC_BASE_PATH || "";
}

function snapshotUrls(): string[] {
  const bp = basePath();
  return [
    `${bp}/market-snapshot.json`,
    "https://raw.githubusercontent.com/KhanShahzeb01/meridian/main/docs/market-snapshot.json",
  ];
}

let snapshotPromise: Promise<MarketSnapshot | null> | null = null;

export async function loadSnapshot(): Promise<MarketSnapshot | null> {
  if (!snapshotPromise) {
    snapshotPromise = (async () => {
      for (const url of snapshotUrls()) {
        try {
          const res = await fetch(url, { cache: "no-store" });
          if (!res.ok) continue;
          const data = (await res.json()) as MarketSnapshot;
          if (data.indices?.length || data.headlines?.length || data.quotes) return data;
        } catch {
          /* try next */
        }
      }
      return null;
    })();
  }
  return snapshotPromise;
}

async function fetchIndex(meta: (typeof INDICES)[number]): Promise<MarketIndex> {
  let { series, price, prev } = await fetchYahooChart(meta.symbol);
  if (!series.length && price == null) {
    const fb = await fetchYahooChart(meta.fallback);
    series = fb.series;
    price = fb.price;
    prev = fb.prev;
  }
  let change: number | null = null;
  let change_pct: number | null = null;
  if (price != null && prev != null && prev !== 0) {
    change = price - prev;
    change_pct = (change / prev) * 100;
  }
  return {
    id: meta.id,
    name: meta.name,
    symbol: meta.symbol,
    price,
    change,
    change_pct,
    series,
    source: "yahoo",
  };
}

async function fetchLiveIndices(): Promise<MarketIndex[] | null> {
  try {
    const indices = await Promise.all(INDICES.map(fetchIndex));
    if (indices.every((i) => !i.series.length && i.price == null)) return null;
    return indices;
  } catch {
    return null;
  }
}

async function fetchLiveHeadlines(limit: number): Promise<MarketHeadline[] | null> {
  try {
    const url = `https://query1.finance.yahoo.com/v1/finance/search?q=finance&newsCount=${limit}`;
    const data = (await fetchYahooJson(url)) as { news?: { title?: string; link?: string; providerPublishTime?: number; publisher?: string }[] } | null;
    if (!data?.news?.length) return null;
    const headlines: MarketHeadline[] = data.news.slice(0, limit).map((n) => ({
      title: n.title || "",
      url: n.link || "",
      published: n.providerPublishTime
        ? new Date(n.providerPublishTime * 1000).toISOString()
        : "",
      source: n.publisher || "Yahoo Finance",
    }));
    return headlines.length ? headlines : null;
  } catch {
    return null;
  }
}

export async function clientFetchMarketIndices(): Promise<{
  indices: MarketIndex[];
  updated_at: string;
}> {
  const snapshot = await loadSnapshot();
  const live = await fetchLiveIndices();

  const indices = live?.length ? live : snapshot?.indices || [];
  const updated_at =
    (live?.length ? new Date().toISOString() : null) ||
    snapshot?.updated_at ||
    new Date().toISOString();

  return { indices, updated_at };
}

export async function clientFetchMarketHeadlines(limit = 25): Promise<{
  headlines: MarketHeadline[];
  updated_at: string;
}> {
  const snapshot = await loadSnapshot();
  const live = await fetchLiveHeadlines(limit);

  const headlines = live?.length
    ? live
    : (snapshot?.headlines || []).slice(0, limit);
  const updated_at =
    (live?.length ? new Date().toISOString() : null) ||
    snapshot?.updated_at ||
    new Date().toISOString();

  if (!headlines.length) throw new Error("No headlines available");
  return { headlines, updated_at };
}

function formatQuoteMarkdown(sym: string, price: number, changePct: number | null, source: string): string {
  const chg = changePct != null ? changePct.toFixed(2) : "—";
  const sign = changePct != null && changePct >= 0 ? "+" : "";
  return `## ${sym}\n\n| Metric | Value |\n| --- | --- |\n| Price | $${price.toFixed(2)} |\n| Change (1d) | ${sign}${chg}% |\n\n*${source}*`;
}

export async function clientFetchQuote(ticker: string): Promise<string> {
  const sym = ticker.toUpperCase().replace(/^\$/, "");

  const { price, prev } = await fetchYahooChart(sym);
  if (price != null) {
    const changePct =
      prev != null && prev !== 0 ? ((price - prev) / prev) * 100 : null;
    return formatQuoteMarkdown(sym, price, changePct, "Yahoo Finance · live");
  }

  const snapshot = await loadSnapshot();
  const cached = snapshot?.quotes?.[sym];
  if (cached?.price != null) {
    let changePct = cached.change_pct ?? null;
    if (changePct == null && cached.prev_close) {
      changePct = ((cached.price - cached.prev_close) / cached.prev_close) * 100;
    }
    const age = snapshot?.updated_at
      ? ` · snapshot ${new Date(snapshot.updated_at).toLocaleString()}`
      : "";
    return formatQuoteMarkdown(sym, cached.price, changePct, `Yahoo Finance · cached${age}`);
  }

  return `Could not fetch quote for **${sym}**. Yahoo Finance blocks direct browser access on GitHub Pages — try again after the market snapshot refreshes (~10 min), or run the local backend for live quotes on any ticker.`;
}
