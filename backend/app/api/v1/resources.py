from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.crud import experience as experience_crud
from app.crud import job as job_crud
from app.crud import resource as resource_crud
from app.crud import research_plan as research_plan_crud
from app.crud import starter_plan as starter_plan_crud
from app.db.session import get_db
from app.schemas.experience import ExperienceRead
from app.schemas.resource import (
    ResourceComplete,
    ResourceExperienceDraftRequest,
    ResourceFeedbackCreate,
    ResourceRead,
    StarterPlanRead,
    StarterPlanRequest,
    StarterPlanRefineRequest,
    StarterPlanUpdate,
    ResearchPlanRead,
    ResearchPlanRequest,
    ResearchPlanUpdate,
)
from app.config import settings
from app.services.job_analysis_service import match_job
from app.services.resource_service import RESOURCE_CATALOG, recommend_resources
from app.services.resource_experience_service import experience_values_from_completed_resource
from app.services.resource_health_service import check_resource_link
from app.services.starter_plan_service import build_starter_plan
from app.services.research_plan_service import build_research_plan

router = APIRouter()


def _resource_payload(resource, completed: bool, recommendation=None) -> dict:

    return {
        "id": resource.id,
        "title": resource.title,
        "url": resource.url,
        "provider": resource.provider,
        "skills": resource.skills,
        "difficulty": resource.difficulty,
        "duration_hours": resource.duration_hours,
        "free": resource.free,
        "description": resource.description,
        "project": resource.project,
        "verified": resource.verified,
        "completed": completed,
        "created_at": resource.created_at,
        "link_status": resource.link_status,
        "last_checked_at": resource.last_checked_at,
        "match_score": recommendation.match_score if recommendation else 0,
        "matched_skills": recommendation.matched_skills if recommendation else [],
        "recommendation_reason": recommendation.recommendation_reason if recommendation else "",
    }


@router.post("/starter-plan", response_model=StarterPlanRead)
def starter_plan(payload: StarterPlanRequest, db: Session = Depends(get_db)):
    """AI-assisted, no-CV onboarding; it never creates experience evidence."""
    resource_crud.seed_if_empty(db, RESOURCE_CATALOG)
    plan = build_starter_plan(
        payload.interest,
        resource_crud.list_all(db),
        max_total_hours=payload.max_total_hours,
        language=payload.language,
        goal=payload.goal,
        experience_level=payload.experience_level,
        preferred_formats=payload.preferred_formats,
        experience_level_other=payload.experience_level_other,
        goal_other=payload.goal_other,
        preferred_format_other=payload.preferred_format_other,
    )
    progress = resource_crud.progress_map(db)
    resource_payloads = [
        _resource_payload(item.resource, progress.get(item.resource.id, False), item)
        for item in plan["resources"]
    ]
    saved = starter_plan_crud.create_or_replace(
        db,
        int(db.info.get("current_user_id") or 0),
        {
            "interest": payload.interest,
            "focus": plan["focus"],
            "headline": plan["headline"],
            "first_action": plan["first_action"],
            "milestones": plan["milestones"],
            "resource_ids": [item.resource.id for item in plan["resources"]],
            "used_fallback": bool(plan.get("used_fallback", False)),
        },
    )
    return {
        "id": saved.id,
        "interest": saved.interest,
        **plan,
        "resources": resource_payloads,
        "created_at": saved.created_at,
        "updated_at": saved.updated_at,
    }


