from app.main import app
from fastapi.testclient import TestClient


client = TestClient(app)


def _job():
    response = client.post(
        "/api/v1/jobs/analyze",
        json={
            "title": "Application QA",
            "description": "A software internship involving Python and communication skills.",
        },
    )

    assert response.status_code == 200

    return response.json()["id"]


def test_detection_rejects_whitespace_only_payload_after_normalization():
    assert (
        client.post(
            "/api/v1/applications/questions/detect", json={"job_id": 1, "raw_text": "          "}
        ).status_code
        == 422
    )


def test_unconfirmed_experience_is_not_used_to_validate_user_answer():
    job_id = _job()

    client.post(
        "/api/v1/experiences",
        json={
            "title": "Unconfirmed source for form",
            "description": "Won 999 awards",
            "confirmed": False,
        },
    )

    application = client.post(
        "/api/v1/applications/questions/detect",
        json={
            "job_id": job_id,
            "raw_text": "Describe a project you are proud of?",
        },
    ).json()

    answer = client.patch(
        f"/api/v1/applications/{application['id']}/questions/{application['questions'][0]['id']}/answer",
        json={"answer": "Won 999 awards"},
    )

    assert answer.status_code == 200

    assert answer.json()["fact_check_passed"] is False

    assert any("999" in warning for warning in answer.json()["warnings"])


def test_screenshot_rejects_unsupported_type_before_ocr(monkeypatch):
    job_id = _job()

    monkeypatch.setattr("app.api.v1.applications.settings.screenshot_ocr_enabled", True)

    response = client.post(
        "/api/v1/applications/questions/detect-screenshot",
        data={"job_id": str(job_id), "consent_to_cloud_ocr": "true"},
        files={"file": ("form.gif", b"GIF89a", "image/gif")},
    )

    assert response.status_code == 400
