import type { ChatResponse } from "./api";
import { clientFetchQuote } from "./client-market";
import { openRouterChat } from "./openrouter-client";
import { getPersonaName, getPersonaPrompt, hasPersonaPrompt } from "./persona-resolve";
import { getFinnhubKey } from "./storage";

/** Seven-expert panel for browser-side /consensus */
export const CONSENSUS_PANEL = [
  "buffett",
  "munger",
  "lynch",
  "cathie_wood",
  "simons",
  "dalio",
  "ackman",
] as const;

const MANAGER_PROMPT = `You are the Chief Investment Officer synthesizing multiple analyst opinions.
You will receive analyses from different investment personas on the same stock.
Your job:
1. Summarize each persona's key points (bull/bear case, rating)
2. Identify areas of agreement and disagreement
3. Conduct a vote: each persona gets one vote (BUY/HOLD/SELL)
4. Majority opinion wins as the final consensus
5. Provide a structured final recommendation with confidence level

Format your response with clear sections:
## Individual Analyses Summary
## Points of Agreement
## Points of Disagreement
## Voting Results
## Final Consensus Recommendation`;

const MEMO_SYSTEM = `You are a buyside analyst writing a concise investment memo in markdown.
Use ONLY numbers from the live data block. Never invent prices, dates, or financials.
If data is missing, say unavailable.

Structure (use these headings):
## Executive summary
## Investment thesis (3-5 bullets)
## Valuation & price target ({horizon} horizon, {direction})
## Key risks
## Catalysts to watch

Keep the memo under 400 words. Be direct. Cite actual figures from the data.`;

function parseTickerFromArgs(text: string, cmd: string): string | null {
  const parts = text.trim().split(/\s+/);
  if (parts.length < 2 || !parts[0].toLowerCase().startsWith(cmd)) return null;
  const raw = parts[1].replace(/^\$/, "").toUpperCase();
  if (!/^[A-Z][A-Z0-9.\-]{0,5}$/.test(raw)) return null;
  return raw;
}

function parseMemoArgs(
  text: string
): { ticker: string; direction: string; horizon: string } | { full: true } | null {
  const parts = text.trim().split(/\s+/);
  if (!parts[0]?.toLowerCase().startsWith("/memo")) return null;
  if (parts[1]?.toLowerCase() === "--full" || parts[1]?.toLowerCase() === "-f") {
    return { full: true };
  }
  if (parts.length < 3) return null;
  const ticker = parts[1].toUpperCase().replace(/^\$/, "");
  const dir = parts[2].toLowerCase();
  if (!/^[A-Z][A-Z0-9.\-]{0,5}$/.test(ticker)) return null;
  if (!/^(long|short|l|s)$/.test(dir)) return null;
  const direction = dir.startsWith("l") ? "LONG" : "SHORT";
  const horizon = parts[3] || "12mo";
  return { ticker, direction, horizon };
}

async function fetchFinnhubHeadlines(ticker: string): Promise<string> {
  const key = getFinnhubKey();
  if (!key) return "";

  try {
    const to = new Date();
    const from = new Date(to.getTime() - 5 * 24 * 60 * 60 * 1000);
    const fmt = (d: Date) => d.toISOString().slice(0, 10);
    const url = `https://finnhub.io/api/v1/company-news?symbol=${encodeURIComponent(ticker)}&from=${fmt(from)}&to=${fmt(to)}&token=${encodeURIComponent(key)}`;
    const res = await fetch(url);
    if (!res.ok) return "";
    const articles = (await res.json()) as { headline?: string }[];
    const lines = ["## Recent headlines"];
    for (const art of (articles || []).slice(0, 4)) {
      const headline = art.headline?.slice(0, 100);
      if (headline) lines.push(`- ${headline}`);
    }
    return lines.length > 1 ? lines.join("\n") : "";
  } catch {
    return "";
  }
}

