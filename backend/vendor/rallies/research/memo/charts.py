"""Chart.js charts for investment memo HTML (data-driven, explanatory)."""

from __future__ import annotations

import json
from html import escape
from typing import Any


def _iso_labels(index) -> list[str]:
    return [str(ts.date()) for ts in index]


def _safe_series(values) -> list[float | None]:
    out: list[float | None] = []
    for v in values:
        try:
            if v is None or (isinstance(v, float) and v != v):
                out.append(None)
            else:
                out.append(round(float(v), 4))
        except (TypeError, ValueError):
            out.append(None)
    return out


def _chart_payload(ticker: str, series, facts: dict[str, Any]) -> dict[str, Any]:
    df = series.frame.copy()
    labels = _iso_labels(df.index)
    snap = facts.get("snapshot") or {}
    pe_hist = facts.get("pe_history_in_window") or {}
    fair = facts.get("fair_value_bands_panel_a") or {}

    return {
        "ticker": ticker.upper(),
        "company": series.company_name,
        "labels": labels,
        "price": _safe_series(df.get("price", [])),
        "pe": _safe_series(df.get("pe", [])),
        "eps": _safe_series(df.get("eps_ttm", [])),
        "fair_low": _safe_series(df.get("price_fair_low", [])),
        "fair_median": _safe_series(df.get("price_fair_median", [])),
        "fair_high": _safe_series(df.get("price_fair_high", [])),
        "snapshot": {
            "price": snap.get("price_usd"),
            "pe": snap.get("pe_trailing"),
            "peg": snap.get("peg_5yr_expected"),
            "eps": snap.get("eps_ttm_usd"),
        },
        "pe_median": pe_hist.get("median"),
        "pe_percentile": pe_hist.get("current_percentile_vs_window"),
        "fair_median_usd": fair.get("price_fair_median_usd"),
        "horizon": facts.get("horizon") or series.horizon.label,
    }


def _chart_script(payload: dict[str, Any]) -> str:
    data_json = json.dumps(payload, ensure_ascii=True)
    return f"""
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script>
document.addEventListener('DOMContentLoaded', function() {{
  const D = {data_json};
  const gridColor = 'rgba(0,0,0,0.06)';
  const font = {{ family: 'Inter, system-ui, sans-serif', size: 10 }};

  function lineChart(id, cfg) {{
    const el = document.getElementById(id);
    if (!el) return;
    new Chart(el.getContext('2d'), {{
      type: 'line',
      data: cfg.data,
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        interaction: {{ mode: 'index', intersect: false }},
        plugins: {{
          legend: {{ labels: {{ font, boxWidth: 10, padding: 8 }} }},
          tooltip: {{ titleFont: font, bodyFont: font }}
        }},
        scales: {{
          x: {{
            ticks: {{ maxTicksLimit: 6, font }},
            grid: {{ color: gridColor }}
          }},
          y: {{
            ticks: {{ font }},
            grid: {{ color: gridColor }},
            title: cfg.yTitle ? {{ display: true, text: cfg.yTitle, font }} : undefined
          }}
        }}
      }}
    }});
  }}

  lineChart('memoPriceChart', {{
    yTitle: 'USD',
    data: {{
      labels: D.labels,
      datasets: [{{
        label: D.ticker + ' price',
        data: D.price,
        borderColor: '#2E86AB',
        backgroundColor: 'rgba(46,134,171,0.12)',
        fill: true,
        tension: 0.15,
        pointRadius: 0,
        borderWidth: 2
      }}]
    }}
  }});

  lineChart('memoPeChart', {{
    yTitle: 'P/E (trailing)',
    data: {{
      labels: D.labels,
      datasets: [
        {{
          label: 'Trailing P/E',
          data: D.pe,
          borderColor: '#1a1a1a',
          tension: 0.15,
          pointRadius: 0,
          borderWidth: 2
        }},
        ...(D.pe_median ? [{{
          label: 'Median ' + D.pe_median,
          data: D.labels.map(() => D.pe_median),
          borderColor: '#E94F37',
          borderDash: [6, 4],
          pointRadius: 0,
          borderWidth: 1.5
        }}] : [])
      ]
    }}
  }});

  const epsEl = document.getElementById('memoEpsChart');
  if (epsEl) {{
    new Chart(epsEl.getContext('2d'), {{
      type: 'line',
      data: {{
        labels: D.labels,
        datasets: [
          {{
            label: 'Share price',
            data: D.price,
            borderColor: '#2E86AB',
            tension: 0.15,
            pointRadius: 0,
            borderWidth: 2,
            yAxisID: 'y'
          }},
          {{
            label: 'EPS (TTM)',
            data: D.eps,
            borderColor: '#0a4d2e',
            tension: 0.15,
            pointRadius: 0,
            borderWidth: 2,
            yAxisID: 'y1'
          }}
        ]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{ legend: {{ labels: {{ font, boxWidth: 10 }} }} }},
        scales: {{
          x: {{ ticks: {{ maxTicksLimit: 6, font }}, grid: {{ color: gridColor }} }},
          y: {{
            type: 'linear',
            position: 'left',
            ticks: {{ font }},
            grid: {{ color: gridColor }},
            title: {{ display: true, text: 'Price (USD)', font }}
          }},
          y1: {{
            type: 'linear',
            position: 'right',
            ticks: {{ font }},
            grid: {{ drawOnChartArea: false }},
            title: {{ display: true, text: 'EPS (USD)', font }}
          }}
        }}
      }}
    }});
  }}

  const fairEl = document.getElementById('memoFairChart');
  if (fairEl) {{
    new Chart(fairEl.getContext('2d'), {{
      type: 'line',
      data: {{
        labels: D.labels,
        datasets: [
          {{
            label: 'Price',
            data: D.price,
            borderColor: '#2E86AB',
            tension: 0.15,
            pointRadius: 0,
            borderWidth: 2.5,
            order: 1
          }},
          {{
            label: 'Fair (P/E median band)',
            data: D.fair_median,
            borderColor: '#E94F37',
            borderDash: [5, 4],
            pointRadius: 0,
            borderWidth: 1.5,
            order: 2
          }},
          {{
            label: 'Fair low (P/E 25th)',
            data: D.fair_low,
            borderColor: 'rgba(122,31,31,0.55)',
            borderDash: [2, 3],
            pointRadius: 0,
            borderWidth: 1,
            order: 3
          }},
          {{
            label: 'Fair high (P/E 75th)',
            data: D.fair_high,
            borderColor: 'rgba(10,77,46,0.55)',
            borderDash: [2, 3],
            pointRadius: 0,
            borderWidth: 1,
            order: 3
          }}
        ]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{ legend: {{ labels: {{ font, boxWidth: 10 }} }} }},
        scales: {{
          x: {{ ticks: {{ maxTicksLimit: 6, font }}, grid: {{ color: gridColor }} }},
          y: {{ ticks: {{ font }}, grid: {{ color: gridColor }}, title: {{ display: true, text: 'USD', font }} }}
        }}
      }}
    }});
  }}
}});
</script>
"""


