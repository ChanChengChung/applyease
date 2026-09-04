import asyncio

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Query
from sqlalchemy.orm import Session

from app.crud import experience as experience_crud
from app.crud import application as application_crud
from app.crud import material as material_crud
from app.db.session import get_db
from app.crud import job as job_crud
from app.schemas.job import (
    ApplicationReadiness,
    JobAnalyzeRequest,
    JobImportDraft,
    JobImportUrlRequest,
    ManualJobBriefRequest,
    JobRead,
    JobSaveAnalyzedRequest,
    MatchReport,
)
from app.config import settings
from app.services.job_analysis_service import analyze_job_requirements, build_preview_job, match_job
from app.ai.observability import ai_user_scope
from app.ai.providers import ProviderError
from app.services.application_question_service import extract_screenshot_text
from app.services.job_import_service import (
    draft_from_text,
    import_public_job_page,
    validate_public_job_url,
)
from app.services.application_readiness_service import build_application_readiness
from app.services.manual_job_brief_service import build_manual_analysis_request
from app.api.v1.ai_quota import reserve_ai_generation, reserve_cloud_ocr, reserve_job_import

router = APIRouter()
SCREENSHOT_TYPES = {"image/png", "image/jpeg", "image/webp"}


def _valid_image_signature(data: bytes, mime_type: str) -> bool:

    return (
        (mime_type == "image/png" and data.startswith(b"\x89PNG\r\n\x1a\n"))
        or (mime_type == "image/jpeg" and data.startswith(b"\xff\xd8\xff"))
        or (
            mime_type == "image/webp"
            and len(data) >= 12
            and data[:4] == b"RIFF"
            and data[8:12] == b"WEBP"
        )
    )


@router.post("/import-url", response_model=JobImportDraft)
def import_url(payload: JobImportUrlRequest, db: Session = Depends(get_db)):

    try:

        # Reject malformed/private URLs before consuming the outbound budget.
        validated_url = validate_public_job_url(payload.url)
        reserve_job_import(db)
        # The third import layer uses the configured local model (then Gemini
        # only if needed), so enforce the same account-level AI budget as the
        # rest of ApplyEase. Rule/JSON-LD import still works when disabled.
        if settings.ai_job_analysis_enabled:
            reserve_ai_generation(db)

        return import_public_job_page(validated_url)

    except ValueError as exc:

        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/import-screenshot", response_model=JobImportDraft)
async def import_screenshot(
    consent_to_cloud_ocr: bool = Form(False),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):

    if not settings.screenshot_ocr_enabled:

        raise HTTPException(status_code=503, detail="Screenshot OCR is disabled")

    if not consent_to_cloud_ocr:

        raise HTTPException(
            status_code=400,
            detail="Explicit consent is required before sending a job screenshot to Gemini OCR",
        )
    mime_type = (file.content_type or "").casefold()

    if mime_type not in SCREENSHOT_TYPES:

        raise HTTPException(
            status_code=400, detail="Only PNG, JPEG and WebP screenshots are supported"
        )
    content = await file.read(settings.max_screenshot_bytes + 1)

    if not content:

        raise HTTPException(status_code=400, detail="Screenshot is empty")

    if len(content) > settings.max_screenshot_bytes:

        raise HTTPException(status_code=413, detail="Screenshot exceeds the 5 MB limit")

    if not _valid_image_signature(content, mime_type):

        raise HTTPException(
            status_code=400, detail="File contents do not match the declared image type"
        )

    try:
        reserve_cloud_ocr(db)

        with ai_user_scope(db.info.get("current_user_id")):
            # OCR calls an external provider synchronously; keep the async
            # request handler responsive while it is in flight.
            raw_text = await asyncio.to_thread(extract_screenshot_text, content, mime_type)

        return draft_from_text(raw_text)

    except (ProviderError, ValueError) as exc:

        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/analyze", response_model=JobRead)
def analyze_job(payload: JobAnalyzeRequest, db: Session = Depends(get_db)):

    if settings.ai_job_analysis_enabled:
        reserve_ai_generation(db)

    with ai_user_scope(db.info.get("current_user_id")):
        requirements = analyze_job_requirements(
            payload.description, ai_enabled=settings.ai_job_analysis_enabled
        )

    return job_crud.create(db, **payload.model_dump(), **requirements)


