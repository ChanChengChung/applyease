from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.ai.evaluation import run_evaluation
from app.ai.observability import ai_trace, ai_user_scope, record_outcome
from app.ai.providers import FallbackLLM, ProviderError
from app.auth import hash_password
from app.crud import user as user_crud
from app.db.session import SessionLocal
from app.main import app
from app.models.ai_observation import AIInvocation


def _account(client: TestClient) -> tuple[int, dict[str, str]]:
    email = f"stage10-{uuid4()}@example.com"

    response = client.post(
        "/api/v1/auth/register",
        headers={"X-ApplyEase-Client": "browser-extension"},
        json={"email": email, "password": "strong-pass-123"},
    )

    body = response.json()

    return body["user"]["id"], {"Authorization": f"Bearer {body['access_token']}"}


def test_provider_attempts_and_terminal_fallback_are_content_free(monkeypatch):

    with SessionLocal() as db:
        user = user_crud.create(
            db, email=f"telemetry-{uuid4()}@example.com", password_hash=hash_password("password")
        )

        user_id = user.id
    service = FallbackLLM()

    monkeypatch.setattr(
        service.providers["ollama"],
        "generate_json",
        lambda *_: (_ for _ in ()).throw(ProviderError("offline")),
    )
    monkeypatch.setattr(service.providers["gemini"], "generate_json", lambda *_: {"safe": True})

    monkeypatch.setattr("app.ai.providers.settings.llm_max_retries", 0)

    monkeypatch.setattr("app.ai.providers.settings.llm_provider", "ollama")

    monkeypatch.setattr("app.ai.providers.settings.llm_fallback_provider", "gemini")

    secret_prompt = "SECRET CV CONTENT MUST NOT BE STORED"

    with ai_user_scope(user_id), ai_trace("test_feature", "test-prompt-v1", len(secret_prompt)):
        assert service.generate_json(secret_prompt, {"type": "object"}) == {"safe": True}

        record_outcome(status="success", provider="llm")

    with SessionLocal() as db:
        events = list(db.scalars(select(AIInvocation).where(AIInvocation.user_id == user_id)).all())
    assert [event.provider for event in events] == ["ollama", "gemini", "llm"]

    assert [event.status for event in events] == ["error", "success", "success"]

    assert events[1].fallback_from == "ollama"

    assert all(event.input_characters == len(secret_prompt) for event in events)

    assert "prompt" not in AIInvocation.__table__.columns

    assert "output" not in AIInvocation.__table__.columns

    assert secret_prompt not in " ".join(
        str(value) for event in events for value in event.__dict__.values()
    )


def test_metrics_are_aggregated_and_isolated_per_user():
    client = TestClient(app)

    first_id, first_headers = _account(client)

    second_id, second_headers = _account(client)

    with SessionLocal() as db:

        for user_id, status in (
            (first_id, "success"),
            (first_id, "rule_fallback"),
            (second_id, "error"),
        ):
            db.add(
                AIInvocation(
                    user_id=user_id,
                    request_id=str(uuid4()),
                    event_type="feature_outcome",
                    feature="job_requirements",
                    provider="rules" if status == "rule_fallback" else "llm",
                    model="",
                    prompt_version="job-requirements-v1",
                    status=status,
                    latency_ms=10,
                    attempt=1,
                    input_characters=120,
                )
            )
        db.add(
            AIInvocation(
                user_id=first_id,
                request_id=str(uuid4()),
                event_type="provider_attempt",
                feature="job_requirements",
                provider="ollama",
                model="qwen3:4b",
                prompt_version="job-requirements-v1",
                status="success",
                latency_ms=42,
                attempt=1,
                input_characters=120,
                output_characters=30,
            )
        )
        db.commit()
    first = client.get("/api/v1/ai/metrics?days=30", headers=first_headers)

    second = client.get("/api/v1/ai/metrics?days=30", headers=second_headers)

    assert first.status_code == 200

    assert first.json()["total_feature_calls"] == 2

    assert first.json()["ai_successes"] == 1

    assert first.json()["rule_fallbacks"] == 1

    assert first.json()["provider_attempts"] == 1

    assert first.json()["by_provider"][0]["average_latency_ms"] == 42

    assert second.json()["total_feature_calls"] == 1

    assert second.json()["errors"] == 1

    assert client.get("/api/v1/ai/metrics?days=91", headers=first_headers).status_code == 422


def test_versioned_offline_evaluation_suite_passes_without_network():
    result = run_evaluation("rules")

    assert result["dataset"] == "stage10_cases.json"

    assert result["case_count"] >= 4

    assert result["pass_rate"] == 1.0
