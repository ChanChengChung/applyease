from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.material import GeneratedMaterial


def get(db: Session, material_id: int):

    return db.get(GeneratedMaterial, material_id)


def list_by_job(db: Session, job_id: int, material_type: str | None = None):
    statement = select(GeneratedMaterial).where(GeneratedMaterial.job_id == job_id)

    if material_type:
        statement = statement.where(GeneratedMaterial.material_type == material_type)

    return db.scalars(
        statement.order_by(GeneratedMaterial.created_at.desc(), GeneratedMaterial.id.desc())
    ).all()


def list_all(db: Session, *, limit: int = 500):
    return db.scalars(
        select(GeneratedMaterial)
        .order_by(GeneratedMaterial.created_at.desc(), GeneratedMaterial.id.desc())
        .limit(limit)
    ).all()


def create(db: Session, job_id: int, material_type: str, content: dict):
    record = GeneratedMaterial(job_id=job_id, material_type=material_type, content=content)

    db.add(record)

    db.commit()

    db.refresh(record)

    return record


def update_content(db: Session, record: GeneratedMaterial, content: dict):
    record.content = content

    db.commit()

    db.refresh(record)

    return record


def create_edit_snapshot(db: Session, record: GeneratedMaterial):
    """Keep the pre-edit material as a recoverable history version."""
    snapshot = GeneratedMaterial(
        user_id=record.user_id,
        job_id=record.job_id,
        material_type=record.material_type,
        content=dict(record.content or {}),
        # Keep the live edited record newer than its snapshot in history lists.
        created_at=(record.created_at - timedelta(microseconds=1)) if record.created_at else None,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot
