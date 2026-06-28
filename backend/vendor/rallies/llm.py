import json
import os
import random
import re
import requests
import threading
import time
import hashlib
from functools import wraps
from .helpers import load_provider_config, get_provider_api_key
from .storage import Storage


def _classify_http_error_response(response):
    """Map HTTP errors to stable reason codes for history logging."""
    status = getattr(response, "status_code", None) or 0
    text = ""
    try:
        body = response.json()
        err = body.get("error", body)
        if isinstance(err, dict):
            parts = [
                str(err.get("message") or err.get("msg") or ""),
                str(err.get("code") or ""),
                str(err.get("type") or ""),
            ]
            text = " ".join(p for p in parts if p)
        else:
            text = str(err)
    except (ValueError, TypeError, json.JSONDecodeError):
        text = (getattr(response, "text", None) or "")[:2000]

    low = text.lower()
    if status == 401:
        return "auth_error", text.strip()[:2000]
    if status == 402:
        return "payment_required", text.strip()[:2000]
    if status == 403:
        return "forbidden", text.strip()[:2000]
    if status == 404:
        return "not_found", text.strip()[:2000]
    if status in (502, 503, 504):
        return "provider_unavailable", text.strip()[:2000]
    if status == 429:
        return "rate_limit", text.strip()[:2000]
    if status == 400 and any(
        k in low
        for k in (
            "context",
            "token",
            "length",
            "maximum",
            "too long",
            "max_tokens",
            "reduced your max_tokens",
            "requested",
            "exceed",
        )
    ):
        return "context_token_limit", text.strip()[:2000]
    if status == 400:
        return "bad_request", text.strip()[:2000]
    return "api_error", text.strip()[:2000]


class LLMError(Exception):
    """Chat/completions failure with a reason code for JSONL history."""

    def __init__(self, message, reason_code="api_error", http_status=None):
        super().__init__(message)
        self.reason_code = reason_code
        self.http_status = http_status

    def user_message(self, model: str | None = None, *, technical: bool = False) -> str:
        from .llm_user_message import format_llm_error_for_user

        return format_llm_error_for_user(self, model=model, include_technical=technical)


