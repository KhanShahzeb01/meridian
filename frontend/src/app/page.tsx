"use client";

import Link from "next/link";
import {
  Terminal,
  TrendingUp,
  Users,
  BarChart3,
  Shield,
  Zap,
  ArrowRight,
  Command,
} from "lucide-react";
import { MarketPulse } from "@/components/MarketPulse";
import { TerminalScene3D } from "@/components/TerminalScene3D";

const features = [
  {
    icon: Terminal,
    title: "CLI Terminal",
    description:
      "Analyze stocks through a powerful command-line interface. Type /quote AAPL or /dcf MSFT for instant insights.",
  },
  {
    icon: Users,
    title: "36 Investment Personas",
    description:
      "Ask Warren Buffett, Charlie Munger, Cathie Wood, Jim Simons, Ray Dalio, and 31 more across 7 investing categories.",
  },
  {
    icon: BarChart3,
    title: "Consensus Engine",
    description:
      "Run /consensus to have a randomized 7-expert panel analyze stocks, vote BUY/HOLD/SELL, and synthesize a majority opinion.",
  },
  {
    icon: TrendingUp,
    title: "Live Market Data",
    description:
      "Real-time quotes, financials, news, and SEC filings powered by Yahoo Finance and EDGAR.",
  },
  {
    icon: Shield,
    title: "Portfolio Tools",
    description:
      "Track watchlists and portfolios with live price updates, P/E ratios, and 52-week ranges.",
  },
  {
    icon: Zap,
    title: "AI-Powered Analysis",
    description:
      "DeepSeek LLM via OpenRouter delivers in-depth DCF valuations and personalized stock analysis.",
  },
];

const stats = [
  { label: "Personas", value: "36 investors" },
  { label: "Commands", value: "14+ slash cmds" },
  { label: "Data", value: "Yahoo · EDGAR" },
  { label: "Quotes", value: "Sub-second" },
  { label: "Analysis", value: "DeepSeek LLM" },
  { label: "Engine", value: "Rallies-powered" },
];

