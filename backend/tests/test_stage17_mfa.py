import base64
import hashlib
import hmac
import struct
import time
import zipfile
from io import BytesIO
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.api.v1 import auth as auth_api
from app.services.rag_service import RAGPurgeError

client = TestClient(app)


def _code(secret: str) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    counter = int(time.time()) // 30
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 15
    return f"{(struct.unpack('>I', digest[offset:offset + 4])[0] & 0x7fffffff) % 1_000_000:06d}"


def _register() -> tuple[str, dict[str, str]]:
    email = f"mfa-{uuid4()}@example.com"
    response = client.post(
        "/api/v1/auth/register",
        headers={"X-ApplyEase-Client": "browser-extension"},
        json={"email": email, "password": "mfa-secure-password"},
    )
    assert response.status_code == 201, response.text
    return email, {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_totp_setup_login_recovery_and_disable():
    email, headers = _register()
    assert (
        client.post(
            "/api/v1/auth/mfa/setup", headers=headers, json={"current_password": "wrong"}
        ).status_code
        == 401
    )
    setup = client.post(
        "/api/v1/auth/mfa/setup", headers=headers, json={"current_password": "mfa-secure-password"}
    )
    assert setup.status_code == 200, setup.text
    secret = setup.json()["secret"]
    assert secret not in setup.json()["provisioning_uri"].split("secret=")[0]
    assert (
        client.post(
            "/api/v1/auth/mfa/confirm", headers=headers, json={"code": "000000"}
        ).status_code
        == 422
    )
    enabled = client.post("/api/v1/auth/mfa/confirm", headers=headers, json={"code": _code(secret)})
    assert enabled.status_code == 200, enabled.text
    recovery = enabled.json()["recovery_codes"]
    assert len(recovery) == 8 and len(set(recovery)) == 8
    assert client.get("/api/v1/auth/mfa", headers=headers).json() == {
        "enabled": True,
        "recovery_codes_remaining": 8,
    }

    login = TestClient(app).post(
        "/api/v1/auth/login",
        headers={"X-ApplyEase-Client": "browser-extension"},
        json={"email": email, "password": "mfa-secure-password"},
    )
    assert (
        login.status_code == 200
        and login.json()["mfa_required"] is True
        and login.json()["access_token"] is None
    )
    token = login.json()["mfa_token"]
    assert (
        TestClient(app)
        .post(
            "/api/v1/auth/mfa/login/verify",
            headers={"X-ApplyEase-Client": "browser-extension"},
            json={"mfa_token": token, "code": "000000"},
        )
        .status_code
        == 401
    )
    verified = TestClient(app).post(
        "/api/v1/auth/mfa/login/verify",
        headers={"X-ApplyEase-Client": "browser-extension"},
        json={"mfa_token": token, "code": _code(secret)},
    )
    assert verified.status_code == 200 and verified.json()["access_token"]

    used = client.post(
        "/api/v1/auth/mfa/recovery-codes", headers=headers, json={"code": recovery[0]}
    )
    assert used.status_code == 200 and len(used.json()["recovery_codes"]) == 8
    assert (
        client.post(
            "/api/v1/auth/mfa/disable", headers=headers, json={"code": recovery[0]}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/auth/mfa/disable", headers=headers, json={"code": _code(secret)}
        ).status_code
        == 204
    )
    assert client.get("/api/v1/auth/mfa", headers=headers).json() == {
        "enabled": False,
        "recovery_codes_remaining": 0,
    }


def test_mfa_challenge_is_one_time_and_owner_cannot_skip_setup():
    _, headers = _register()
    assert (
        client.post(
            "/api/v1/auth/mfa/confirm", headers=headers, json={"code": "123456"}
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/auth/mfa/disable", headers=headers, json={"code": "123456"}
        ).status_code
        == 422
    )


def test_account_settings_change_password_and_revoke_other_device():
    email, first_headers = _register()
    second = TestClient(app).post(
        "/api/v1/auth/login",
        headers={"X-ApplyEase-Client": "browser-extension"},
        json={"email": email, "password": "mfa-secure-password"},
    )
    assert second.status_code == 200
    sessions = client.get("/api/v1/auth/sessions", headers=first_headers).json()
    other = next(item for item in sessions if not item["current"])
    assert (
        client.delete(f"/api/v1/auth/sessions/{other['id']}", headers=first_headers).status_code
        == 204
    )
    assert (
        client.delete(f"/api/v1/auth/sessions/{other['id']}", headers=first_headers).status_code
        == 404
    )
    current = next(
        item
        for item in client.get("/api/v1/auth/sessions", headers=first_headers).json()
        if item["current"]
    )
    assert (
        client.delete(f"/api/v1/auth/sessions/{current['id']}", headers=first_headers).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/auth/password/change",
            headers=first_headers,
            json={"current_password": "wrong", "new_password": "replacement-secure-password"},
        ).status_code
        == 401
    )
    changed = client.post(
        "/api/v1/auth/password/change",
        headers=first_headers,
        json={
            "current_password": "mfa-secure-password",
            "new_password": "replacement-secure-password",
        },
    )
    assert changed.status_code == 200
    assert client.get("/api/v1/auth/me", headers=first_headers).status_code == 401
    assert (
        TestClient(app)
        .post(
            "/api/v1/auth/login", json={"email": email, "password": "replacement-secure-password"}
        )
        .status_code
        == 200
    )


