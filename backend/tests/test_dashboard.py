from datetime import date
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.services.dashboard_service import build_dashboard_summary

client = TestClient(app)


def snapshot(**overrides):
    base = {
        "experiences": [],
        "jobs": [],
        "latest_job": None,
        "materials": [],
        "application": None,
        "questions": [],
        "tracked": [],
    }

    return {**base, **overrides}


def test_empty_dashboard_directs_user_to_upload_cv():
    result = build_dashboard_summary(snapshot(), date(2026, 8, 13))

    assert result["next_action"]["target"] == "profile"

    assert result["steps"][0]["status"] == "current"

    assert result["experience_total"] == 0


def test_dashboard_requires_confirmation_before_job_analysis():
    experience = SimpleNamespace(confirmed=False)

    result = build_dashboard_summary(snapshot(experiences=[experience]), date(2026, 8, 13))

    assert result["next_action"]["title"] == "确认个人经历"

    assert result["pending_experiences"] == 1


def test_dashboard_does_not_skip_remaining_unconfirmed_experiences():
    experiences = [SimpleNamespace(confirmed=True), SimpleNamespace(confirmed=False)]

    result = build_dashboard_summary(snapshot(experiences=experiences), date(2026, 8, 13))

    assert result["next_action"]["target"] == "profile"

    assert result["confirmed_experiences"] == 1


def test_complete_materials_advance_to_required_application_answers():
    job = SimpleNamespace(id=7, title="AI Intern", company="Polymer")

    application = SimpleNamespace(id=9)

    questions = [
        SimpleNamespace(required=True, answer={}),
        SimpleNamespace(required=False, answer={}),
    ]

    result = build_dashboard_summary(
        snapshot(
            experiences=[SimpleNamespace(confirmed=True)],
            jobs=[job],
            latest_job=job,
            materials=[
                SimpleNamespace(material_type="resume"),
                SimpleNamespace(material_type="cover_letter"),
            ],
            application=application,
            questions=questions,
        ),
        date(2026, 8, 13),
    )

    assert result["next_action"]["target"] == "form"

    assert "1 个必填问题" in result["next_action"]["description"]


def test_completed_workflow_shows_linked_tracker_and_upcoming_deadline():
    job = SimpleNamespace(id=7, title="AI Intern", company="Polymer")

    application = SimpleNamespace(id=9)

    question = SimpleNamespace(required=True, answer={"result": {"text": "Ready"}})

    tracked = SimpleNamespace(
        id=3,
        job_id=7,
        company="Polymer",
        role="AI Intern",
        deadline=date(2026, 8, 20),
        status="applied",
    )
    result = build_dashboard_summary(
        snapshot(
            experiences=[SimpleNamespace(confirmed=True)],
            jobs=[job],
            latest_job=job,
            materials=[
                SimpleNamespace(material_type="resume"),
                SimpleNamespace(material_type="cover_letter"),
            ],
            application=application,
            questions=[question],
            tracked=[tracked],
        ),
        date(2026, 8, 13),
    )

    assert result["next_action"]["title"] == "检查申请进度"

    assert result["steps"][-1]["status"] == "complete"

    assert result["upcoming_deadlines"][0]["deadline"] == date(2026, 8, 20)


def test_dashboard_keeps_all_saved_tracker_dates_not_only_the_next_14_days():
    tracked = SimpleNamespace(
        id=3,
        job_id=7,
        company="Polymer",
        role="AI Intern",
        deadline=date(2026, 10, 20),
        interview_date=date(2026, 9, 3),
        follow_up_at=date(2026, 8, 28),
        status="saved",
    )

    result = build_dashboard_summary(snapshot(tracked=[tracked]), date(2026, 8, 13))

    assert [event["kind"] for event in result["upcoming_deadlines"]] == [
        "follow_up",
        "interview",
        "deadline",
    ]
    assert result["upcoming_deadlines"][-1]["deadline"] == date(2026, 10, 20)
    assert result["upcoming_deadlines"][0]["job_id"] == 7


def test_dashboard_summary_endpoint_contract():
    response = client.get("/api/v1/dashboard/summary")

    assert response.status_code == 200

    body = response.json()

    assert {"steps", "next_action", "experience_total", "active_applications"}.issubset(body)

    assert len(body["steps"]) == 5

    # Per-role completion must survive FastAPI response serialization. The
    # frontend uses these fields to render independent progress for each job.
    for workspace in body.get("job_workspaces", []):
        assert 0 <= workspace["progress"] <= 100
        assert len(workspace["steps"]) == 5
