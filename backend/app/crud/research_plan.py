from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.research_plan import ResearchPlan


def latest_for_job(
    db: Session,
    user_id: int,
    job_id: int,
    starter_plan_id: int | None = None,
    *,
    match_starter_plan: bool = False,
) -> ResearchPlan | None:
    """Return the current saved plan for one user's target role."""
    statement = select(ResearchPlan).where(
        ResearchPlan.user_id == user_id, ResearchPlan.job_id == job_id
    )
    if match_starter_plan:
        if starter_plan_id is None:
            statement = statement.where(ResearchPlan.starter_plan_id.is_(None))
        else:
            statement = statement.where(ResearchPlan.starter_plan_id == starter_plan_id)
    return db.scalar(statement.order_by(ResearchPlan.updated_at.desc(), ResearchPlan.id.desc()))


def list_for_job(
    db: Session,
    user_id: int,
    job_id: int,
    starter_plan_id: int | None = None,
    *,
    match_starter_plan: bool = False,
) -> list[ResearchPlan]:
    statement = select(ResearchPlan).where(
        ResearchPlan.user_id == user_id, ResearchPlan.job_id == job_id
    )
    if match_starter_plan:
        if starter_plan_id is None:
            statement = statement.where(ResearchPlan.starter_plan_id.is_(None))
        else:
            statement = statement.where(ResearchPlan.starter_plan_id == starter_plan_id)
    return list(db.scalars(statement.order_by(ResearchPlan.updated_at.desc(), ResearchPlan.id.desc())).all())


def create_or_replace(db: Session, user_id: int, job_id: int, values: dict) -> ResearchPlan:
    """Keep one editable plan per user, job, and optional starter plan.

    Re-running research refreshes the matching plan.  Different starter plans
    intentionally get separate records so a student can compare preparation
    paths for the same role without silently overwriting either one.
    """
    has_starter_link = "starter_plan_id" in values
    item = latest_for_job(
        db,
        user_id,
        job_id,
        values.get("starter_plan_id"),
        match_starter_plan=has_starter_link,
    )
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
