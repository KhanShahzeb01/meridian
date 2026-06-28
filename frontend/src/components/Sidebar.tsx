"use client";

import { ChatSession } from "@/lib/storage";
import { Plus, MessageSquare, Trash2, X } from "lucide-react";

interface SidebarProps {
  sessions: ChatSession[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
  isOpen: boolean;
  onClose: () => void;
}

export default function Sidebar({
  sessions,
  activeId,
  onSelect,
  onNew,
  onDelete,
  isOpen,
  onClose,
}: SidebarProps) {
  return (
    <>
      {isOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}
      <aside
        className={`fixed lg:static inset-y-0 left-0 z-50 flex w-72 flex-col border-r border-[var(--color-border)] bg-[var(--color-surface)] transition-transform duration-300 lg:translate-x-0 ${
          isOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-[var(--color-primary)] text-[var(--color-on-primary)] font-mono text-xs font-bold">
              M
            </div>
            <span className="font-display text-sm tracking-tight">
              Meridian<span className="text-[var(--color-success)]">.</span>
            </span>
          </div>
          <button
            onClick={onClose}
            className="lg:hidden p-1 text-[var(--color-muted)] hover:text-[var(--color-foreground)] cursor-pointer"
            aria-label="Close sidebar"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-3">
          <button
            onClick={onNew}
            className="flex w-full items-center gap-2 rounded-lg border border-dashed border-[var(--color-border)] px-3 py-2.5 text-sm text-[var(--color-muted)] transition-all duration-200 hover:border-[var(--color-primary)]/50 hover:text-[var(--color-foreground)] cursor-pointer"
          >
            <Plus className="h-4 w-4" />
            New Session
          </button>
        </div>

        <div className="flex-1 overflow-y-auto terminal-scroll px-3 pb-3">
          <h3 className="mb-2 px-1 text-xs font-medium uppercase tracking-wider text-[var(--color-muted)]">
            History
          </h3>
          {sessions.length === 0 ? (
            <p className="px-1 text-xs text-[var(--color-muted)]">No sessions yet</p>
          ) : (
            <div className="space-y-1">
              {sessions.map((s) => (
                <div
                  key={s.id}
                  className={`group flex items-center gap-2 rounded-lg px-3 py-2.5 cursor-pointer transition-all duration-200 ${
                    activeId === s.id
                      ? "bg-[var(--color-surface-elevated)] border border-[var(--color-primary)]/30"
                      : "hover:bg-[var(--color-surface-elevated)]/50 border border-transparent"
                  }`}
                  onClick={() => {
                    onSelect(s.id);
                    onClose();
                  }}
                >
                  <MessageSquare className="h-3.5 w-3.5 shrink-0 text-[var(--color-muted)]" />
                  <div className="min-w-0 flex-1">
                    <div className="text-sm truncate">{s.title}</div>
                    <div className="text-xs text-[var(--color-muted)]">
                      {new Date(s.updatedAt).toLocaleDateString()}
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onDelete(s.id);
                    }}
                    className="opacity-0 group-hover:opacity-100 p-1 text-[var(--color-muted)] hover:text-[var(--color-danger)] transition-all cursor-pointer"
                    aria-label="Delete session"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
