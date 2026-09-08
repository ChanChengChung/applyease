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
    ResourceRead,
    StarterPlanRead,
    StarterPlanRequest,
    StarterPlanRefineRequest,
    StarterPlanUpdate,
    ResearchPlanRead,
    ResearchPlanRequest,
    ResearchPlanUpdate,
    ResourceFeedbackCreate,
    ResourceFeedbackRead,
)
from app.config import settings
from app.services.job_analysis_service import match_job
from app.services.resource_service import (
    RESOURCE_CATALOG,
    baseline_resource_score,
    match_level_for_score,
    recommend_resources,
)
from app.services.resource_experience_service import experience_values_from_completed_resource
from app.services.resource_web_search_service import search_and_persist_resources
from app.services.starter_plan_service import build_starter_plan, detect_plan_language
from app.services.research_plan_service import build_research_plan
from app.services.resource_health_service import update_resource_health

router = APIRouter()


@router.post("/{resource_id}/health-check", response_model=ResourceRead)
def health_check(resource_id: int, db: Session = Depends(get_db)):
    resource = resource_crud.get(db, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    resource = update_resource_health(db, resource)
    progress = resource_crud.progress_map(db)
    return _resource_payload(resource, progress.get(resource.id, False))


@router.post("/{resource_id}/feedback", response_model=ResourceFeedbackRead, status_code=201)
def feedback(
    resource_id: int,
    payload: ResourceFeedbackCreate,
    db: Session = Depends(get_db),
):
    resource = resource_crud.get(db, resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")
    return resource_crud.create_feedback(db, resource_id, payload.category, payload.message)


def _resource_payload(resource, completed: bool, recommendation=None) -> dict:

    # Saved-plan resources and completion updates do not carry a fresh
    # recommendation object. Use the deterministic resource-quality baseline
    # rather than the invalid ``0`` placeholder; job-specific recommendations
    # still use their actual role-match score.
    score = (
        recommendation.match_score
        if recommendation
        else baseline_resource_score(resource)
    )
    # Recommendations carry the qualitative band from the service.  Saved
    # resources are assigned the same band from their deterministic baseline.
    match_level = recommendation.match_level if recommendation else match_level_for_score(score)
    reason = (
        recommendation.recommendation_reason
        if recommendation
        else "基于资源可信度、技能信息和可验证交付物的基准匹配度。"
    )

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
        "match_score": score,
        "match_level": match_level,
        "matched_skills": recommendation.matched_skills if recommendation else [],
        "recommendation_reason": reason,
    }


def _starter_payload(db: Session, item) -> dict:
    resources = {resource.id: resource for resource in resource_crud.list_all(db)}
    progress = resource_crud.progress_map(db)
    return {
        "id": item.id,
        "interest": item.interest,
        "focus": item.focus,
        "headline": item.headline,
        "first_action": item.first_action,
        "milestones": item.milestones,
        "milestone_sections": item.milestone_sections or {},
        "resources": [
            _resource_payload(resources[resource_id], progress.get(resource_id, False))
            for resource_id in item.resource_ids
            if resource_id in resources
        ],
        "used_fallback": item.used_fallback,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


def _research_plan_payload(db: Session, item) -> dict:
    """Expose the starter-plan provenance alongside the research brief."""
    user_id = int(db.info.get("current_user_id") or 0)
    starter = None
    if item.starter_plan_id:
        starter = starter_plan_crud.get(db, item.starter_plan_id, user_id)
    return {
        "id": item.id,
        "job_id": item.job_id,
        "starter_plan_id": item.starter_plan_id,
        "starter_plan_interest": starter.interest if starter else None,
        "starter_plan_headline": starter.headline if starter else None,
        "profile_summary": item.profile_summary,
        "gaps": item.gaps,
        "method": item.method,
        "sources": item.sources,
        "searched_at": item.searched_at,
        "used_fallback": item.used_fallback,
        "focuses": item.focuses or [],
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


@router.post("/starter-plan", response_model=StarterPlanRead)
def starter_plan(payload: StarterPlanRequest, db: Session = Depends(get_db)):
    """AI-assisted, no-CV onboarding; it never creates experience evidence."""
    resource_crud.seed_if_empty(db, RESOURCE_CATALOG)
    # Starter-plan content follows the free-text intent rather than the global
    # interface locale supplied by the browser.
    content_language = detect_plan_language(payload.interest)
    plan = build_starter_plan(
        payload.interest,
        resource_crud.list_all(db),
        db=db,
        max_total_hours=payload.max_total_hours,
        language=content_language,
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
    saved = starter_plan_crud.create(
        db,
        int(db.info.get("current_user_id") or 0),
        {
            "interest": payload.interest,
            "focus": plan["focus"],
            "headline": plan["headline"],
            "first_action": plan["first_action"],
            "milestones": plan["milestones"],
            "milestone_sections": plan.get("milestone_sections", {}),
            "resource_ids": [item.resource.id for item in plan["resources"]],
            "used_fallback": bool(plan.get("used_fallback", False)),
        },
    )
    return {"id": saved.id, "interest": saved.interest, **plan, "resources": resource_payloads,
            "created_at": saved.created_at, "updated_at": saved.updated_at}


@router.get("/starter-plans", response_model=StarterPlanRead)
def get_saved_starter_plan(db: Session = Depends(get_db)):
    item = starter_plan_crud.get_latest(db, int(db.info.get("current_user_id") or 0))
    if not item:
        raise HTTPException(status_code=404, detail="Starter plan not found")
    return _starter_payload(db, item)


@router.get("/starter-plans/list", response_model=list[StarterPlanRead])
def list_saved_starter_plans(db: Session = Depends(get_db)):
    user_id = int(db.info.get("current_user_id") or 0)
    return [_starter_payload(db, item) for item in starter_plan_crud.list_for_user(db, user_id)]


@router.patch("/starter-plans/{plan_id}", response_model=StarterPlanRead)
def update_saved_starter_plan(
    plan_id: int, payload: StarterPlanUpdate, db: Session = Depends(get_db)
):
    user_id = int(db.info.get("current_user_id") or 0)
    item = starter_plan_crud.get(db, plan_id, user_id)
    if not item or item.id != plan_id:
        raise HTTPException(status_code=404, detail="Starter plan not found")
    item = starter_plan_crud.update(db, item, payload.model_dump())
    return _starter_payload(db, item)


@router.delete("/starter-plans/{plan_id}", status_code=204)
def delete_saved_starter_plan(plan_id: int, db: Session = Depends(get_db)):
    item = starter_plan_crud.get(db, plan_id, int(db.info.get("current_user_id") or 0))
    if not item:
        raise HTTPException(status_code=404, detail="Starter plan not found")
    starter_plan_crud.delete(db, item)


@router.post("/starter-plans/{plan_id}/refine", response_model=StarterPlanRead)
def refine_saved_starter_plan(
    plan_id: int, payload: StarterPlanRefineRequest, db: Session = Depends(get_db)
):
    """Refine a no-job plan from saved onboarding intent, never from invented experience."""
    user_id = int(db.info.get("current_user_id") or 0)
    item = starter_plan_crud.get(db, plan_id, user_id)
    if not item or item.id != plan_id:
        raise HTTPException(status_code=404, detail="Starter plan not found")
    resource_crud.seed_if_empty(db, RESOURCE_CATALOG)
    content_language = detect_plan_language(item.interest)
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
        db=db,
        max_total_hours=payload.max_total_hours,
        language=content_language,
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
            "milestone_sections": plan.get("milestone_sections", {}),
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
    user_id = int(db.info.get("current_user_id") or 0)
    starter = None
    if payload.starter_plan_id is not None:
        starter = starter_plan_crud.get(db, payload.starter_plan_id, user_id)
        if not starter:
            raise HTTPException(status_code=404, detail="Starter plan not found")
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
        focuses=payload.focuses,
    )
    # The nullable key is persisted even for unlinked plans so repeated
    # generations update the same provenance bucket instead of creating an
    # accidental duplicate each time.
    values["starter_plan_id"] = starter.id if starter else None
    values["focuses"] = payload.focuses
    saved = research_plan_crud.create_or_replace(db, user_id, job.id, values)
    return _research_plan_payload(db, saved)


@router.get("/research-plans/history", response_model=list[ResearchPlanRead])
def list_research_plan_history(
    job_id: int = Query(gt=0), db: Session = Depends(get_db)
):
    """Return saved role plans for the document-style history folder."""
    user_id = int(db.info.get("current_user_id") or 0)
    return [
        _research_plan_payload(db, item)
        for item in research_plan_crud.list_for_job(
            db, user_id, job_id, match_starter_plan=True
        )
    ]


@router.get("/research-plans", response_model=ResearchPlanRead)
def get_saved_research_plan(
    job_id: int = Query(gt=0),
    starter_plan_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
):
    """Restore the user's saved, editable plan after navigation or refresh."""
    user_id = int(db.info.get("current_user_id") or 0)
    item = research_plan_crud.latest_for_job(
        db,
        user_id,
        job_id,
        starter_plan_id,
        # A request without starter_plan_id is the role workspace bucket;
        # never restore a starter-linked plan into that view.
        match_starter_plan=True,
    )
    if not item:
        raise HTTPException(status_code=404, detail="Research plan not found")
    return _research_plan_payload(db, item)


@router.patch("/research-plans/{plan_id}", response_model=ResearchPlanRead)
def update_research_plan(plan_id: int, payload: ResearchPlanUpdate, db: Session = Depends(get_db)):
    item = research_plan_crud.get(db, plan_id, int(db.info.get("current_user_id") or 0))
    if not item:
        raise HTTPException(status_code=404, detail="Research plan not found")
    return _research_plan_payload(db, research_plan_crud.update(db, item, payload.model_dump()))


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

    # Recommendations must use the stable server-resolved report.  Otherwise a
    # transient model degradation can erase a technology such as OCaml and
    # make the resource ranker fall back to unrelated beginner material.
    report = match_job(job, experience_crud.list_all(db), ai_enabled=False)

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
    if not resources and report.missing_skills:
        query = " ".join(
            [job.title, *report.missing_skills[:5], "official learning documentation"]
        )
        resources, _ = search_and_persist_resources(
            db,
            query,
            max_total_hours=(max_total_hours if max_total_hours is not None else max_hours) or 8,
            limit=min(limit, 4),
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
