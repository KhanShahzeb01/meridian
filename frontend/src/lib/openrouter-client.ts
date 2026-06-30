import { getActiveOpenRouterModel } from "./storage";

export async function openRouterChat(
  apiKey: string,
  messages: { role: string; content: string }[],
  options?: { maxTokens?: number; temperature?: number }
): Promise<string> {
  const model = getActiveOpenRouterModel();
  const maxTokens = options?.maxTokens ?? 4096;
  const temperature = options?.temperature ?? 0.7;
  let lastError = "OpenRouter request failed";

  for (let attempt = 0; attempt < 2; attempt++) {
    if (attempt > 0) {
      await new Promise((r) => setTimeout(r, 1200));
    }

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
          max_tokens: maxTokens,
          temperature,
        }),
      });
    } catch {
      throw new Error("Cannot reach OpenRouter. Check your connection and API key.");
    }

    if (!res.ok) {
      try {
        const err = await res.json();
        lastError = err.error?.message || `HTTP ${res.status}`;
      } catch {
        lastError = `HTTP ${res.status}`;
      }
      const retryable =
        attempt === 0 &&
        (res.status === 429 ||
          res.status === 502 ||
          res.status === 503 ||
          /rate|overload|provider/i.test(lastError));
      if (retryable) continue;
      throw new Error(
        `**${model}:** ${lastError}\n\nOnly your selected model is used — change it in **Settings** (⚙) if needed.`
      );
    }

    const data = await res.json();
    const content = data.choices?.[0]?.message?.content?.trim();
    if (content) return content;
    lastError = "Empty response from model";
  }

  throw new Error(
    `**${model}:** ${lastError}\n\nTry again in a moment, or pick another model in **Settings** (⚙).`
  );
}
