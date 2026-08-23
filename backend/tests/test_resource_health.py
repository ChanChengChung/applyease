from fastapi.testclient import TestClient
from urllib.error import HTTPError

from app.main import app

client = TestClient(app)


class _Response:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _resource_id():
    job = client.post(
        "/api/v1/jobs/analyze",
        json={
            "title": "Quant intern",
            "description": "Quantitative Research and Algorithms are required for this internship role.",
        },
    ).json()
    return client.get(f"/api/v1/resources/recommendations?job_id={job['id']}").json()[0]["id"]


def test_resource_health_check_persists_healthy_and_broken_status(monkeypatch):
    resource_id = _resource_id()
    monkeypatch.setattr(
        "app.services.resource_health_service.urlopen", lambda *_args, **_kwargs: _Response()
    )
    healthy = client.post(f"/api/v1/resources/{resource_id}/health-check")
    assert healthy.status_code == 200
    assert healthy.json()["link_status"] == "healthy"
    assert healthy.json()["last_checked_at"]

    def fail(*_args, **_kwargs):
        raise OSError("network unavailable")

    monkeypatch.setattr("app.services.resource_health_service.urlopen", fail)
    broken = client.post(f"/api/v1/resources/{resource_id}/health-check")
    assert broken.status_code == 200
    assert broken.json()["link_status"] == "broken"


def test_resource_health_check_missing_resource_returns_404():
    assert client.post("/api/v1/resources/999999/health-check").status_code == 404


def test_head_rejection_uses_bounded_get_fallback(monkeypatch):
    resource_id = _resource_id()
    methods = []

    def head_hostile(request, **_kwargs):
        methods.append(request.get_method())
        if request.get_method() == "HEAD":
            raise HTTPError(request.full_url, 405, "Method Not Allowed", None, None)
        return _Response()

    monkeypatch.setattr("app.services.resource_health_service.urlopen", head_hostile)
    response = client.post(f"/api/v1/resources/{resource_id}/health-check")
    assert response.status_code == 200
    assert response.json()["link_status"] == "healthy"
    assert methods == ["HEAD", "GET"]


def test_feedback_is_validated_and_recorded():
    resource_id = _resource_id()
    saved = client.post(
        f"/api/v1/resources/{resource_id}/feedback",
        json={
            "category": "outdated_content",
            "message": "The exercise refers to an obsolete API version.",
        },
    )
    assert saved.status_code == 201
    assert saved.json()["id"] > 0
    assert (
        client.post(
            f"/api/v1/resources/{resource_id}/feedback",
            json={
                "category": "bad_category",
                "message": "Valid message",
            },
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/api/v1/resources/{resource_id}/feedback",
            json={
                "category": "broken_link",
                "message": "  ",
            },
        ).status_code
        == 422
    )
