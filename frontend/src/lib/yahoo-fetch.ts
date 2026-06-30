/** Fetch Yahoo Finance JSON in the browser (CORS-safe on GitHub Pages). */

const HEADERS = { "User-Agent": "MozillaFinance/1.0" };

function onStaticHosting(): boolean {
  if (typeof window === "undefined") return false;
  const h = window.location.hostname;
  return h.endsWith("github.io") || h.endsWith("githubpreview.dev");
}

type ProxyFn = (url: string) => string;

const CORS_PROXIES: ProxyFn[] = [
  (url) => `https://proxy.cors.sh/${url}`,
  (url) => `https://api.allorigins.win/raw?url=${encodeURIComponent(url)}`,
  (url) => `https://corsproxy.io/?${encodeURIComponent(url)}`,
];

async function fetchViaProxy(url: string): Promise<unknown | null> {
  for (const wrap of CORS_PROXIES) {
    try {
      const res = await fetch(wrap(url), { cache: "no-store" });
      if (!res.ok) continue;
      const text = await res.text();
      if (!text.trim()) continue;
      return JSON.parse(text);
    } catch {
      continue;
    }
  }
  return null;
}

export async function fetchYahooJson(url: string): Promise<unknown | null> {
  if (!onStaticHosting()) {
    try {
      const res = await fetch(url, { headers: HEADERS, cache: "no-store" });
      if (res.ok) return res.json();
    } catch {
      /* fall through to proxies */
    }
  }
  return fetchViaProxy(url);
}

export interface ChartQuote {
  series: number[];
  price: number | null;
  prev: number | null;
}

export async function fetchYahooChart(symbol: string): Promise<ChartQuote> {
  const empty: ChartQuote = { series: [], price: null, prev: null };
  const hosts = ["query1.finance.yahoo.com", "query2.finance.yahoo.com"];
  for (const host of hosts) {
    const url = `https://${host}/v8/finance/chart/${encodeURIComponent(symbol)}?range=5d&interval=30m`;
    const data = (await fetchYahooJson(url)) as {
      chart?: {
        result?: {
          meta?: Record<string, number>;
          indicators?: { quote?: { close?: (number | null)[] }[] };
        }[];
      };
    } | null;
    if (!data?.chart?.result?.[0]) continue;
    const block = data.chart.result[0];
    const meta = block.meta || {};
    const closes = (block.indicators?.quote?.[0]?.close || []).filter(
      (c): c is number => c != null
    );
    const series = closes.slice(-32);
    const price = meta.regularMarketPrice ?? series.at(-1) ?? null;
    const prev = meta.previousClose ?? meta.chartPreviousClose ?? null;
    if (price != null) return { series, price, prev };
  }
  return empty;
}
