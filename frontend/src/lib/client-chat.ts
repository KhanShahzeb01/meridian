import type { ChatResponse } from "./api";
import personaPrompts from "@/data/persona-prompts.json";
import personasGrouped from "@/data/personas.json";
import { OPENROUTER_MODEL } from "./runtime";
import { clientFetchQuote } from "./client-market";

const STATIC_HELP = `## Meridian commands (GitHub Pages)

**Data:** \`/quote TICKER\` — any symbol (e.g. \`/quote AAPL\`, \`/quote NVDA\`)

**Info:** \`/help\` · \`/personas\` · \`/clear\`

**AI (OpenRouter key in Settings):** type any question, \`/ask buffett Is NVDA a buy?\`, or select a persona

**System:** \`/key YOUR_KEY\` — save API key in this browser

Full rallies commands (\`/memo\`, \`/research\`, \`/dcf\`, \`/news\`, etc.) need the optional local backend — see README.`;

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
        model: OPENROUTER_MODEL,
        messages,
        max_tokens: 4096,
        temperature: 0.7,
      }),
    });
  } catch {
    throw new Error(
      "Cannot reach OpenRouter. Check your internet connection and API key in Settings."
    );
  }
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const err = await res.json();
      detail = err.error?.message || detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  const data = await res.json();
  return data.choices?.[0]?.message?.content?.trim() || "(empty response)";
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
    if (personaId && personaPrompts[personaId as keyof typeof personaPrompts]) {
      messages.push({
        role: "system",
        content: personaPrompts[personaId as keyof typeof personaPrompts],
      });
    } else if (lower.startsWith("/ask ")) {
      const parts = text.split(/\s+/);
      const pid = parts[1]?.toLowerCase();
      const question = parts.slice(2).join(" ");
      if (!pid || !personaPrompts[pid as keyof typeof personaPrompts]) {
        return {
          type: "error",
          content: `Unknown persona \`${pid || "?"}\`. Run \`/personas\` for IDs.`,
          is_command: true,
          query: text,
        };
      }
      messages.push({
        role: "system",
        content: personaPrompts[pid as keyof typeof personaPrompts],
      });
      messages.push({ role: "user", content: question || text });
      const content = await openRouterChat(key, messages);
      return { type: "ask", content, persona: pid, query: text };
    }

    if (!messages.length) {
      messages.push({
        role: "system",
        content:
          "You are Meridian, a concise financial analysis assistant. Use markdown tables when showing numbers.",
      });
    }
    messages.push({ role: "user", content: text });

    const content = await openRouterChat(key, messages);
    return {
      type: personaId ? "ask" : "chat",
      content,
      persona: personaId || undefined,
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
