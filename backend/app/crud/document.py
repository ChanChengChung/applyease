from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.experience import Experience


def get_by_sha256(db: Session, digest: str):

    return db.scalar(select(Document).where(Document.sha256 == digest))


def create_with_experiences(db: Session, document_values: dict, experience_values: list[dict]):
    """Atomically persist a document and its extracted experiences.

    A concurrent upload of the same hash resolves to the already-created document.

    """

    document = Document(**document_values)

    records = [Experience(**values, document=document) for values in experience_values]

    db.add(document)

    db.add_all(records)

    try:
        db.commit()

    except IntegrityError:
        db.rollback()

        existing = get_by_sha256(db, document_values["sha256"])

        if existing:

            return existing, list(existing.experiences), False

        raise
    db.refresh(document)

    for record in records:
        db.refresh(record)

    return document, records, True


def ensure_personal_experience(db: Session, document: Document, values: dict) -> list[Experience]:
    """Attach a contact profile to an existing upload once, if it is missing."""
    if any(record.category == "personal" for record in document.experiences):
        return list(document.experiences)
    record = Experience(**values, document=document)
    db.add(record)
    db.commit()
    db.refresh(document)
    return list(document.experiences)


def restore_missing_experiences(
    db: Session, document: Document, experience_values: list[dict]
) -> tuple[list[Experience], bool]:
    """Restore parsed cards removed from an existing upload without duplicating survivors."""

    def fingerprint(values: dict) -> tuple[str, str, str, str]:
        return (
            str(values.get("category") or "other").strip().casefold(),
            str(values.get("title") or "").strip().casefold(),
            str(values.get("organization") or "").strip().casefold(),
            str(values.get("description") or "").strip().casefold(),
        )

    records = list(document.experiences)
    known = {
        fingerprint(
            {
                "category": record.category,
                "title": record.title,
                "organization": record.organization,
                "description": record.description,
            }
        )
        for record in records
    }
    restored = False

    for values in experience_values:
        key = fingerprint(values)
        if key in known:
            continue
        record = Experience(**values, document=document)
        db.add(record)
        records.append(record)
        known.add(key)
        restored = True

    if restored:
        db.commit()
        db.refresh(document)
        records = list(document.experiences)

    return records, restored


def update_metadata(db: Session, document: Document, *, filename: str, content_type: str, text_length: int) -> Document:
    """Persist duplicate-upload metadata without exposing transaction control to routes."""
    try:
        document.filename = filename[:255]
        document.content_type = content_type or "application/octet-stream"
        document.text_length = text_length
        db.commit()
        db.refresh(document)
        return document
    except Exception:
        db.rollback()
        raise
