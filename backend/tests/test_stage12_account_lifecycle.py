import json
import re
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth import utc_now
from app.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.models.security import AccountToken, AuthSession, SecurityAudit
from app.models.user import User
from app.services import account_lifecycle_service as lifecycle
from app.services.email_service import deliver_account_email


def _capture_mail(monkeypatch):
    messages: list[dict[str, str]] = []

    monkeypatch.setattr(
        lifecycle,
        "deliver_account_email",
        lambda recipient, subject, text: messages.append(
            {"to": recipient, "subject": subject, "text": text}
        ),
    )

    return messages


def _token(messages, name: str) -> str:
    match = re.search(rf"[?#&]{name}=([^\s]+)", messages[-1]["text"])

    assert match

    return match.group(1)


def _register(client: TestClient, monkeypatch, email: str | None = None, *, extension: bool = True):
    messages = _capture_mail(monkeypatch)
    email = email or f"lifecycle-{uuid4()}@example.com"

    headers = {"X-ApplyEase-Client": "browser-extension"} if extension else {}

    response = client.post(
        "/api/v1/auth/register",
        headers=headers,
        json={"email": email, "password": "initial-secure-pass"},
    )
    assert response.status_code == 201, response.text

    return email, response, messages


def test_email_verification_is_hashed_one_time_and_old_request_is_invalidated(monkeypatch):
    client = TestClient(app)

    email, response, messages = _register(client, monkeypatch)

    first = _token(messages, "verify_token")
    assert "#verify_token=" in messages[-1]["text"] and "?verify_token=" not in messages[-1]["text"]

    assert response.json()["user"]["email_verified"] is False

    requested = client.post("/api/v1/auth/email-verification/request", json={"email": email})

    assert requested.status_code == 202

    second = _token(messages, "verify_token")

    assert second != first

    assert (
        client.post("/api/v1/auth/email-verification/confirm", json={"token": first}).status_code
        == 400
    )

    confirmed = client.post("/api/v1/auth/email-verification/confirm", json={"token": second})

    assert confirmed.status_code == 200

    assert (
        client.post("/api/v1/auth/email-verification/confirm", json={"token": second}).status_code
        == 400
    )

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        tokens = list(db.scalars(select(AccountToken).where(AccountToken.user_id == user.id)).all())
        assert user.email_verified and all(item.consumed_at is not None for item in tokens)

        assert first not in " ".join(
            str(value) for item in tokens for value in item.__dict__.values()
        )


def test_password_reset_is_non_enumerating_one_time_and_revokes_all_sessions(monkeypatch):
    first_client = TestClient(app)
    second_client = TestClient(app)

    email, registered, messages = _register(first_client, monkeypatch)

    first_token = registered.json()["access_token"]

    second_login = second_client.post(
        "/api/v1/auth/login",
        headers={"X-ApplyEase-Client": "browser-extension"},
        json={"email": email, "password": "initial-secure-pass"},
    )
    second_token = second_login.json()["access_token"]

    existing = first_client.post("/api/v1/auth/password/forgot", json={"email": email})

    missing = first_client.post(
        "/api/v1/auth/password/forgot", json={"email": f"missing-{uuid4()}@example.com"}
    )

    assert existing.status_code == missing.status_code == 202

    assert existing.json() == missing.json()

    reset_token = _token(messages, "reset_token")
    assert "#reset_token=" in messages[-1]["text"] and "?reset_token=" not in messages[-1]["text"]

    reset = first_client.post(
        "/api/v1/auth/password/reset",
        json={"token": reset_token, "new_password": "replacement-secure-pass"},
    )

    assert reset.status_code == 200

    assert (
        first_client.post(
            "/api/v1/auth/password/reset",
            json={"token": reset_token, "new_password": "another-secure-pass"},
        ).status_code
        == 400
    )

    for token in (first_token, second_token):
        check = TestClient(app)
        check.cookies.clear()

        assert (
            check.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code
            == 401
        )
    assert (
        TestClient(app)
        .post("/api/v1/auth/login", json={"email": email, "password": "initial-secure-pass"})
        .status_code
        == 401
    )

    assert (
        TestClient(app)
        .post("/api/v1/auth/login", json={"email": email, "password": "replacement-secure-pass"})
        .status_code
        == 200
    )


def test_password_reset_accepts_the_one_time_six_digit_mailbox_code(monkeypatch):
    client = TestClient(app)
    email, _registered, messages = _register(client, monkeypatch)

    requested = client.post("/api/v1/auth/password/forgot", json={"email": email})
    assert requested.status_code == 202
    code_match = re.search(r"6-digit code in ApplyEase:\s*\n\s*(\d{6})", messages[-1]["text"])
    assert code_match

    reset = client.post(
        "/api/v1/auth/password/reset",
        json={"token": code_match.group(1), "new_password": "code-reset-secure-pass"},
    )
    assert reset.status_code == 200, reset.text
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": "code-reset-secure-pass"},
        ).status_code
        == 200
    )


