"use client";

import { ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type BoxVariant = "query" | "planning" | "thinking" | "response" | "output" | "system";

const VARIANT_STYLES: Record<
  BoxVariant,
  { border: string; bg: string; label: string; labelColor: string }
> = {
  query: {
    border: "border-[#3b82f6]/45",
    bg: "bg-[#3b82f6]/[0.06]",
    label: "Query",
    labelColor: "text-[#60a5fa]",
  },
  planning: {
    border: "border-[#d946ef]/40",
    bg: "bg-[#d946ef]/[0.06]",
    label: "Planning",
    labelColor: "text-[#e879f9]",
  },
  thinking: {
    border: "border-[#a78bfa]/40",
    bg: "bg-[#a78bfa]/[0.06]",
    label: "Thinking",
    labelColor: "text-[#c4b5fd]",
  },
  response: {
    border: "border-[#22d3ee]/40",
    bg: "bg-[#22d3ee]/[0.05]",
    label: "Response",
    labelColor: "text-[#67e8f9]",
  },
  output: {
    border: "border-[var(--color-border)]",
    bg: "bg-[var(--color-surface)]/40",
    label: "Output",
    labelColor: "text-[var(--color-muted)]",
  },
  system: {
    border: "border-[var(--color-border)]",
    bg: "bg-transparent",
    label: "System",
    labelColor: "text-[var(--color-muted)]",
  },
};

interface ChatBoxProps {
  variant: BoxVariant;
  title?: string;
  children: ReactNode;
  markdown?: boolean;
  mono?: boolean;
}

export default function ChatBox({
  variant,
  title,
  children,
  markdown = false,
  mono = false,
}: ChatBoxProps) {
  const styles = VARIANT_STYLES[variant];
  const label = title || styles.label;

  return (
    <div
      className={`chat-box rounded-lg border ${styles.border} ${styles.bg} overflow-hidden`}
    >
      <div
        className={`chat-box-header flex items-center gap-2 border-b ${styles.border} px-3 py-1.5`}
      >
        <span
          className={`font-mono text-[10px] font-medium uppercase tracking-[0.14em] ${styles.labelColor}`}
        >
          {label}
        </span>
      </div>
      <div
        className={`chat-box-body px-3 py-2.5 ${
          mono ? "font-mono text-xs leading-relaxed text-[#cbd5e1]" : ""
        }`}
      >
        {markdown && typeof children === "string" ? (
          <div className="terminal-markdown text-sm">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{children}</ReactMarkdown>
          </div>
        ) : (
          children
        )}
      </div>
    </div>
  );
}
