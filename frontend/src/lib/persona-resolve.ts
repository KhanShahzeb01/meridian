import personaPrompts from "@/data/persona-prompts.json";
import personasGrouped from "@/data/personas.json";

const PROMPTS = personaPrompts as Record<string, string>;

/** Common misspellings and nicknames → canonical persona id */
const ALIASES: Record<string, string> = {
  buffet: "buffett",
  warren: "buffett",
  buffett: "buffett",
  charlie: "munger",
  munger: "munger",
  ben: "graham",
  graham: "graham",
  lynch: "lynch",
  peter: "lynch",
  cathie: "wood",
  wood: "wood",
  dalio: "dalio",
  ray: "dalio",
  soros: "soros",
  druck: "druckenmiller",
  druckenmiller: "druckenmiller",
  burry: "burry",
  ackman: "ackman",
  icahn: "icahn",
  klarman: "klarman",
  marks: "marks",
  greenblatt: "greenblatt",
  pabrai: "pabrai",
};

function allPersonas(): { id: string; name: string; short: string }[] {
  return Object.values(personasGrouped).flat() as {
    id: string;
    name: string;
    short: string;
  }[];
}

/** Resolve user input to a persona id with prompts, or null */
export function resolvePersonaId(raw: string | null | undefined): string | null {
  if (!raw?.trim()) return null;
  const key = raw.toLowerCase().trim().replace(/^@/, "");

  if (PROMPTS[key]) return key;
  if (ALIASES[key] && PROMPTS[ALIASES[key]]) return ALIASES[key];

  for (const p of allPersonas()) {
    const id = p.id.toLowerCase();
    const short = p.short.toLowerCase();
    const name = p.name.toLowerCase();
    const first = name.split(/\s+/)[0];
    if (key === id || key === short || key === first) {
      if (PROMPTS[p.id]) return p.id;
    }
    // Fuzzy name match only for longer tokens (avoid "is" → Mohnish)
    if (key.length >= 4 && name.includes(key)) {
      if (PROMPTS[p.id]) return p.id;
    }
  }
  return null;
}

export function hasPersonaPrompt(id: string): boolean {
  return Boolean(PROMPTS[id]);
}

export function getPersonaPrompt(id: string): string | null {
  return PROMPTS[id] ?? null;
}

export function getPersonaName(id: string): string {
  for (const list of Object.values(personasGrouped)) {
    const match = (list as { id: string; name: string }[]).find((p) => p.id === id);
    if (match) return match.name;
  }
  return id;
}

export interface ParsedAsk {
  personaId: string;
  question: string;
}

/**
 * Parse `/ask …` using optional selected persona as fallback.
 * `/ask buffet is NVDA a buy` → buffett + question
 * `/ask is NVDA a buy` + selected buffett → buffett + question
 */
export function parseAskCommand(
  text: string,
  selectedPersonaId: string | null
): ParsedAsk | { error: string } {
  const rest = text.trim().slice(5).trim(); // after "/ask"
  if (!rest) {
    return {
      error:
        "Usage: select a persona and ask a question, or `/ask buffett Is NVDA a buy?`",
    };
  }

  const parts = rest.split(/\s+/);
  const firstResolved = resolvePersonaId(parts[0]);

  if (firstResolved) {
    const question = parts.slice(1).join(" ").trim();
    if (!question) {
      return { error: `Add a question after \`/ask ${parts[0]}\`.` };
    }
    return { personaId: firstResolved, question };
  }

  const fromSelection = resolvePersonaId(selectedPersonaId);
  if (fromSelection) {
    return { personaId: fromSelection, question: rest };
  }

  const hint = parts[0];
  return {
    error: `Unknown persona \`${hint}\`. Select one in the sidebar or run \`/personas\` for IDs (e.g. \`buffett\`, not \`buffet\`).`,
  };
}
