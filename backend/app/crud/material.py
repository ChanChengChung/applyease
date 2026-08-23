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