@router.post("/analyze-preview", response_model=MatchReport)
def analyze_job_preview(payload: JobAnalyzeRequest, db: Session = Depends(get_db)):
    """Analyse a role without creating a workspace record.

    A transient Job carries the server-derived requirements into the matching
    service.  ``id=0`` is explicitly a preview sentinel and is never stored.
    """
    if settings.ai_job_analysis_enabled:
        reserve_ai_generation(db)
    with ai_user_scope(db.info.get("current_user_id")):
        requirements = analyze_job_requirements(
            payload.description, ai_enabled=settings.ai_job_analysis_enabled
        )
        preview = build_preview_job(payload, requirements, db.info.get("current_user_id"))
        return match_job(
            preview,
            experience_crud.list_all(db),
            ai_enabled=settings.ai_job_analysis_enabled,
            db=db,
            user_id=db.info.get("current_user_id"),
        )


@router.post("/analyze-manual-preview", response_model=MatchReport)
def analyze_manual_job_preview(payload: ManualJobBriefRequest, db: Session = Depends(get_db)):
    """Analyse a structured manual role brief without persisting a job yet."""
    analysis_payload = build_manual_analysis_request(payload)
    if settings.ai_job_analysis_enabled:
        reserve_ai_generation(db)
    with ai_user_scope(db.info.get("current_user_id")):
        requirements = analyze_job_requirements(
            analysis_payload.description, ai_enabled=settings.ai_job_analysis_enabled
        )
        preview = build_preview_job(
            analysis_payload, requirements, db.info.get("current_user_id")
        )
        return match_job(
            preview,
            experience_crud.list_all(db),
            ai_enabled=settings.ai_job_analysis_enabled,
            db=db,
            user_id=db.info.get("current_user_id"),
        )


@router.post("/save-analyzed", response_model=JobRead)
def save_analyzed_job(payload: JobSaveAnalyzedRequest, db: Session = Depends(get_db)):
    """Persist an analysis only after the user elects to open a workspace."""
    return job_crud.create(db, **payload.model_dump())


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = job_crud.get_for_user(db, job_id, db.info.get("current_user_id"))

    if not job:

        raise HTTPException(status_code=404, detail="Job not found")

    return job


@router.delete("/{job_id}", status_code=204)
def delete_job(job_id: int, db: Session = Depends(get_db)):
    if not job_crud.delete_for_user(db, job_id, db.info.get("current_user_id")):
        raise HTTPException(status_code=404, detail="Job not found")


@router.get("/{job_id}/match-report", response_model=MatchReport)
def get_match_report(job_id: int, db: Session = Depends(get_db)):
    job = job_crud.get_for_user(db, job_id, db.info.get("current_user_id"))

    if not job:

        raise HTTPException(status_code=404, detail="Job not found")
    experiences = experience_crud.list_all(db)
    user_id = db.info.get("current_user_id")

    # This endpoint is fetched automatically whenever a saved role is opened.
    # Keep it deterministic and quota-free: requirements may have been AI
    # extracted when the role was imported, but viewing the evidence report
    # must never silently consume another model request.
    return match_job(job, experiences, ai_enabled=False, db=db, user_id=user_id)


@router.get("/{job_id}/readiness", response_model=ApplicationReadiness)
def get_readiness(job_id: int, db: Session = Depends(get_db)):
    job = job_crud.get_for_user(db, job_id, db.info.get("current_user_id"))
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    applications = application_crud.list_by_job(db, job_id)
    for application in applications:
        application.questions = application_crud.list_questions(db, application.id)
    return build_application_readiness(
        job, experience_crud.list_all(db), material_crud.list_by_job(db, job_id), applications
    )


@router.get("", response_model=list[JobRead])
def list_jobs(limit: int = Query(default=30, ge=1, le=100), db: Session = Depends(get_db)):
    """User-facing target selector; never expose database IDs as an input field."""
    return job_crud.list_recent(db, db.info.get("current_user_id"), limit=limit)
