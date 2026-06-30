"use client";

import { useCallback, useEffect, useState } from "react";
import { Activity } from "lucide-react";
import {
  fetchMarketHeadlines,
  fetchMarketIndices,
  type MarketHeadline,
  type MarketIndex,
} from "@/lib/api";
import { HeadlinesPager } from "./HeadlinesPager";
import { IndexCard } from "./IndexCard";

const REFRESH_MS = 120_000;

export function MarketPulse() {
  const [indices, setIndices] = useState<MarketIndex[]>([]);
  const [headlines, setHeadlines] = useState<MarketHeadline[]>([]);
  const [indicesLoading, setIndicesLoading] = useState(true);
  const [headlinesLoading, setHeadlinesLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const loadIndices = useCallback(async () => {
    try {
      const res = await fetchMarketIndices();
      setIndices(res.indices);
      setLastUpdated((prev) => res.updated_at || prev);
    } catch {
      // keep prior indices on refresh failure
    } finally {
      setIndicesLoading(false);
    }
  }, []);

  const loadHeadlines = useCallback(async () => {
    try {
      const res = await fetchMarketHeadlines(25);
      setHeadlines(res.headlines);
      setLastUpdated((prev) => res.updated_at || prev);
    } catch {
      setHeadlines([]);
    } finally {
      setHeadlinesLoading(false);
    }
  }, []);

  const loadAll = useCallback(() => {
    void loadIndices();
    void loadHeadlines();
  }, [loadIndices, loadHeadlines]);

  useEffect(() => {
    loadAll();
    const interval = setInterval(loadAll, REFRESH_MS);
    return () => clearInterval(interval);
  }, [loadAll]);

  const loading = indicesLoading && headlinesLoading;
  const showApiError =
    !indicesLoading && !headlinesLoading && indices.length === 0 && headlines.length === 0;

  return (
    <section
      aria-labelledby="market-pulse-heading"
      className="market-pulse relative px-6 pb-8 pt-4"
      data-testid="market-pulse"
    >
      <div className="pointer-events-none absolute inset-0 overflow-hidden">
        <div className="market-orb market-orb-a" />
        <div className="market-orb market-orb-b" />
      </div>

      <div className="relative mx-auto max-w-[1240px]">
        <div className="mb-6 flex flex-wrap items-end justify-between gap-4 fade-in-up">
          <div>
            <div className="mb-2 inline-flex items-center gap-2 font-mono text-xs uppercase tracking-widest text-[var(--color-success)]">
              <Activity className="h-3.5 w-3.5" aria-hidden="true" />
              Market pulse
            </div>
            <h2 id="market-pulse-heading" className="font-display text-2xl sm:text-3xl">
              Live markets & headlines
            </h2>
          </div>
          <p className="text-xs text-[var(--color-muted)] font-mono">
            {loading ? "Updating…" : "Refreshes every 2 min · Yahoo Finance"}
            {lastUpdated && !loading ? (
              <span className="hidden sm:inline" suppressHydrationWarning>
                {" · Updated "}
                {new Date(lastUpdated).toLocaleTimeString()}
              </span>
            ) : null}
          </p>
        </div>

        {showApiError ? (
          <p
            className="mb-5 rounded-lg border border-[var(--color-danger)]/30 bg-[var(--color-danger)]/5 px-4 py-3 text-sm text-[var(--color-muted)]"
            role="status"
          >
            Market data temporarily unavailable — check your connection and refresh. Yahoo Finance
            is fetched directly in your browser (no server required).
          </p>
        ) : null}

        <div
          className="market-indices-grid fade-in-up fade-in-up-delay-1"
          aria-live="polite"
          aria-busy={indicesLoading}
          data-testid="market-indices"
        >
          {indicesLoading && !indices.length
            ? Array.from({ length: 6 }, (_, i) => (
                <div
                  key={i}
                  className="h-[132px] animate-pulse rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]"
                />
              ))
            : indices.map((idx, i) => (
                <IndexCard key={idx.id} index={idx} delayMs={i * 60} compact />
              ))}
        </div>

        <div className="mt-5 fade-in-up fade-in-up-delay-2">
          <HeadlinesPager headlines={headlines} loading={headlinesLoading} />
        </div>
      </div>
    </section>
  );
}
