from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.ai.providers import ProviderError
from app.config import settings
from app.crud import application as application_crud
from app.crud import experience as experience_crud
from app.crud import job as job_crud
from app.db.session import get_db
from app.schemas.application import (
    AnswerGenerationRequest,
    AnswerRead,
    AnswerUpdate,
    ApplicationRead,
    BatchAnswerRequest,
    DetectedFormField,
    DetectQuestionsRequest,
    FillPreviewRequest,
    FillPreviewResponse,
)
from app.services.form_fill_service import build_fill_preview
from app.schemas.material import MaterialContent
from app.services.answer_template_service import (
    evaluate_template,
    recommended_template,
    resolve_template,
)
from app.services.application_question_service import (
    analyze_application_form,
    extract_screenshot_text,
    generate_question_answer,
    is_manual_question,
    max_words_for,
    trim_to_word_limit,
)
from app.services.material_validation_service import validate_material_text
from app.ai.observability import ai_user_scope
from app.api.v1.ai_quota import reserve_ai_generation, reserve_cloud_ocr

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


def _application_payload(application, questions):

    return {
        "id": application.id,
        "job_id": application.job_id,
        "raw_text": application.raw_text,
        "questions": questions,
        "created_at": application.created_at,
    }


def _answer_payload(question, material: MaterialContent | None, status: str) -> dict:
    max_words = max_words_for(question)

    text = material.text if material else ""

    metadata = (question.answer or {}).get("metadata", {})
    template = metadata.get("answer_template")
    selected_template, target_characters = resolve_template(
        template or "auto", question.question_type, question.max_characters
    )
    return {
        "question_id": question.id,
        "question": question.question,
        "answer": text,
        "character_count": len(text),
        "max_characters": question.max_characters,
        "fact_check_passed": material.fact_check_passed if material else False,
        "warnings": (
            material.warnings
            if material
            else ["此字段必须由用户本人填写，AI 不会猜测敏感或个人信息。"]
        ),
        "sources": [source.model_dump() for source in material.sources] if material else [],
        "status": status,
        "generation_method": material.generation_method if material else "none",
        "word_count": len(text.split()) if text else 0,
        "max_words": max_words,
        "template": template,
        "recommended_template": recommended_template(
            question.question_type, question.max_characters
        ),
        "template_target_characters": target_characters,
        "structure_warnings": (
            evaluate_template(text, selected_template, target_characters)
            if text and template
            else []
        ),
    }


def _stored_result(question) -> dict | None:
    answer = question.answer or {}

    result = answer.get("result") if isinstance(answer, dict) else None

    if not isinstance(result, dict) or not result.get("text"):
        return None

    try:
        material = MaterialContent.model_validate(result)

    except ValueError:

        return None

    return _answer_payload(question, material, str(answer.get("status") or "generated"))


def _generate(
    application,
    question,
    db: Session,
    template: str = "auto",
    output_language: str = "en",
    answer_tone: str = "professional",
    desired_content: str = "",
) -> dict:

    if is_manual_question(question):
        return _answer_payload(question, None, "manual_required")

    job = job_crud.get(db, application.job_id)

    if not job:
        raise HTTPException(
            status_code=409, detail="The job linked to this application no longer exists"
        )

    experiences = [item for item in experience_crud.list_all(db) if item.confirmed]

    if settings.ai_application_form_enabled:
        reserve_ai_generation(db)

    with ai_user_scope(db.info.get("current_user_id")):
        material = generate_question_answer(
            job,
            question,
            experiences,
            ai_enabled=settings.ai_application_form_enabled,
            template=template,
            output_language=output_language,
            answer_tone=answer_tone,
            desired_content=desired_content,
            db=db,
            user_id=db.info.get("current_user_id"),
        )

    if material is None:

        return _answer_payload(question, None, "manual_required")
    max_words = max_words_for(question)

    trimmed = trim_to_word_limit(material.text, max_words)

    if trimmed != material.text:
        material = material.model_copy(
            update={
                "text": trimmed,
                "character_count": len(trimmed),
                "warnings": [*material.warnings, f"答案已截断至 {max_words} words。"],
            }
        )
    metadata = dict((question.answer or {}).get("metadata", {}))
    effective_template, _ = resolve_template(
        template, question.question_type, question.max_characters
    )
    metadata["answer_template"] = effective_template

    application_crud.save_answer(
        db, question, {"metadata": metadata, "result": material.model_dump(), "status": "generated"}
    )

    return _answer_payload(question, material, "generated")


@router.post("/questions/detect", response_model=ApplicationRead)
def detect(payload: DetectQuestionsRequest, db: Session = Depends(get_db)):

    if not job_crud.get(db, payload.job_id):
        raise HTTPException(status_code=404, detail="Job not found")

    try:

        if settings.ai_application_form_enabled:
            reserve_ai_generation(db)

        with ai_user_scope(db.info.get("current_user_id")):
            parsed = analyze_application_form(
                payload.raw_text, ai_enabled=settings.ai_application_form_enabled
            )

    except ValueError as exc:

        raise HTTPException(status_code=400, detail=str(exc)) from exc
    application, questions = application_crud.create_with_questions(
        db, payload.job_id, payload.raw_text, parsed
    )

    return _application_payload(application, questions)


