from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from app.models.application import Application, ApplicationQuestion
from app.models.job import Job
from app.models.material import GeneratedMaterial
from app.models.research_plan import ResearchPlan
from app.models.tracker import TrackedApplication


def get(db: Session, job_id: int):
    return db.get(Job, job_id)


def get_for_user(db: Session, job_id: int, user_id: int | None) -> Job | None:
    return db.scalar(select(Job).where(Job.id == job_id, Job.user_id == user_id))


def list_recent(db: Session, user_id: int | None, *, limit: int = 30) -> list[Job]:
    """Return the current user's most recently analysed target roles."""
    return list(
        db.scalars(
            select(Job).where(Job.user_id == user_id).order_by(Job.created_at.desc()).limit(limit)
        ).all()
    )


def create(db: Session, **values):
    item = Job(**values)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def delete_for_user(db: Session, job_id: int, user_id: int | None) -> bool:
    """Delete a target role and its generated workspace artifacts safely.

    Experience Bank records are deliberately not touched. Every artifact and
    tracker entry derived from this target role is deleted so no role-specific
    application data survives after a user explicitly removes the workspace.
    """
    item = db.scalar(select(Job).where(Job.id == job_id, Job.user_id == user_id))
    if not item:
        return False

    application_ids = list(
        db.scalars(
            select(Application.id).where(
                Application.user_id == user_id, Application.job_id == job_id
            )
        ).all()
    )
    if application_ids:
        db.execute(
            delete(ApplicationQuestion).where(
                ApplicationQuestion.user_id == user_id,
                ApplicationQuestion.application_id.in_(application_ids),
            )
        )
    db.execute(
        delete(Application).where(Application.user_id == user_id, Application.job_id == job_id)
    )
    db.execute(
        delete(GeneratedMaterial).where(
            GeneratedMaterial.user_id == user_id, GeneratedMaterial.job_id == job_id
        )
    )
    db.execute(
        delete(ResearchPlan).where(ResearchPlan.user_id == user_id, ResearchPlan.job_id == job_id)
    )
    db.execute(
        delete(TrackedApplication).where(
            TrackedApplication.user_id == user_id, TrackedApplication.job_id == job_id
        )
    )
    db.delete(item)
    db.commit()
    return True
