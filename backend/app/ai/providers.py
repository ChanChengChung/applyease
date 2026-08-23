"""Provider abstraction with a quota-safe Ollama -> Gemini fallback."""

from __future__ import annotations

import json
import logging
import threading
import time
from collections import deque
from typing import Any

import httpx

from app.config import settings
from app.ai.observability import current_trace, error_category, record_event

logger = logging.getLogger(__name__)


class ProviderError(RuntimeError):
    """A provider failed without exposing credentials or prompt contents."""


class RateLimitExceeded(ProviderError):
    pass


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_seconds: float = 60.0) -> None:
        self.limit = max(1, limit)

        self.window_seconds = window_seconds

        self._calls: deque[float] = deque()

        self._lock = threading.Lock()

    def acquire(self) -> None:
        now = time.monotonic()

        with self._lock:

            while self._calls and now - self._calls[0] >= self.window_seconds:
                self._calls.popleft()

            if len(self._calls) >= self.limit:

                raise RateLimitExceeded("Gemini local rate limit reached; retry later")
            self._calls.append(now)


def _bounded_prompt(prompt: str) -> str:

    if not prompt or not prompt.strip():

        raise ProviderError("Prompt must not be empty")

    if len(prompt) > settings.llm_max_prompt_characters:

        raise ProviderError("Prompt exceeds the configured safety limit")

    return prompt


def _parse_json(text: str) -> dict[str, Any]:

    try:
        value = json.loads(text)

    except json.JSONDecodeError as exc:

        raise ProviderError("Provider returned invalid JSON") from exc

    if not isinstance(value, dict):

        raise ProviderError("Provider JSON response must be an object")

    return value


class OllamaProvider:
    name = "ollama"

    def generate_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        prompt = _bounded_prompt(prompt)

        payload = {
            "model": settings.ollama_model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            # CV extraction is a constrained JSON task; disabling Qwen3's visible
            # reasoning keeps latency and token usage predictable on 16GB Macs.
            "think": False,
            "format": schema,
            "options": {"temperature": 0.1, "num_ctx": 8192},
        }

        try:
            response = httpx.post(
                f"{settings.ollama_base_url.rstrip('/')}/api/chat",
                json=payload,
                timeout=settings.llm_timeout_seconds,
            )

            response.raise_for_status()

            content = response.json().get("message", {}).get("content", "")

            return _parse_json(content)

        except (httpx.HTTPError, ValueError, TypeError) as exc:

            raise ProviderError("Ollama request failed") from exc


class GeminiProvider:
    name = "gemini"

    def __init__(self, limiter: SlidingWindowLimiter | None = None) -> None:
        self.limiter = limiter or SlidingWindowLimiter(settings.gemini_max_requests_per_minute)

    def generate_json(self, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        prompt = _bounded_prompt(prompt)

        if not settings.gemini_api_key:

            raise ProviderError("Gemini API key is not configured")
        self.limiter.acquire()

        try:
            from google import genai

            from google.genai import types

            client = genai.Client(api_key=settings.gemini_api_key)

            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                    response_schema=schema,
                ),
            )

            return _parse_json(response.text or "")

        except RateLimitExceeded:

            raise

        except Exception as exc:  # SDK exceptions vary by version/provider status.
            logger.warning("Gemini request failed (%s)", type(exc).__name__)

            raise ProviderError("Gemini request failed") from exc

    def extract_image_text(self, data: bytes, mime_type: str) -> str:

        if not settings.gemini_api_key:

            raise ProviderError("Gemini API key is not configured")
        self.limiter.acquire()

        try:
            from google import genai

            from google.genai import types

            client = genai.Client(api_key=settings.gemini_api_key)

            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=[
                    types.Part.from_bytes(data=data, mime_type=mime_type),
                    "Transcribe all visible internship application form labels, questions, required markers, options, and character or word limits. Preserve reading order. Do not answer any fields and do not infer hidden text.",
                ],
                config=types.GenerateContentConfig(temperature=0),
            )

            text = (response.text or "").strip()

            if not text:

                raise ProviderError("No readable form text was found in the screenshot")

            return text

        except RateLimitExceeded:

            raise

        except ProviderError:

            raise

        except Exception as exc:
            logger.warning("Gemini screenshot OCR failed (%s)", type(exc).__name__)

            raise ProviderError("Screenshot OCR failed") from exc

    def search_grounded_json(
        self, prompt: str, schema: dict[str, Any]
    ) -> tuple[dict[str, Any], list[dict[str, str]]]:
        """Explicit user-triggered public-web research; URLs come from grounding metadata."""
        prompt = _bounded_prompt(prompt)
        if not settings.gemini_api_key:
            raise ProviderError("Gemini API key is not configured")
        self.limiter.acquire()
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=settings.gemini_api_key)
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    # Gemini currently rejects JSON response MIME types when a
                    # built-in Google Search tool is enabled. The prompt asks
                    # for JSON; we validate it locally below and trust URLs
                    # only from grounding metadata.
                    temperature=0.1,
                    tools=[types.Tool(google_search=types.GoogleSearch())],
                ),
            )
            text = (response.text or "").strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1] if "\n" in text else ""
                text = text.rsplit("```", 1)[0].strip()
            parsed = _parse_json(text)
            metadata = (
                getattr(response.candidates[0], "grounding_metadata", None)
                if response.candidates
                else None
            )
            sources = []
            for chunk in getattr(metadata, "grounding_chunks", None) or []:
                web = getattr(chunk, "web", None)
                uri = str(getattr(web, "uri", "") or "").strip()
                title = str(getattr(web, "title", "") or uri).strip()
                if uri.startswith("https://") and not any(row["url"] == uri for row in sources):
                    sources.append({"title": title[:240], "url": uri[:2048]})
            return parsed, sources[:8]
        except RateLimitExceeded:
            raise
        except Exception as exc:
            # Keep the diagnostic type/message in server logs, never in the API
            # response and never including credentials or prompt contents.
            logger.warning(
                "Gemini grounded search failed (%s): %s", type(exc).__name__, str(exc)[:500]
            )
            message = str(exc).casefold()
            if "resource_exhausted" in message or "429" in message or "quota exceeded" in message:
                raise RateLimitExceeded(
                    "Gemini web research quota is temporarily exhausted"
                ) from exc
            raise ProviderError("Gemini web research failed") from exc


