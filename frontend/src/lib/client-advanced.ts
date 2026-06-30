import type { ChatResponse } from "./api";
import { clientFetchQuote } from "./client-market";
import { openRouterChat } from "./openrouter-client";
import { getPersonaName, getPersonaPrompt, hasPersonaPrompt } from "./persona-resolve";
import { getFinnhubKey } from "./storage";

/** Seven-expert panel for full /consensus --panel mode */
export const CONSENSUS_PANEL = [
  "buffett",
  "munger",
  "lynch",
  "cathie_wood",
  "simons",
  "dalio",
  "ackman",
] as const;

const MANAGER_PROMPT = `You are the Chief Investment Officer synthesizing analyst opinions on one stock.
Summarize key points, areas of agreement/disagreement, vote tally (BUY/HOLD/SELL), and a final recommendation with confidence.
Use markdown sections: ## Summary · ## Agreement · ## Disagreement · ## Votes · ## Final call`;

function expertBlurbs(): string {
  return CONSENSUS_PANEL.filter(hasPersonaPrompt)
    .map((id) => `- **${getPersonaName(id)}**`)
    .join("\n");
}

const FAST_CONSENSUS_SYSTEM = `You run a fast investment consensus panel in one response.
Use ONLY numbers from the live data block — never invent prices or financials.

For each expert below, write a ### heading with their name, then 2-4 sentences in their style, ending with **Vote: BUY | HOLD | SELL** and a brief reason.

Experts:
${CONSENSUS_PANEL.map((id) => (hasPersonaPrompt(id) ? `### ${getPersonaName(id)}\n(In character as: ${getPersonaPrompt(id)!.slice(0, 160)}…)` : ""))
  .filter(Boolean)
  .join("\n\n")}

After all experts, add:
## CIO synthesis
## Vote tally
## Final consensus (BUY/HOLD/SELL) with confidence level

Keep each expert under 90 words. Be direct.`;

async function runParallelPanel(
  apiKey: string,
  ticker: string,
  quoteBlock: string
): Promise<{ combined: string; panels: { title: string; content: string }[] }> {
  const expertPrompt = `Analyze ${ticker} using the live quote data. Max 80 words. End with **Vote: BUY | HOLD | SELL**.

## Live data
${quoteBlock}`;

  const blocks = await Promise.all(
    CONSENSUS_PANEL.filter(hasPersonaPrompt).map(async (personaId) => {
      const name = getPersonaName(personaId);
      const analysis = await openRouterChat(
        apiKey,
        [
          { role: "system", content: getPersonaPrompt(personaId)! },
          { role: "user", content: expertPrompt },
        ],
        { maxTokens: 320, temperature: 0.5 }
      );
      return `### ${name}\n${analysis}`;
    })
  );

  const combined = blocks.join("\n\n");
  const managerSummary = await openRouterChat(
    apiKey,
    [
      { role: "system", content: MANAGER_PROMPT },
      {
        role: "user",
        content: `Synthesize these opinions on ${ticker}:\n\n${combined}`,
      },
    ],
    { maxTokens: 1400, temperature: 0.45 }
  );

  return {
    combined: `${combined}\n\n---\n\n## CIO synthesis\n\n${managerSummary}`,
    panels: blocks.map((block) => {
      const title = block.match(/^### (.+)/)?.[1] || "Expert";
      const content = block.replace(/^### .+\n/, "");
      return { title, content };
    }),
  };
}

async function runFastConsensus(
  apiKey: string,
  ticker: string,
  quoteBlock: string
): Promise<string> {
  return openRouterChat(
    apiKey,
    [
      { role: "system", content: FAST_CONSENSUS_SYSTEM },
      {
        role: "user",
        content: `Ticker: ${ticker}\n\n## Live data\n${quoteBlock}\n\nRun the full panel now.`,
      },
    ],
    { maxTokens: 2200, temperature: 0.55 }
  );
}

function parseConsensusArgs(text: string): { ticker: string; fullPanel: boolean } | null {
  const parts = text.trim().split(/\s+/);
  if (!parts[0]?.toLowerCase().startsWith("/consensus")) return null;

  const fullPanel = parts.some((p) => /^(--panel|--full|-p|-f)$/i.test(p));
  const tickerPart = parts.find(
    (p) => !p.startsWith("/") && !/^--/.test(p) && !/^-[a-z]$/i.test(p)
  );
  if (!tickerPart) return null;
  const ticker = tickerPart.replace(/^\$/, "").toUpperCase();
  if (!/^[A-Z][A-Z0-9.\-]{0,5}$/.test(ticker)) return null;
  return { ticker, fullPanel };
}

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
  const parsed = parseConsensusArgs(text);
  if (!parsed) {
    return {
      type: "error",
      content:
        "Usage: `/consensus TICKER` (fast, ~30s)\n\nExample: `/consensus NVDA`\n\nSlower full panel: `/consensus --panel NVDA`",
      is_command: true,
      query: text,
    };
  }

  const { ticker, fullPanel } = parsed;
  const quoteBlock = await clientFetchQuote(ticker);
  if (quoteBlock.startsWith("Could not fetch")) {
    return { type: "error", content: quoteBlock, is_command: true, query: text };
  }

  if (fullPanel) {
    const { combined, panels } = await runParallelPanel(apiKey, ticker, quoteBlock);
    return {
      type: "consensus",
      content: `# Consensus — ${ticker}\n\n*Full panel mode (${CONSENSUS_PANEL.length} parallel experts)*\n\n${combined}`,
      is_command: true,
      query: text,
      sections: {
        panels,
        response: combined.split("## CIO synthesis\n\n")[1] || combined,
      },
    };
  }

  const body = await runFastConsensus(apiKey, ticker, quoteBlock);
  return {
    type: "consensus",
    content: `# Consensus — ${ticker}\n\n*Fast panel · ${expertBlurbs().split("\n").length} experts · one pass*\n\n${body}`,
    is_command: true,
    query: text,
    sections: { response: body },
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
