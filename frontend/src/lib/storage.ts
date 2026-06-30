import { DEFAULT_OPENROUTER_MODEL } from "./openrouter-models";

export interface ChatSections {
  planning?: string | null;
  thinking?: string | null;
  response?: string | null;
  panels?: { title: string; content: string }[] | null;
  extra?: string | null;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
  type?: string;
  persona?: string;
  sections?: ChatSections;
}

export interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  personaId: string;
  createdAt: number;
  updatedAt: number;
}

export interface WatchlistItem {
  ticker: string;
  addedAt: number;
}

export interface PortfolioItem {
  ticker: string;
  shares: number;
  avgCost: number;
  addedAt: number;
}

const SESSIONS_KEY = "meridian_sessions";
const ACTIVE_SESSION_KEY = "meridian_active_session";
const WATCHLIST_KEY = "meridian_watchlist";
const PORTFOLIO_KEY = "meridian_portfolio";
const PERSONA_KEY = "meridian_persona";
const API_KEY_STORAGE = "meridian_openrouter_api_key";
const MODEL_KEY = "meridian_openrouter_model";
const FINNHUB_KEY_STORAGE = "meridian_finnhub_api_key";

function generateId(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

export function getSessions(): ChatSession[] {
  if (typeof window === "undefined") return [];
  try {
    const data = localStorage.getItem(SESSIONS_KEY);
    return data ? JSON.parse(data) : [];
  } catch {
    return [];
  }
}

export function saveSessions(sessions: ChatSession[]): void {
  localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions));
}

export function getActiveSessionId(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACTIVE_SESSION_KEY);
}

export function setActiveSessionId(id: string): void {
  localStorage.setItem(ACTIVE_SESSION_KEY, id);
}

export function createSession(personaId: string | null): ChatSession {
  const session: ChatSession = {
    id: generateId(),
    title: "New Analysis",
    messages: [
      {
        id: generateId(),
        role: "system",
        content:
          "Welcome to Meridian Finance. General conversation mode — select a persona in the side panel to analyze as a specific investor. Type /help for commands.",
        timestamp: Date.now(),
        type: "system",
      },
    ],
    personaId: personaId || "",
    createdAt: Date.now(),
    updatedAt: Date.now(),
  };
  const sessions = getSessions();
  sessions.unshift(session);
  saveSessions(sessions);
  setActiveSessionId(session.id);
  return session;
}

export function updateSession(session: ChatSession): void {
  session.updatedAt = Date.now();
  const sessions = getSessions();
  const idx = sessions.findIndex((s) => s.id === session.id);
  if (idx >= 0) {
    sessions[idx] = session;
  } else {
    sessions.unshift(session);
  }
  saveSessions(sessions);
}

export function deleteSession(id: string): void {
  const sessions = getSessions().filter((s) => s.id !== id);
  saveSessions(sessions);
  if (getActiveSessionId() === id) {
    const next = sessions[0]?.id || null;
    if (next) setActiveSessionId(next);
    else localStorage.removeItem(ACTIVE_SESSION_KEY);
  }
}

export function getWatchlist(): WatchlistItem[] {
  if (typeof window === "undefined") return [];
  try {
    const data = localStorage.getItem(WATCHLIST_KEY);
    return data ? JSON.parse(data) : [];
  } catch {
    return [];
  }
}

export function saveWatchlist(items: WatchlistItem[]): void {
  localStorage.setItem(WATCHLIST_KEY, JSON.stringify(items));
}

export function addToWatchlist(ticker: string): WatchlistItem[] {
  const list = getWatchlist();
  const upper = ticker.toUpperCase();
  if (!list.find((i) => i.ticker === upper)) {
    list.push({ ticker: upper, addedAt: Date.now() });
    saveWatchlist(list);
  }
  return list;
}

export function removeFromWatchlist(ticker: string): WatchlistItem[] {
  const list = getWatchlist().filter((i) => i.ticker !== ticker.toUpperCase());
  saveWatchlist(list);
  return list;
}

export function getPortfolio(): PortfolioItem[] {
  if (typeof window === "undefined") return [];
  try {
    const data = localStorage.getItem(PORTFOLIO_KEY);
    return data ? JSON.parse(data) : [];
  } catch {
    return [];
  }
}

export function savePortfolio(items: PortfolioItem[]): void {
  localStorage.setItem(PORTFOLIO_KEY, JSON.stringify(items));
}

export function addToPortfolio(
  ticker: string,
  shares: number,
  avgCost: number
): PortfolioItem[] {
  const list = getPortfolio();
  const upper = ticker.toUpperCase();
  const existing = list.find((i) => i.ticker === upper);
  if (existing) {
    const totalShares = existing.shares + shares;
    existing.avgCost =
      (existing.avgCost * existing.shares + avgCost * shares) / totalShares;
    existing.shares = totalShares;
  } else {
    list.push({ ticker: upper, shares, avgCost, addedAt: Date.now() });
  }
  savePortfolio(list);
  return list;
}

export function removeFromPortfolio(ticker: string): PortfolioItem[] {
  const list = getPortfolio().filter((i) => i.ticker !== ticker.toUpperCase());
  savePortfolio(list);
  return list;
}

export function getSavedPersona(): string | null {
  if (typeof window === "undefined") return null;
  const v = localStorage.getItem(PERSONA_KEY);
  return v && v.trim() ? v : null;
}

export function savePersona(id: string | null): void {
  if (!id) {
    localStorage.removeItem(PERSONA_KEY);
    return;
  }
  localStorage.setItem(PERSONA_KEY, id);
}

export function getApiKey(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(API_KEY_STORAGE)?.trim() || "";
}

export function saveApiKey(key: string): void {
  const trimmed = key.trim();
  if (!trimmed) {
    localStorage.removeItem(API_KEY_STORAGE);
    return;
  }
  localStorage.setItem(API_KEY_STORAGE, trimmed);
}

export function clearApiKey(): void {
  localStorage.removeItem(API_KEY_STORAGE);
}

export function hasApiKey(): boolean {
  return getApiKey().length > 0;
}

export function getOpenRouterModel(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(MODEL_KEY)?.trim() || "";
}

export function saveOpenRouterModel(model: string): void {
  const trimmed = model.trim();
  if (!trimmed) {
    localStorage.removeItem(MODEL_KEY);
    return;
  }
  localStorage.setItem(MODEL_KEY, trimmed);
}

export function clearOpenRouterModel(): void {
  localStorage.removeItem(MODEL_KEY);
}

/** Model from Settings, or site default. No silent fallback to other models. */
export function getActiveOpenRouterModel(): string {
  const user = getOpenRouterModel();
  return user || DEFAULT_OPENROUTER_MODEL;
}

export function getFinnhubKey(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem(FINNHUB_KEY_STORAGE)?.trim() || "";
}

export function saveFinnhubKey(key: string): void {
  const trimmed = key.trim();
  if (!trimmed) {
    localStorage.removeItem(FINNHUB_KEY_STORAGE);
    return;
  }
  localStorage.setItem(FINNHUB_KEY_STORAGE, trimmed);
}

export function clearFinnhubKey(): void {
  localStorage.removeItem(FINNHUB_KEY_STORAGE);
}