export async function runClientConsensus(text: string, apiKey: string): Promise<ChatResponse> {
  const ticker = parseTickerFromArgs(text, "/consensus");
  if (!ticker) {
    return {
      type: "error",
      content: "Usage: `/consensus TICKER` (e.g. `/consensus NVDA` or `/consensus $AAPL`)",
      is_command: true,
      query: text,
    };
  }

  const quoteBlock = await clientFetchQuote(ticker);
  if (quoteBlock.startsWith("Could not fetch")) {
    return { type: "error", content: quoteBlock, is_command: true, query: text };
  }

  const analyses: string[] = [];
  const expertPrompt = `Analyze ${ticker} using the live quote data below. Be concise (under 200 words). End with a clear line: **Vote: BUY | HOLD | SELL** and one sentence why.

## Live data
${quoteBlock}`;

  for (const personaId of CONSENSUS_PANEL) {
    if (!hasPersonaPrompt(personaId)) continue;
    const name = getPersonaName(personaId);
    const analysis = await openRouterChat(
      apiKey,
      [
        { role: "system", content: getPersonaPrompt(personaId)! },
        { role: "user", content: expertPrompt },
      ],
      { maxTokens: 800, temperature: 0.6 }
    );
    analyses.push(`### ${name}\n${analysis}`);
  }

  const combined = analyses.join("\n\n");
  const managerSummary = await openRouterChat(
    apiKey,
    [
      { role: "system", content: MANAGER_PROMPT },
      {
        role: "user",
        content: `Synthesize these analyst opinions on ${ticker}:\n\n${combined}`,
      },
    ],
    { maxTokens: 2500, temperature: 0.5 }
  );

  return {
    type: "consensus",
    content: `# Consensus — ${ticker}\n\n## Expert panel (${CONSENSUS_PANEL.length} analysts)\n\n${combined}\n\n---\n\n## CIO synthesis\n\n${managerSummary}`,
    is_command: true,
    query: text,
    sections: {
      panels: analyses.map((block) => {
        const title = block.match(/^### (.+)/)?.[1] || "Expert";
        const content = block.replace(/^### .+\n/, "");
        return { title, content };
      }),
      response: managerSummary,
    },
  };
}

export async function runClientMemo(text: string, apiKey: string): Promise<ChatResponse> {
  const parsed = parseMemoArgs(text);
  if (!parsed) {
    return {
      type: "error",
      content:
        "Usage: `/memo TICKER long|short [horizon]`\n\nExample: `/memo NVDA long 12mo`",
      is_command: true,
      query: text,
    };
  }

  if ("full" in parsed) {
    return {
      type: "error",
      content:
        "**`/memo --full`** (HTML memo with expert panel) needs the local Meridian backend.\n\nOn GitHub Pages use **`/memo TICKER long`** for a fast browser memo (OpenRouter + live quote).",
      is_command: true,
      query: text,
    };
  }

  const { ticker, direction, horizon } = parsed;
  const quoteBlock = await clientFetchQuote(ticker);
  if (quoteBlock.startsWith("Could not fetch")) {
    return { type: "error", content: quoteBlock, is_command: true, query: text };
  }

  const news = await fetchFinnhubHeadlines(ticker);
  const dataBlock = [quoteBlock, news].filter(Boolean).join("\n\n");
  const finnhubNote = getFinnhubKey()
    ? ""
    : "\n\n*Optional: add a Finnhub API key in Settings for recent headlines in memos.*";

  const system = MEMO_SYSTEM.replace("{horizon}", horizon).replace("{direction}", direction);
  const memoBody = await openRouterChat(
    apiKey,
    [
      { role: "system", content: system },
      {
        role: "user",
        content: `Ticker: ${ticker}\nDirection: ${direction}\nHorizon: ${horizon}\n\n## Live data\n${dataBlock}\n\nWrite the investment memo in markdown.`,
      },
    ],
    { maxTokens: 1200, temperature: 0.55 }
  );

  return {
    type: "memo",
    content: `# ${ticker} — ${direction} memo (${horizon})\n\n${memoBody}${finnhubNote}`,
    is_command: true,
    query: text,
  };
}
