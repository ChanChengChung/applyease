"""Web-grounded plans: profile evidence + target role + live official sources."""

from datetime import datetime, timezone
import json
import re
from typing import Any

from app.ai.providers import GeminiProvider, ProviderError
from app.models.experience import Experience
from app.models.job import Job
from app.services.resource_service import recommend_resources

SCHEMA = {
    "type": "object",
    "properties": {
        "profile_summary": {"type": "string"},
        "gaps": {"type": "array", "items": {"type": "string"}},
        "method": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["profile_summary", "gaps", "method"],
}


def _plain_text(value: Any, *, purpose: str, limit: int) -> str:
    """Turn permissive grounded-model output into safe human-facing text.

    Google Search grounding cannot currently be combined with Gemini's strict
    JSON response MIME type.  Even when asked for string arrays, a model may
    return objects such as ``{"capability_gap": ..., "explanation": ...}``.
    Never stringify those Python objects into the UI; select their meaningful
    fields, collapse whitespace, and place a hard display bound on them.
    """
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("{") or text.startswith("["):
            try:
                return _plain_text(json.loads(text), purpose=purpose, limit=limit)
            except json.JSONDecodeError:
                pass
        return re.sub(r"\s+", " ", text).strip()[:limit]
    if not isinstance(value, dict):
        return ""

    if purpose == "gap":
        headline = value.get("capability_gap") or value.get("gap") or value.get("title")
        detail = value.get("explanation") or value.get("reason")
    else:
        headline = value.get("action") or value.get("step") or value.get("title")
        detail = value.get("description") or value.get("explanation") or value.get("why")

    head = _plain_text(headline, purpose=purpose, limit=max(80, limit // 2))
    body = _plain_text(detail, purpose=purpose, limit=limit)
    if head and body and body.casefold() not in head.casefold():
        return f"{head} — {body}"[:limit]
    return (head or body)[:limit]


def _clean_items(values: Any, *, purpose: str, limit: int, max_items: int) -> list[str]:
    rows = values if isinstance(values, list) else []
    cleaned: list[str] = []
    for value in rows:
        text = _plain_text(value, purpose=purpose, limit=limit)
        if text and text not in cleaned:
            cleaned.append(text)
        if len(cleaned) >= max_items:
            break
    return cleaned


def _profile_summary(value: Any) -> str:
    text = _plain_text(value, purpose="summary", limit=700)
    # A research brief is context, not an essay. Preserve at most two sentence
    # boundaries when the model is unusually verbose.
    pieces = re.split(r"(?<=[.!?。！？])\s+", text)
    return " ".join(pieces[:2]).strip()[:520]


def build_research_plan(
    job: Job,
    experiences: list[Experience],
    resources: list,
    *,
    weekly_hours: int,
    weeks: int,
    goal: str,
    language: str,
    learning_style: str = "hands_on",
) -> dict:
    facts = [
        {"title": item.title, "description": item.description[:600], "skills": item.skills[:20]}
        for item in experiences
        if item.confirmed
    ][:10]
    budget = weekly_hours * weeks
    prompt = f"""You are an evidence-first career learning mentor. Reply in {language}. Use Google Search to research current public, primary sources only: official competition organisers, official software/documentation, public-data publishers, university/research institutions, or the organisation that runs the programme. Exclude blogs, Medium, Substack, Scribd, SEO pages, trading-course sellers and unverified aggregators. Do not claim the student completed anything. Do not recommend beginner material for skills clearly evidenced unless you explain missing depth. Return ONLY a valid JSON object, without markdown, with exactly: profile_summary (string), gaps (2-5 capability gaps), method (3-5 ordered, concrete actions). Cite only sources retrieved by the search tool.\nTARGET JOB: {job.company} · {job.title}\nREQUIREMENTS: {job.required_skills}; preferred={job.preferred_skills}\nCONFIRMED EVIDENCE: {facts}\nCONSTRAINTS: {weekly_hours} hours/week for {weeks} weeks ({budget} hours); goal={goal}."""
    prompt += (
        "\\nLEARNING STYLE: "
        f"{learning_style}. Respect it in the ordered actions: hands_on means "
        "a small verifiable build first; guided means structured official "
        "documentation and exercises; intensive means a demanding deliverable "
        "with deliberate practice. Do not mention the style label unless useful."
    )
    try:
        data, sources = GeminiProvider().search_grounded_json(prompt, SCHEMA)
        if not sources:
            raise ProviderError("No verifiable search sources")
        gaps = _clean_items(data.get("gaps"), purpose="gap", limit=300, max_items=5)
        method = _clean_items(data.get("method"), purpose="method", limit=500, max_items=5)
        summary = _profile_summary(data.get("profile_summary"))
        # An incomplete response is less useful than the reviewed fallback and
        # must never leave the UI with raw JSON or empty learning actions.
        if not summary or not gaps or not method:
            raise ProviderError("Grounded response did not satisfy the plan contract")
        return {
            "profile_summary": summary,
            "gaps": gaps,
            "method": method,
            "sources": sources,
            "searched_at": datetime.now(timezone.utc),
            "used_fallback": False,
        }
    except ProviderError:
        fallback = recommend_resources(
            list(job.required_skills or [])[:5],
            resources,
            max_total_hours=budget,
            limit=4,
            goal=goal,
            language=language,
        )
        return {
            "profile_summary": "Live web research is unavailable; showing reviewed fallback resources for the selected role.",
            "gaps": list(job.required_skills or [])[:5],
            "method": [x.recommendation_reason for x in fallback],
            "sources": [{"title": x.resource.title, "url": x.resource.url} for x in fallback],
            "searched_at": datetime.now(timezone.utc),
            "used_fallback": True,
        }
