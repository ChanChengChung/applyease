from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def register(email: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        headers={"X-ApplyEase-Client": "browser-extension"},
        json={"email": email, "password": "secure-pass-123"},
    )

    assert response.status_code == 201, response.text

    return response.json()["access_token"]


def test_register_login_me_and_duplicate_account():
    email = "stage9-auth@example.com"

    token = register(email)

    duplicate = client.post(
        "/api/v1/auth/register", json={"email": email, "password": "secure-pass-123"}
    )

    assert duplicate.status_code == 409

    login = client.post("/api/v1/auth/login", json={"email": email, "password": "secure-pass-123"})

    assert login.status_code == 200

    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert me.status_code == 200 and me.json()["email"] == email

    assert (
        client.post(
            "/api/v1/auth/login", json={"email": email, "password": "wrong-pass"}
        ).status_code
        == 401
    )


def test_user_owned_jobs_are_not_visible_across_accounts():
    first = register("stage9-owner-a@example.com")

    second = register("stage9-owner-b@example.com")

    created = client.post(
        "/api/v1/jobs/analyze",
        headers={"Authorization": f"Bearer {first}"},
        json={
            "title": "Private AI Intern",
            "company": "PrivateCo",
            "description": "Build Python tools for a private research team and collaborate with engineers.",
        },
    )

    assert created.status_code == 200

    job_id = created.json()["id"]

    assert (
        client.get(
            f"/api/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {first}"}
        ).status_code
        == 200
    )

    assert (
        client.get(
            f"/api/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {second}"}
        ).status_code
        == 404
    )


def test_production_requires_bearer_token(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "app_env", "production")

    client.cookies.clear()

    try:
        assert client.get("/api/v1/experiences").status_code == 401

    finally:
        monkeypatch.setattr(settings, "app_env", "test")
