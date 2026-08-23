from fastapi import APIRouter

from app.api.v1 import (
    experiences,
    documents,
    jobs,
    materials,
    applications,
    resources,
    tracker,
    dashboard,
    ai_observability,
    applicant_profile,
    advisor,
    opportunities,
)

api_router = APIRouter()
api_router.include_router(experiences.router, prefix="/experiences", tags=["experiences"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
api_router.include_router(materials.router, prefix="/materials", tags=["materials"])
api_router.include_router(applications.router, prefix="/applications", tags=["applications"])
api_router.include_router(resources.router, prefix="/resources", tags=["resources"])
api_router.include_router(tracker.router, prefix="/tracker/applications", tags=["tracker"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(ai_observability.router, prefix="/ai", tags=["ai-observability"])
api_router.include_router(
    applicant_profile.router, prefix="/applicant-profile", tags=["applicant-profile"]
)
api_router.include_router(advisor.router, prefix="/advisor", tags=["advisor"])
api_router.include_router(opportunities.router, prefix="/opportunities", tags=["opportunities"])
