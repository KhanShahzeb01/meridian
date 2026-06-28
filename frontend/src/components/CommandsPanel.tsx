"use client";

import { CommandStructure } from "@/lib/api";
import { useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";

interface CommandsPanelProps {
  commands: CommandStructure;
  onRun: (cmd: string) => void;
}

export default function CommandsPanel({ commands, onRun }: CommandsPanelProps) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>(() => {
    const init: Record<string, boolean> = {};
    Object.keys(commands).forEach((cat, i) => {
      init[cat] = ["Data", "Personas", "Portfolio"].includes(cat) || i < 2;
    });
    return init;
  });

  return (
    <div className="space-y-2">
      <h3 className="text-xs font-medium uppercase tracking-wider text-[var(--color-muted)] px-1">
        Commands
      </h3>
      {Object.entries(commands).map(([category, { commands: cmds }]) => (
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
            {category}
          </button>
          {expanded[category] && (
            <div className="space-y-0.5 mt-0.5">
              {cmds.map((c) => {
                const baseCmd = c.cmd.split(" ")[0];
                return (
                  <button
                    key={c.cmd}
                    onClick={() => onRun(c.cmd.endsWith(" ") ? c.cmd : `${baseCmd} `)}
                    title={c.desc}
                    className="w-full text-left px-2 py-1.5 rounded transition-colors hover:bg-[var(--color-surface-elevated)] cursor-pointer group"
                  >
                    <code className="font-mono text-[10px] text-[var(--color-success)] group-hover:text-[#5eead4]">
                      {c.cmd.split(" ")[0]}
                    </code>
                    <div className="text-[10px] text-[var(--color-muted)] truncate mt-0.5">
                      {c.desc}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
