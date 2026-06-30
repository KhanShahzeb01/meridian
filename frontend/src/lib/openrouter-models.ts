/** Suggested OpenRouter models (Settings datalist + fallbacks). */
export const DEFAULT_OPENROUTER_MODEL =
  process.env.NEXT_PUBLIC_OPENROUTER_MODEL || "openai/gpt-oss-120b:free";

/** Shown as suggestions; user can type any OpenRouter model id */
export const SUGGESTED_OPENROUTER_MODELS: { id: string; label: string }[] = [
  { id: "openai/gpt-oss-120b:free", label: "GPT-OSS 120B (free)" },
  { id: "openai/gpt-oss-20b:free", label: "GPT-OSS 20B (free)" },
  { id: "google/gemini-2.0-flash-exp:free", label: "Gemini 2.0 Flash (free)" },
  { id: "meta-llama/llama-3.3-70b-instruct:free", label: "Llama 3.3 70B (free)" },
  { id: "qwen/qwen-2.5-72b-instruct:free", label: "Qwen 2.5 72B (free)" },
  { id: "deepseek/deepseek-chat", label: "DeepSeek V3" },
  { id: "openai/gpt-4o-mini", label: "GPT-4o Mini" },
  { id: "openai/gpt-4o", label: "GPT-4o" },
  { id: "google/gemini-2.5-flash", label: "Gemini 2.5 Flash" },
  { id: "anthropic/claude-sonnet-4", label: "Claude Sonnet 4" },
];

/** Fallback chain when the primary model errors (excludes user pick) */
export const OPENROUTER_FALLBACK_MODELS = [
  "google/gemini-2.0-flash-exp:free",
  "meta-llama/llama-3.3-70b-instruct:free",
  "qwen/qwen-2.5-72b-instruct:free",
  "openai/gpt-oss-120b:free",
].filter((m, i, a) => a.indexOf(m) === i);