def build_charts_section(ticker: str) -> str:
    """Return Chart.js canvas grid + init script, or fallback message."""
    try:
        from rallies.charts.data import build_pe_frame
        from rallies.charts.facts import build_valuation_facts
        from rallies.charts.horizons import horizon_for_key
    except ImportError:
        return "<p><em>Charts unavailable (install rallies[viz]).</em></p>"

    sym = ticker.upper().strip()
    try:
        series = build_pe_frame(sym, horizon_for_key("5y"))
        facts = build_valuation_facts(series)
        if facts.get("error"):
            return f"<p><em>Charts unavailable: {escape(str(facts['error']))}</em></p>"
        payload = _chart_payload(sym, series, facts)
    except Exception as exc:
        return f"<p><em>Charts unavailable: {escape(str(exc))}</em></p>"

    snap = payload.get("snapshot") or {}
    pe_pct = payload.get("pe_percentile")
    price = snap.get("price")
    pe = snap.get("pe")
    peg = snap.get("peg")
    fair_med = payload.get("fair_median_usd")
    horizon = payload.get("horizon", "5 years")

    note_price = f"Current ${price} · {horizon} window" if price else horizon
    note_pe = (
        f"Trailing P/E {pe} · {pe_pct}th percentile vs {horizon}"
        if pe and pe_pct is not None
        else f"Median dashed · {horizon}"
    )
    note_eps = "Price vs trailing EPS (TTM from filings)"
    note_fair = (
        f"Fair median ≈ ${fair_med} (EPS × historical P/E median)"
        if fair_med
        else "Fair bands = EPS × P/E 25th–75th percentile"
    )

    html = f"""
<div class="chart-grid">
  <div class="chart-box">
    <h3>Share price ({escape(horizon)})</h3>
    <div class="chart-canvas-wrap"><canvas id="memoPriceChart"></canvas></div>
    <div class="chart-note">{escape(note_price)}</div>
  </div>
  <div class="chart-box">
    <h3>Trailing P/E ({escape(horizon)})</h3>
    <div class="chart-canvas-wrap"><canvas id="memoPeChart"></canvas></div>
    <div class="chart-note">{escape(note_pe)}</div>
  </div>
  <div class="chart-box">
    <h3>Price vs EPS (TTM)</h3>
    <div class="chart-canvas-wrap"><canvas id="memoEpsChart"></canvas></div>
    <div class="chart-note">{escape(note_eps)}</div>
  </div>
  <div class="chart-box">
    <h3>Price vs fair-value bands</h3>
    <div class="chart-canvas-wrap"><canvas id="memoFairChart"></canvas></div>
    <div class="chart-note">{escape(note_fair)}</div>
  </div>
</div>
{_chart_script(payload)}
"""
    return html.strip()
