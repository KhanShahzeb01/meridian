/** True when built with a remote Meridian API (local dev proxy or self-hosted). */
export function hasBackendApi(): boolean {
  return Boolean(process.env.NEXT_PUBLIC_API_URL?.trim());
}

export const OPENROUTER_MODEL =
  process.env.NEXT_PUBLIC_OPENROUTER_MODEL || "openai/gpt-oss-120b:free";
