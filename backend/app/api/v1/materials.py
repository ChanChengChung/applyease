from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from io import BytesIO
from sqlalchemy.orm import Session

from app.config import settings
from app.crud import experience as experience_crud
from app.crud import job as job_crud
from app.crud import material as material_crud
from app.db.session import get_db
from app.schemas.material import AnswerRequest, MaterialRead, MaterialUpdate, ResumeExportRequest
from app.services.material_service import generate_material
from app.services.material_validation_service import validate_material_text
from app.services.resume_export_service import build_resume_docx, build_resume_pdf, export_filename
from app.ai.observability import ai_user_scope
from app.api.v1.ai_quota import reserve_ai_generation

router = APIRouter()
MaterialType = Literal["resume", "cover_letter", "application_answer"]


def _job(job_id: int, db: Session):
    job = job_crud.get(db, job_id)

    if not job:

        raise HTTPException(status_code=404, detail="Job not found")

    return job


def _save(job_id: int, material, db: Session):
    record = material_crud.create(db, job_id, material.material_type, material.model_dump())

    return {
        **material.model_dump(),
        "id": record.id,
        "job_id": job_id,
        "created_at": record.created_at,
    }


def _record_payload(record):

    return {
        **record.content,
        "id": record.id,
        "job_id": record.job_id,
        "created_at": record.created_at,
    }


@router.post("/resume/generate", response_model=MaterialRead)
def resume(
    job_id: int,
    output_language: Literal["en", "zh-CN", "zh-TW"] = "en",
    db: Session = Depends(get_db),
):
    job = _job(job_id, db)
    user_id = db.info.get("current_user_id")

    if settings.ai_material_generation_enabled:
        reserve_ai_generation(db)

    with ai_user_scope(user_id):
        material = generate_material(
            job,
            experience_crud.list_all(db),
            "resume",
            ai_enabled=settings.ai_material_generation_enabled,
            output_language=output_language,
            db=db,
            user_id=user_id,
        )

    return _save(job_id, material, db)


@router.post("/cover-letter/generate", response_model=MaterialRead)
def cover_letter(
    job_id: int,
    output_language: Literal["en", "zh-CN", "zh-TW"] = "en",
    db: Session = Depends(get_db),
):
    job = _job(job_id, db)
    user_id = db.info.get("current_user_id")

    if settings.ai_material_generation_enabled:
        reserve_ai_generation(db)

    with ai_user_scope(user_id):
        material = generate_material(
            job,
            experience_crud.list_all(db),
            "cover_letter",
            ai_enabled=settings.ai_material_generation_enabled,
            output_language=output_language,
            db=db,
            user_id=user_id,
        )

    return _save(job_id, material, db)


@router.post("/answer/generate", response_model=MaterialRead)
def answer(job_id: int, payload: AnswerRequest, db: Session = Depends(get_db)):
    job = _job(job_id, db)
    user_id = db.info.get("current_user_id")

    if settings.ai_material_generation_enabled:
        reserve_ai_generation(db)

    with ai_user_scope(user_id):
        material = generate_material(
            job,
            experience_crud.list_all(db),
            "application_answer",
            ai_enabled=settings.ai_material_generation_enabled,
            question=payload.question,
            max_characters=payload.max_characters,
            answer_tone=payload.answer_tone,
            desired_content=payload.desired_content,
            output_language=payload.output_language,
            db=db,
            user_id=user_id,
        )

    return _save(job_id, material, db)


@router.get("", response_model=list[MaterialRead])
def list_materials(
    job_id: int,
    material_type: MaterialType | None = Query(default=None),
    db: Session = Depends(get_db),
):
    _job(job_id, db)

    return [
        _record_payload(record) for record in material_crud.list_by_job(db, job_id, material_type)
    ]


@router.patch("/{material_id}", response_model=MaterialRead)
def update_material(material_id: int, payload: MaterialUpdate, db: Session = Depends(get_db)):
    record = material_crud.get(db, material_id)

    if not record:

        raise HTTPException(status_code=404, detail="Material not found")
    job = _job(record.job_id, db)

    max_characters = (
        record.content.get("max_characters") if isinstance(record.content, dict) else None
    )

    if max_characters is not None and len(payload.text) > max_characters:

        raise HTTPException(
            status_code=422, detail=f"Material exceeds the {max_characters}-character limit"
        )
    experiences = experience_crud.list_all(db)

    source_ids = {
        source.get("experience_id")
        for source in record.content.get("sources", [])
        if isinstance(source, dict)
    }

    selected = [item for item in experiences if item.confirmed and item.id in source_ids]

    passed, warnings = validate_material_text(
        payload.text, selected, f"{job.title} {job.company} {job.description}"
    )

    content = {
        **record.content,
        "text": payload.text,
        "character_count": len(payload.text),
        "fact_check_passed": passed,
        "warnings": warnings,
        "generation_method": "user_edited",
    }
    material_crud.create_edit_snapshot(db, record)
    return _record_payload(material_crud.update_content(db, record, content))


@router.post("/{material_id}/export")
def export_resume(material_id: int, payload: ResumeExportRequest, db: Session = Depends(get_db)):
    record = material_crud.get(db, material_id)

    if not record:

        raise HTTPException(status_code=404, detail="Material not found")

    if record.material_type != "resume":

        raise HTTPException(status_code=400, detail="Only resume materials can be exported")

    if not bool((record.content or {}).get("fact_check_passed")):

        raise HTTPException(
            status_code=409, detail="Resolve fact-check warnings before exporting this resume"
        )
    job = _job(record.job_id, db)

    try:
        artifact = (
            build_resume_docx(
                record,
                job,
                payload.template,
                payload.include_sources,
                payload.display_name,
                payload.contact_line,
                payload.email,
                payload.phone,
                payload.location,
                payload.linkedin_url,
                payload.github_url,
                payload.section_order,
                payload.hidden_sections,
                payload.font_style,
                payload.density,
                payload.accent,
            )
            if payload.format == "docx"
            else build_resume_pdf(
                record,
                job,
                payload.template,
                payload.include_sources,
                payload.display_name,
                payload.contact_line,
                payload.email,
                payload.phone,
                payload.location,
                payload.linkedin_url,
                payload.github_url,
                payload.section_order,
                payload.hidden_sections,
                payload.font_style,
                payload.density,
                payload.accent,
            )
        )

    except ValueError as exc:

        raise HTTPException(status_code=422, detail=str(exc)) from exc
    media_type = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if payload.format == "docx"
        else "application/pdf"
    )

    filename = export_filename(job, payload.template, payload.format)

    return StreamingResponse(
        BytesIO(artifact),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
