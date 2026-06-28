"use client";

import { useState, useRef, useEffect, KeyboardEvent } from "react";
import { Send, ChevronUp } from "lucide-react";

interface CommandInputProps {
  onSubmit: (command: string) => void;
  personaId: string | null;
  slashCommands: string[];
  disabled?: boolean;
  prefill?: string;
  onPrefillUsed?: () => void;
}

export default function CommandInput({
  onSubmit,
  personaId,
  slashCommands,
  disabled,
  prefill,
  onPrefillUsed,
}: CommandInputProps) {
  const [input, setInput] = useState("");
  const [history, setHistory] = useState<string[]>([]);
  const [historyIdx, setHistoryIdx] = useState(-1);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    if (prefill) {
      setInput(prefill);
      inputRef.current?.focus();
      onPrefillUsed?.();
    }
  }, [prefill, onPrefillUsed]);

  const filtered = input.startsWith("/") && !input.includes(" ", 1)
    ? slashCommands.filter((s) => s.startsWith(input.toLowerCase()))
    : [];

  const handleSubmit = () => {
    const trimmed = input.trim();
    if (!trimmed || disabled) return;
    onSubmit(trimmed);
    setHistory((prev) => [trimmed, ...prev.filter((h) => h !== trimmed)].slice(0, 100));
    setHistoryIdx(-1);
    setInput("");
    setShowSuggestions(false);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      if (showSuggestions && filtered.length > 0 && input !== filtered[0]) {
        setInput(filtered[0] + " ");
        setShowSuggestions(false);
        return;
      }
      handleSubmit();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (history.length > 0) {
        const newIdx = Math.min(historyIdx + 1, history.length - 1);
        setHistoryIdx(newIdx);
        setInput(history[newIdx]);
      }
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      if (historyIdx > 0) {
        const newIdx = historyIdx - 1;
        setHistoryIdx(newIdx);
        setInput(history[newIdx]);
      } else {
        setHistoryIdx(-1);
        setInput("");
      }
    } else if (e.key === "Tab" && filtered.length > 0) {
      e.preventDefault();
      setInput(filtered[0] + " ");
      setShowSuggestions(false);
    } else if (e.key === "Escape") {
      setShowSuggestions(false);
    }
  };

  return (
    <div className="relative border-t border-[var(--color-border)] bg-[var(--color-terminal-bg)]">
      {showSuggestions && filtered.length > 0 && (
        <div className="absolute bottom-full left-0 right-0 border-t border-[var(--color-border)] bg-[var(--color-surface)] max-h-48 overflow-y-auto terminal-scroll z-10">
          {filtered.slice(0, 12).map((s) => (
            <button
              key={s}
              onClick={() => {
                setInput(s + " ");
                setShowSuggestions(false);
                inputRef.current?.focus();
              }}
              className="w-full text-left px-4 py-2 font-mono text-sm text-[var(--color-muted)] hover:bg-[var(--color-surface-elevated)] hover:text-[var(--color-success)] transition-colors cursor-pointer"
            >
              {s}
            </button>
          ))}
        </div>
      )}
      <div className="flex items-center gap-2 px-4 py-3">
        <div className="font-mono text-sm shrink-0 select-none hidden sm:block">
          <span className="text-[var(--color-success)]">meridian</span>
          <span className="text-[var(--color-muted)]">@</span>
          <span className="text-[var(--color-accent)]">{personaId || "general"}</span>
          <span className="text-[var(--color-muted)]"> ~ </span>
        </div>
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => {
            const val = e.target.value;
            setInput(val);
            setShowSuggestions(
              val.startsWith("/") && !val.includes(" ", val.indexOf("/") + 1)
            );
          }}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder="Type /help, /quote $AAPL, /ask buffett $NVDA, or ask a question..."
          className="flex-1 bg-transparent font-mono text-sm text-[var(--color-foreground)] placeholder:text-[var(--color-muted)]/50 outline-none disabled:opacity-50"
          autoComplete="off"
          spellCheck={false}
        />
        <button
          onClick={handleSubmit}
          disabled={disabled || !input.trim()}
          className="p-2 rounded-md text-[var(--color-muted)] hover:text-[var(--color-success)] disabled:opacity-30 transition-colors cursor-pointer disabled:cursor-not-allowed"
          aria-label="Send command"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
      <div className="px-4 pb-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[var(--color-muted)]/60">
        <span className="flex items-center gap-1">
          <ChevronUp className="h-3 w-3" /> history
        </span>
        <span>Tab autocomplete</span>
        <span>/help for all commands</span>
        <span>$TICKER syntax</span>
      </div>
    </div>
  );
}
