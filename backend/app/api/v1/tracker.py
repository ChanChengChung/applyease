from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.crud import job as job_crud
from app.crud import application as application_crud
from app.crud import experience as experience_crud
from app.crud import material as material_crud
from app.crud import research_plan as research_plan_crud
from app.crud import tracker as tracker_crud
from app.db.session import get_db
from app.schemas.tracker import (
    STATUSES,
    TrackerCreate,
    ApplicationWorkspaceRead,
    MaterialVersionRead,
    TrackerRead,
    TrackerReminder,
    TrackerSummary,
    TrackerUpdate,
)
from app.schemas.notifications import InterviewReviewCoachRequest
from app.services.interview_review_service import coach_review
from app.api.v1.ai_quota import reserve_ai_generation
from app.config import settings
from app.auth import utc_now
from app.services.calendar_service import build_calendar, build_reminders, calendar_filename
from app.services.tracker_service import build_tracker_summary, serialize_tracker
from app.services.job_analysis_service import build_match_report

router = APIRouter()
Status = Literal["saved", "applied", "assessment", "interview", "offer", "rejected", "withdrawn"]


def _validate_job(job_id: int | None, db: Session) -> None:

    if job_id is not None and not job_crud.get(db, job_id):

        raise HTTPException(status_code=404, detail="Linked job not found")


@router.get("", response_model=list[TrackerRead])
def list_applications(
    status: Status | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    sort: Literal["deadline", "created_at", "follow_up"] = "deadline",
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):

    if from_date and to_date and from_date > to_date:

        raise HTTPException(status_code=422, detail="from_date cannot be later than to_date")
    items = tracker_crud.list_all(
        db,
        status=status,
        from_date=from_date,
        to_date=to_date,
        sort=sort,
        limit=limit,
        offset=offset,
    )

    return [serialize_tracker(item) for item in items]


@router.get("/summary", response_model=TrackerSummary)
def summary(db: Session = Depends(get_db)):

    return build_tracker_summary(tracker_crud.list_all(db, limit=500))


@router.get("/reminders", response_model=list[TrackerReminder])
def reminders(days: int = Query(default=14, ge=1, le=90), db: Session = Depends(get_db)):
    return build_reminders(tracker_crud.list_all(db, limit=500), days=days)


@router.get("/{application_id}/workspace", response_model=ApplicationWorkspaceRead)
def workspace(application_id: int, db: Session = Depends(get_db)):
    item = tracker_crud.get(db, application_id)
    if not item:
        raise HTTPException(status_code=404, detail="Tracked application not found")
    if not item.job_id:
        return ApplicationWorkspaceRead(application_id=item.id, application_status=item.status)
    job = job_crud.get(db, item.job_id)
    if not job:
        return ApplicationWorkspaceRead(application_id=item.id, application_status=item.status)
    # A tracker view can contain many cards. It must not fan out into costly or
    # slow model calls on every page load; the deterministic report remains
    # fully grounded in confirmed experiences and is sufficient for progress.
    report = build_match_report(job, experience_crud.list_all(db))
    materials = material_crud.list_by_job(db, job.id)
    applications = application_crud.list_by_job(db, job.id)
    questions = application_crud.list_questions(db, applications[0].id) if applications else []
    plan = research_plan_crud.latest_for_job(db, int(db.info.get("current_user_id") or 0), job.id)
    answers_ready = sum(
        bool(
            isinstance(question.answer, dict) and (question.answer.get("result") or {}).get("text")
        )
        for question in questions
    )
    return ApplicationWorkspaceRead(
        application_id=item.id,
        job_id=job.id,
        match_score=report.overall_score,
        evidence_count=len(report.evidence),
        missing_skills=report.missing_skills,
        material_types=sorted({material.material_type for material in materials}),
        questions_total=len(questions),
        answers_ready=answers_ready,
        learning_plan_id=plan.id if plan else None,
        learning_plan_steps=len(plan.method or []) if plan else 0,
        learning_plan_sources=len(plan.sources or []) if plan else 0,
        learning_plan_updated_at=plan.updated_at if plan else None,
        application_status=item.status,
        material_versions=[
            MaterialVersionRead(
                id=material.id,
                material_type=material.material_type,
                generation_method=str((material.content or {}).get("generation_method", "rules")),
                created_at=material.created_at,
                fact_check_passed=bool((material.content or {}).get("fact_check_passed", False)),
                source_count=len((material.content or {}).get("sources", [])),
            )
            for material in materials
        ],
    )


@router.get("/{application_id}/calendar")
def export_calendar(application_id: int, db: Session = Depends(get_db)):
    item = tracker_crud.get(db, application_id)
    if not item:
        raise HTTPException(status_code=404, detail="Tracked application not found")
    try:
        content = build_calendar(item)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{calendar_filename(item)}"'},
    )


@router.post("", response_model=TrackerRead)
def create_application(payload: TrackerCreate, db: Session = Depends(get_db)):
    _validate_job(payload.job_id, db)

    # Tracking is a workflow state for a target role, not a second copy of the
    # role.  Returning the existing record keeps a double-click (or a second
    # "track this role" action) from creating duplicate applications.
    user_id = db.info.get("current_user_id")
    if payload.job_id is not None:
        existing = tracker_crud.get_by_job(db, user_id, payload.job_id)
        if existing:
            return serialize_tracker(existing)

    return serialize_tracker(tracker_crud.create(db, **payload.model_dump()))


@router.patch("/{application_id}", response_model=TrackerRead)
def update_application(application_id: int, payload: TrackerUpdate, db: Session = Depends(get_db)):
    item = tracker_crud.get(db, application_id)

    if not item:

        raise HTTPException(status_code=404, detail="Tracked application not found")
    values = payload.model_dump(exclude_unset=True)

    if "job_id" in values:
        _validate_job(values["job_id"], db)
        if values["job_id"] is not None:
            existing = tracker_crud.get_by_job(db, db.info.get("current_user_id"), values["job_id"])
            if existing and existing.id != item.id:
                raise HTTPException(
                    status_code=409,
                    detail="This role already has an application tracking record",
                )

    return serialize_tracker(tracker_crud.update(db, item, values))


@router.post("/{application_id}/interview-review/coach", response_model=TrackerRead)
def coach_interview_review(
    application_id: int,
    payload: InterviewReviewCoachRequest,
    db: Session = Depends(get_db),
):
    """Generate grounded coaching and persist it with the interview debrief."""
    item = tracker_crud.get(db, application_id)
    if not item:
        raise HTTPException(status_code=404, detail="Tracked application not found")
    if not payload.has_content():
        raise HTTPException(status_code=422, detail="Add at least one interview debrief field first")

    if settings.ai_interview_review_enabled:
        reserve_ai_generation(db)

    review_values = {
        "questions": payload.questions,
        "strengths": payload.strengths,
        "improvements": payload.improvements,
        "next_steps": payload.next_steps,
    }
    feedback = coach_review(
        db,
        item,
        review_values,
        output_language=payload.output_language,
    )
    review_values.update({"completed_at": utc_now().isoformat(), "ai_feedback": feedback})
    return serialize_tracker(tracker_crud.update(db, item, {"interview_review": review_values}))


@router.delete("/{application_id}", status_code=204)
def delete_application(application_id: int, db: Session = Depends(get_db)):
    item = tracker_crud.get(db, application_id)

    if not item:

        raise HTTPException(status_code=404, detail="Tracked application not found")
    tracker_crud.delete(db, item)
