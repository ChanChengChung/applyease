from datetime import date

from sqlalchemy import delete as sa_delete, select
from sqlalchemy.orm import Session

from app.models.tracker import TrackedApplication


def list_all(
    db: Session,
    *,
    status: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    sort: str = "deadline",
    limit: int = 200,
    offset: int = 0
):
    statement = select(TrackedApplication)

    if status:
        statement = statement.where(TrackedApplication.status == status)

    if from_date:
        statement = statement.where(TrackedApplication.deadline >= from_date)

    if to_date:
        statement = statement.where(TrackedApplication.deadline <= to_date)

    if sort == "created_at":
        statement = statement.order_by(
            TrackedApplication.created_at.desc(), TrackedApplication.id.desc()
        )

    elif sort == "follow_up":
        statement = statement.order_by(
            TrackedApplication.follow_up_at.asc().nullslast(), TrackedApplication.id.desc()
        )

    else:
        statement = statement.order_by(
            TrackedApplication.deadline.asc().nullslast(),
            TrackedApplication.created_at.desc(),
            TrackedApplication.id.desc(),
        )

    return db.scalars(statement.limit(limit).offset(offset)).all()


def get(db: Session, item_id: int):

    return db.get(TrackedApplication, item_id)


def get_for_user(db: Session, item_id: int, user_id: int | None):
    """Fetch a tracker record while preserving tenant isolation."""
    return db.scalar(
        select(TrackedApplication).where(
            TrackedApplication.id == item_id,
            TrackedApplication.user_id == user_id,
        )
    )


def get_by_job(db: Session, user_id: int | None, job_id: int) -> TrackedApplication | None:
    """Return the one tracker record permitted for a role in a user's workspace."""
    return db.scalar(
        select(TrackedApplication).where(
            TrackedApplication.user_id == user_id,
            TrackedApplication.job_id == job_id,
        )
    )


def create(db: Session, *, commit: bool = True, **values):
    item = TrackedApplication(**values)

    db.add(item)
    if commit:
        db.commit()
        db.refresh(item)
    else:
        db.flush()

    return item


def commit_import_and_track(db: Session, job, tracker: TrackedApplication) -> None:
    """Atomically persist the reviewed role and its tracker entry."""
    db.commit()
    db.refresh(job)
    db.refresh(tracker)


def rollback_import_and_track(db: Session) -> None:
    db.rollback()


def update(db: Session, item: TrackedApplication, values: dict):

    for key, value in values.items():
        setattr(item, key, value)
    db.commit()

    db.refresh(item)

    return item


def delete(db: Session, item: TrackedApplication):
    db.delete(item)

    db.commit()


def delete_for_user(db: Session, item_id: int, user_id: int | None) -> bool:
    """Delete one unlinked application by its immutable record id.

    Company names are deliberately not part of this predicate: the same
    employer can have several distinct roles and each must remain independent.
    """
    result = db.execute(
        sa_delete(TrackedApplication).where(
            TrackedApplication.id == item_id,
            TrackedApplication.user_id == user_id,
        )
    )
    db.commit()
    return bool(result.rowcount)
