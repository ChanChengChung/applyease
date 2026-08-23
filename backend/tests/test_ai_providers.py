import pytest

from app.ai.providers import (
    DashScopeProvider,
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


def test_dashscope_posts_openai_compatible_json_request(monkeypatch):
    calls = []

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": '{"ok": true}'}}]}

    def fake_post(url, *, headers, json, timeout):
        calls.append((url, headers, json, timeout))
        return Response()

    monkeypatch.setattr("app.ai.providers.settings.dashscope_api_key", "test-key")
    monkeypatch.setattr(
        "app.ai.providers.settings.dashscope_base_url", "https://workspace.example/v1/"
    )
    monkeypatch.setattr("app.ai.providers.settings.dashscope_model", "qwen-plus")
    monkeypatch.setattr("app.ai.providers.httpx.post", fake_post)

    assert DashScopeProvider().generate_json("hello", {"type": "object"}) == {"ok": True}
    url, headers, payload, _timeout = calls[0]
    assert url == "https://workspace.example/v1/chat/completions"
    assert headers["Authorization"] == "Bearer test-key"
    assert payload["model"] == "qwen-plus"
    assert payload["response_format"] == {"type": "json_object"}
