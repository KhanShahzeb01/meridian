import type { MarketHeadline, MarketIndex } from "./api";

const HEADERS = { "User-Agent": "MeridianFinance/1.0" };

const INDICES = [
  { id: "sp500", name: "S&P 500", symbol: "^GSPC", fallback: "SPY" },
  { id: "nasdaq", name: "NASDAQ", symbol: "^IXIC", fallback: "QQQ" },
  { id: "dow", name: "Dow Jones", symbol: "^DJI", fallback: "DIA" },
  { id: "gold", name: "Gold", symbol: "GC=F", fallback: "GLD" },
  { id: "crude", name: "Crude Oil", symbol: "CL=F", fallback: "USO" },
  { id: "vix", name: "VIX", symbol: "^VIX", fallback: "VIXY" },
] as const;

interface MarketSnapshot {
  indices: MarketIndex[];
  headlines: MarketHeadline[];
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

function snapshotUrl(): string {
  const bp = basePath();
  return `${bp}/data/market-snapshot.json`;
}

async function loadSnapshot(): Promise<MarketSnapshot | null> {
  try {
    const res = await fetch(snapshotUrl(), { cache: "no-store" });
    if (!res.ok) return null;
    return (await res.json()) as MarketSnapshot;
  } catch {
    return null;
  }
}

async function fetchChart(symbol: string): Promise<{
  series: number[];
  price: number | null;
  prev: number | null;
}> {
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(symbol)}?range=5d&interval=30m`;
  const res = await fetch(url, { headers: HEADERS });
  if (!res.ok) return { series: [], price: null, prev: null };
  const data = await res.json();
  const block = data?.chart?.result?.[0];
  if (!block) return { series: [], price: null, prev: null };
  const meta = block.meta || {};
  const closes = (block.indicators?.quote?.[0]?.close || []).filter(
    (c: number | null) => c != null
  ) as number[];
  const series = closes.slice(-32);
  const price = meta.regularMarketPrice ?? (series.at(-1) ?? null);
  const prev = meta.previousClose ?? meta.chartPreviousClose ?? null;
  return { series, price, prev };
}

async function fetchIndex(meta: (typeof INDICES)[number]): Promise<MarketIndex> {
  let { series, price, prev } = await fetchChart(meta.symbol);
  if (!series.length) {
    const fb = await fetchChart(meta.fallback);
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
    const res = await fetch(url, { headers: HEADERS });
    if (!res.ok) return null;
    const data = await res.json();
    const headlines: MarketHeadline[] = (data.news || []).slice(0, limit).map(
      (n: {
        title?: string;
        link?: string;
        providerPublishTime?: number;
        publisher?: string;
      }) => ({
        title: n.title || "",
        url: n.link || "",
        published: n.providerPublishTime
          ? new Date(n.providerPublishTime * 1000).toISOString()
          : "",
        source: n.publisher || "Yahoo Finance",
      })
    );
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

export async function clientFetchQuote(ticker: string): Promise<string> {
  const sym = ticker.toUpperCase().replace(/^\$/, "");
  const { price, prev, series } = await fetchChart(sym);
  if (price == null) {
    return `Could not fetch quote for **${sym}**. Check the ticker symbol.`;
  }
  const chg =
    prev != null && prev !== 0 ? (((price - prev) / prev) * 100).toFixed(2) : "—";
  const sign = Number(chg) >= 0 ? "+" : "";
  return `## ${sym}\n\n| Metric | Value |\n| --- | --- |\n| Price | $${price.toFixed(2)} |\n| Change (1d) | ${sign}${chg}% |\n\n*Yahoo Finance · browser*`;
}
