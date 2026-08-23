from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.api.v1 import advisor as advisor_api
from app.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.models.ai_observation import AIUsageBucket
from app.models.user import User
from app.services.ai_usage_limit_service import AIUsageLimitExceeded, consume_ai_usage, utc_now


def _user_id() -> int:
    with SessionLocal() as db:
        user = User(email=f"quota-{uuid4()}@example.com", password_hash="test")
        db.add(user)
        db.commit()
        return int(user.id)


def test_database_quota_is_per_user_category_and_resets_after_its_window():
    user_id = _user_id()
    other_user_id = _user_id()
    now = utc_now()

    with SessionLocal() as db:
        consume_ai_usage(
            db, user_id=user_id, category="test_generation", maximum=2, window_seconds=60, now=now
        )
        consume_ai_usage(
            db, user_id=user_id, category="test_generation", maximum=2, window_seconds=60, now=now
        )
        with pytest.raises(AIUsageLimitExceeded) as blocked:
            consume_ai_usage(
                db,
                user_id=user_id,
                category="test_generation",
                maximum=2,
                window_seconds=60,
                now=now,
            )
        assert 55 <= blocked.value.retry_after_seconds <= 60

        # A second account and a second category retain independent budgets.
        consume_ai_usage(
            db,
            user_id=other_user_id,
            category="test_generation",
            maximum=2,
            window_seconds=60,
            now=now,
        )
        consume_ai_usage(
            db, user_id=user_id, category="test_ocr", maximum=1, window_seconds=60, now=now
        )

        consume_ai_usage(
            db,
            user_id=user_id,
            category="test_generation",
            maximum=2,
            window_seconds=60,
            now=now + timedelta(seconds=60),
        )


def test_advisor_returns_standard_429_before_a_second_provider_call(monkeypatch):
    # Development's compatibility account makes this endpoint usable without a
    # login, while the quota itself remains stored in the database.
    with SessionLocal() as db:
        local_user = db.query(User).filter(User.email == "local@applyease.dev").first()
        if local_user:
            db.execute(
                delete(AIUsageBucket).where(
                    AIUsageBucket.user_id == local_user.id, AIUsageBucket.category == "generation"
                )
            )
            db.commit()

    calls = []
    monkeypatch.setattr(settings, "ai_generation_max_requests", 1)
    monkeypatch.setattr(settings, "ai_generation_rate_limit_window_seconds", 120)
    monkeypatch.setattr(
        advisor_api,
        "answer_advisor",
        lambda *_: calls.append(True)
        or {
            "answer": "Safe advice",
            "sources": [],
            "suggested_prompts": [],
            "used_fallback": True,
        },
    )
    client = TestClient(app)

    first = client.post("/api/v1/advisor/chat", json={"message": "What should I do next?"})
    second = client.post("/api/v1/advisor/chat", json={"message": "What should I do next?"})

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.headers["retry-after"].isdigit()
    assert len(calls) == 1
