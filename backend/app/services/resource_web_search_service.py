"""Open-web retrieval for starter-plan learning resources.

Starter plans are not limited to the small, technology-oriented catalogue.  We
retrieve public learning pages for the student's own wording, rank the snippets
with the same local embedding fallback used by the evidence RAG, and persist
the selected pages so progress/completion still works after refresh.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.providers import ProviderError, RateLimitExceeded
from app.config import settings
from app.models.resource import LearningResource
from app.services.rag_service import _cosine, embed
from app.services.resource_service import ResourceRecommendation, match_level_for_score


_BOCHA_URL = "https://api.bochaai.com/v1/web-search"
_BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"


def _clean(value: object, limit: int = 600) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _safe_url(value: object) -> str | None:
    parsed = urlparse(str(value or "").strip())
    host = (parsed.hostname or "").casefold()
    if parsed.scheme != "https" or not host or parsed.username or parsed.password:
        return None
    if host in {"localhost", "127.0.0.1", "::1"}:
        return None
    return parsed._replace(fragment="").geturl()


def _bocha(query: str) -> list[dict]:
    token = settings.bocha_search_api_key.strip()
    if not token:
        return []
    response = httpx.post(
        _BOCHA_URL,
        json={"query": query, "count": 12, "summary": True},
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "ApplyEaseResourceRAG/1.0",
        },
        timeout=settings.bocha_search_timeout_seconds,
        trust_env=False,
    )
    if response.status_code == 429:
        raise RateLimitExceeded("Bocha Search API quota is temporarily exhausted")
    response.raise_for_status()
    payload = response.json()
    pages = (payload.get("data", {}) or {}).get("webPages", {})
    rows = pages.get("value", []) if isinstance(pages, dict) else []
    return [row for row in rows if isinstance(row, dict)]


def _brave(query: str) -> list[dict]:
    token = settings.brave_search_api_key.strip()
    if not token:
        return []
    response = httpx.get(
        _BRAVE_URL,
        params={"q": query, "count": 12, "result_filter": "web"},
        headers={"X-Subscription-Token": token, "Accept": "application/json"},
        timeout=settings.brave_search_timeout_seconds,
        trust_env=False,
    )
    if response.status_code == 429:
        raise RateLimitExceeded("Brave Search API quota is temporarily exhausted")
    response.raise_for_status()
    payload = response.json()
    rows = (payload.get("web", {}) or {}).get("results", [])
    return [row for row in rows if isinstance(row, dict)]


def _candidate_rows(query: str) -> list[dict]:
    rows: list[dict] = []
    errors: list[Exception] = []
    for provider in (_bocha, _brave):
        try:
            rows.extend(provider(query))
            if rows:
                break
        except (httpx.HTTPError, ValueError, TypeError, ProviderError) as exc:
            errors.append(exc)
    # Search is an enhancement; callers retain the deterministic catalogue when
    # both configured providers are unavailable.
    del errors
    return rows


def search_and_persist_resources(
    db: Session,
    query: str,
    *,
    max_total_hours: int,
    limit: int = 4,
) -> tuple[list[ResourceRecommendation], bool]:
    """Retrieve and persist resources relevant to an arbitrary career interest.

    Returns ``(recommendations, used_fallback)``.  ``used_fallback`` is true
    when no web result was usable, so the UI/API can be transparent about a
    deterministic catalogue fallback.
    """
    rows = _candidate_rows(query)
    query_vector = embed(query)
    seen: set[str] = set()
    ranked: list[tuple[float, dict]] = []
    for row in rows:
        url = _safe_url(row.get("url") or row.get("link"))
        title = _clean(row.get("name") or row.get("title"), 250)
        description = _clean(row.get("snippet") or row.get("description"), 900)
        if not url or not title or url in seen:
            continue
        seen.add(url)
        score = _cosine(query_vector, embed(f"{title}\n{description}"))
        ranked.append((score, {"url": url, "title": title, "description": description}))

    ranked.sort(key=lambda item: item[0], reverse=True)
    recommendations: list[ResourceRecommendation] = []
    for score, candidate in ranked[:limit]:
        resource = db.scalar(select(LearningResource).where(LearningResource.url == candidate["url"]))
        if resource is None:
            host = (urlparse(candidate["url"]).hostname or "Web resource").removeprefix("www.")
            resource = LearningResource(
                title=candidate["title"],
                url=candidate["url"],
                provider=host[:100],
                skills=[],
                difficulty="beginner",
                duration_hours=max(1, min(8, max_total_hours)),
                # Public pages are not assumed to be free.  The UI can show the
                # source and the user can verify access/pricing before starting.
                free=False,
                description=candidate["description"],
                project={
                    "title": f"{candidate['title']} practice note",
                    "task": "Complete one small exercise or observation from this resource and explain what you learned.",
                    "estimated_days": 7,
                    "deliverables": ["Learning notes", "One worked example", "Short reflection"],
                    "completion_criteria": ["Source is cited", "Example is reproducible", "Limitations are noted"],
                    "cv_bullet_template": "Completed a source-backed learning exercise and documented a reproducible example.",
                },
                verified=False,
                link_status="unchecked",
            )
            db.add(resource)
            db.flush()
        match_score = max(1, min(100, round(score * 100)))
        recommendations.append(
            ResourceRecommendation(
                resource=resource,
                match_score=match_score,
                match_level=match_level_for_score(match_score),
                matched_skills=[],
                recommendation_reason="Retrieved from a public web search and ranked by semantic relevance.",
            )
        )
    if recommendations:
        db.commit()
        return recommendations, False
    return [], True
