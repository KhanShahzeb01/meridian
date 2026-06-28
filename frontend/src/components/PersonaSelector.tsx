"use client";

import { useState } from "react";
import { PersonaGroup } from "@/lib/api";
import { ChevronDown, ChevronRight, MessageCircle } from "lucide-react";

interface PersonaSelectorProps {
  grouped: PersonaGroup;
  selected: string | null;
  onSelect: (id: string | null) => void;
  onAsk?: (id: string) => void;
}

export default function PersonaSelector({
  grouped,
  selected,
  onSelect,
  onAsk,
}: PersonaSelectorProps) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>(() => {
    const init: Record<string, boolean> = {};
    Object.keys(grouped).forEach((cat, i) => {
      init[cat] = i < 2;
    });
    return init;
  });

  return (
    <div className="space-y-3">
      <div>
        <h3 className="text-xs font-medium uppercase tracking-wider text-[var(--color-muted)] px-1">
          Persona
        </h3>
        <p className="text-xs text-[var(--color-muted)]/70 px-1 mt-1 leading-[1.55]">
          Default is open conversation. Select a persona to route messages as /ask.
        </p>
      </div>

      <button
        onClick={() => onSelect(null)}
        className={`w-full flex items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-all duration-200 cursor-pointer ${
          selected === null
            ? "bg-[var(--color-surface-elevated)] border border-[var(--color-success)]/40"
            : "hover:bg-[var(--color-surface-elevated)]/50 border border-transparent"
        }`}
      >
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--color-surface-elevated)] text-[var(--color-muted)] border border-[var(--color-border)]">
          <MessageCircle className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <div className="text-sm font-medium">General</div>
          <div className="text-xs text-[var(--color-muted)]">Open conversation</div>
        </div>
        {selected === null && (
          <div className="ml-auto h-2 w-2 rounded-full shrink-0 bg-[var(--color-success)]" />
        )}
      </button>

      {Object.entries(grouped).map(([category, personas]) => (
        <div key={category}>
          <button
            onClick={() =>
              setExpanded((prev) => ({ ...prev, [category]: !prev[category] }))
            }
            className="flex w-full items-center gap-1.5 px-1 py-1 text-xs font-medium text-[var(--color-muted)] hover:text-[var(--color-foreground)] transition-colors cursor-pointer"
          >
            {expanded[category] ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )}
            <span
              className="h-2 w-2 rounded-full shrink-0"
              style={{ backgroundColor: personas[0]?.color || "#94A3B8" }}
            />
            {category}
            <span className="text-[var(--color-muted)]/50 ml-auto">{personas.length}</span>
          </button>

          {expanded[category] && (
            <div className="space-y-0.5 mt-1">
              {personas.map((p) => (
                <button
                  key={p.id}
                  onClick={() => onSelect(p.id)}
                  onDoubleClick={() => onAsk?.(p.id)}
                  title={p.quote}
                  className={`w-full flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition-all duration-200 cursor-pointer ${
                    selected === p.id
                      ? "bg-[var(--color-surface-elevated)] border border-[var(--color-success)]/40"
                      : "hover:bg-[var(--color-surface-elevated)]/50 border border-transparent"
                  }`}
                >
                  <div
                    className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-[10px] font-bold"
                    style={{
                      backgroundColor: `${p.color}20`,
                      color: p.color,
                      border: `1.5px solid ${p.color}40`,
                    }}
                  >
                    {p.avatar}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-xs font-medium truncate">{p.name}</div>
                    <div className="text-[10px] text-[var(--color-muted)] truncate">
                      {p.title}
                    </div>
                  </div>
                  {selected === p.id && (
                    <div
                      className="h-1.5 w-1.5 rounded-full shrink-0"
                      style={{ backgroundColor: p.color }}
                    />
                  )}
                </button>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