class FallbackLLM:
    def __init__(self) -> None:
        self.providers = {
            "ollama": OllamaProvider(),
            "gemini": GeminiProvider(),
        }

    def generate_json(
        self,
        prompt: str,
        schema: dict[str, Any],
        *,
        feature: str = "unspecified",
        prompt_version: str = "unversioned",
    ) -> dict[str, Any]:
        names = [settings.llm_provider, settings.llm_fallback_provider]

        errors: list[str] = []

        trace = current_trace(feature, prompt_version, len(prompt))

        previous_provider: str | None = None

        for name in dict.fromkeys(names):
            provider = self.providers.get(name.lower())

            if not provider:
                errors.append(f"unsupported provider: {name}")

                record_event(
                    trace=trace,
                    event_type="provider_attempt",
                    provider=name,
                    status="unsupported",
                    category="unsupported_provider",
                    fallback_from=previous_provider,
                )
                previous_provider = name

                continue

            for attempt in range(settings.llm_max_retries + 1):
                started = time.monotonic()

                try:
                    result = provider.generate_json(prompt, schema)

                    latency = round((time.monotonic() - started) * 1000)

                    record_event(
                        trace=trace,
                        event_type="provider_attempt",
                        provider=provider.name,
                        model=_provider_model(provider.name),
                        status="success",
                        latency_ms=latency,
                        attempt=attempt + 1,
                        output_characters=len(json.dumps(result, ensure_ascii=False)),
                        fallback_from=previous_provider,
                    )

                    return result

                except RateLimitExceeded as exc:
                    errors.append(f"{name}: local rate limit")

                    record_event(
                        trace=trace,
                        event_type="provider_attempt",
                        provider=provider.name,
                        model=_provider_model(provider.name),
                        status="rate_limited",
                        latency_ms=round((time.monotonic() - started) * 1000),
                        attempt=attempt + 1,
                        category=error_category(exc),
                        fallback_from=previous_provider,
                    )

                    break

                except ProviderError as exc:
                    errors.append(f"{name}: {exc}")

                    record_event(
                        trace=trace,
                        event_type="provider_attempt",
                        provider=provider.name,
                        model=_provider_model(provider.name),
                        status="error",
                        latency_ms=round((time.monotonic() - started) * 1000),
                        attempt=attempt + 1,
                        category=error_category(exc),
                        fallback_from=previous_provider,
                    )

                    if attempt < settings.llm_max_retries:
                        time.sleep(min(2**attempt, 4))
            previous_provider = provider.name

        raise ProviderError("All configured LLM providers failed")


def _provider_model(provider: str) -> str:

    if provider == "ollama":

        return settings.ollama_model

    if provider == "gemini":

        return settings.gemini_model

    return ""


llm = FallbackLLM()
