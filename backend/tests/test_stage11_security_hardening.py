import base64
import hashlib
from uuid import uuid4

from fastapi.testclient import TestClient
from starlette.requests import Request
from sqlalchemy import select

from app.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.models.security import AuthSession, SecurityAudit
from app.models.user import User
from app import auth as auth_service


def _register(client: TestClient, email: str | None = None, *, extension: bool = False):
    email = email or f"secure-{uuid4()}@example.com"

    headers = {"X-ApplyEase-Client": "browser-extension"} if extension else {}

    response = client.post(
        "/api/v1/auth/register",
        headers=headers,
        json={"email": email, "password": "a-secure-passphrase"},
    )

    assert response.status_code == 201, response.text

    return email, response


def test_web_session_uses_httponly_cookie_csrf_and_stores_only_hashes():
    client = TestClient(app)

    email, response = _register(client)

    assert response.json()["access_token"] is None

    token = client.cookies.get(settings.auth_cookie_name)

    cookies = response.headers.get_list("set-cookie")

    assert any("applyease_session=" in item and "HttpOnly" in item for item in cookies)

    assert any("applyease_csrf=" in item and "HttpOnly" not in item for item in cookies)

    assert client.get("/api/v1/auth/me").json()["email"] == email

    # Cookie-authenticated state changes require a bound double-submit token.

    blocked = client.post(
        "/api/v1/jobs/analyze",
        json={
            "title": "Secure role",
            "description": "Build secure Python services for a production engineering team.",
        },
    )

    assert blocked.status_code == 403 and "CSRF" in blocked.json()["detail"]

    csrf = client.cookies.get(settings.auth_csrf_cookie_name)

    allowed = client.post(
        "/api/v1/jobs/analyze",
        headers={"X-CSRF-Token": csrf},
        json={
            "title": "Secure role",
            "description": "Build secure Python services for a production engineering team.",
        },
    )

    assert allowed.status_code == 200

    with SessionLocal() as db:
        session = db.scalar(
            select(AuthSession).where(AuthSession.user_id == response.json()["user"]["id"])
        )

        assert session and len(session.token_hash) == 64 and token != session.token_hash

        assert token not in " ".join(str(value) for value in session.__dict__.values())

        assert "token" not in SecurityAudit.__table__.columns

        assert "email" not in SecurityAudit.__table__.columns


def test_bearer_extension_flow_needs_no_csrf_and_logout_revokes_token():
    client = TestClient(app)

    _, response = _register(client, extension=True)

    token = response.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}

    assert (
        client.post(
            "/api/v1/jobs/analyze",
            headers=headers,
            json={
                "title": "Extension role",
                "description": "Build TypeScript interfaces and collaborate with the product team.",
            },
        ).status_code
        == 200
    )

    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204

    client.cookies.clear()

    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401


def test_logout_all_revokes_every_active_session():
    first = TestClient(app)
    second = TestClient(app)

    email, registered = _register(first, extension=True)

    first_token = registered.json()["access_token"]

    login = second.post(
        "/api/v1/auth/login",
        headers={"X-ApplyEase-Client": "browser-extension"},
        json={"email": email, "password": "a-secure-passphrase"},
    )

    second_token = login.json()["access_token"]

    sessions = second.get(
        "/api/v1/auth/sessions", headers={"Authorization": f"Bearer {second_token}"}
    )

    assert sessions.status_code == 200 and len(sessions.json()) == 2

    assert (
        second.post(
            "/api/v1/auth/logout-all", headers={"Authorization": f"Bearer {second_token}"}
        ).status_code
        == 204
    )

    for token in (first_token, second_token):
        client = TestClient(app)
        client.cookies.clear()

        assert (
            client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code
            == 401
        )


def test_invalid_credentials_never_fall_back_to_local_user():
    client = TestClient(app)
    client.cookies.clear()

    assert (
        client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid-token"}).status_code
        == 401
    )


