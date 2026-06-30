"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  Menu,
  PanelRightOpen,
  PanelRightClose,
  Home,
  Key,
  Circle,
  Settings,
} from "lucide-react";
import Sidebar from "@/components/Sidebar";
import PersonaSelector from "@/components/PersonaSelector";
import CommandsPanel from "@/components/CommandsPanel";
import TerminalOutput from "@/components/TerminalOutput";
import CommandInput from "@/components/CommandInput";
import { SettingsModal } from "@/components/SettingsModal";
import {
  sendChat,
  fetchPersonasGrouped,
  fetchCommands,
  fetchSlashCommands,
  fetchHealth,
  PersonaGroup,
  CommandStructure,
} from "@/lib/api";
import {
  ChatSession,
  ChatMessage,
  getSessions,
  createSession,
  updateSession,
  deleteSession,
  getActiveSessionId,
  setActiveSessionId,
  getSavedPersona,
  savePersona,
  getApiKey,
  saveApiKey,
  hasApiKey as clientHasApiKey,
} from "@/lib/storage";

export default function TerminalPage() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSession, setActiveSession] = useState<ChatSession | null>(null);
  const [personaGroups, setPersonaGroups] = useState<PersonaGroup>({});
  const [commands, setCommands] = useState<CommandStructure>({});
  const [slashCommands, setSlashCommands] = useState<string[]>([]);
  const [personaId, setPersonaId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [pendingQuery, setPendingQuery] = useState<string | undefined>();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [rightPanelOpen, setRightPanelOpen] = useState(false);
  const [prefill, setPrefill] = useState<string | undefined>();
  const [hasApiKey, setHasApiKey] = useState<boolean | null>(null);
  const [backendOk, setBackendOk] = useState(true);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const refreshApiKeyState = useCallback(() => {
    setHasApiKey(clientHasApiKey());
  }, []);

  useEffect(() => {
    const saved = getSavedPersona();
    setPersonaId(saved);
    setSessions(getSessions());

    const activeId = getActiveSessionId();
    const allSessions = getSessions();
    if (activeId && allSessions.find((s) => s.id === activeId)) {
      const s = allSessions.find((s) => s.id === activeId)!;
      setActiveSession(s);
      setPersonaId(saved ?? (s.personaId || null));
    } else if (allSessions.length > 0) {
      setActiveSession(allSessions[0]);
      setActiveSessionId(allSessions[0].id);
    } else {
      const s = createSession(saved);
      setActiveSession(s);
      setSessions([s]);
    }

    fetchPersonasGrouped().then(setPersonaGroups).catch(() => {});
    fetchCommands().then(setCommands).catch(() => {});
    fetchSlashCommands()
      .then(setSlashCommands)
      .catch(() =>
        setSlashCommands([
          "/help", "/quote", "/financials", "/news", "/dcf", "/sec",
          "/earnings", "/consensus", "/ask", "/debate", "/personas",
          "/screen", "/watchlist", "/portfolio", "/macro", "/vix",
          "/research", "/memo", "/clear", "/key",
        ])
      );
    fetchHealth()
      .then(() => {
        refreshApiKeyState();
        setBackendOk(true);
      })
      .catch(() => setBackendOk(false));
    refreshApiKeyState();
  }, [refreshApiKeyState]);

  useEffect(() => {
    const mq = window.matchMedia("(min-width: 1024px)");
    const openOnDesktop = () => {
      if (mq.matches) setRightPanelOpen(true);
    };
    openOnDesktop();
    mq.addEventListener("change", openOnDesktop);
    return () => mq.removeEventListener("change", openOnDesktop);
  }, []);

  const handleNewSession = () => {
    const s = createSession(personaId);
    setSessions(getSessions());
    setActiveSession(s);
  };

  const handleSelectSession = (id: string) => {
    const s = getSessions().find((sess) => sess.id === id);
    if (s) {
      setActiveSession(s);
      setActiveSessionId(id);
      setPersonaId(s.personaId ? s.personaId : null);
    }
  };

  const handleDeleteSession = (id: string) => {
    deleteSession(id);
    const updated = getSessions();
    setSessions(updated);
    const activeId = getActiveSessionId();
    if (activeId) {
      setActiveSession(updated.find((s) => s.id === activeId) || null);
    } else {
      const s = createSession(personaId);
      setActiveSession(s);
      setSessions(getSessions());
    }
  };

  const handlePersonaChange = (id: string | null) => {
    setPersonaId(id);
    savePersona(id);
    if (activeSession) {
      const updated = { ...activeSession, personaId: id || "" };
      setActiveSession(updated);
      updateSession(updated);
    }
  };

  const addMessage = useCallback(
    (msg: ChatMessage) => {
      if (!activeSession) return;
      const updated: ChatSession = {
        ...activeSession,
        messages: [...activeSession.messages, msg],
      };
      if (msg.role === "user" && activeSession.title === "New Analysis") {
        updated.title = msg.content.slice(0, 40);
      }
      setActiveSession(updated);
      updateSession(updated);
      setSessions(getSessions());
    },
    [activeSession]
  );

  const handleCommand = async (text: string) => {
    if (!activeSession) return;

    const trimmed = text.trim();
    if (trimmed.toLowerCase().startsWith("/key")) {
      const key = trimmed.slice(4).trim();
      const userMsg: ChatMessage = {
        id: `${Date.now()}-user`,
        role: "user",
        content: text,
        timestamp: Date.now(),
      };
      addMessage(userMsg);
      if (!key) {
        setSettingsOpen(true);
        addMessage({
          id: `${Date.now()}-asst`,
          role: "assistant",
          content: "Open **Settings** to paste your OpenRouter API key. It stays in this browser only.",
          timestamp: Date.now(),
          type: "system",
        });
        return;
      }
      saveApiKey(key);
      refreshApiKeyState();
      addMessage({
        id: `${Date.now()}-asst`,
        role: "assistant",
        content: `API key saved in this browser (\`…${key.slice(-4)}\`). AI commands are ready.`,
        timestamp: Date.now(),
        type: "system",
      });
      return;
    }

    const userMsg: ChatMessage = {
      id: `${Date.now()}-user`,
      role: "user",
      content: text,
      timestamp: Date.now(),
    };
    addMessage(userMsg);

    setIsLoading(true);
    setPendingQuery(text);
    try {
      const isSlash = text.startsWith("/");
      const needsKey =
        !clientHasApiKey() &&
        (isSlash
          ? /^\/(memo|ask|debate|consensus|research|screen|dcf)\b/i.test(trimmed)
          : Boolean(personaId));
      if (needsKey) {
        addMessage({
          id: `${Date.now()}-asst`,
          role: "assistant",
          content:
            "**OpenRouter API key required.** Click **Settings** (⚙) or run `/key YOUR_KEY`. Your key stays in this browser only.",
          timestamp: Date.now(),
          type: "error",
        });
        return;
      }

      const response = await sendChat(
        text,
        isSlash ? null : personaId,
        activeSession.id,
        getApiKey()
      );

      if (response.type === "clear") {
        const cleared: ChatSession = {
          ...activeSession,
          messages: [
            {
              id: `${Date.now()}-sys`,
              role: "system",
              content: "Terminal cleared. Type /help for all commands.",
              timestamp: Date.now(),
              type: "system",
            },
          ],
        };
        setActiveSession(cleared);
        updateSession(cleared);
        setSessions(getSessions());
        return;
      }

      addMessage({
        id: `${Date.now()}-asst`,
        role: "assistant",
        content: response.content,
        timestamp: Date.now(),
        type: response.type,
        persona: response.persona,
        sections: response.sections,
      });

    } catch (err) {
      addMessage({
        id: `${Date.now()}-err`,
        role: "assistant",
        content: `**Error:** ${err instanceof Error ? err.message : "Request failed"}`,
        timestamp: Date.now(),
        type: "error",
      });
    } finally {
      setIsLoading(false);
      setPendingQuery(undefined);
    }
  };

  const runCommand = (cmd: string) => {
    setPrefill(cmd);
  };

  const askPersona = (id: string) => {
    setPrefill(`/ask ${id} `);
  };

  return (
    <div className="flex h-dvh bg-[var(--color-background)]">
      <Sidebar
        sessions={sessions}
        activeId={activeSession?.id || null}
        onSelect={handleSelectSession}
        onNew={handleNewSession}
        onDelete={handleDeleteSession}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      <div className="flex flex-1 flex-col min-w-0">
        <header className="flex items-center justify-between border-b border-[var(--color-border)] bg-[var(--color-surface)] px-4 py-2.5">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden p-1.5 text-[var(--color-muted)] hover:text-[var(--color-foreground)] cursor-pointer"
              aria-label="Open sidebar"
            >
              <Menu className="h-5 w-5" />
            </button>
            <Link
              href="/"
              className="p-1.5 text-[var(--color-muted)] hover:text-[var(--color-foreground)] transition-colors cursor-pointer"
              aria-label="Home"
            >
              <Home className="h-4 w-4" />
            </Link>
            <div className="flex items-center gap-2 font-mono text-xs">
              <Circle
                className={`h-2 w-2 fill-current ${
                  backendOk ? "text-[var(--color-success)]" : "text-[var(--color-danger)]"
                }`}
              />
              <span className="text-[var(--color-muted)] hidden sm:inline">
                meridian engine
              </span>
              {!hasApiKey && backendOk && (
                <button
                  onClick={() => setSettingsOpen(true)}
                  className="flex items-center gap-1 text-[var(--color-success)] hover:underline cursor-pointer"
                >
                  <Key className="h-3 w-3" />
                  <span className="hidden sm:inline">set API key</span>
                </button>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => setSettingsOpen(true)}
              className="p-1.5 rounded-md text-[var(--color-muted)] hover:text-[var(--color-foreground)] hover:bg-[var(--color-surface-elevated)] cursor-pointer"
              aria-label="Settings"
              title="Settings"
            >
              <Settings className="h-4 w-4" />
            </button>
            <button
              onClick={() => handleCommand("/help")}
              className="px-3 py-1.5 rounded-md text-xs font-medium text-[var(--color-muted)] hover:text-[var(--color-success)] hover:bg-[var(--color-surface-elevated)] transition-colors cursor-pointer"
            >
              /help
            </button>
            <button
              onClick={() => handleCommand("/personas")}
              className="px-3 py-1.5 rounded-md text-xs font-medium text-[var(--color-muted)] hover:text-[var(--color-success)] hover:bg-[var(--color-surface-elevated)] transition-colors cursor-pointer hidden sm:block"
            >
              /personas
            </button>
            <button
              onClick={() => setRightPanelOpen(!rightPanelOpen)}
              className="p-1.5 text-[var(--color-muted)] hover:text-[var(--color-foreground)] cursor-pointer"
              aria-label={rightPanelOpen ? "Hide side panel" : "Show side panel"}
              title={rightPanelOpen ? "Hide personas & commands" : "Show personas & commands"}
            >
              {rightPanelOpen ? (
                <PanelRightClose className="h-4 w-4" />
              ) : (
                <PanelRightOpen className="h-4 w-4" />
              )}
            </button>
          </div>
        </header>

        <div className="flex flex-1 min-h-0">
          <div className="flex flex-1 flex-col min-w-0 bg-[var(--color-terminal-bg)]">
            <TerminalOutput
              messages={activeSession?.messages || []}
              isLoading={isLoading}
              pendingQuery={pendingQuery}
            />
            <CommandInput
              onSubmit={handleCommand}
              personaId={personaId}
              slashCommands={slashCommands}
              disabled={isLoading}
              prefill={prefill}
              onPrefillUsed={() => setPrefill(undefined)}
            />
          </div>

          {rightPanelOpen && (
            <>
              <div
                className="fixed inset-0 z-40 bg-black/50 lg:hidden"
                onClick={() => setRightPanelOpen(false)}
                aria-hidden="true"
              />
              <aside
                className="fixed inset-y-0 right-0 z-50 flex w-80 max-w-[min(20rem,90vw)] flex-col border-l border-[var(--color-border)] bg-[var(--color-surface)] overflow-y-auto terminal-scroll lg:static lg:z-auto lg:w-72 lg:max-w-none"
              >
                <div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-2.5 lg:hidden">
                  <span className="text-xs font-medium uppercase tracking-wider text-[var(--color-muted)]">
                    Personas & Commands
                  </span>
                  <button
                    type="button"
                    onClick={() => setRightPanelOpen(false)}
                    className="p-1 text-[var(--color-muted)] hover:text-[var(--color-foreground)] cursor-pointer"
                    aria-label="Close side panel"
                  >
                    <PanelRightClose className="h-4 w-4" />
                  </button>
                </div>
                <div className="p-4 border-b border-[var(--color-border)]">
                  <PersonaSelector
                    grouped={personaGroups}
                    selected={personaId}
                    onSelect={handlePersonaChange}
                    onAsk={askPersona}
                  />
                </div>
                <div className="p-4 flex-1">
                  <CommandsPanel commands={commands} onRun={runCommand} />
                </div>
              </aside>
            </>
          )}
        </div>
      </div>

      <SettingsModal
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        onSaved={refreshApiKeyState}
      />
    </div>
  );
}
