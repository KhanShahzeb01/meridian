import { getApiKey } from "@/lib/storage";
import { clientSendChat } from "@/lib/client-chat";
import {
  clientFetchMarketHeadlines,
  clientFetchMarketIndices,
} from "@/lib/client-market";
import { hasBackendApi } from "@/lib/runtime";
import personasGrouped from "@/data/personas.json";

/** Same-origin `/api/…/` in dev (Next proxy); full URL if self-hosting backend. */
function apiUrl(path: string): string {
  const base = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");
  let normalized = path.startsWith("/") ? path : `/${path}`;

  const qIndex = normalized.indexOf("?");
  let pathPart = qIndex >= 0 ? normalized.slice(0, qIndex) : normalized;
  const query = qIndex >= 0 ? normalized.slice(qIndex) : "";
  if (!pathPart.endsWith("/")) {
    pathPart += "/";
  }
  normalized = pathPart + query;

  return base ? `${base}${normalized}` : normalized;
}

export interface Persona {
  id: string;
  name: string;
  short: string;
  title: string;
  category: string;
  quote: string;
  avatar: string;
  color: string;
}

export interface PersonaGroup {
  [category: string]: Persona[];
}

export interface CommandItem {
  cmd: string;
  desc: string;
}

export interface CommandCategory {
  commands: CommandItem[];
}

export interface CommandStructure {
  [category: string]: CommandCategory;
}

export interface ChatSections {
  planning?: string | null;
  thinking?: string | null;
  response?: string | null;
  panels?: { title: string; content: string }[] | null;
  extra?: string | null;
}

export interface ChatResponse {
  type: string;
  content: string;
  is_command?: boolean;
  persona?: string;
  query?: string;
  sections?: ChatSections;
}

const STATIC_COMMANDS: CommandStructure = {
  Data: {
    commands: [
      { cmd: "/quote TICKER", desc: "Real-time price (Yahoo)" },
      { cmd: "/help", desc: "Command list" },
      { cmd: "/personas", desc: "List investor personas" },
    ],
  },
  System: {
    commands: [
      { cmd: "/clear", desc: "Clear terminal" },
      { cmd: "/key", desc: "Set OpenRouter API key (browser)" },
    ],
  },
};

const STATIC_SLASH = [
  "/help",
  "/quote",
  "/personas",
  "/ask",
  "/clear",
  "/key",
];

async function backendFetch<T>(path: string): Promise<T> {
  const res = await fetch(apiUrl(path));
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

export async function fetchPersonas(): Promise<Persona[]> {
  if (!hasBackendApi()) {
    return Object.values(personasGrouped as PersonaGroup).flat();
  }
  return backendFetch("/api/personas");
}

export async function fetchPersonasGrouped(): Promise<PersonaGroup> {
  if (!hasBackendApi()) {
    return personasGrouped as PersonaGroup;
  }
  return backendFetch("/api/personas/grouped");
}

export async function fetchCommands(): Promise<CommandStructure> {
  if (!hasBackendApi()) return STATIC_COMMANDS;
  return backendFetch("/api/commands");
}

export async function fetchSlashCommands(): Promise<string[]> {
  if (!hasBackendApi()) return STATIC_SLASH;
  return backendFetch("/api/commands/slash");
}

export async function fetchHelp(): Promise<string> {
  if (!hasBackendApi()) {
    const r = await clientSendChat("/help", null, null);
    return r.content;
  }
  const data = await backendFetch<{ content: string }>("/api/help");
  return data.content;
}

export async function sendChat(
  message: string,
  personaId: string | null,
  sessionId: string,
  apiKey?: string | null
): Promise<ChatResponse> {
  const key = apiKey ?? getApiKey();

  if (!hasBackendApi()) {
    return clientSendChat(message, personaId, key);
  }

  const controller = new AbortController();
  const isHeavy =
    (message.trim().toLowerCase().startsWith("/memo") &&
      /\b--full\b/i.test(message)) ||
    message.trim().toLowerCase().startsWith("/research") ||
    message.trim().toLowerCase().startsWith("/consensus") ||
    message.trim().toLowerCase().startsWith("/screen");
  const timeoutMs = isHeavy ? 300_000 : 90_000;
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(apiUrl("/api/chat"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        persona_id: personaId || null,
        session_id: sessionId,
        api_key: key || null,
      }),
      signal: controller.signal,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
      const detail = err.detail;
      throw new Error(
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join("; ") ||
              `HTTP ${res.status}`
            : `HTTP ${res.status}`
      );
    }
    return res.json();
  } catch (e) {
    if (e instanceof Error && e.name === "AbortError") {
      throw new Error(
        isHeavy
          ? "Request timed out. Heavy commands like /memo can take several minutes."
          : "Request timed out after 90s."
      );
    }
    if (e instanceof TypeError && e.message === "Failed to fetch") {
      throw new Error(
        "Cannot reach the Meridian API. For full commands, run the local backend (see README)."
      );
    }
    throw e;
  } finally {
    clearTimeout(timer);
  }
}

export async function fetchHealth(): Promise<{
  status: string;
  has_api_key: boolean;
  client_api_key?: boolean;
  initialized: boolean;
}> {
  if (!hasBackendApi()) {
    return {
      status: "ok",
      has_api_key: false,
      client_api_key: true,
      initialized: true,
    };
  }
  return backendFetch("/api/health");
}

export interface MarketIndex {
  id: string;
  name: string;
  symbol: string;
  price: number | null;
  change: number | null;
  change_pct: number | null;
  series: number[];
  as_of?: string;
  source?: string;
}

export interface MarketHeadline {
  title: string;
  url: string;
  published: string;
  source: string;
}

export interface MarketTapeItem {
  symbol: string;
  price: number | null;
  change_pct: number | null;
}

export interface MarketDashboardData {
  indices: MarketIndex[];
  headlines: MarketHeadline[];
}

export async function fetchMarketIndices(): Promise<{
  indices: MarketIndex[];
  updated_at: string;
}> {
  if (!hasBackendApi()) return clientFetchMarketIndices();
  return backendFetch("/api/market/indices");
}

export async function fetchMarketHeadlines(limit = 25): Promise<{
  headlines: MarketHeadline[];
  updated_at: string;
}> {
  if (!hasBackendApi()) return clientFetchMarketHeadlines(limit);
  return backendFetch(`/api/market/headlines?limit=${limit}`);
}

export async function fetchMarketTape(): Promise<{
  tape: MarketTapeItem[];
  updated_at: string;
}> {
  if (!hasBackendApi()) throw new Error("Market tape requires backend");
  return backendFetch("/api/market/tape");
}
