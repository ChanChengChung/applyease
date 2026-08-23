from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.application import Application, ApplicationQuestion
from app.models.experience import Experience
from app.models.job import Job
from app.models.material import GeneratedMaterial
from app.models.tracker import TrackedApplication


def get_snapshot(db: Session) -> dict:
    experiences = db.scalars(select(Experience).order_by(Experience.id)).all()

    jobs = db.scalars(select(Job).order_by(Job.created_at.desc(), Job.id.desc())).all()

    latest_job = jobs[0] if jobs else None

    all_materials = db.scalars(
        select(GeneratedMaterial).order_by(
            GeneratedMaterial.created_at.desc(), GeneratedMaterial.id.desc()
        )
    ).all()
    materials = [item for item in all_materials if latest_job and item.job_id == latest_job.id]

    all_applications = db.scalars(
        select(Application).order_by(Application.created_at.desc(), Application.id.desc())
    ).all()
    application = (
        db.scalar(
            select(Application)
            .where(Application.job_id == latest_job.id)
            .order_by(Application.created_at.desc(), Application.id.desc())
        )
        if latest_job
        else None
    )

    all_questions = db.scalars(select(ApplicationQuestion).order_by(ApplicationQuestion.id)).all()
    questions = [
        item for item in all_questions if application and item.application_id == application.id
    ]

    tracked = db.scalars(
        select(TrackedApplication).order_by(
            TrackedApplication.deadline.asc().nullslast(), TrackedApplication.created_at.desc()
        )
    ).all()

    return {
        "experiences": experiences,
        "jobs": jobs,
        "latest_job": latest_job,
        "materials": materials,
        "all_materials": all_materials,
        "application": application,
        "all_applications": all_applications,
        "questions": questions,
        "all_questions": all_questions,
        "tracked": tracked,
    }
