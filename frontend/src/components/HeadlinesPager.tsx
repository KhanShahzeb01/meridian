"use client";

import { useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, ExternalLink, Newspaper } from "lucide-react";
import type { MarketHeadline } from "@/lib/api";

const PAGE_SIZE = 5;

interface HeadlinesPagerProps {
  headlines: MarketHeadline[];
}

function formatPublished(raw: string): string {
  if (!raw) return "";
  const d = new Date(raw);
  if (Number.isNaN(d.getTime())) return raw;
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(d);
}

export function HeadlinesPager({ headlines }: HeadlinesPagerProps) {
  const [page, setPage] = useState(0);

  const totalPages = Math.max(1, Math.ceil(headlines.length / PAGE_SIZE));

  useEffect(() => {
    setPage(0);
  }, [headlines]);

  useEffect(() => {
    if (page > totalPages - 1) {
      setPage(Math.max(0, totalPages - 1));
    }
  }, [page, totalPages]);

  const slice = useMemo(() => {
    const start = page * PAGE_SIZE;
    return headlines.slice(start, start + PAGE_SIZE);
  }, [headlines, page]);

  const canPrev = page > 0;
  const canNext = page < totalPages - 1;

  if (!headlines.length) {
    return (
      <div
        className="headlines-panel rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] px-5 py-8 text-center text-sm text-[var(--color-muted)]"
        role="status"
      >
        Market headlines unavailable — open the terminal and run /news for the latest.
      </div>
    );
  }

  return (
    <div
      className="headlines-panel overflow-hidden rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)]"
      data-testid="market-headlines"
    >
      <div className="flex flex-wrap items-center gap-3 border-b border-[var(--color-border)] px-4 py-3 sm:px-5">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <Newspaper className="h-4 w-4 shrink-0 text-[var(--color-success)]" aria-hidden="true" />
          <span id="headlines-label" className="font-mono text-xs uppercase tracking-wider text-[var(--color-muted)]">
            Yahoo Finance · Headlines
          </span>
          <span className="hidden sm:inline-flex items-center gap-1.5">
            <span className="live-dot h-1.5 w-1.5 rounded-full bg-[var(--color-success)]" aria-hidden="true" />
            <span className="font-mono text-[10px] text-[var(--color-success)]">LIVE</span>
          </span>
        </div>

        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] tabular-nums text-[var(--color-muted)]">
            Page {page + 1} / {totalPages}
          </span>
          <button
            type="button"
            aria-label="Previous headlines"
            disabled={!canPrev}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            className="headlines-nav-btn"
          >
            <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          </button>
          <button
            type="button"
            aria-label="Next headlines"
            disabled={!canNext}
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            className="headlines-nav-btn"
          >
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>
      </div>

      <ul aria-labelledby="headlines-label" className="divide-y divide-[var(--color-border)]/60">
        {slice.map((h, i) => (
          <li key={`${page}-${h.title}-${i}`}>
            <a
              href={h.url || "#"}
              target="_blank"
              rel="noopener noreferrer"
              className="headline-row group flex items-start gap-4 px-4 py-4 transition-colors hover:bg-[var(--color-surface-elevated)] sm:px-5 sm:py-4"
            >
              <span className="headline-index font-mono text-xs tabular-nums text-[var(--color-muted)]">
                {String(page * PAGE_SIZE + i + 1).padStart(2, "0")}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-base leading-snug text-[var(--color-foreground)] transition-colors group-hover:text-[var(--color-success)]">
                  {h.title}
                </span>
                <span className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[10px] uppercase tracking-wide text-[var(--color-muted)]">
                  <span className="text-[var(--color-primary)]">{h.source || "Yahoo"}</span>
                  {h.published ? (
                    <span>{formatPublished(h.published)}</span>
                  ) : null}
                </span>
              </span>
              <ExternalLink
                className="mt-1 h-4 w-4 shrink-0 text-[var(--color-muted)] opacity-40 transition-opacity group-hover:opacity-100"
                aria-hidden="true"
              />
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}
