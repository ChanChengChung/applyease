from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _job():
    response = client.post(
        "/api/v1/jobs/analyze",
        json={
            "title": "Stage 4 Intern",
            "company": "ApplyEase",
            "description": "Build application materials and communicate project results clearly.",
        },
    )

    assert response.status_code == 200, response.text

    return response.json()["id"]


def test_answer_limit_is_persisted_and_enforced_on_edit():
    job_id = _job()

    generated = client.post(
        f"/api/v1/materials/answer/generate?job_id={job_id}",
        json={
            "question": "Why are you interested in this role?",
            "max_characters": 50,
        },
    )

    assert generated.status_code == 200, generated.text

    data = generated.json()

    assert data["max_characters"] == 50

    assert (
        client.patch(f"/api/v1/materials/{data['id']}", json={"text": "x" * 51}).status_code == 422
    )


def test_material_query_filter_and_blank_question_validation():
    job_id = _job()

    generated = client.post(f"/api/v1/materials/resume/generate?job_id={job_id}")

    assert generated.status_code == 200

    assert client.get(f"/api/v1/materials?job_id={job_id}&material_type=resume").status_code == 200

    assert client.get(f"/api/v1/materials?job_id={job_id}&material_type=unknown").status_code == 422

    assert (
        client.post(
            f"/api/v1/materials/answer/generate?job_id={job_id}", json={"question": "     "}
        ).status_code
        == 422
    )


def test_missing_job_is_reported_when_editing_or_listing_materials():
    assert client.get("/api/v1/materials?job_id=999999").status_code == 404
