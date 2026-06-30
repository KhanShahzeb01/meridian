/** Fetch Yahoo Finance JSON from the browser (direct, then CORS proxy fallbacks). */

const HEADERS = { "User-Agent": "MeridianFinance/1.0" };

const CORS_PROXIES = [
  (url: string) => `https://api.allorigins.win/raw?url=${encodeURIComponent(url)}`,
  (url: string) => `https://corsproxy.io/?${encodeURIComponent(url)}`,
];

export async function fetchYahooJson(url: string): Promise<unknown | null> {
  try {
    const res = await fetch(url, { headers: HEADERS, cache: "no-store" });
    if (res.ok) return res.json();
  } catch {
    /* direct blocked by CORS on github.io */
  }

  for (const wrap of CORS_PROXIES) {
    try {
      const res = await fetch(wrap(url), { cache: "no-store" });
      if (!res.ok) continue;
      const text = await res.text();
      return JSON.parse(text);
    } catch {
      continue;
    }
  }
  return null;
}

export interface ChartQuote {
  series: number[];
  price: number | null;
  prev: number | null;
}

export async function fetchYahooChart(symbol: string): Promise<ChartQuote> {
  const empty: ChartQuote = { series: [], price: null, prev: null };
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?range=5d&interval=30m`;
  const data = (await fetchYahooJson(url)) as {
    chart?: { result?: { meta?: Record<string, number>; indicators?: { quote?: { close?: (number | null)[] }[] } }[] };
  } | null;
  if (!data) return empty;

  const block = data.chart?.result?.[0];
  if (!block) return empty;

  const meta = block.meta || {};
  const closes = (block.indicators?.quote?.[0]?.close || []).filter(
    (c): c is number => c != null
  );
  const series = closes.slice(-32);
  const price = meta.regularMarketPrice ?? series.at(-1) ?? null;
  const prev = meta.previousClose ?? meta.chartPreviousClose ?? null;
  return { series, price, prev };
}
