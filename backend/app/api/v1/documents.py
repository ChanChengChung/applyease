from hashlib import sha256
from pathlib import Path
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.ai.experience_extractor import extract_experiences_safe
from app.ai.personal_info_extractor import extract_personal_information
from app.crud import document as document_crud
from app.db.session import get_db
from app.parsers.pdf_parser import extract_text
from app.config import settings
from app.ai.observability import ai_user_scope
from app.api.v1.ai_quota import reserve_ai_generation

router = APIRouter()
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


def _extract_experience_values(db: Session, text: str, filename: str) -> list[dict]:
    if settings.ai_extraction_enabled:
        reserve_ai_generation(db)
        with ai_user_scope(db.info.get("current_user_id")):
            extracted, _extraction_mode = extract_experiences_safe(text, filename)
    else:
        from app.ai.mock_extractor import extract_experiences

        extracted = extract_experiences(text, filename)

    personal = extract_personal_information(text, filename)
    if personal:
        extracted.insert(0, personal)
    return extracted


@router.post("/upload")
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):

    if not file.filename:

        raise HTTPException(status_code=400, detail="Filename is required")
    suffix = Path(file.filename).suffix.lower()

    if suffix not in ALLOWED_EXTENSIONS:

        raise HTTPException(
            status_code=400, detail="Only PDF, DOCX, TXT and MD files are supported"
        )
    content = await file.read(settings.max_upload_bytes + 1)

    if len(content) > settings.max_upload_bytes:

        raise HTTPException(status_code=413, detail="Uploaded file exceeds the 10 MB limit")
    digest = sha256(content).hexdigest()

    existing = document_crud.get_by_sha256(db, digest)

    if existing:
        try:
            duplicate_text = extract_text(
                file.filename,
                content,
                max_pdf_pages=settings.max_document_pages,
                max_text_characters=settings.max_document_text_characters,
                max_docx_uncompressed_bytes=settings.max_docx_uncompressed_bytes,
            )
            # The hash identifies the source document, not a permanent ban on
            # reparsing it. Always extract again so partial or complete evidence
            # deletion can be repaired. The CRUD layer de-duplicates cards that
            # are still present.
            extracted = _extract_experience_values(db, duplicate_text, file.filename)
            records, restored = document_crud.restore_missing_experiences(
                db, existing, extracted
            )
            existing.filename = file.filename[:255]
            existing.content_type = file.content_type or "application/octet-stream"
            existing.text_length = len(duplicate_text)
            db.commit()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except SQLAlchemyError as exc:
            db.rollback()
            raise HTTPException(status_code=500, detail="Unable to restore uploaded document") from exc
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Unable to parse document: {exc}") from exc

        return {
            "filename": existing.filename,
            "text_length": existing.text_length,
            "document_id": existing.id,
            "duplicate": True,
            "restored": restored,
            "reused": not restored,
            "experiences": records,
        }

    try:
        text = extract_text(
            file.filename,
            content,
            max_pdf_pages=settings.max_document_pages,
            max_text_characters=settings.max_document_text_characters,
            max_docx_uncompressed_bytes=settings.max_docx_uncompressed_bytes,
        )

        extracted = _extract_experience_values(db, text, file.filename)

    except ValueError as exc:

        raise HTTPException(status_code=400, detail=str(exc)) from exc

    except Exception as exc:

        raise HTTPException(status_code=422, detail=f"Unable to parse document: {exc}") from exc

    try:
        document, records, created = document_crud.create_with_experiences(
            db,
            {
                "filename": file.filename[:255],
                "sha256": digest,
                "content_type": file.content_type or "application/octet-stream",
                "text_length": len(text),
            },
            extracted,
        )

    except SQLAlchemyError as exc:

        raise HTTPException(status_code=500, detail="Unable to save uploaded document") from exc

    return {
        "filename": document.filename,
        "text_length": document.text_length,
        "document_id": document.id,
        "duplicate": not created,
        "restored": False,
        "reused": not created,
        "experiences": records,
    }
