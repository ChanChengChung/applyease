from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_job_analysis_extracts_requirements_and_matches_confirmed_evidence():
    experience = client.post(
        "/api/v1/experiences",
        json={
            "title": "ML Research Project",
            "organization": "CUHK",
            "description": "Built a Transformer model and evaluated it with Python and PyTorch.",
            "skills": ["Python", "PyTorch", "Transformer"],
            "confirmed": True,
            "achievements": [
                {"text": "Reduced inference latency by 20%", "source": "project", "verified": True}
            ],
        },
    ).json()

    job = client.post(
        "/api/v1/jobs/analyze",
        json={
            "title": "AI Research Intern",
            "company": "Example",
            "description": "Required: Python, PyTorch and C++. Develop machine learning models.",
        },
    )

    assert job.status_code == 200

    job_data = job.json()

    assert "Python" in job_data["required_skills"]

    assert job_data["id"] > 0

    report = client.get(f"/api/v1/jobs/{job_data['id']}/match-report")

    assert report.status_code == 200

    data = report.json()

    assert "Python" in data["matched_skills"]

    assert "C++" in data["missing_skills"]

    assert any(item["experience_id"] == experience["id"] for item in data["evidence"])


def test_unconfirmed_experience_is_not_used_as_evidence():
    client.post(
        "/api/v1/experiences",
        json={"title": "Unconfirmed", "description": "Python C++ project", "confirmed": False},
    )

    job = client.post(
        "/api/v1/jobs/analyze",
        json={"title": "Developer", "description": "Python and C++ required for this role."},
    ).json()

    report = client.get(f"/api/v1/jobs/{job['id']}/match-report").json()

    assert all(item["experience_id"] != 999999 for item in report["evidence"])

    assert report["considered_experience_ids"]


def test_job_description_validation_and_missing_job():
    assert client.post("/api/v1/jobs/analyze", json={"description": "too short"}).status_code == 422

    assert client.get("/api/v1/jobs/999999/match-report").status_code == 404
