from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.config import settings
from app.db.session import SessionLocal
from app.main import app
from app.models.user import User
from app.services.deadline_reminder_service import run_deadline_reminder_scan


client = TestClient(app)


def test_interview_coach_persists_grounded_fallback_feedback():
    created = client.post(
        "/api/v1/tracker/applications",
        json={"company": "Coach Demo", "role": "Research Intern"},
    )
    assert created.status_code == 200
    application_id = created.json()["id"]

    coached = client.post(
        f"/api/v1/tracker/applications/{application_id}/interview-review/coach",
        json={
            "questions": "How did you validate your analysis?",
            "strengths": "I explained the assumptions clearly.",
            "improvements": "Give a more structured result.",
            "next_steps": "Practise a two-minute answer.",
            "output_language": "en",
        },
    )
    assert coached.status_code == 200, coached.text
    review = coached.json()["interview_review"]
    assert review["ai_feedback"]["generation_method"] == "rules"
    assert review["ai_feedback"]["summary"]
    listed = client.get("/api/v1/tracker/applications").json()
    assert next(item for item in listed if item["id"] == application_id)["interview_review"]


def test_deadline_scan_uses_local_hour_and_is_idempotent(monkeypatch):
    previous_mode = settings.mail_delivery_mode
    settings.mail_delivery_mode = "smtp"
    sent: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        "app.services.deadline_reminder_service.deliver_account_email",
        lambda recipient, subject, text: sent.append((recipient, subject, text)),
    )
    due = date.today() + timedelta(days=1)
    created = client.post(
        "/api/v1/tracker/applications",
        json={
            "company": "Reminder Demo",
            "role": "Platform Intern",
            "deadline": due.isoformat(),
        },
    )
    assert created.status_code == 200
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "local@applyease.dev"))
        assert user is not None
        user.timezone = "Asia/Hong_Kong"
        user.deadline_reminders_enabled = True
        user.deadline_reminder_days = 7
        user.deadline_reminder_hour = 9
        db.commit()
        local_now = datetime.combine(due - timedelta(days=1), datetime.min.time()).replace(
            hour=9, tzinfo=timezone(timedelta(hours=8))
        )
        assert run_deadline_reminder_scan(db, now=local_now) >= 1
        first_count = len(sent)
        run_deadline_reminder_scan(db, now=local_now)
        assert len(sent) == first_count
    settings.mail_delivery_mode = previous_mode
