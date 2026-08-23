import pytest
from fastapi.testclient import TestClient

from sqlalchemy import delete

from app.db.session import SessionLocal
from app.main import app
from app.models.experience import Experience


client = TestClient(app)


@pytest.fixture(autouse=True)
def _isolate_experiences():
    """The recommendations endpoint matches a job against *every* confirmed
    experience in the database. Other test modules seed confirmed experiences
    into the shared process-wide sqlite engine, which would otherwise leak into
    this module's assertions. Reset only the experiences table before each test
    so the module stays self-contained without dropping the whole schema."""
    with SessionLocal() as db:
        db.execute(delete(Experience))
        db.commit()
    yield


def _job():
    response = client.post(
        "/api/v1/jobs/analyze",
        json={
            "title": "ML and API Intern",
            "description": "Python, Machine Learning, Docker and FastAPI are required for this internship.",
        },
    )

    assert response.status_code == 200

    return response.json()["id"]


def test_recommendations_explain_skill_match_and_respect_filters():
    job_id = _job()

    response = client.get(
        "/api/v1/resources/recommendations",
        params={
            "job_id": job_id,
            "level": "beginner",
            "max_hours": 6,
            "free_only": True,
            "limit": 20,
        },
    )

    assert response.status_code == 200

    items = response.json()

    assert items

    assert all(item["difficulty"] == "beginner" for item in items)

    assert all(item["duration_hours"] <= 6 for item in items)

    assert all(item["free"] for item in items)

    assert all(
        item["match_score"] > 0 and item["matched_skills"] and item["recommendation_reason"]
        for item in items
    )


def test_recommendation_limit_and_invalid_options():
    job_id = _job()

    assert (
        len(
            client.get(
                "/api/v1/resources/recommendations", params={"job_id": job_id, "limit": 1}
            ).json()
        )
        <= 1
    )

    assert (
        client.get(
            "/api/v1/resources/recommendations", params={"job_id": job_id, "max_hours": 0}
        ).status_code
        == 422
    )

    assert (
        client.get(
            "/api/v1/resources/recommendations", params={"job_id": job_id, "level": "expert"}
        ).status_code
        == 422
    )


def test_goal_and_total_time_budget_change_the_recommendation_plan():
    job_id = _job()
    response = client.get(
        "/api/v1/resources/recommendations",
        params={
            "job_id": job_id,
            "goal": "project",
            "max_total_hours": 10,
            "language": "en",
            "limit": 20,
        },
    )

    assert response.status_code == 200
    items = response.json()
    assert items
    assert sum(item["duration_hours"] for item in items) <= 10
    assert all("Portfolio-project focus" in item["recommendation_reason"] for item in items)


def test_completion_can_be_reverted():
    job_id = _job()

    item = client.get("/api/v1/resources/recommendations", params={"job_id": job_id}).json()[0]

    completed = client.post(f"/api/v1/resources/{item['id']}/complete", json={"completed": True})

    assert completed.status_code == 200 and completed.json()["completed"] is True

    reverted = client.post(f"/api/v1/resources/{item['id']}/complete", json={"completed": False})

    assert reverted.status_code == 200 and reverted.json()["completed"] is False
