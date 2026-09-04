"""Timezone-aware, idempotent email reminders for tracked deadlines."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db.session import SessionLocal
from app.models.tracker import DeadlineReminderDelivery, TrackedApplication
from app.models.user import User
from app.services.email_service import MailDeliveryError, deliver_account_email

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = ("saved", "applied", "assessment", "interview", "offer")


def _zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("Invalid user timezone %r; using UTC", name)
        return ZoneInfo("UTC")


def _body(item: TrackedApplication, due_date: date, days_until: int, zone: str) -> str:
    if days_until < 0:
        timing = f"This deadline was {abs(days_until)} day(s) ago."
    elif days_until == 0:
        timing = "This deadline is today."
    elif days_until == 1:
        timing = "This deadline is tomorrow."
    else:
        timing = f"This deadline is in {days_until} days."
    return (
        f"ApplyEase deadline reminder\n\n"
        f"{item.company} · {item.role}\n"
        f"Deadline: {due_date.isoformat()} ({zone})\n\n"
        f"{timing}\n"
        f"Open your application tracker to review the next action:\n"
        f"{settings.frontend_base_url.rstrip('/')}/\n"
    )


def run_deadline_reminder_scan(
    db: Session | None = None,
    *,
    now: datetime | None = None,
) -> int:
    """Send each due reminder at the user's local configured hour.

    ``now`` is injectable for tests.  The returned count is the number of
    successfully delivered messages.  A delivery ledger row is claimed before
    sending and is rolled back when the mail transport fails, allowing a later
    scheduler tick to retry safely.
    """
    if settings.mail_delivery_mode == "disabled":
        return 0
    owns_db = db is None
    session = db or SessionLocal()
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    sent = 0
    try:
        users = session.scalars(
            select(User).where(User.deadline_reminders_enabled.is_(True))
        ).all()
        for user in users:
            zone = _zone(user.timezone)
            local_now = current.astimezone(zone)
            # If the process was restarted after the preferred hour, send the
            # same day's reminder on the next tick instead of silently losing
            # it.  The delivery ledger still guarantees one message per day.
            if local_now.hour < int(user.deadline_reminder_hour):
                continue
            apps = session.scalars(
                select(TrackedApplication).where(
                    TrackedApplication.user_id == user.id,
                    TrackedApplication.status.in_(ACTIVE_STATUSES),
                    TrackedApplication.deadline.is_not(None),
                )
            ).all()
            for item in apps:
                due_date = item.deadline
                if due_date is None:
                    continue
                days_until = (due_date - local_now.date()).days
                # Send a single reminder in the configured window, plus one
                # overdue notification on the first day after the deadline.
                if days_until > int(user.deadline_reminder_days) or days_until < -1:
                    continue
                already_sent = session.scalar(
                    select(DeadlineReminderDelivery.id).where(
                        DeadlineReminderDelivery.user_id == user.id,
                        DeadlineReminderDelivery.tracked_application_id == item.id,
                        DeadlineReminderDelivery.kind == "deadline",
                        DeadlineReminderDelivery.due_date == due_date,
                    )
                )
                if already_sent:
                    continue
                delivery = DeadlineReminderDelivery(
                    user_id=user.id,
                    tracked_application_id=item.id,
                    kind="deadline",
                    due_date=due_date,
                    sent_at=datetime.now(timezone.utc).replace(tzinfo=None),
                )
                session.add(delivery)
                try:
                    session.flush()
                except IntegrityError:
                    session.rollback()
                    continue
                try:
                    deliver_account_email(
                        user.email,
                        f"ApplyEase deadline reminder: {item.company} · {item.role}",
                        _body(item, due_date, days_until, user.timezone or "UTC"),
                    )
                    session.commit()
                    sent += 1
                except MailDeliveryError:
                    session.rollback()
                    logger.warning("Deadline reminder delivery failed for user %s", user.id)
        return sent
    finally:
        if owns_db:
            session.close()


async def reminder_scheduler_loop() -> None:
    """Run in the FastAPI process; DB and SMTP work is moved off the event loop."""
    import asyncio

    while True:
        try:
            await asyncio.to_thread(run_deadline_reminder_scan)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Deadline reminder scan failed")
        await asyncio.sleep(settings.deadline_reminder_interval_seconds)
