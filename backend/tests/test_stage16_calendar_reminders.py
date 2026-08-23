from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _token(email: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        headers={"X-ApplyEase-Client": "browser-extension"},
        json={"email": email, "password": "secure-pass-123"},
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def test_reminder_window_excludes_inactive_records_and_calendar_is_valid():
    token = _token("stage16-calendar-owner@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    today = date.today()
    created = client.post(
        "/api/v1/tracker/applications",
        headers=headers,
        json={
            "company": "Comma, Co; \\ Lab",
            "role": "Research Intern",
            "status": "applied",
            "deadline": (today - timedelta(days=1)).isoformat(),
            "follow_up_at": today.isoformat(),
            "interview_date": (today + timedelta(days=2)).isoformat(),
            "notes": "Bring CV\nAsk about research",
        },
    )
    assert created.status_code == 200, created.text
    item_id = created.json()["id"]
    inactive = client.post(
        "/api/v1/tracker/applications",
        headers=headers,
        json={
            "company": "Closed Co",
            "role": "Intern",
            "status": "rejected",
            "deadline": today.isoformat(),
        },
    )
    assert inactive.status_code == 200

    reminders = client.get("/api/v1/tracker/applications/reminders?days=7", headers=headers)
    assert reminders.status_code == 200, reminders.text
    body = reminders.json()
    assert [entry["state"] for entry in body if entry["application_id"] == item_id] == [
        "overdue",
        "today",
        "upcoming",
    ]
    assert all(entry["company"] != "Closed Co" for entry in body)
    assert (
        client.get("/api/v1/tracker/applications/reminders?days=0", headers=headers).status_code
        == 422
    )

    exported = client.get(f"/api/v1/tracker/applications/{item_id}/calendar", headers=headers)
    assert exported.status_code == 200, exported.text
    assert exported.headers["content-type"].startswith("text/calendar")
    assert exported.headers["content-disposition"].endswith('.ics"')
    content = exported.content.decode()
    assert content.startswith("BEGIN:VCALENDAR\r\n") and content.endswith("END:VCALENDAR\r\n")
    assert content.count("BEGIN:VEVENT") == 3
    assert "Comma\\, Co\\; \\\\ Lab" in content
    assert "Bring CV\\nAsk about research" in content
    assert "\n" not in content.replace("\r\n", "")


def test_calendar_requires_dates_and_respects_owner_isolation():
    owner = _token("stage16-calendar-a@example.com")
    other = _token("stage16-calendar-b@example.com")
    created = client.post(
        "/api/v1/tracker/applications",
        headers={"Authorization": f"Bearer {owner}"},
        json={"company": "Private Co", "role": "Quant Intern", "status": "saved"},
    )
    assert created.status_code == 200
    item_id = created.json()["id"]
    owner_headers = {"Authorization": f"Bearer {owner}"}
    assert (
        client.get(
            f"/api/v1/tracker/applications/{item_id}/calendar", headers=owner_headers
        ).status_code
        == 422
    )
    assert (
        client.get(
            f"/api/v1/tracker/applications/{item_id}/calendar",
            headers={"Authorization": f"Bearer {other}"},
        ).status_code
        == 404
    )
