from __future__ import annotations

from collections import Counter
from datetime import date

from app.models.tracker import TrackedApplication

ACTIVE_STATUSES = {"saved", "applied", "assessment", "interview", "offer"}


def serialize_tracker(item: TrackedApplication, today: date | None = None) -> dict:
    today = today or date.today()

    overdue = bool(item.deadline and item.deadline < today and item.status in ACTIVE_STATUSES)

    follow_up_due = bool(
        item.follow_up_at and item.follow_up_at <= today and item.status in ACTIVE_STATUSES
    )

    if overdue:
        action = "尽快处理已逾期截止日期"

    elif follow_up_due:
        action = "发送 follow-up"

    elif item.status == "saved":
        action = "准备并提交申请"

    elif item.status == "applied":
        # A submitted application needs no generic instruction. Only a real
        # deadline or user-entered follow-up date should surface an action.
        action = None

    elif item.status == "assessment":
        action = "完成 assessment"

    elif item.status == "interview":
        action = "准备面试"

    elif item.status == "offer":
        action = "评估 offer"

    else:
        action = None

    return {
        "id": item.id,
        "company": item.company,
        "role": item.role,
        "job_id": item.job_id,
        "deadline": item.deadline,
        "status": item.status,
        "interview_date": item.interview_date,
        "follow_up_at": item.follow_up_at,
        "notes": item.notes or "",
        "interview_review": item.interview_review,
        "created_at": item.created_at,
        "is_overdue": overdue,
        "is_follow_up_due": follow_up_due,
        "next_action": action,
    }


def build_tracker_summary(items: list[TrackedApplication], today: date | None = None) -> dict:
    today = today or date.today()

    serialized = [serialize_tracker(item, today) for item in items]

    by_status = dict(Counter(item.status for item in items))

    candidates = [
        item
        for item in serialized
        if item["next_action"] is not None
    ]

    candidates.sort(
        key=lambda item: (
            not item["is_overdue"],
            not item["is_follow_up_due"],
            item["deadline"] or date.max,
            item["id"],
        )
    )

    return {
        "total": len(items),
        "by_status": by_status,
        "active": sum(item.status in ACTIVE_STATUSES for item in items),
        "overdue": sum(item["is_overdue"] for item in serialized),
        "follow_ups_due": sum(item["is_follow_up_due"] for item in serialized),
        "next_action": candidates[0] if candidates else None,
    }
