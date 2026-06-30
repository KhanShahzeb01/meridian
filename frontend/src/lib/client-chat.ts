import type { ChatResponse } from "./api";
import personaPrompts from "@/data/persona-prompts.json";
import personasGrouped from "@/data/personas.json";
import { OPENROUTER_MODEL } from "./runtime";
import { clientFetchQuote } from "./client-market";

const STATIC_HELP = `## Meridian commands (GitHub Pages)

**Data:** \`/quote TICKER\` · \`/help\` · \`/personas\` · \`/clear\`

**AI (needs OpenRouter key in Settings):** ask any question, or select a persona and type your question.

Full rallies commands (\`/memo\`, \`/research\`, \`/dcf\`, etc.) need the optional local backend — see README.`;

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
  const res = await fetch("https://openrouter.ai/api/v1/chat/completions", {
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

  if (lower.startsWith("/quote")) {
    const ticker = text.split(/\s+/)[1];
    if (!ticker) {
      return {
        type: "error",
        content: "Usage: `/quote AAPL`",
        is_command: true,
        query: text,
      };
    }
    try {
      const md = await clientFetchQuote(ticker);
      const isError = md.startsWith("Could not fetch");
      return {
        type: isError ? "error" : "quote",
        content: md,
        is_command: true,
        query: text,
      };
    } catch {
      return {
        type: "error",
        content: `Could not fetch quote for **${ticker.toUpperCase()}**. Check your connection and try again.`,
        is_command: true,
        query: text,
      };
    }
  }

  if (!apiKey?.trim()) {
    return {
      type: "error",
      content: "**OpenRouter API key required.** Open **Settings** (⚙) and paste your key.",
      query: text,
    };
  }

  const key = apiKey.trim();
  const messages: { role: string; content: string }[] = [];

  if (personaId && personaPrompts[personaId as keyof typeof personaPrompts]) {
    messages.push({
      role: "system",
      content: personaPrompts[personaId as keyof typeof personaPrompts],
    });
  } else if (lower.startsWith("/ask ")) {
    const parts = text.split(/\s+/);
    const pid = parts[1]?.toLowerCase();
    const question = parts.slice(2).join(" ");
    if (pid && personaPrompts[pid as keyof typeof personaPrompts]) {
      messages.push({
        role: "system",
        content: personaPrompts[pid as keyof typeof personaPrompts],
      });
      messages.push({ role: "user", content: question || text });
      const content = await openRouterChat(key, messages);
      return { type: "ask", content, persona: pid, query: text };
    }
  }

  const userContent = personaId ? text : text;
  if (!messages.length) {
    messages.push({
      role: "system",
      content:
        "You are Meridian, a concise financial analysis assistant. Use markdown tables when showing numbers.",
    });
  }
  messages.push({ role: "user", content: userContent });

  const content = await openRouterChat(key, messages);
  return {
    type: personaId ? "ask" : "chat",
    content,
    persona: personaId || undefined,
    query: text,
  };
}