@router.get("/latest", response_model=ApplicationRead)
def latest_application(job_id: int, db: Session = Depends(get_db)):
    if not job_crud.get(db, job_id):
        raise HTTPException(status_code=404, detail="Job not found")
    application = application_crud.latest_by_job(db, job_id)
    if not application:
        raise HTTPException(status_code=404, detail="No saved application form for this job")
    return _application_payload(application, application_crud.list_questions(db, application.id))


@router.post("/questions/detect-screenshot", response_model=ApplicationRead)
async def detect_screenshot(
    job_id: int = Form(...),
    consent_to_cloud_ocr: bool = Form(False),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):

    if not settings.screenshot_ocr_enabled:

        raise HTTPException(status_code=503, detail="Screenshot OCR is disabled")

    if not consent_to_cloud_ocr:

        raise HTTPException(
            status_code=400,
            detail="Explicit consent is required before sending a screenshot to Gemini OCR",
        )

    if not job_crud.get(db, job_id):
        raise HTTPException(status_code=404, detail="Job not found")

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
            raw_text = extract_screenshot_text(content, mime_type)

            if settings.ai_application_form_enabled:
                reserve_ai_generation(db)

            parsed = analyze_application_form(
                raw_text, ai_enabled=settings.ai_application_form_enabled
            )

    except (ProviderError, ValueError) as exc:

        raise HTTPException(status_code=422, detail=str(exc)) from exc
    application, questions = application_crud.create_with_questions(db, job_id, raw_text, parsed)

    return _application_payload(application, questions)


@router.get("/{application_id}", response_model=ApplicationRead)
def get_application(application_id: int, db: Session = Depends(get_db)):
    application = application_crud.get(db, application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    return _application_payload(application, application_crud.list_questions(db, application_id))


@router.get("/{application_id}/answers", response_model=list[AnswerRead])
def saved_answers(application_id: int, db: Session = Depends(get_db)):
    application = application_crud.get(db, application_id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return [
        result
        for question in application_crud.list_questions(db, application_id)
        if (result := _stored_result(question)) is not None
    ]


@router.post("/{application_id}/questions/{question_id}/answer", response_model=AnswerRead)
def answer(
    application_id: int,
    question_id: int,
    payload: AnswerGenerationRequest | None = None,
    db: Session = Depends(get_db),
):
    application = application_crud.get(db, application_id)

    question = application_crud.get_question(db, application_id, question_id)

    if not application or not question:
        raise HTTPException(status_code=404, detail="Application question not found")

    request = payload or AnswerGenerationRequest()
    return _generate(
        application,
        question,
        db,
        request.template,
        request.output_language,
        request.answer_tone,
        request.desired_content,
    )


@router.post("/{application_id}/answers/generate-all", response_model=list[AnswerRead])
def generate_all(application_id: int, payload: BatchAnswerRequest, db: Session = Depends(get_db)):
    application = application_crud.get(db, application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    results: list[dict] = []

    for question in application_crud.list_questions(db, application_id):
        stored = _stored_result(question)

        results.append(
            stored
            if stored and not payload.regenerate
            else _generate(
                application,
                question,
                db,
                payload.template,
                payload.output_language,
                payload.answer_tone,
                payload.desired_content,
            )
        )

    return results


@router.post("/{application_id}/fill-preview", response_model=FillPreviewResponse)
def fill_preview(application_id: int, payload: FillPreviewRequest, db: Session = Depends(get_db)):
    application = application_crud.get(db, application_id)

    if not application:
        raise HTTPException(status_code=404, detail="Application not found")

    questions = application_crud.list_questions(db, application_id)

    return {
        "application_id": application_id,
        "items": build_fill_preview(payload.fields, questions),
    }


@router.patch("/{application_id}/questions/{question_id}/answer", response_model=AnswerRead)
def update_answer(
    application_id: int, question_id: int, payload: AnswerUpdate, db: Session = Depends(get_db)
):
    application = application_crud.get(db, application_id)

    question = application_crud.get_question(db, application_id, question_id)

    if not application or not question:
        raise HTTPException(status_code=404, detail="Application question not found")

    text = payload.answer.strip()

    if len(text) > question.max_characters:
        raise HTTPException(
            status_code=422, detail=f"Answer exceeds the {question.max_characters}-character limit"
        )

    max_words = max_words_for(question)

    if max_words and len(text.split()) > max_words:
        raise HTTPException(status_code=422, detail=f"Answer exceeds the {max_words}-word limit")

    experiences = [item for item in experience_crud.list_all(db) if item.confirmed]

    job = job_crud.get(db, application.job_id)

    if is_manual_question(question):
        passed, warnings, sources = False, ["用户提供的个人或敏感信息未由系统验证。"], []

    else:
        passed, warnings = validate_material_text(
            text, experiences, f"{job.title} {job.company} {job.description}" if job else ""
        )

        sources = []
    material = MaterialContent(
        material_type="application_answer",
        text=text,
        character_count=len(text),
        fact_check_passed=passed,
        warnings=warnings,
        sources=sources,
        generation_method="user_edited",
    )
    metadata = (question.answer or {}).get("metadata", {})

    application_crud.save_answer(
        db,
        question,
        {"metadata": metadata, "result": material.model_dump(), "status": "user_provided"},
    )

    return _answer_payload(question, material, "user_provided")