def test_forwarded_client_ip_is_only_trusted_at_the_production_edge(monkeypatch):
    def request(real_ip: str) -> Request:
        return Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/",
                "headers": [(b"x-real-ip", real_ip.encode())],
                "client": ("127.0.0.1", 12345),
                "scheme": "http",
                "server": ("testserver", 80),
            }
        )

    monkeypatch.setattr(settings, "app_env", "development")
    assert (
        auth_service._request_hashes(request("198.51.100.10"))[1]
        == auth_service._request_hashes(request("203.0.113.20"))[1]
    )

    monkeypatch.setattr(settings, "app_env", "production")
    assert (
        auth_service._request_hashes(request("198.51.100.10"))[1]
        != auth_service._request_hashes(request("203.0.113.20"))[1]
    )


def test_login_rate_limit_is_persistent_and_audit_is_pseudonymous(monkeypatch):
    client = TestClient(app)

    email, _ = _register(client)

    client.cookies.clear()

    monkeypatch.setattr(settings, "auth_max_failed_attempts", 2)

    monkeypatch.setattr(settings, "auth_max_failed_ip_attempts", 100)

    for _ in range(2):
        assert (
            client.post(
                "/api/v1/auth/login", json={"email": email, "password": "wrong"}
            ).status_code
            == 401
        )
    limited = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong"})

    assert limited.status_code == 429 and limited.headers["retry-after"] == str(
        settings.auth_rate_limit_window_seconds
    )

    with SessionLocal() as db:
        rows = list(
            db.scalars(
                select(SecurityAudit).where(
                    SecurityAudit.event_type == "login", SecurityAudit.outcome == "failure"
                )
            ).all()
        )
    assert len(rows) >= 2

    assert all(len(row.subject_hash) == 64 and len(row.ip_hash) == 64 for row in rows)

    assert email not in " ".join(str(value) for row in rows for value in row.__dict__.values())


def test_legacy_password_hash_is_upgraded_after_successful_login():
    rounds = 100_000
    password = "legacy-pass"
    salt = b"0123456789abcdef"

    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, rounds)

    encoded = f"pbkdf2_sha256${rounds}${base64.urlsafe_b64encode(salt).decode()}${base64.urlsafe_b64encode(digest).decode()}"

    email = f"legacy-{uuid4()}@example.com"

    with SessionLocal() as db:
        db.add(User(email=email, password_hash=encoded, is_active=True))
        db.commit()
    response = TestClient(app).post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    )

    assert response.status_code == 200

    with SessionLocal() as db:
        upgraded = db.scalar(select(User).where(User.email == email))

        assert int(upgraded.password_hash.split("$")[1]) >= 310_000


def test_security_headers_are_present_on_api_responses():
    response = TestClient(app).get("/health/live")

    assert response.headers["x-content-type-options"] == "nosniff"

    assert response.headers["x-frame-options"] == "DENY"

    assert response.headers["referrer-policy"] == "no-referrer"

    assert "camera=()" in response.headers["permissions-policy"]


def test_production_rejects_bad_hosts_and_plain_http(monkeypatch):
    client = TestClient(app)

    monkeypatch.setattr(settings, "app_env", "production")

    monkeypatch.setattr(settings, "enforce_https", True)

    monkeypatch.setattr(settings, "allowed_hosts", "api.example.com")

    bad_host = client.get(
        "/health/live", headers={"host": "evil.example", "x-forwarded-proto": "https"}
    )

    assert bad_host.status_code == 400 and bad_host.headers["x-frame-options"] == "DENY"

    plain = client.get("/health/live", headers={"host": "api.example.com"})

    assert plain.status_code == 400 and plain.json()["detail"] == "HTTPS is required"

    secure = client.get(
        "/health/live", headers={"host": "api.example.com", "x-forwarded-proto": "https"}
    )

    assert secure.status_code == 200

    assert "default-src 'none'" in secure.headers["content-security-policy"]