def test_password_change_requires_mfa_when_mfa_is_enabled():
    _email, headers = _register()
    setup = client.post(
        "/api/v1/auth/mfa/setup", headers=headers, json={"current_password": "mfa-secure-password"}
    ).json()
    assert (
        client.post(
            "/api/v1/auth/mfa/confirm", headers=headers, json={"code": _code(setup["secret"])}
        ).status_code
        == 200
    )

    missing = client.post(
        "/api/v1/auth/password/change",
        headers=headers,
        json={
            "current_password": "mfa-secure-password",
            "new_password": "replacement-secure-password",
        },
    )
    invalid = client.post(
        "/api/v1/auth/password/change",
        headers=headers,
        json={
            "current_password": "mfa-secure-password",
            "new_password": "replacement-secure-password",
            "mfa_code": "000000",
        },
    )
    changed = client.post(
        "/api/v1/auth/password/change",
        headers=headers,
        json={
            "current_password": "mfa-secure-password",
            "new_password": "replacement-secure-password",
            "mfa_code": _code(setup["secret"]),
        },
    )

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert changed.status_code == 200


def test_private_data_export_and_irreversible_account_deletion(monkeypatch):
    email, headers = _register()
    purged: list[int] = []
    monkeypatch.setattr(auth_api, "purge_user_context", lambda user_id: purged.append(user_id))
    assert (
        client.post(
            "/api/v1/tracker/applications",
            headers=headers,
            json={"company": "Private Co", "role": "AI Intern"},
        ).status_code
        == 200
    )
    exported = client.post(
        "/api/v1/auth/data-export",
        headers=headers,
        json={"current_password": "mfa-secure-password"},
    )
    assert exported.status_code == 200 and exported.headers["content-type"].startswith(
        "application/zip"
    )
    with zipfile.ZipFile(BytesIO(exported.content)) as archive:
        payload = archive.read("applyease-account-export.json").decode()
        assert email in payload and "Private Co" in payload
        assert (
            "password_hash" not in payload
            and "token_hash" not in payload
            and "encrypted_secret" not in payload
        )
    assert (
        client.post(
            "/api/v1/auth/data-export", headers=headers, json={"current_password": "wrong"}
        ).status_code
        == 401
    )
    assert (
        client.request(
            "DELETE",
            "/api/v1/auth/account",
            headers=headers,
            json={"current_password": "mfa-secure-password"},
        ).status_code
        == 204
    )
    assert len(purged) == 1
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert (
        TestClient(app)
        .post("/api/v1/auth/login", json={"email": email, "password": "mfa-secure-password"})
        .status_code
        == 401
    )


def test_account_deletion_fails_closed_when_vector_purge_is_unavailable(monkeypatch):
    _email, headers = _register()

    def unavailable(_user_id: int) -> None:
        raise RAGPurgeError("Milvus unavailable")

    monkeypatch.setattr(auth_api, "purge_user_context", unavailable)
    response = client.request(
        "DELETE",
        "/api/v1/auth/account",
        headers=headers,
        json={"current_password": "mfa-secure-password"},
    )

    assert response.status_code == 503
    # The account remains usable so deletion can be safely retried later.
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
