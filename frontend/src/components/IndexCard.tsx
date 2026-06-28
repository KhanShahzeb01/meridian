"use client";

import { MiniSparkline } from "./MiniSparkline";
import type { MarketIndex } from "@/lib/api";

function fmtPrice(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return v >= 1000 ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) : v.toFixed(2);
}

function fmtPct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "—";
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

interface IndexCardProps {
  index: MarketIndex;
  delayMs?: number;
  compact?: boolean;
}

export function IndexCard({ index, delayMs = 0, compact = false }: IndexCardProps) {
  const positive = (index.change_pct ?? 0) >= 0;
  const changeColor = positive ? "text-[var(--color-success)]" : "text-[var(--color-danger)]";

  return (
    <article
      className={`index-card group relative overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] transition-[transform,border-color,box-shadow] duration-300 hover:border-[var(--color-success)]/35 hover:-translate-y-0.5 hover:shadow-lg hover:shadow-black/20 ${
        compact ? "p-3 sm:p-4" : "p-4"
      }`}
      style={{ animationDelay: `${delayMs}ms` }}
    >
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-[var(--color-success)]/5 via-transparent to-transparent opacity-0 transition-opacity duration-300 group-hover:opacity-100" />
      <div className="relative flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <p className="font-mono text-[10px] uppercase tracking-widest text-[var(--color-muted)] truncate">
            {index.symbol}
          </p>
          <h3 className={`font-display leading-tight ${compact ? "text-base sm:text-lg" : "text-lg"}`}>
            {index.name}
          </h3>
          <p className={`mt-1 font-mono tabular-nums text-[var(--color-foreground)] ${compact ? "text-lg sm:text-xl" : "text-xl"}`}>
            {fmtPrice(index.price)}
          </p>
          <p className={`mt-0.5 font-mono text-xs tabular-nums ${changeColor}`}>
            {fmtPct(index.change_pct)}
          </p>
        </div>
        <MiniSparkline
          series={index.series}
          positive={positive}
          className={compact ? "hidden sm:block h-9 w-[88px] shrink-0" : "shrink-0"}
        />
      </div>
      <div
        className={`mt-3 h-0.5 w-full rounded-full ${positive ? "index-bar-up" : "index-bar-down"}`}
      />
    </article>
  );
}
