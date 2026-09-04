from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_stage8_core_application_workflow_contract():
    cv = b"""WORK EXPERIENCE\nAI Developer | ApplyEase Demo\nBuilt a React and FastAPI application platform.\nImproved conversion by 8%.\n\nRESEARCH EXPERIENCE\nResearch Assistant | HKU\nImplemented PyTorch Transformer experiments.\n"""

    uploaded = client.post(
        "/api/v1/documents/upload", files={"file": ("stage8-demo.txt", cv, "text/plain")}
    )

    assert uploaded.status_code == 200, uploaded.text

    experiences = uploaded.json()["experiences"]

    assert experiences and all(item["confirmed"] is False for item in experiences)

    confirmed = client.post(
        "/api/v1/experiences/bulk-confirm", json={"ids": [item["id"] for item in experiences]}
    )

    assert confirmed.status_code == 200 and confirmed.json()["updated"] == len(experiences)

    job = client.post(
        "/api/v1/jobs/analyze",
        json={
            "title": "AI and Quantitative Technology Intern",
            "company": "Polymer Capital",
            "description": "Build AI tools with Python, React and FastAPI for quantitative technology teams.",
        },
    )

    assert job.status_code == 200, job.text

    job_id = job.json()["id"]

    report = client.get(f"/api/v1/jobs/{job_id}/match-report")

    assert report.status_code == 200

    assert {item["id"] for item in experiences}.issubset(
        set(report.json()["considered_experience_ids"])
    )

    resume = client.post(f"/api/v1/materials/resume/generate?job_id={job_id}")

    cover = client.post(f"/api/v1/materials/cover-letter/generate?job_id={job_id}")

    assert resume.status_code == 200 and cover.status_code == 200

    assert resume.json()["fact_check_passed"] is True

    application = client.post(
        "/api/v1/applications/questions/detect",
        json={
            "job_id": job_id,
            "raw_text": "Why are you interested in this role?\nWork authorization *",
        },
    )

    assert application.status_code == 200

    generated = client.post(
        f"/api/v1/applications/{application.json()['id']}/answers/generate-all", json={}
    )

    assert generated.status_code == 202
    task = generated.json()
    assert task["task_id"]
    assert task["status"] in {"queued", "running", "completed", "completed_with_errors"}
    if task["status"] in {"queued", "running"}:
        task = client.get(f"/api/v1/applications/batch-tasks/{task['task_id']}").json()
    assert any(item["status"] == "generated" for item in task["results"])
    assert any(item["status"] == "manual_required" for item in task["results"])

    manual_question = next(
        item
        for item in application.json()["questions"]
        if "authorization" in item["question"].lower()
    )

    manual_saved = client.patch(
        f"/api/v1/applications/{application.json()['id']}/questions/{manual_question['id']}/answer",
        json={"answer": "I will provide my confirmed work authorization details."},
    )

    assert manual_saved.status_code == 200

    all_experiences = client.get("/api/v1/experiences").json()

    all_confirmed = client.post(
        "/api/v1/experiences/bulk-confirm", json={"ids": [item["id"] for item in all_experiences]}
    )

    assert all_confirmed.status_code == 200

    deadline = (date.today() + timedelta(days=7)).isoformat()

    tracked = client.post(
        "/api/v1/tracker/applications",
        json={
            "company": "Polymer Capital",
            "role": "AI and Quantitative Technology Intern",
            "job_id": job_id,
            "status": "applied",
            "deadline": deadline,
        },
    )

    assert tracked.status_code == 200

    dashboard = client.get("/api/v1/dashboard/summary")

    assert dashboard.status_code == 200

    body = dashboard.json()

    assert body["next_action"]["target"] == "tracker"

    assert any(item["id"] == tracked.json()["id"] for item in body["upcoming_deadlines"])
