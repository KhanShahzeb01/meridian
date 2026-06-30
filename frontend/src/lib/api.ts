/** Same-origin `/api/…/` in dev (Next proxy); full URL on GitHub Pages builds. */
function apiUrl(path: string): string {
  const base = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/$/, "");
  let normalized = path.startsWith("/") ? path : `/${path}`;

  // Next.js trailingSlash redirects POST without preserving body — always use trailing slash.
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

export async function fetchPersonas(): Promise<Persona[]> {
  const res = await fetch(apiUrl("/api/personas"));
  if (!res.ok) throw new Error("Failed to fetch personas");
  return res.json();
}

export async function fetchPersonasGrouped(): Promise<PersonaGroup> {
  const res = await fetch(apiUrl("/api/personas/grouped"));
  if (!res.ok) throw new Error("Failed to fetch personas");
  return res.json();
}

export async function fetchCommands(): Promise<CommandStructure> {
  const res = await fetch(apiUrl("/api/commands"));
  if (!res.ok) throw new Error("Failed to fetch commands");
  return res.json();
}

export async function fetchSlashCommands(): Promise<string[]> {
  const res = await fetch(apiUrl("/api/commands/slash"));
  if (!res.ok) throw new Error("Failed to fetch slash commands");
  return res.json();
}

export async function fetchHelp(): Promise<string> {
  const res = await fetch(apiUrl("/api/help"));
  if (!res.ok) throw new Error("Failed to fetch help");
  const data = await res.json();
  return data.content;
}

import { getApiKey } from "@/lib/storage";

export async function sendChat(
  message: string,
  personaId: string | null,
  sessionId: string,
  apiKey?: string | null
): Promise<ChatResponse> {
  const controller = new AbortController();
  const key = apiKey ?? getApiKey();
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
            ? detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join("; ") || `HTTP ${res.status}`
            : `HTTP ${res.status}`
      );
    }
    return res.json();
  } catch (e) {
    if (e instanceof Error && e.name === "AbortError") {
      throw new Error(
        isHeavy
          ? "Request timed out. Heavy commands like /memo can take several minutes — try again or check backend logs."
          : "Request timed out after 90s. Try a shorter question or /quote TICKER."
      );
    }
    if (e instanceof TypeError && e.message === "Failed to fetch") {
      throw new Error(
        "Cannot reach the Meridian API. Start the backend (uvicorn main:app --port 8000) and use npm run dev for the frontend."
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
  const res = await fetch(apiUrl("/api/health"));
  if (!res.ok) throw new Error("Backend unavailable");
  return res.json();
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
  const res = await fetch(apiUrl("/api/market/indices"));
  if (!res.ok) throw new Error("Failed to fetch indices");
  return res.json();
}

export async function fetchMarketHeadlines(limit = 25): Promise<{
  headlines: MarketHeadline[];
  updated_at: string;
}> {
  const res = await fetch(apiUrl(`/api/market/headlines?limit=${limit}`));
  if (!res.ok) throw new Error("Failed to fetch headlines");
  return res.json();
}

export async function fetchMarketTape(): Promise<{
  tape: MarketTapeItem[];
  updated_at: string;
}> {
  const res = await fetch(apiUrl("/api/market/tape"));
  if (!res.ok) throw new Error("Failed to fetch market tape");
  return res.json();
}