def test_expired_token_and_production_verification_gate(monkeypatch):
    client = TestClient(app)

    email, registered, messages = _register(client, monkeypatch)

    raw = _token(messages, "verify_token")

    with SessionLocal() as db:
        token = db.scalar(
            select(AccountToken)
            .where(AccountToken.purpose == lifecycle.VERIFY_PURPOSE)
            .order_by(AccountToken.created_at.desc())
        )

        token.expires_at = utc_now() - timedelta(seconds=1)
        db.commit()
    assert (
        client.post("/api/v1/auth/email-verification/confirm", json={"token": raw}).status_code
        == 400
    )

    monkeypatch.setattr(settings, "auth_require_verified_email", True)

    bearer = registered.json()["access_token"]

    assert (
        client.get("/api/v1/experiences", headers={"Authorization": f"Bearer {bearer}"}).status_code
        == 403
    )

    # A fresh link restores access without creating another account.

    assert (
        client.post("/api/v1/auth/email-verification/request", json={"email": email}).status_code
        == 202
    )

    fresh = _token(messages, "verify_token")

    assert (
        client.post("/api/v1/auth/email-verification/confirm", json={"token": fresh}).status_code
        == 200
    )

    assert (
        client.get("/api/v1/experiences", headers={"Authorization": f"Bearer {bearer}"}).status_code
        == 200
    )


def test_verified_email_policy_does_not_create_a_registration_session(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(settings, "auth_require_verified_email", True)
    monkeypatch.setattr(settings, "app_env", "production")
    email, response, messages = _register(client, monkeypatch, extension=False)

    assert response.json()["session_ready"] is False
    assert response.json()["access_token"] is None
    assert client.get("/api/v1/auth/me").status_code == 401

    verify_token = _token(messages, "verify_token")
    assert (
        client.post(
            "/api/v1/auth/email-verification/confirm", json={"token": verify_token}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": email, "password": "initial-secure-pass"}
        ).status_code
        == 200
    )


def test_account_email_rate_limit_and_pseudonymous_audit(monkeypatch):
    client = TestClient(app)
    messages = _capture_mail(monkeypatch)

    email = f"rate-{uuid4()}@example.com"

    monkeypatch.setattr(settings, "account_email_max_requests", 2)

    monkeypatch.setattr(settings, "account_email_max_ip_requests", 10_000)

    for _ in range(2):
        assert client.post("/api/v1/auth/password/forgot", json={"email": email}).status_code == 202
    limited = client.post("/api/v1/auth/password/forgot", json={"email": email})

    assert limited.status_code == 429 and limited.headers["retry-after"] == str(
        settings.account_email_rate_limit_window_seconds
    )

    assert not messages

    with SessionLocal() as db:
        rows = list(
            db.scalars(
                select(SecurityAudit).where(SecurityAudit.event_type == "password_reset_request")
            ).all()
        )

        assert rows and all(len(row.subject_hash) == 64 for row in rows)

        assert email not in " ".join(str(value) for row in rows for value in row.__dict__.values())


def test_invalid_token_attempts_are_ip_limited(monkeypatch):
    client = TestClient(app)

    with SessionLocal() as db:
        existing = len(
            list(
                db.scalars(
                    select(SecurityAudit).where(
                        SecurityAudit.event_type == "email_verification_confirm",
                        SecurityAudit.outcome == "failure",
                    )
                ).all()
            )
        )
    monkeypatch.setattr(settings, "account_token_max_failed_attempts", existing + 2)

    for suffix in ("a", "b"):
        result = client.post("/api/v1/auth/email-verification/confirm", json={"token": suffix * 40})

        assert result.status_code == 400
    limited = client.post("/api/v1/auth/email-verification/confirm", json={"token": "c" * 40})

    assert limited.status_code == 429


def test_development_file_mailbox_is_private_and_contains_link(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "mail_delivery_mode", "file")

    monkeypatch.setattr(settings, "mail_file_dir", str(tmp_path / "mailbox"))

    deliver_account_email("student@example.com", "Verify", "http://localhost/#verify_token=secret")

    files = list((tmp_path / "mailbox").glob("*.json"))
    assert len(files) == 1

    payload = json.loads(files[0].read_text())

    assert payload["to"] == "student@example.com" and "#verify_token=" in payload["text"]

    assert files[0].stat().st_mode & 0o777 == 0o600


def test_password_reset_reports_transport_without_revealing_account(monkeypatch):
    """The response can explain local mail without becoming an account oracle."""
    client = TestClient(app)
    monkeypatch.setattr(settings, "mail_delivery_mode", "file")
    email = f"transport-{uuid4()}@example.com"

    response = client.post("/api/v1/auth/password/forgot", json={"email": email})

    assert response.status_code == 202
    assert response.json()["delivery_channel"] == "local_mailbox"


def test_production_configuration_requires_verified_email_and_smtp():
    from pydantic import ValidationError

    from app.config import Settings

    base = dict(
        app_env="production",
        database_url="postgresql+psycopg://safe:unique@db/applyease",
        cors_origins="https://app.example.com",
        auth_secret="x" * 32,
        auth_cookie_secure=True,
        enforce_https=True,
        allowed_hosts="api.example.com",
        frontend_base_url="https://app.example.com",
        app_version="v1.0.0",
    )

    try:
        Settings(**base)

        assert False, "weak lifecycle configuration should fail"

    except ValidationError:
        pass
    configured = Settings(
        **base,
        auth_require_verified_email=True,
        mail_delivery_mode="smtp",
        smtp_host="smtp.example.com",
    )

    assert configured.auth_require_verified_email is True

    with pytest.raises(ValidationError, match="SMTP_STARTTLS"):
        Settings(
            **base,
            auth_require_verified_email=True,
            mail_delivery_mode="smtp",
            smtp_host="smtp.example.com",
            smtp_starttls=False,
        )
