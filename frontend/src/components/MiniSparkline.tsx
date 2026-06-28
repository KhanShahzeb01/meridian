"use client";

import { useEffect, useId, useMemo, useState } from "react";

interface MiniSparklineProps {
  series: number[];
  positive: boolean;
  className?: string;
}

export function MiniSparkline({ series, positive, className = "" }: MiniSparklineProps) {
  const gradId = useId().replace(/:/g, "");
  const [ready, setReady] = useState(false);

  const { path, areaPath, width, height } = useMemo(() => {
    const w = 120;
    const h = 40;
    const pad = 2;
    if (!series.length) {
      return { path: "", areaPath: "", width: w, height: h };
    }
    const min = Math.min(...series);
    const max = Math.max(...series);
    const range = max - min || 1;
    const pts = series.map((v, i) => {
      const x = pad + (i / Math.max(series.length - 1, 1)) * (w - pad * 2);
      const y = pad + (1 - (v - min) / range) * (h - pad * 2);
      return [x, y] as const;
    });
    const line = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
    const area = `${line} L${pts[pts.length - 1][0].toFixed(1)},${h} L${pts[0][0].toFixed(1)},${h} Z`;
    return { path: line, areaPath: area, width: w, height: h };
  }, [series]);

  useEffect(() => {
    const t = requestAnimationFrame(() => setReady(true));
    return () => cancelAnimationFrame(t);
  }, [path]);

  const stroke = positive ? "var(--color-success)" : "var(--color-danger)";
  const fillTop = positive ? "rgba(61, 214, 140, 0.22)" : "rgba(239, 68, 68, 0.18)";

  if (!path) {
    return (
      <div
        className={`h-10 w-[120px] rounded bg-[var(--color-surface-elevated)] animate-pulse ${className}`}
      />
    );
  }

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      className={`sparkline-draw h-10 w-[120px] ${ready ? "sparkline-ready" : ""} ${className}`}
      aria-hidden
    >
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={fillTop} />
          <stop offset="100%" stopColor="transparent" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill={`url(#${gradId})`} className="sparkline-area" />
      <path
        d={path}
        fill="none"
        stroke={stroke}
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="sparkline-line"
      />
    </svg>
  );
}
