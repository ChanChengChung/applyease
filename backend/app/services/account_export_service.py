"""Privacy-preserving user data export.  Excludes credentials, sessions and secrets."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import Session

from app.models.applicant_profile import ApplicantProfile
from app.models.application import Application, ApplicationQuestion
from app.models.document import Document
from app.models.experience import Experience
from app.models.job import Job
from app.models.material import GeneratedMaterial
from app.models.resource import ResourceProgress
from app.models.tracker import TrackedApplication
from app.models.user import User

EXPORT_MODELS = {
    "documents": Document,
    "experiences": Experience,
    "jobs": Job,
    "materials": GeneratedMaterial,
    "applications": Application,
    "application_questions": ApplicationQuestion,
    "resource_progress": ResourceProgress,
    "tracked_applications": TrackedApplication,
}


def _json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    raise TypeError(f"Unsupported export value: {type(value)!r}")


def _records(db: Session, model, user_id: int) -> list[dict]:
    rows = db.scalars(select(model).where(model.user_id == user_id).order_by(model.id)).all()
    columns = [column.key for column in inspect(model).columns if column.key != "user_id"]
    return [{name: getattr(row, name) for name in columns} for row in rows]


def build_account_export(db: Session, user: User) -> bytes:
    """Return a ZIP with user-created records, never auth/session/MFA secrets or original uploads."""
    payload: dict[str, object] = {
        "format_version": 1,
        "exported_at": datetime.now(UTC).isoformat(),
        "account": {
            "email": user.email,
            "email_verified": user.email_verified,
            "created_at": user.created_at,
        },
        "privacy": {
            "included": "Application records and user-authored content; uploaded file metadata only.",
            "excluded": "Passwords, sessions, MFA secrets, recovery codes, audit hashes, API keys and original uploaded files.",
        },
    }
    for name, model in EXPORT_MODELS.items():
        payload[name] = _records(db, model, user.id)
    profile = db.get(ApplicantProfile, user.id)
    payload["applicant_profile"] = (
        {
            "display_name": profile.display_name,
            "contact_line": profile.contact_line,
            "updated_at": profile.updated_at,
        }
        if profile
        else None
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "applyease-account-export.json",
            json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default),
        )
        archive.writestr(
            "README.txt",
            "This export excludes passwords, sessions, MFA secrets, recovery codes, audit hashes, API keys and original uploaded files.\n",
        )
    return buffer.getvalue()
