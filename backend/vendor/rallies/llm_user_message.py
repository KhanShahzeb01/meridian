"""Plain-language LLM failure messages for CLI users (no debug required)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .llm import LLMError


def format_llm_error_for_user(
    error: LLMError,
    *,
    model: str | None = None,
    include_technical: bool = False,
) -> str:
    """
    Return a short, actionable message for terminal display.
    Technical detail is optional (for support / logs).
    """
    status = getattr(error, "http_status", None)
    code = getattr(error, "reason_code", None) or "api_error"
    model_hint = f" (model: {model})" if model else ""

    title, body, tips = _message_parts(status, code, model_hint)

    lines = [title, "", body]
    if tips:
        lines.extend(["", "What you can do:", *tips])
    if include_technical:
        detail = str(error).strip()
        if detail and detail not in body:
            lines.extend(["", f"Technical detail: {detail}"])
    return "\n".join(lines)


def format_llm_error_rich(
    error: LLMError,
    *,
    model: str | None = None,
    include_technical: bool = False,
) -> str:
    """Rich-markup version for console.print."""
    text = format_llm_error_for_user(
        error, model=model, include_technical=include_technical
    )
    parts = text.split("\n", 1)
    head = parts[0]
    rest = parts[1] if len(parts) > 1 else ""
    if not rest.strip():
        return f"[bold red]{head}[/bold red]"
    return f"[bold red]{head}[/bold red]{rest}"


def _message_parts(
    status: int | None,
    reason_code: str,
    model_hint: str,
) -> tuple[str, str, list[str]]:
    tips_common = [
        "Check config/rallies-provider.yaml (models.cheap / models.heavy / model).",
        "Set OPENROUTER_API_KEY or run /key if you use OpenRouter.",
        "Set GEMINI_API_KEY for automatic fallback when free models fail.",
    ]

    if status == 401 or reason_code == "auth_error":
        return (
            "Authentication failed",
            f"The API rejected your key{model_hint}. It may be missing, expired, or invalid.",
            [
                "Set OPENROUTER_API_KEY in your environment or run /key in rallies.",
                "Confirm the key works at https://openrouter.ai/settings/keys",
            ],
        )

    if status == 402 or reason_code == "payment_required":
        return (
            "Model requires payment or credits",
            f"This model is not available on your current plan{model_hint}. "
            "Free-tier models can still hit credit limits.",
            [
                "Switch to a free model in rallies-provider.yaml (e.g. openrouter/free or another :free slug).",
                "Add credits on OpenRouter, or set GEMINI_API_KEY for fallback.",
            ],
        )

    if status == 403 or reason_code == "forbidden":
        return (
            "Access denied",
            f"You do not have permission to use this model or endpoint{model_hint}.",
            [
                "Pick a different model in rallies-provider.yaml.",
                "Verify your OpenRouter account can access the requested model.",
            ],
        )

    if status == 404 or reason_code == "not_found":
        return (
            "Model not found",
            f"The configured model name may be wrong or retired{model_hint}.",
            [
                "Open config/rallies-provider.yaml and fix the model id.",
                "See https://openrouter.ai/models for current model slugs.",
            ],
        )

    if status in (502, 503, 504) or reason_code == "provider_unavailable":
        return (
            "AI provider temporarily unavailable",
            f"The service returned HTTP {status or '503'}{model_hint}. "
            "This is usually overload or maintenance — not a bug in your question.",
            [
                "Wait a minute and try again.",
                "Try another free model in rallies-provider.yaml or set GEMINI_API_KEY.",
            ],
        )

    if status == 429 or reason_code == "rate_limit":
        return (
            "Rate limit reached",
            f"Too many requests to the provider{model_hint}.",
            [
                "Wait a few minutes and retry.",
                "Use a different model or enable GEMINI_API_KEY fallback.",
            ],
        )

    if reason_code == "context_token_limit":
        return (
            "Prompt too long for this model",
            "Your question plus context exceeded the model's token limit.",
            [
                "Ask a shorter question or use /compact on the conversation.",
                "Use a model with a larger context window in rallies-provider.yaml.",
            ],
        )

    if status == 400 or reason_code == "bad_request":
        return (
            "Invalid request",
            f"The provider rejected the request{model_hint}. "
            "Parameters or message format may be incompatible with this model.",
            [
                "Try a different model in rallies-provider.yaml.",
                "If this persists, shorten the prompt or disable JSON-only planner output.",
            ],
        )

    if reason_code == "empty_response":
        return (
            "Model returned no answer",
            f"The provider responded but sent empty text{model_hint}.",
            [
                "Retry the same question.",
                "Switch models in rallies-provider.yaml — some free models do this often.",
            ],
        )

    if reason_code == "timeout":
        return (
            "Request timed out",
            f"The provider did not respond in time{model_hint}.",
            [
                "Try again with a simpler question.",
                "Increase timeout_seconds in rallies-provider.yaml if needed.",
            ],
        )

    if reason_code == "network":
        return (
            "Network error",
            "Could not reach the AI provider. Check your internet connection.",
            [
                "Verify you can open https://openrouter.ai in a browser.",
                "Retry in a moment if you are on VPN or corporate firewall.",
            ],
        )

    if reason_code == "max_retries":
        return (
            "Request failed after retries",
            f"Rallies retried several times without success{model_hint}.",
            tips_common,
        )

    if reason_code == "plan_parse_error":
        return (
            "Planner could not parse the model output",
            "The planning step did not return valid JSON.",
            [
                "Retry your question.",
                "Try a model that follows instructions more reliably.",
            ],
        )

    # Generic API error (includes unknown 4xx/5xx)
    if status:
        return (
            f"API error (HTTP {status})",
            f"The provider returned an error{model_hint}. Try again later or change model.",
            tips_common,
        )

    return (
        "AI request failed",
        f"Something went wrong while calling the model{model_hint}.",
        tips_common,
    )
