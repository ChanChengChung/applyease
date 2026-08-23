import pytest

from app.ai.providers import (
    FallbackLLM,
    ProviderError,
    RateLimitExceeded,
    SlidingWindowLimiter,
    _parse_json,
)


def test_sliding_window_limiter_rejects_excess_calls():
    limiter = SlidingWindowLimiter(1, window_seconds=60)

    limiter.acquire()

    with pytest.raises(RateLimitExceeded):
        limiter.acquire()


def test_parse_json_rejects_non_object():

    with pytest.raises(ProviderError):
        _parse_json("[]")


def test_fallback_uses_second_provider(monkeypatch):
    service = FallbackLLM()

    calls = []

    def fail(_prompt, _schema):
        calls.append("ollama")

        raise ProviderError("offline")

    def succeed(_prompt, _schema):
        calls.append("gemini")

        return {"experiences": []}

    monkeypatch.setattr(service.providers["ollama"], "generate_json", fail)

    monkeypatch.setattr(service.providers["gemini"], "generate_json", succeed)

    monkeypatch.setattr("app.ai.providers.settings.llm_max_retries", 0)

    monkeypatch.setattr("app.ai.providers.settings.llm_provider", "ollama")

    monkeypatch.setattr("app.ai.providers.settings.llm_fallback_provider", "gemini")

    assert service.generate_json("hello", {"type": "object"}) == {"experiences": []}

    assert calls == ["ollama", "gemini"]
