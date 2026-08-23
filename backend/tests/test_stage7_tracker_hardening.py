from datetime import date, timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.services.dashboard_service import build_dashboard_summary

client = TestClient(app)


def test_tracker_filters_and_action_metadata():
    today = date.today()

    overdue = client.post(
        "/api/v1/tracker/applications",
        json={
            "company": "Stage7 Overdue",
            "role": "Quant Intern",
            "deadline": (today - timedelta(days=1)).isoformat(),
            "status": "applied",
            "follow_up_at": today.isoformat(),
        },
    )

    assert overdue.status_code == 200, overdue.text

    assert overdue.json()["is_overdue"] is True

    assert overdue.json()["is_follow_up_due"] is True

    assert overdue.json()["next_action"]

    filtered = client.get(
        "/api/v1/tracker/applications", params={"status": "applied", "sort": "follow_up"}
    )

    assert filtered.status_code == 200

    assert all(item["status"] == "applied" for item in filtered.json())

    assert any(item["company"] == "Stage7 Overdue" for item in filtered.json())

    invalid_range = client.get(
        "/api/v1/tracker/applications", params={"from_date": "2026-09-02", "to_date": "2026-09-01"}
    )

    assert invalid_range.status_code == 422


def test_tracker_summary_and_validation():
    response = client.get("/api/v1/tracker/applications/summary")

    assert response.status_code == 200

    body = response.json()

    assert set(("total", "by_status", "active", "overdue", "follow_ups_due")) <= set(body)

    assert body["total"] >= body["active"]

    blank = client.post("/api/v1/tracker/applications", json={"company": "   ", "role": "Intern"})

    assert blank.status_code == 422

    invalid_job = client.post(
        "/api/v1/tracker/applications",
        json={"company": "No Job", "role": "Intern", "job_id": 999999999},
    )

    assert invalid_job.status_code == 404

    too_large = client.get("/api/v1/tracker/applications", params={"limit": 501})

    assert too_large.status_code == 422


def test_dashboard_includes_due_follow_up_event():
    today = date(2026, 8, 13)

    tracked = SimpleNamespace(
        id=8,
        job_id=None,
        company="FollowCo",
        role="Research Intern",
        deadline=None,
        follow_up_at=date(2026, 8, 14),
        status="applied",
    )
    snapshot = {
        "experiences": [],
        "jobs": [],
        "latest_job": None,
        "materials": [],
        "application": None,
        "questions": [],
        "tracked": [tracked],
    }
    result = build_dashboard_summary(snapshot, today)

    assert result["upcoming_deadlines"][0]["kind"] == "follow_up"

    assert result["upcoming_deadlines"][0]["deadline"] == date(2026, 8, 14)


def test_submitted_item_without_real_date_has_no_generic_next_action_and_can_return_to_saved():
    created = client.post(
        "/api/v1/tracker/applications",
        json={
            "company": "Tracker State Test",
            "role": "State Transition Intern",
            "status": "applied",
        },
    )
    assert created.status_code == 200, created.text
    application_id = created.json()["id"]
    assert created.json()["next_action"] is None

    moved_back = client.patch(
        f"/api/v1/tracker/applications/{application_id}",
        json={"status": "saved"},
    )
    assert moved_back.status_code == 200, moved_back.text
    assert moved_back.json()["status"] == "saved"
    assert moved_back.json()["next_action"] == "准备并提交申请"

    deleted = client.delete(f"/api/v1/tracker/applications/{application_id}")
    assert deleted.status_code == 204
