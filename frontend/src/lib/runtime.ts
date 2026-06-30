/** True when built with a remote Meridian API (local dev proxy or self-hosted). */
export function hasBackendApi(): boolean {
  return Boolean(process.env.NEXT_PUBLIC_API_URL?.trim());
}

export {
  DEFAULT_OPENROUTER_MODEL,
  SUGGESTED_OPENROUTER_MODELS,
} from "./openrouter-models";
