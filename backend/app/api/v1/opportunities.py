from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.ai_quota import reserve_ai_generation, reserve_job_import
from app.ai.observability import ai_user_scope
from app.config import settings
from app.crud import experience as experience_crud
from app.crud import job as job_crud
from app.crud import opportunity as opportunity_crud
from app.crud import tracker as tracker_crud
from app.db.session import get_db
from app.schemas.job import JobRead
from app.schemas.opportunity import (
    OpportunityImportTrackedRead,
    OpportunitySearchRead,
    OpportunitySearchRequest,
)
from app.services.tracker_service import serialize_tracker
from app.services.job_analysis_service import analyze_job_requirements
from app.services.job_import_service import import_public_job_page, validate_public_job_url
from app.services.opportunity_service import discover_opportunities

router = APIRouter()


def _import_reviewed_opportunity(search_id: int, opportunity_index: int, db: Session):
    """Create an analysed job only from a verified, reviewed radar result."""
    search = opportunity_crud.get(db, search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Opportunity search not found")
    opportunities = list(search.opportunities or [])
    if opportunity_index < 0 or opportunity_index >= len(opportunities):
        raise HTTPException(status_code=404, detail="Opportunity not found")
    row = opportunities[opportunity_index]
    if not isinstance(row, dict):
        raise HTTPException(status_code=422, detail="Saved opportunity is invalid")
    source_url = str(row.get("source_url", ""))
    trusted_urls = {
        str(source.get("url", "")) for source in (search.sources or []) if isinstance(source, dict)
    }
    if source_url not in trusted_urls:
        raise HTTPException(
            status_code=422, detail="Opportunity source is not a verified search result"
        )
    try:
        reserve_job_import(db)
        draft = import_public_job_page(validate_public_job_url(source_url))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    title = draft.title or str(row.get("title", ""))
    company = draft.company or str(row.get("company", ""))
    description = draft.description
    if len(description.strip()) < 20:
        raise HTTPException(
            status_code=422,
            detail="The official page did not expose enough job-description text. Open the source and import it manually after review.",
        )
    if settings.ai_job_analysis_enabled:
        reserve_ai_generation(db)
    with ai_user_scope(db.info.get("current_user_id")):
        requirements = analyze_job_requirements(
            description, ai_enabled=settings.ai_job_analysis_enabled
        )
    return job_crud.create(
        db, title=title, company=company, description=description, **requirements
    )


@router.post("/search", response_model=OpportunitySearchRead)
def search_opportunities(payload: OpportunitySearchRequest, db: Session = Depends(get_db)):
    if not payload.consent_to_web_search:
        raise HTTPException(
            status_code=400,
            detail="Explicit consent is required before ApplyEase searches the public web with your confirmed evidence summary.",
        )
    confirmed_experiences = experience_crud.list_all(db, confirmed=True, limit=500)
    if not confirmed_experiences:
        raise HTTPException(
            status_code=409,
            detail="Confirm at least one experience before using Opportunity Radar. This prevents unsupported recommendations.",
        )
    # Empty is kept as a backwards-compatible "all confirmed" request. New
    # clients always send the visible selected IDs, so the stored audit trail
    # precisely represents what the student approved for this web search.
    requested_ids = set(payload.experience_ids)
    available_ids = {item.id for item in confirmed_experiences}
    if requested_ids and not requested_ids.issubset(available_ids):
        raise HTTPException(
            status_code=422,
            detail="Selected evidence must exist and be confirmed before it can be used for public-web research.",
        )
    selected_experiences = (
        [item for item in confirmed_experiences if item.id in requested_ids]
        if requested_ids
        else confirmed_experiences
    )
    if not selected_experiences:
        raise HTTPException(
            status_code=409, detail="Select at least one confirmed experience before searching."
        )
    # Official ATS discovery is keyless.  The optional guided web-research
    # mode uses a dedicated server-side search token, rather than consuming an
    # LLM generation quota or relying on Google Search grounding.
    with ai_user_scope(db.info.get("current_user_id")):
        values = discover_opportunities(
            selected_experiences,
            **payload.model_dump(exclude={"consent_to_web_search", "experience_ids"}),
        )
    return opportunity_crud.create(
        db,
        **payload.model_dump(exclude={"consent_to_web_search", "limit"}),
        **values,
    )


@router.get("/searches", response_model=list[OpportunitySearchRead])
def list_searches(db: Session = Depends(get_db)):
    return opportunity_crud.list_recent(db)


@router.delete("/searches/{search_id}", status_code=204)
def delete_search(search_id: int, db: Session = Depends(get_db)):
    search = opportunity_crud.get(db, search_id)
    if not search:
        raise HTTPException(status_code=404, detail="Opportunity search not found")
    opportunity_crud.delete(db, search)


@router.post("/searches/{search_id}/import/{opportunity_index}", response_model=JobRead)
def import_opportunity(search_id: int, opportunity_index: int, db: Session = Depends(get_db)):
    return _import_reviewed_opportunity(search_id, opportunity_index, db)


@router.post(
    "/searches/{search_id}/import-and-track/{opportunity_index}",
    response_model=OpportunityImportTrackedRead,
)
def import_and_track_opportunity(
    search_id: int, opportunity_index: int, db: Session = Depends(get_db)
):
    """Review/import a verified role, then create its application tracker record.

    Tracking starts at ``saved``: importing a role is an expression of intent,
    never a claim that an application was submitted.
    """
    job = _import_reviewed_opportunity(search_id, opportunity_index, db)
    user_id = db.info.get("current_user_id")
    tracker = tracker_crud.get_by_job(db, user_id, job.id)
    if tracker is None:
        tracker = tracker_crud.create(
            db,
            company=job.company or "Unknown company",
            role=job.title or "Untitled role",
            job_id=job.id,
            status="saved",
            notes="Imported from a reviewed Opportunity Radar result.",
        )
    return OpportunityImportTrackedRead(job=job, tracker=serialize_tracker(tracker))
