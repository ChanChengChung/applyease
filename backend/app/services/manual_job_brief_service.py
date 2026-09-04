"""Normalize structured manual job facts into the shared analysis request."""

from app.schemas.job import JobAnalyzeRequest, ManualJobBriefRequest


def build_manual_analysis_request(payload: ManualJobBriefRequest) -> JobAnalyzeRequest:
    return JobAnalyzeRequest(
        title=payload.title or "Untitled role",
        company=payload.company,
        description=payload.to_description(),
    )
