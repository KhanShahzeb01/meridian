import type { ChatResponse } from "./api";
import personasGrouped from "@/data/personas.json";
import { OPENROUTER_MODELS } from "./runtime";
import { clientFetchQuote } from "./client-market";
import {
  getPersonaPrompt,
  hasPersonaPrompt,
  parseAskCommand,
  resolvePersonaId,
} from "./persona-resolve";

const STATIC_HELP = `## Meridian commands (GitHub Pages)

**Data:** \`/quote TICKER\` — any symbol (e.g. \`/quote AAPL\`, \`/quote NVDA\`)

**Info:** \`/help\` · \`/personas\` · \`/clear\`

**AI (OpenRouter key in Settings):**
- Select a persona in the sidebar, then type your question
- Or: \`/ask buffett Is NVDA a buy?\` (aliases like \`buffet\` → Buffett work)

**System:** \`/key YOUR_KEY\` — save API key in this browser

Full rallies commands (\`/memo\`, \`/research\`, \`/dcf\`, etc.) need the local backend.`;

const BACKEND_ONLY =
  /^\/(memo|research|consensus|dcf|financials|news|sec|filing|screen|debate|compare|macro|vix|watchlist|portfolio|options|chart|insider|holdings|hedgefund|bundle|optimize|analysis|fetch|skill|searchsec)\b/i;

function formatPersonas(): string {
  const lines = ["## Investor personas\n"];
  for (const [cat, list] of Object.entries(personasGrouped)) {
    lines.push(`### ${cat}`);
    for (const p of list as { name: string; id: string; quote: string }[]) {
      lines.push(`- **${p.name}** (\`${p.id}\`) — ${p.quote}`);
    }
    lines.push("");
  }
  return lines.join("\n");
}

async function openRouterChat(
  apiKey: string,
  messages: { role: string; content: string }[]
): Promise<string> {
  let lastError = "OpenRouter request failed";

  for (const model of OPENROUTER_MODELS) {
    let res: Response;
    try {
      res = await fetch("https://openrouter.ai/api/v1/chat/completions", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${apiKey}`,
          "HTTP-Referer": typeof window !== "undefined" ? window.location.origin : "",
          "X-Title": "Meridian Finance",
        },
        body: JSON.stringify({
          model,
          messages,
          max_tokens: 4096,
          temperature: 0.7,
        }),
      });
    } catch {
      lastError = "Cannot reach OpenRouter. Check your connection and API key.";
      continue;
    }

    if (!res.ok) {
      try {
        const err = await res.json();
        lastError = err.error?.message || `HTTP ${res.status}`;
      } catch {
        lastError = `HTTP ${res.status}`;
      }
      // Try next model on provider/rate-limit errors
      if (res.status === 402 || res.status === 429 || /provider/i.test(lastError)) {
        continue;
      }
      throw new Error(lastError);
    }

    const data = await res.json();
    const content = data.choices?.[0]?.message?.content?.trim();
    if (content) return content;
    lastError = "Empty response from model";
  }

  throw new Error(
    `${lastError}. Try again in a moment or add credits at openrouter.ai — free models can be rate-limited.`
  );
}

function backendOnlyMessage(cmd: string): ChatResponse {
  const name = cmd.split(/\s+/)[0];
  return {
    type: "error",
    content:
      `**\`${name}\` needs the local Meridian backend** (not available on GitHub Pages).\n\n` +
      "Available here: `/quote TICKER`, `/help`, `/personas`, `/clear`, `/key`, `/ask`, or chat with an OpenRouter key.",
    is_command: true,
    query: cmd,
  };
}

export async function clientSendChat(
  message: string,
  personaId: string | null,
  apiKey: string | null
): Promise<ChatResponse> {
  const text = message.trim();
  if (!text) return { type: "empty", content: "" };

  const lower = text.toLowerCase();
  const resolvedSelection = resolvePersonaId(personaId);

  if (lower === "/clear") return { type: "clear", content: "" };
  if (lower === "/help" || lower.startsWith("/help "))
    return { type: "help", content: STATIC_HELP, is_command: true, query: text };
  if (lower === "/personas" || lower.startsWith("/personas "))
    return {
      type: "personas",
      content: formatPersonas(),
      is_command: true,
      query: text,
    };

  if (BACKEND_ONLY.test(lower)) return backendOnlyMessage(text);

  if (lower.startsWith("/quote")) {
    const ticker = text.split(/\s+/)[1]?.replace(/^\$/, "");
    if (!ticker) {
      return {
        type: "error",
        content: "Usage: `/quote AAPL` or `/quote $NVDA`",
        is_command: true,
        query: text,
      };
    }
    const md = await clientFetchQuote(ticker);
    const isError = md.startsWith("Could not fetch");
    return {
      type: isError ? "error" : "quote",
      content: md,
      is_command: true,
      query: text,
    };
  }

  if (lower.startsWith("/ask")) {
    if (!apiKey?.trim()) {
      return {
        type: "error",
        content: "**OpenRouter API key required.** Open **Settings** (⚙) or run `/key YOUR_KEY`.",
        query: text,
      };
    }
    const parsed = parseAskCommand(text, resolvedSelection);
    if ("error" in parsed) {
      return { type: "error", content: parsed.error, is_command: true, query: text };
    }
    try {
      const content = await openRouterChat(apiKey.trim(), [
        { role: "system", content: getPersonaPrompt(parsed.personaId)! },
        { role: "user", content: parsed.question },
      ]);
      return {
        type: "ask",
        content,
        persona: parsed.personaId,
        is_command: true,
        query: text,
      };
    } catch (err) {
      return {
        type: "error",
        content: `**Error:** ${err instanceof Error ? err.message : "Request failed"}`,
        query: text,
      };
    }
  }

  if (!apiKey?.trim()) {
    return {
      type: "error",
      content: "**OpenRouter API key required.** Open **Settings** (⚙) or run `/key YOUR_KEY`.",
      query: text,
    };
  }

  const key = apiKey.trim();
  const messages: { role: string; content: string }[] = [];

  try {
    if (resolvedSelection && hasPersonaPrompt(resolvedSelection)) {
      messages.push({
        role: "system",
        content: getPersonaPrompt(resolvedSelection)!,
      });
    } else {
      messages.push({
        role: "system",
        content:
          "You are Meridian, a concise financial analysis assistant. Use markdown tables when showing numbers.",
      });
    }
    messages.push({ role: "user", content: text });

    const content = await openRouterChat(key, messages);
    return {
      type: resolvedSelection ? "ask" : "chat",
      content,
      persona: resolvedSelection || undefined,
      query: text,
    };
  } catch (err) {
    return {
      type: "error",
      content: `**Error:** ${err instanceof Error ? err.message : "Request failed"}`,
      query: text,
    };
  }
}
