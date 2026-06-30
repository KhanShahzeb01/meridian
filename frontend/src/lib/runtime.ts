/** True when built with a remote Meridian API (local dev proxy or self-hosted). */
export function hasBackendApi(): boolean {
  return Boolean(process.env.NEXT_PUBLIC_API_URL?.trim());
}

const DEFAULT_MODEL =
  process.env.NEXT_PUBLIC_OPENROUTER_MODEL || "openai/gpt-oss-120b:free";

/** Try in order when a provider errors or rate-limits */
export const OPENROUTER_MODELS = [
  DEFAULT_MODEL,
  "google/gemini-2.0-flash-exp:free",
  "meta-llama/llama-3.3-70b-instruct:free",
  "qwen/qwen-2.5-72b-instruct:free",
].filter((m, i, a) => a.indexOf(m) === i);

export const OPENROUTER_MODEL = OPENROUTER_MODELS[0];