export default function LandingPage() {
  return (
    <div className="min-h-dvh bg-[var(--color-background)]">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-[100] focus:rounded-md focus:bg-[var(--color-surface-elevated)] focus:px-4 focus:py-2 focus:text-sm focus:text-[var(--color-foreground)]"
      >
        Skip to main content
      </a>

      <nav
        aria-label="Primary"
        className="fixed top-0 left-0 right-0 z-50 border-b border-[var(--color-border)] bg-[var(--color-background)]/80 backdrop-blur-md"
      >
        <div className="mx-auto flex h-16 max-w-[1240px] items-center justify-between px-6">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-md bg-[var(--color-primary)] text-[var(--color-on-primary)] font-mono text-sm font-bold">
              M
            </div>
            <span className="font-display text-lg tracking-tight">
              Meridian<span className="text-[var(--color-success)]">.</span>
            </span>
          </div>
          <Link
            href="/terminal"
            className="btn-browseros inline-flex items-center gap-2 rounded-full bg-[var(--color-foreground)] px-5 py-2.5 text-sm text-[var(--color-background)] transition-[filter] duration-200 hover:brightness-110 cursor-pointer"
          >
            Launch Terminal
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        </div>
      </nav>

      <main id="main-content">
        {/* Hero — Plexus-style split: copy left, 3D terminal right */}
        <section
          aria-labelledby="hero-heading"
          className="hero-section relative grid-bg px-6 pb-16 pt-28 lg:pt-32"
        >
          <div className="absolute inset-0 bg-gradient-to-b from-transparent via-transparent to-[var(--color-background)]" />
          <div className="hero-grid relative mx-auto max-w-[1240px]">
            <div className="hero-copy">
              <p className="hero-eyebrow fade-in-up">
                Yahoo Finance · OpenRouter · Rallies engine
              </p>
              <div className="fade-in-up mb-6 inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-1.5 text-sm text-[var(--color-muted)]">
                <Command className="h-3.5 w-3.5 text-[var(--color-primary)]" aria-hidden="true" />
                AI financial analysis terminal
              </div>
              <h1 id="hero-heading" className="text-glow font-display mb-6 fade-in-up fade-in-up-delay-1">
                Analyze stocks like the{" "}
                <em className="italic text-[var(--color-success)]">greatest investors</em>
              </h1>
              <p className="hero-lead fade-in-up fade-in-up-delay-2">
                A professional terminal with AI personas, live market data, DCF valuations,
                and consensus analysis — all from a single command line.
              </p>
              <div className="hero-actions fade-in-up fade-in-up-delay-2">
                <Link
                  href="/terminal"
                  className="btn-browseros inline-flex items-center gap-2 rounded-full bg-[var(--color-foreground)] px-8 py-3.5 text-base text-[var(--color-background)] transition-[filter] duration-200 hover:brightness-110 pulse-gold cursor-pointer"
                >
                  Open Terminal
                  <ArrowRight className="h-5 w-5" aria-hidden="true" />
                </Link>
                <a
                  href="#features"
                  className="btn-browseros inline-flex items-center gap-2 rounded-full border border-[var(--color-border)] bg-[var(--color-surface)] px-8 py-3.5 text-base text-[var(--color-foreground)] transition-[border-color] duration-200 hover:border-[var(--color-success)]/40 cursor-pointer"
                >
                  See Features
                </a>
              </div>
              <div className="trust-row fade-in-up fade-in-up-delay-2">
                <span className="trust-pill">36 investor personas</span>
                <span className="trust-pill">Live market data</span>
                <span className="trust-pill">Consensus engine</span>
              </div>
              <dl className="stats-grid fade-in-up fade-in-up-delay-3">
                {stats.map((s) => (
                  <div key={s.label}>
                    <dt>{s.label}</dt>
                    <dd>{s.value}</dd>
                  </div>
                ))}
              </dl>
            </div>

            <TerminalScene3D />
          </div>
        </section>

        <MarketPulse />

        <section id="features" aria-labelledby="features-heading" className="py-20 px-6">
          <div className="mx-auto max-w-[1240px]">
            <p className="section-tag text-center">[ 01 ] — FEATURES</p>
            <h2 id="features-heading" className="font-display mb-4 text-center">
              Everything you need for deep analysis
            </h2>
            <p className="mb-12 text-center text-[var(--color-muted)] max-w-xl mx-auto leading-[1.55]">
              Professional-grade tools combined with legendary investor perspectives,
              all in one minimal terminal interface.
            </p>
            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              {features.map((f, i) => (
                <div
                  key={f.title}
                  className="feature-card group rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] p-6 transition-[transform,border-color,background-color] duration-300 hover:border-[var(--color-primary)]/30 hover:bg-[var(--color-surface-elevated)] hover:-translate-y-1"
                  style={{ animationDelay: `${120 + i * 60}ms` }}
                >
                  <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--color-primary)]/10 text-[var(--color-primary)] transition-[transform,background-color] duration-300 group-hover:bg-[var(--color-primary)]/20 group-hover:scale-110">
                    <f.icon className="h-5 w-5" aria-hidden="true" />
                  </div>
                  <h3 className="font-display mb-2">{f.title}</h3>
                  <p className="text-sm text-[var(--color-muted)] leading-[1.55]">
                    {f.description}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="py-20 px-6 border-t border-[var(--color-border)]">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="font-display mb-4">Ready to analyze?</h2>
            <p className="mb-8 text-[var(--color-muted)] leading-[1.55]">
              Launch the terminal and start with /help or jump straight into /quote AAPL
            </p>
            <Link
              href="/terminal"
              className="btn-browseros inline-flex items-center gap-2 rounded-full bg-[var(--color-foreground)] px-8 py-3.5 text-base text-[var(--color-background)] transition-[filter] duration-200 hover:brightness-110 cursor-pointer"
            >
              Launch Terminal
              <ArrowRight className="h-5 w-5" aria-hidden="true" />
            </Link>
          </div>
        </section>
      </main>

      <footer className="border-t border-[var(--color-border)] py-8 px-6">
        <div className="mx-auto max-w-[1240px] flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-[var(--color-muted)]">
          <span>Meridian Finance — AI Stock Analysis Terminal</span>
          <span>Data: Yahoo Finance · AI: DeepSeek via OpenRouter</span>
        </div>
      </footer>
    </div>
  );
}
