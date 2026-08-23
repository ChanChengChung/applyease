"""Calendar and reminder helpers for the application tracker."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

from app.models.tracker import TrackedApplication
from app.services.tracker_service import ACTIVE_STATUSES


def _ics_text(value: str) -> str:
    """Escape RFC 5545 text values and strip unsupported control characters."""
    value = value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
    value = value.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")
    return "".join(char for char in value if ord(char) >= 32 or char == "\t")


def _event(item: TrackedApplication, kind: str, due: date) -> list[str]:
    labels = {
        "deadline": ("提交申请", "申请截止日"),
        "follow_up": ("跟进申请", "跟进日期"),
        "interview": ("准备面试", "面试日期"),
    }
    action, label = labels[kind]
    subject = f"{item.company} — {item.role}"
    description = f"{label}：{subject}" + (f"\\n备注：{item.notes}" if item.notes else "")
    return [
        "BEGIN:VEVENT",
        f"UID:applyease-{item.id}-{kind}@local",
        f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART;VALUE=DATE:{due.strftime('%Y%m%d')}",
        f"DTEND;VALUE=DATE:{(due + timedelta(days=1)).strftime('%Y%m%d')}",
        f"SUMMARY:{_ics_text(f'ApplyEase：{action} — {subject}')}",
        f"DESCRIPTION:{_ics_text(description)}",
        "STATUS:CONFIRMED",
        "END:VEVENT",
    ]


def build_calendar(item: TrackedApplication) -> bytes:
    """Build an all-day iCalendar file without inventing meeting times/time zones."""
    events = [
        _event(item, kind, due)
        for kind, due in (
            ("deadline", item.deadline),
            ("follow_up", item.follow_up_at),
            ("interview", item.interview_date),
        )
        if due
    ]
    if not events:
        raise ValueError("No deadline, follow-up date, or interview date to export")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ApplyEase//Application Tracker//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    for event in events:
        lines.extend(event)
    return ("\r\n".join([*lines, "END:VCALENDAR"]) + "\r\n").encode("utf-8")


def calendar_filename(item: TrackedApplication) -> str:
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", f"ApplyEase-{item.company}-{item.role}").strip("-")[:100]
    return f"{stem or 'ApplyEase-application'}-reminders.ics"


def build_reminders(
    items: list[TrackedApplication], *, today: date | None = None, days: int = 14
) -> list[dict]:
    """Return actionable overdue and near-term dates in attention order."""
    today = today or date.today()
    horizon = today + timedelta(days=days)
    labels = {"deadline": "申请截止", "follow_up": "跟进申请", "interview": "面试"}
    reminders: list[dict] = []
    for item in items:
        if item.status not in ACTIVE_STATUSES:
            continue
        for kind, due in (
            ("deadline", item.deadline),
            ("follow_up", item.follow_up_at),
            ("interview", item.interview_date),
        ):
            if due is None or due > horizon:
                continue
            state = "overdue" if due < today else "today" if due == today else "upcoming"
            reminders.append(
                {
                    "application_id": item.id,
                    "kind": kind,
                    "due_date": due,
                    "state": state,
                    "company": item.company,
                    "role": item.role,
                    "title": f"{labels[kind]}：{item.company} · {item.role}",
                }
            )
    priority = {"overdue": 0, "today": 1, "upcoming": 2}
    return sorted(
        reminders,
        key=lambda value: (
            priority[value["state"]],
            value["due_date"],
            value["application_id"],
            value["kind"],
        ),
    )
