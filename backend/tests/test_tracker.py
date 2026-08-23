from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_tracker_crud_and_status_validation():
    created = client.post(
        "/api/v1/tracker/applications",
        json={
            "company": "Demo",
            "role": "AI Intern",
            "deadline": "2026-09-01",
            "status": "saved",
            "notes": "Follow up after assessment",
        },
    )

    assert created.status_code == 200

    item = created.json()
    assert item["company"] == "Demo"

    updated = client.patch(
        f"/api/v1/tracker/applications/{item['id']}",
        json={"status": "interview", "interview_date": "2026-09-03"},
    )

    assert updated.status_code == 200 and updated.json()["status"] == "interview"

    assert (
        client.patch(
            f"/api/v1/tracker/applications/{item['id']}", json={"status": "unknown"}
        ).status_code
        == 422
    )

    assert client.delete(f"/api/v1/tracker/applications/{item['id']}").status_code == 204

    assert client.delete(f"/api/v1/tracker/applications/{item['id']}").status_code == 404


def test_tracker_required_fields():
    assert client.post("/api/v1/tracker/applications", json={"company": ""}).status_code == 422


def test_workspace_aggregates_job_linked_application_artifacts():
    experience = client.post(
        "/api/v1/experiences",
        json={
            "title": "Python Project",
            "organization": "HKU",
            "description": "Built a Python analysis pipeline.",
            "skills": ["Python"],
            "confirmed": True,
        },
    )
    assert experience.status_code == 200
    job = client.post(
        "/api/v1/jobs/analyze",
        json={
            "title": "Quant Intern",
            "company": "Demo",
            "description": "Python and C++ required.",
        },
    ).json()
    client.post(f"/api/v1/materials/resume/generate?job_id={job['id']}")
    tracked = client.post(
        "/api/v1/tracker/applications",
        json={"company": "Demo", "role": "Quant Intern", "job_id": job["id"]},
    ).json()

    workspace = client.get(f"/api/v1/tracker/applications/{tracked['id']}/workspace")
    assert workspace.status_code == 200, workspace.text
    body = workspace.json()
    assert body["job_id"] == job["id"]
    assert body["evidence_count"] >= 1
    assert "resume" in body["material_types"]
    assert "C++" in body["missing_skills"]
    # The tracker is a shared job workspace, not an isolated checklist: even
    # before a study plan is generated it returns explicit plan metadata for
    # the frontend to render the correct next action.
    assert body["learning_plan_id"] is None
    assert body["learning_plan_steps"] == 0
    assert body["learning_plan_sources"] == 0


def test_tracker_reuses_existing_record_for_the_same_job():
    job = client.post(
        "/api/v1/jobs/analyze",
        json={
            "title": "One role, one tracker",
            "company": "ApplyEase Test",
            "description": "Python programming experience is required.",
        },
    ).json()

    first = client.post(
        "/api/v1/tracker/applications",
        json={"company": "ApplyEase Test", "role": "One role, one tracker", "job_id": job["id"]},
    )
    second = client.post(
        "/api/v1/tracker/applications",
        json={"company": "ApplyEase Test", "role": "One role, one tracker", "job_id": job["id"]},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
