"use client";

import { useEffect, useState } from "react";
import { Activity } from "lucide-react";
import { fetchMarketHeadlines, fetchMarketIndices, type MarketDashboardData } from "@/lib/api";
import { HeadlinesPager } from "./HeadlinesPager";
import { IndexCard } from "./IndexCard";

const REFRESH_MS = 120_000;

export function MarketPulse() {
  const [data, setData] = useState<MarketDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [indices, headlines] = await Promise.all([
          fetchMarketIndices(),
          fetchMarketHeadlines(25),
        ]);
        if (!cancelled) {
          setData({ indices: indices.indices, headlines: headlines.headlines });
          setLastUpdated(indices.updated_at || headlines.updated_at);
        }
      } catch {
        if (!cancelled) setData(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    const interval = setInterval(load, REFRESH_MS);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

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
              <span className="hidden sm:inline"> · Updated {new Date(lastUpdated).toLocaleTimeString()}</span>
            ) : null}
          </p>
        </div>

        <div
          className="market-indices-grid fade-in-up fade-in-up-delay-1"
          aria-live="polite"
          aria-busy={loading}
          data-testid="market-indices"
        >
          {loading && !data
            ? Array.from({ length: 6 }, (_, i) => (
                <div
                  key={i}
                  className="h-[132px] animate-pulse rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]"
                />
              ))
            : (data?.indices ?? []).map((idx, i) => (
                <IndexCard key={idx.id} index={idx} delayMs={i * 60} compact />
              ))}
        </div>

        <div className="mt-5 fade-in-up fade-in-up-delay-2">
          <HeadlinesPager headlines={data?.headlines ?? []} />
        </div>
      </div>
    </section>
  );
}