@router.get("/starter-plans", response_model=StarterPlanRead)
def get_saved_starter_plan(db: Session = Depends(get_db)):
    item = starter_plan_crud.get(db, int(db.info.get("current_user_id") or 0))
    if not item:
        raise HTTPException(status_code=404, detail="Starter plan not found")
    resources = {resource.id: resource for resource in resource_crud.list_all(db)}
    progress = resource_crud.progress_map(db)
    payloads = [
        _resource_payload(resources[resource_id], progress.get(resource_id, False))
        for resource_id in item.resource_ids
        if resource_id in resources
    ]
    return {
        "id": item.id,
        "interest": item.interest,
        "focus": item.focus,
        "headline": item.headline,
        "first_action": item.first_action,
        "milestones": item.milestones,
        "resources": payloads,
        "used_fallback": item.used_fallback,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


@router.patch("/starter-plans/{plan_id}", response_model=StarterPlanRead)
def update_saved_starter_plan(
    plan_id: int, payload: StarterPlanUpdate, db: Session = Depends(get_db)
):
    user_id = int(db.info.get("current_user_id") or 0)
    item = starter_plan_crud.get(db, user_id)
    if not item or item.id != plan_id:
        raise HTTPException(status_code=404, detail="Starter plan not found")
    item = starter_plan_crud.update(db, item, payload.model_dump())
    resources = {resource.id: resource for resource in resource_crud.list_all(db)}
    progress = resource_crud.progress_map(db)
    return {
        "id": item.id,
        "interest": item.interest,
        "focus": item.focus,
        "headline": item.headline,
        "first_action": item.first_action,
        "milestones": item.milestones,
        "resources": [
            _resource_payload(resources[resource_id], progress.get(resource_id, False))
            for resource_id in item.resource_ids
            if resource_id in resources
        ],
        "used_fallback": item.used_fallback,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


@router.post("/starter-plans/{plan_id}/refine", response_model=StarterPlanRead)
def refine_saved_starter_plan(
    plan_id: int, payload: StarterPlanRefineRequest, db: Session = Depends(get_db)
):
    """Refine a no-job plan from saved onboarding intent, never from invented experience."""
    user_id = int(db.info.get("current_user_id") or 0)
    item = starter_plan_crud.get(db, user_id)
    if not item or item.id != plan_id:
        raise HTTPException(status_code=404, detail="Starter plan not found")
    resource_crud.seed_if_empty(db, RESOURCE_CATALOG)
    saved_context = "\n".join(
        [
            item.interest,
            f"Saved plan: {item.headline}",
            f"Saved first action: {item.first_action}",
            "Saved milestones: " + "; ".join(item.milestones),
        ]
    )
    goal_map = {"skills": "explore", "project": "portfolio", "interview": "portfolio"}
    style_map = {
        "hands_on": ["project"],
        "guided": ["course"],
        "intensive": ["project", "competition"],
    }
    plan = build_starter_plan(
        saved_context,
        resource_crud.list_all(db),
        max_total_hours=payload.max_total_hours,
        language=payload.language,
        goal=goal_map[payload.goal],
        experience_level="none",
        preferred_formats=style_map[payload.learning_style],
    )
    saved = starter_plan_crud.update(
        db,
        item,
        {
            "focus": plan["focus"],
            "headline": plan["headline"],
            "first_action": plan["first_action"],
            "milestones": plan["milestones"],
            "resource_ids": [entry.resource.id for entry in plan["resources"]],
            "used_fallback": bool(plan.get("used_fallback", False)),
        },
    )
    progress = resource_crud.progress_map(db)
    return {
        "id": saved.id,
        "interest": saved.interest,
        **plan,
        "resources": [
            _resource_payload(entry.resource, progress.get(entry.resource.id, False), entry)
            for entry in plan["resources"]
        ],
        "created_at": saved.created_at,
        "updated_at": saved.updated_at,
    }


@router.post("/research-plan", response_model=ResearchPlanRead)
def research_plan(payload: ResearchPlanRequest, db: Session = Depends(get_db)):
    job = job_crud.get(db, payload.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    resource_crud.seed_if_empty(db, RESOURCE_CATALOG)
    values = build_research_plan(
        job,
        experience_crud.list_all(db),
        resource_crud.list_all(db),
        missing_skills=match_job(job, experience_crud.list_all(db), ai_enabled=False).missing_skills,
        weekly_hours=payload.weekly_hours,
        weeks=payload.weeks,
        goal=payload.goal,
        learning_style=payload.learning_style,
        language=payload.language,
    )
    return research_plan_crud.create_or_replace(
        db, int(db.info.get("current_user_id") or 0), job.id, values
    )


@router.get("/research-plans", response_model=ResearchPlanRead)
def get_saved_research_plan(job_id: int = Query(gt=0), db: Session = Depends(get_db)):
    """Restore the user's saved, editable plan after navigation or refresh."""
    item = research_plan_crud.latest_for_job(db, int(db.info.get("current_user_id") or 0), job_id)
    if not item:
        raise HTTPException(status_code=404, detail="Research plan not found")
    return item


@router.patch("/research-plans/{plan_id}", response_model=ResearchPlanRead)
def update_research_plan(plan_id: int, payload: ResearchPlanUpdate, db: Session = Depends(get_db)):
    item = research_plan_crud.get(db, plan_id, int(db.info.get("current_user_id") or 0))
    if not item:
        raise HTTPException(status_code=404, detail="Research plan not found")
    return research_plan_crud.update(db, item, payload.model_dump())


@router.delete("/research-plans/{plan_id}", status_code=204)
def delete_research_plan(plan_id: int, db: Session = Depends(get_db)):
    item = research_plan_crud.get(db, plan_id, int(db.info.get("current_user_id") or 0))
    if not item:
        raise HTTPException(status_code=404, detail="Research plan not found")
    research_plan_crud.delete(db, item)


@router.get("/recommendations", response_model=list[ResourceRead])
def recommendations(
    job_id: int = Query(gt=0),
    level: Literal["beginner", "intermediate", "advanced"] | None = None,
    max_total_hours: int | None = Query(default=None, ge=1, le=200),
    # Backward-compatible alias for existing clients. New clients use
    # `max_total_hours`, whose name makes the whole-plan budget explicit.
    max_hours: int | None = Query(default=None, ge=1, le=200, deprecated=True),
    free_only: bool = False,
    goal: Literal["skills", "project", "interview"] = "skills",
    language: Literal["en", "zh-CN", "zh-TW"] = "zh-CN",
    limit: int = Query(default=8, ge=1, le=20),
    db: Session = Depends(get_db),
):
    job = job_crud.get(db, job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    resource_crud.seed_if_empty(db, RESOURCE_CATALOG)

    report = match_job(
        job, experience_crud.list_all(db), ai_enabled=settings.ai_job_analysis_enabled
    )

    resources = recommend_resources(
        report.missing_skills,
        resource_crud.list_all(db),
        level=level,
        max_total_hours=(max_total_hours if max_total_hours is not None else max_hours),
        free_only=free_only,
        limit=limit,
        goal=goal,
        language=language,
    )
    progress = resource_crud.progress_map(db)

    return [
        _resource_payload(item.resource, progress.get(item.resource.id, False), item)
        for item in resources
    ]


@router.post("/{resource_id}/complete", response_model=ResourceRead)
def complete(resource_id: int, payload: ResourceComplete, db: Session = Depends(get_db)):
    resource = resource_crud.get(db, resource_id)

    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    progress = resource_crud.set_completed(db, resource_id, payload.completed)

    return _resource_payload(resource, progress.completed)


@router.post("/{resource_id}/health-check", response_model=ResourceRead)
def health_check(resource_id: int, db: Session = Depends(get_db)):
    resource = resource_crud.get(db, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    check_resource_link(resource)
    resource_crud.save_health(db, resource)
    return _resource_payload(resource, resource_crud.progress_map(db).get(resource.id, False))


@router.post("/{resource_id}/feedback", status_code=201)
def feedback(resource_id: int, payload: ResourceFeedbackCreate, db: Session = Depends(get_db)):
    if not resource_crud.get(db, resource_id):
        raise HTTPException(status_code=404, detail="Resource not found")
    item = resource_crud.create_feedback(db, resource_id, payload.category, payload.message)
    return {"id": item.id, "message": "Feedback recorded"}


@router.post("/{resource_id}/experience-draft", response_model=ExperienceRead, status_code=201)
def create_experience_draft(
    resource_id: int, payload: ResourceExperienceDraftRequest, db: Session = Depends(get_db)
):
    resource = resource_crud.get(db, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    progress = resource_crud.get_progress(db, resource_id)
    if not progress or not progress.completed:
        raise HTTPException(
            status_code=409, detail="Mark the resource complete before creating an experience draft"
        )

    item, duplicate = experience_crud.create(
        db, **experience_values_from_completed_resource(resource, payload.reflection)
    )
    if duplicate:
        raise HTTPException(
            status_code=409,
            detail=f"An experience draft for this project already exists (id={item.id})",
        )
    return item