def _coerce_message_content_for_api(content):
    """Never send null/ambiguous content to the API (some providers misbehave)."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                txt = item.get("text") or item.get("content")
                if isinstance(txt, str) and txt.strip():
                    parts.append(txt.strip())
        return "\n".join(parts) if parts else ""
    return str(content)


def clean_model_text(text: str) -> str:
    """Clean common provider encoding artifacts before rendering or storing output."""
    if not isinstance(text, str) or not text:
        return text or ""

    # Attempt to repair common mojibake (UTF-8 bytes decoded as Latin-1 / CP1252).
    repaired = text
    try:
        if any(token in repaired for token in ("Ã", "â", "Â")):
            candidate = repaired.encode("latin-1", errors="ignore").decode("utf-8", errors="ignore")
            if candidate and len(candidate.strip()) >= max(1, len(repaired.strip()) // 2):
                repaired = candidate
    except Exception:
        repaired = text

    replacements = {
        "â": "-",
        "â": "-",
        "â": "'",
        "â": "'",
        "â": '"',
        "â": '"',
        "â¢": "-",
        "â¯": " ",
        "Ã—": "x",
        "Ã·": "/",
        "â‰ˆ": "~",
        "â†’": "->",
        "â€™": "'",
        "â€œ": '"',
        "â€": '"',
        "Â ": " ",
        "Â": "",
    }
    cleaned = repaired
    for bad, good in replacements.items():
        cleaned = cleaned.replace(bad, good)
    # Remove accidental control characters that break terminal rendering.
    cleaned = "".join(ch for ch in cleaned if ch == "\n" or ch == "\t" or ord(ch) >= 32)
    return cleaned


def extract_chat_completion_text(body: dict) -> str:
    """
    Assistant text from OpenAI-compatible /chat/completions JSON.

    OpenRouter and reasoning models often put the visible reply in `reasoning`
    while `content` is null; multimodal replies use a list of parts.
    """
    if not isinstance(body, dict):
        return ""
    choice0 = (body.get("choices") or [{}])[0] or {}
    msg = choice0.get("message")
    if not isinstance(msg, dict):
        msg = {}

    def part_text(item):
        if not isinstance(item, dict):
            return None
        txt = item.get("text")
        if isinstance(txt, str) and txt.strip():
            return txt.strip()
        t = str(item.get("type") or "").lower()
        if t in ("text", "output_text"):
            inner = item.get("content")
            if isinstance(inner, str) and inner.strip():
                return inner.strip()
        for k in ("content", "value", "reasoning"):
            v = item.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return None

    content = msg.get("content")

    if isinstance(content, str) and content.strip():
        return content.strip()

    if isinstance(content, list):
        pieces = []
        for item in content:
            p = part_text(item)
            if p:
                pieces.append(p)
        if pieces:
            return "\n".join(pieces).strip()

    for key in ("reasoning", "reasoning_content", "thought", "thinking"):
        val = msg.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()

    legacy = choice0.get("text")
    if isinstance(legacy, str) and legacy.strip():
        return legacy.strip()

    if isinstance(content, str):
        return content.strip()
    return ""


def _parse_planner_json(raw: str) -> list:
    """
    Planner must return a JSON array of {title, description}. Models often wrap it
    in markdown fences or prose; bare json.loads then fails and must not become a silent [].
    """
    text = (raw or "").strip()
    if not text:
        raise json.JSONDecodeError("Empty planner response", text, 0)

    candidates = []
    seen = set()

    def add_candidate(s):
        s = (s or "").strip()
        if s and s not in seen:
            seen.add(s)
            candidates.append(s)

    add_candidate(text)
    for m in re.finditer(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE):
        add_candidate(m.group(1))
    start, end = text.find("["), text.rfind("]")
    if start != -1 and end != -1 and end > start:
        add_candidate(text[start : end + 1])

    last_err = None
    for cand in candidates:
        try:
            data = json.loads(cand)
        except json.JSONDecodeError as e:
            last_err = e
            continue
        if isinstance(data, dict) and "title" in data and "description" in data:
            return [data]
        if isinstance(data, list):
            normalized = []
            for item in data:
                if isinstance(item, dict) and "title" in item and "description" in item:
                    normalized.append(
                        {
                            "title": str(item["title"]),
                            "description": str(item["description"]),
                        }
                    )
            if normalized:
                return normalized
            last_err = json.JSONDecodeError(
                "Planner returned empty steps", cand, 0
            )
            continue
        last_err = json.JSONDecodeError(
            "Planner JSON must be a list or one step object", cand, 0
        )
        continue
    
    # After the for loop: validate non-empty result
    if last_err and str(last_err).startswith("Planner returned empty"):
        raise last_err

    raise last_err or json.JSONDecodeError("Could not parse planner JSON", text[:500], 0)


def retry_json_decode(max_retries=3):
    def decorator(func):
        @wraps(func)
        def wrapper(self, messages, model="gpt-4.1", requires_json=False, **kwargs):
            if not requires_json:
                return func(self, messages, model, requires_json, **kwargs)

            last_err = None
            for attempt in range(max_retries):
                try:
                    return func(self, messages, model, requires_json, **kwargs)
                except json.JSONDecodeError as e:
                    last_err = e
                    if attempt == max_retries - 1:
                        raise LLMError(
                            f"Planner output was not valid JSON after {max_retries} attempts: {e}",
                            reason_code="plan_parse_error",
                        ) from e
                    continue

        return wrapper

    return decorator

class LLM:
    def __init__(self, provider_config=None, api_key=None, session=None, storage=None):
        self.provider_config = provider_config or load_provider_config()
        self.api_key = api_key or get_provider_api_key(self.provider_config)
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
        self._session = session
        self._thread_local = threading.local()
        self.last_usage = 0
        self.last_limit = 0
        self.last_model: str | None = None
        self.storage = storage or Storage()
        self._fallback_models = self.provider_config.get("free_fallback_models", [
            "google/gemini-2.5-flash-exp:free",
            "meta-llama/llama-4-maverick:free",
            "qwen/qwen-2.5-72b-instruct:free",
            "mistralai/mistral-small-3.1-24b-instruct:free",
        ])
        self._exhausted_models = set()

    def _provider_fingerprint(self):
        fields = {
            "base_url": self.provider_config.get("base_url"),
            "models": self.provider_config.get("models"),
            "model": self.provider_config.get("model"),
            "routing": self.provider_config.get("routing"),
            "temperature": self.provider_config.get("temperature"),
            "token_budgets": self.provider_config.get("token_budgets"),
            "max_tokens": self.provider_config.get("max_tokens"),
            "web_search": self.provider_config.get("web_search"),
        }
        return hashlib.sha256(
            json.dumps(fields, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]

    def _cache_key(self, messages, task_type=None, force_model=None):
        normalized_messages = self._normalize_messages(messages)
        selected_model = force_model or self._choose_model(
            normalized_messages, stream=False
        )
        raw = json.dumps(
            {
                "messages": normalized_messages,
                "task_type": task_type,
                "selected_model": selected_model,
                "provider_fingerprint": self._provider_fingerprint(),
                "cache_schema_version": 2,
            },
            sort_keys=True,
            default=str,
        )
        return "llm:" + hashlib.sha256(raw.encode()).hexdigest()[:32]

    @property
    def session(self):
        if self._session is not None:
            return self._session
        if not hasattr(self._thread_local, "session"):
            self._thread_local.session = requests.Session()
        return self._thread_local.session

    def _normalize_messages(self, messages):
        normalized = []
        for message in messages:
            role = message.get("role", "user")
            content = _coerce_message_content_for_api(message.get("content"))
            if role == "developer":
                role = "system"
            if role not in ["system", "user", "assistant"]:
                role = "user"
            normalized.append({"role": role, "content": content})
        return normalized

    def _is_simple_task(self, text):
        routing = self.provider_config.get("routing", {})
        simple_max_chars = int(routing.get("simple_max_chars", 200))
        simple_max_words = int(routing.get("simple_max_words", 35))
        complex_keywords = routing.get(
            "complex_keywords",
            [
                "compare",
                "analysis",
                "analyze",
                "sentiment",
                "options",
                "earnings",
                "macro",
                "federal reserve",
                "forecast",
                "technical",
                "portfolio",
                "risk",
            ],
        )

        lower_text = text.lower()
        has_complex_keyword = any(keyword in lower_text for keyword in complex_keywords)
        word_count = len(text.split())
        char_count = len(text)
        return (
            not has_complex_keyword
            and word_count <= simple_max_words
            and char_count <= simple_max_chars
        )

    def _choose_model(self, messages, stream=False):
        models = self.provider_config.get("models", {})
        cheap_model = models.get("cheap", self.provider_config.get("model"))
        heavy_model = models.get("heavy", self.provider_config.get("model"))
        routing = self.provider_config.get("routing", {})
        force_heavy_for_stream = bool(routing.get("force_heavy_for_stream", True))

        user_text = " ".join(
            _coerce_message_content_for_api(message.get("content"))
            for message in messages
            if message.get("role") == "user"
        )

        if stream and force_heavy_for_stream:
            return heavy_model
        return cheap_model if self._is_simple_task(user_text) else heavy_model

    def _web_plugin_for_model(self, selected_model):
        web_search = self.provider_config.get("web_search", {})
        if not web_search.get("enabled", False):
            return None

        apply_to = str(web_search.get("apply_to", "heavy")).lower()
        models = self.provider_config.get("models", {})
        heavy_model = models.get("heavy", self.provider_config.get("model"))
        cheap_model = models.get("cheap", self.provider_config.get("model"))

        should_apply = (
            apply_to == "all"
            or (apply_to == "heavy" and selected_model == heavy_model)
            or (apply_to == "cheap" and selected_model == cheap_model)
        )
        if not should_apply:
            return None

        plugin = {"id": "web"}
        if "max_results" in web_search:
            plugin["max_results"] = int(web_search["max_results"])
        if web_search.get("search_prompt"):
            plugin["search_prompt"] = web_search["search_prompt"]
        return [plugin]

    def _headers(self):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        app_name = self.provider_config.get("app_name")
        app_url = self.provider_config.get("app_url")
        if app_name:
            headers["HTTP-Referer"] = app_url or "https://localhost"
            headers["X-Title"] = app_name
        return headers

    def _record_usage(self, body):
        usage = body.get("usage", {}) if isinstance(body, dict) else {}
        self.last_usage = usage.get("total_tokens", 0) or 0
        self.last_limit = 0

    def _max_tokens_for_task(self, task_type=None):
        from .token_budgets import TokenBudgetPolicy

        policy = TokenBudgetPolicy.from_provider_config(self.provider_config)
        if task_type:
            return policy.output_budget_for(task_type)
        return int(self.provider_config.get("max_tokens", 1600))

    def _build_payload(self, messages, stream=False, task_type=None, force_model=None):
        normalized = self._normalize_messages(messages)
        selected = force_model or self._choose_model(normalized, stream=stream)
        payload = {
            "model": selected,
            "messages": normalized,
            "max_tokens": self._max_tokens_for_task(task_type),
        }
        if stream:
            payload["stream"] = True
        if "temperature" in self.provider_config:
            payload["temperature"] = self.provider_config["temperature"]
        plugins = self._web_plugin_for_model(selected)
        if plugins:
            payload["plugins"] = plugins
        return payload

    def _post_with_retry(self, payload):
        max_retries = int(self.provider_config.get("retry_max_retries", 3))
        base_delay = float(self.provider_config.get("retry_base_delay", 1.0))
        url = f"{self.provider_config['base_url'].rstrip('/')}/chat/completions"

        for attempt in range(max_retries):
            try:
                response = self.session.post(
                    url,
                    headers=self._headers(),
                    json=payload,
                    timeout=int(self.provider_config.get("timeout_seconds", 180)),
                    stream=payload.get("stream", False),
                )
            except requests.exceptions.Timeout as e:
                if attempt < max_retries - 1:
                    delay = min(base_delay * (2 ** attempt), 30.0) + random.uniform(0, 0.5)
                    time.sleep(delay)
                    continue
                raise LLMError(str(e), reason_code="timeout") from e
            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    delay = min(base_delay * (2 ** attempt), 30.0) + random.uniform(0, 0.5)
                    time.sleep(delay)
                    continue
                raise LLMError(str(e), reason_code="network") from e

            if response.ok:
                return response

            reason_code, detail = _classify_http_error_response(response)
            retryable = reason_code in (
                "rate_limit",
                "timeout",
                "network",
                "provider_unavailable",
            )
            if retryable and attempt < max_retries - 1:
                delay = min(base_delay * (2 ** attempt), 30.0) + random.uniform(0, 0.5)
                time.sleep(delay)
                continue

            raise LLMError(
                detail or response.reason or str(response.status_code),
                reason_code=reason_code,
                http_status=response.status_code,
            )

        raise LLMError("Max retries exceeded", reason_code="max_retries")

    def _try_models(self, messages, stream=False, task_type=None, force_model=None):
        models = [force_model] if force_model else []
        default = self._choose_model(
            self._normalize_messages(messages), stream=stream
        )
        models.append(default)
        for fb in self._fallback_models:
            if fb != default and fb not in models:
                models.append(fb)

        # Skip models already known to be exhausted
        to_try = [m for m in models if m not in self._exhausted_models]
        if not to_try:
            to_try = models[-1:]  # at least try the last one

        last_error = LLMError("No models attempted", reason_code="no_models")

        for idx, model in enumerate(to_try):
            payload = self._build_payload(
                messages, stream=stream, task_type=task_type, force_model=model
            )
            try:
                result = self._post_with_retry(payload)
                return result, model
            except LLMError as e:
                last_error = e
                if e.http_status == 402:
                    self._exhausted_models.add(model)
                    if idx < len(to_try) - 1:
                        next_name = to_try[idx + 1].split("/")[-1][:30]
                        import logging
                        logging.getLogger("rallies").warning(
                            "Model %s out of credits, trying %s",
                            model, next_name,
                        )
                        continue
                    if self.gemini_api_key:
                        import logging
                        logging.getLogger("rallies").warning(
                            "All OpenRouter models exhausted, falling back to Gemini API"
                        )
                        return self._try_gemini_fallback(messages, task_type), "google/gemini-2.5-flash"
                    raise
                if (
                    e.reason_code in ("rate_limit", "timeout", "network", "provider_unavailable")
                    or e.http_status in (429, 502, 503, 504)
                ) and idx < len(to_try) - 1:
                    continue
                raise

        if self.gemini_api_key:
            return self._try_gemini_fallback(messages, task_type), "google/gemini-2.5-flash"
        raise last_error

    def _try_gemini_fallback(self, messages, task_type=None):
        """Fallback to Google Gemini API when all OpenRouter free models are exhausted."""
        normalized = self._normalize_messages(messages)
        prompt_text = ""
        for msg in normalized:
            if msg.get("content"):
                content = msg["content"]
                if isinstance(content, str):
                    if msg.get("role") in ("user", "system", "developer"):
                        prompt_text += content + "\n"
                elif isinstance(content, list):
                    for part in content:
                        if isinstance(part, dict) and part.get("text"):
                            prompt_text += part["text"] + "\n"

        prompt_text = prompt_text.strip()
        if not prompt_text:
            raise LLMError("No prompt text for Gemini fallback", reason_code="no_content")

        max_tokens = self._max_tokens_for_task(task_type)
        import logging
        logging.getLogger("rallies").warning("All OpenRouter models exhausted, falling back to Gemini API")

        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        payload = {
            "contents": [{"parts": [{"text": prompt_text}]}],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": float(self.provider_config.get("temperature", 0.2)),
            },
        }
        try:
            resp = self.session.post(
                url,
                params={"key": self.gemini_api_key},
                json=payload,
                timeout=int(self.provider_config.get("timeout_seconds", 180)),
            )
            if not resp.ok:
                detail = resp.text[:200]
                raise LLMError(f"Gemini API error: {detail}", reason_code="api_error", http_status=resp.status_code)
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise LLMError("Gemini: no candidates in response", reason_code="empty_response")
            text = ""
            for part in (candidates[0].get("content", {}).get("parts", [])):
                if isinstance(part, dict) and part.get("text"):
                    text += part["text"]
            if not text:
                raise LLMError("Gemini: empty response text", reason_code="empty_response")
            clean_text = clean_model_text(text)
            class _GeminiResponse:
                ok = True
                status_code = 200
                def __init__(self, text):
                    self._text = text
                def json(self):
                    return {
                        "choices": [{"message": {"content": self._text}}],
                        "usage": {"total_tokens": len(self._text) // 4},
                    }
                def iter_lines(self, **kw):
                    yield "data: " + json.dumps({
                        "choices": [{"delta": {"content": self._text}}]
                    })
                    yield "data: [DONE]"
            return _GeminiResponse(clean_text)
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"Gemini fallback failed: {e}", reason_code="network")

    @retry_json_decode()
    def prompt(
        self,
        messages,
        model="gpt-4.1",
        requires_json=False,
        force_model=None,
        task_type=None,
        no_cache=False,
    ):
        cache_ttl = int(self.provider_config.get("cache_ttl_seconds", 300))
        use_cache = cache_ttl > 0 and not no_cache
        cache_key = (
            self._cache_key(messages, task_type, force_model=force_model)
            if use_cache
            else None
        )

        if use_cache:
            cached = self.storage.cache_get(cache_key)
            if cached is not None:
                return cached

        payload = self._build_payload(messages, task_type=task_type, force_model=force_model)
        response, used_model = self._try_models(
            messages, task_type=task_type, force_model=force_model
        )
        self.last_model = used_model
        body = response.json()
        self._record_usage(body)
        choice0 = (body.get("choices") or [{}])[0] or {}
        msg = choice0.get("message") if isinstance(choice0.get("message"), dict) else {}
        response_text = extract_chat_completion_text(body)

        if not str(response_text).strip():
            refusal = msg.get("refusal")
            fr = choice0.get("finish_reason")
            detail = (
                f"No assistant text in response (finish_reason={fr!r}, "
                f"message_keys={sorted(msg.keys())!s}, refusal={refusal!r})."
                if refusal or msg
                else f"No assistant text in response (finish_reason={fr!r})."
            )
            raise LLMError(detail, reason_code="empty_response")

        if requires_json:
            response_text = _parse_planner_json(response_text)
        if isinstance(response_text, str):
            response_text = clean_model_text(response_text)

        if use_cache:
            self.storage.cache_set(cache_key, response_text, ttl_seconds=cache_ttl)
        return response_text

    def prompt_stream(self, messages, model="gpt-4.1", force_model=None, task_type=None):
        response, used_model = self._try_models(
            messages, stream=True, task_type=task_type, force_model=force_model
        )

        for line in response.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data: "):
                continue
            data = line[6:].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                continue
            delta = chunk.get("choices", [{}])[0].get("delta")
            if not isinstance(delta, dict):
                continue
            piece = delta.get("content")
            if isinstance(piece, str) and piece:
                yield clean_model_text(piece)
