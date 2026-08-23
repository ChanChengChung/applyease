import uuid

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_confirmed_experience_has_visible_downstream_job_impact():
    register = client.post(
        "/api/v1/auth/register",
        headers={"X-ApplyEase-Client": "browser-extension"},
        json={
            "email": f"impact-{uuid.uuid4().hex[:12]}@example.com",
            "password": "secure-pass-123",
        },
    )
    assert register.status_code == 201, register.text
    headers = {"Authorization": f"Bearer {register.json()['access_token']}"}
    experience = client.post(
        "/api/v1/experiences",
        headers=headers,
        json={
            "title": "Python API Evidence",
            "organization": "University Project",
            "description": "Built and tested Python APIs with clear documentation.",
            "skills": ["Python", "REST APIs"],
            "achievements": [],
            "source_file": "portfolio",
            "confirmed": True,
        },
    )
    assert experience.status_code == 200, experience.text
    job = client.post(
        "/api/v1/jobs/analyze",
        headers=headers,
        json={
            "title": "Backend Intern",
            "company": "Example Systems",
            "description": "Required: Python. Build and test APIs for an engineering team.",
        },
    )
    assert job.status_code == 200, job.text

    impacts = client.get("/api/v1/experiences/evidence-impact", headers=headers)
    assert impacts.status_code == 200, impacts.text
    impact = next(
        item for item in impacts.json() if item["experience_id"] == experience.json()["id"]
    )
    assert impact["confirmed"] is True
    assert impact["skills_available"] == ["Python", "REST APIs"]
    assert impact["supported_jobs"][0]["job_id"] == job.json()["id"]
