from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.research_plan import ResearchPlan


def latest_for_job(db: Session, user_id: int, job_id: int) -> ResearchPlan | None:
    """Return the current saved plan for one user's target role."""
    return db.scalar(
        select(ResearchPlan)
        .where(ResearchPlan.user_id == user_id, ResearchPlan.job_id == job_id)
        .order_by(ResearchPlan.updated_at.desc(), ResearchPlan.id.desc())
    )


def create_or_replace(db: Session, user_id: int, job_id: int, values: dict) -> ResearchPlan:
    """Keep one editable current plan per user and job.

    Re-running research refreshes the existing plan rather than leaving hidden,
    stale duplicates in the user's account.
    """
    item = latest_for_job(db, user_id, job_id)
    if item is None:
        item = ResearchPlan(user_id=user_id, job_id=job_id, **values)
        db.add(item)
    else:
        for key, value in values.items():
            setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def get(db: Session, plan_id: int, user_id: int) -> ResearchPlan | None:
    return db.scalar(
        select(ResearchPlan).where(ResearchPlan.id == plan_id, ResearchPlan.user_id == user_id)
    )


def update(db: Session, item: ResearchPlan, values: dict) -> ResearchPlan:
    for key, value in values.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


def delete(db: Session, item: ResearchPlan) -> None:
    db.delete(item)
    db.commit()
