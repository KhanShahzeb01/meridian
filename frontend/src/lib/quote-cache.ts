const QUOTE_CACHE_KEY = "meridian_quote_cache_v1";
const TTL_MS = 5 * 60 * 1000;

export interface CachedQuote {
  price: number;
  prev_close?: number | null;
  change_pct?: number | null;
  updated_at: string;
}

type QuoteCacheMap = Record<string, CachedQuote>;

function readCache(): QuoteCacheMap {
  if (typeof window === "undefined") return {};
  try {
    const raw = localStorage.getItem(QUOTE_CACHE_KEY);
    return raw ? (JSON.parse(raw) as QuoteCacheMap) : {};
  } catch {
    return {};
  }
}

function writeCache(map: QuoteCacheMap): void {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(QUOTE_CACHE_KEY, JSON.stringify(map));
  } catch {
    /* quota */
  }
}

export function getCachedQuote(symbol: string): CachedQuote | null {
  const hit = readCache()[symbol.toUpperCase()];
  if (!hit) return null;
  if (Date.now() - new Date(hit.updated_at).getTime() > TTL_MS) return null;
  return hit;
}

export function setCachedQuote(
  symbol: string,
  data: { price: number; prev_close?: number | null; change_pct?: number | null }
): void {
  const sym = symbol.toUpperCase();
  const map = readCache();
  map[sym] = {
    price: data.price,
    prev_close: data.prev_close,
    change_pct: data.change_pct,
    updated_at: new Date().toISOString(),
  };
  writeCache(map);
}
