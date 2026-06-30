"use client";

import { useEffect, useState } from "react";
import { Settings, X } from "lucide-react";
import { DEFAULT_OPENROUTER_MODEL, SUGGESTED_OPENROUTER_MODELS } from "@/lib/openrouter-models";
import {
  clearApiKey,
  clearOpenRouterModel,
  getApiKey,
  getOpenRouterModel,
  saveApiKey,
  saveOpenRouterModel,
} from "@/lib/storage";

interface SettingsModalProps {
  open: boolean;
  onClose: () => void;
  onSaved?: () => void;
}

export function SettingsModal({ open, onClose, onSaved }: SettingsModalProps) {
  const [apiKey, setApiKey] = useState("");
  const [model, setModel] = useState("");
  const [status, setStatus] = useState<{ kind: "ok" | "err" | "info"; text: string } | null>(
    null
  );

  useEffect(() => {
    if (open) {
      setApiKey(getApiKey());
      setModel(getOpenRouterModel() || DEFAULT_OPENROUTER_MODEL);
      setStatus(null);
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const handleSave = () => {
    const trimmedKey = apiKey.trim();
    const trimmedModel = model.trim();

    if (!trimmedModel) {
      setStatus({ kind: "err", text: "Enter an OpenRouter model id." });
      return;
    }

    saveOpenRouterModel(trimmedModel);

    if (trimmedKey) {
      saveApiKey(trimmedKey);
      setStatus({ kind: "ok", text: "API key and model saved in this browser only." });
    } else if (getApiKey()) {
      setStatus({ kind: "ok", text: "Model saved. API key unchanged." });
    } else {
      setStatus({
        kind: "ok",
        text: "Model saved. Add your API key to use AI chat.",
      });
    }
    onSaved?.();
  };

  const handleClearKey = () => {
    setApiKey("");
    clearApiKey();
    setStatus({ kind: "info", text: "API key cleared from this browser." });
    onSaved?.();
  };

  const handleResetModel = () => {
    setModel(DEFAULT_OPENROUTER_MODEL);
    clearOpenRouterModel();
    setStatus({ kind: "info", text: `Model reset to default (${DEFAULT_OPENROUTER_MODEL}).` });
    onSaved?.();
  };

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="settings-title"
    >
      <button
        type="button"
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        aria-label="Close settings"
        onClick={onClose}
      />
      <div className="relative w-full max-w-md rounded-xl border border-[var(--color-border)] bg-[var(--color-surface)] shadow-2xl shadow-black/50">
        <div className="flex items-center justify-between border-b border-[var(--color-border)] px-5 py-4">
          <div className="flex items-center gap-2">
            <Settings className="h-4 w-4 text-[var(--color-success)]" aria-hidden="true" />
            <h2 id="settings-title" className="font-display text-lg">
              Settings
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1.5 text-[var(--color-muted)] hover:bg-[var(--color-surface-elevated)] hover:text-[var(--color-foreground)] cursor-pointer"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-4 px-5 py-5">
          <div>
            <label htmlFor="openrouter-api-key" className="mb-2 block text-sm font-medium">
              OpenRouter API key
            </label>
            <input
              id="openrouter-api-key"
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="sk-or-v1-…"
              autoComplete="off"
              spellCheck={false}
              className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-terminal-bg)] px-3 py-2.5 font-mono text-sm text-[var(--color-foreground)] placeholder:text-[var(--color-muted)] focus:border-[var(--color-success)]/50 focus:outline-none focus:ring-2 focus:ring-[var(--color-success)]/20"
            />
            <p className="mt-2 text-xs leading-relaxed text-[var(--color-muted)]">
              Stored in your browser only (localStorage). Sent directly to OpenRouter with each chat
              request — never stored on our servers.
            </p>
            <p className="mt-1 text-xs text-[var(--color-muted)]">
              Get a key at{" "}
              <a
                href="https://openrouter.ai/keys"
                target="_blank"
                rel="noopener noreferrer"
                className="text-[var(--color-success)] hover:underline"
              >
                openrouter.ai/keys
              </a>
            </p>
          </div>

          <div>
            <label htmlFor="openrouter-model" className="mb-2 block text-sm font-medium">
              Model
            </label>
            <input
              id="openrouter-model"
              type="text"
              list="openrouter-model-suggestions"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder={DEFAULT_OPENROUTER_MODEL}
              autoComplete="off"
              spellCheck={false}
              className="w-full rounded-lg border border-[var(--color-border)] bg-[var(--color-terminal-bg)] px-3 py-2.5 font-mono text-sm text-[var(--color-foreground)] placeholder:text-[var(--color-muted)] focus:border-[var(--color-success)]/50 focus:outline-none focus:ring-2 focus:ring-[var(--color-success)]/20"
            />
            <datalist id="openrouter-model-suggestions">
              {SUGGESTED_OPENROUTER_MODELS.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </datalist>
            <p className="mt-2 text-xs leading-relaxed text-[var(--color-muted)]">
              Any model id from{" "}
              <a
                href="https://openrouter.ai/models"
                target="_blank"
                rel="noopener noreferrer"
                className="text-[var(--color-success)] hover:underline"
              >
                openrouter.ai/models
              </a>
              . Free models often end with <code className="text-[10px]">:free</code>.
            </p>
          </div>

          {status ? (
            <p
              className={`text-sm ${
                status.kind === "ok"
                  ? "text-[var(--color-success)]"
                  : status.kind === "err"
                    ? "text-[var(--color-danger)]"
                    : "text-[var(--color-muted)]"
              }`}
              role="status"
            >
              {status.text}
            </p>
          ) : null}

          <div className="flex flex-wrap gap-2 pt-1">
            <button
              type="button"
              onClick={handleSave}
              className="btn-browseros rounded-full bg-[var(--color-foreground)] px-5 py-2 text-sm text-[var(--color-background)] hover:brightness-110 cursor-pointer"
            >
              Save settings
            </button>
            <button
              type="button"
              onClick={handleClearKey}
              className="btn-browseros rounded-full border border-[var(--color-border)] px-5 py-2 text-sm text-[var(--color-muted)] hover:border-[var(--color-danger)]/40 hover:text-[var(--color-foreground)] cursor-pointer"
            >
              Clear key
            </button>
            <button
              type="button"
              onClick={handleResetModel}
              className="btn-browseros rounded-full border border-[var(--color-border)] px-5 py-2 text-sm text-[var(--color-muted)] hover:border-[var(--color-border)] hover:text-[var(--color-foreground)] cursor-pointer"
            >
              Reset model
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
