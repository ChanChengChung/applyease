"""Grounded AI job analysis with deterministic fallbacks."""

from __future__ import annotations

import re
from typing import Any

from app.ai.providers import ProviderError, llm
from app.ai.observability import ai_trace, error_category, record_outcome
from app.ai.prompt_versions import JOB_MATCH, JOB_REQUIREMENTS
from app.models.experience import Experience
from app.models.job import Job
from app.schemas.job import Evidence, MatchReport
from app.services.job_analysis_service import build_match_report, extract_job_requirements
from app.services.rag_service import format_context, retrieve_context

JOB_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "required_skills": {"type": "array", "items": {"type": "string"}},
        "preferred_skills": {"type": "array", "items": {"type": "string"}},
        "responsibilities": {"type": "array", "items": {"type": "string"}},
        "qualifications": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["required_skills", "preferred_skills", "responsibilities", "qualifications"],
}

MATCH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "matched_skills": {"type": "array", "items": {"type": "string"}},
        "missing_skills": {"type": "array", "items": {"type": "string"}},
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "requirement": {"type": "string"},
                    "experience_id": {"type": "integer"},
                    "evidence": {"type": "string"},
                },
                "required": ["requirement", "experience_id", "evidence"],
            },
        },
    },
    "required": ["matched_skills", "missing_skills", "evidence"],
}


def _clean_list(value: Any, limit: int = 30) -> list[str]:

    if not isinstance(value, list):

        raise ProviderError("AI list field has an invalid type")
    result: list[str] = []

    seen: set[str] = set()

    for raw in value:
        text = re.sub(r"\s+", " ", str(raw)).strip(" -•\t")[:500]

        key = text.casefold()

        if text and key not in seen:
            seen.add(key)
            result.append(text)

    return result[:limit]


def extract_job_requirements_ai(description: str) -> dict[str, list[str]]:
    prompt = (
        "Analyze this job posting. Extract only explicitly stated or clearly required information. "
        "Do not invent technologies. Separate mandatory and preferred skills. Copy responsibilities "
        "and qualifications concisely. Return JSON matching the supplied schema.\n\nJOB POSTING:\n"
        + description
    )

    result = llm.generate_json(prompt, JOB_SCHEMA)

    parsed = {
        "required_skills": _clean_list(result.get("required_skills")),
        "preferred_skills": _clean_list(result.get("preferred_skills")),
        "responsibilities": _clean_list(result.get("responsibilities"), 20),
        "qualifications": _clean_list(result.get("qualifications"), 20),
    }

    if not any(parsed.values()):

        raise ProviderError("AI found no usable job requirements")

    return parsed


def extract_job_requirements_safe(description: str) -> dict[str, list[str]]:

    with ai_trace("job_requirements", JOB_REQUIREMENTS, len(description)):

        try:
            result = extract_job_requirements_ai(description)

            record_outcome(status="success", provider="llm")

            return result

        except ProviderError as exc:
            result = extract_job_requirements(description)

            record_outcome(
                status="rule_fallback",
                provider="rules",
                category=error_category(exc),
                fallback_from="llm",
            )

            return result


def _source_text(item: Experience) -> str:
    achievements = " ".join(
        str(a.get("text", "")) for a in (item.achievements or []) if isinstance(a, dict)
    )

    return " ".join(
        (item.title, item.organization, item.description, " ".join(item.skills or []), achievements)
    )


def _is_grounded(quote: str, source: str) -> bool:
    normalize = lambda text: re.sub(r"\s+", " ", text).strip().casefold()

    return len(normalize(quote)) >= 8 and normalize(quote) in normalize(source)


def build_match_report_ai(
    job: Job, experiences: list[Experience], rag_context: str | None = None
) -> MatchReport:
    confirmed = [item for item in experiences if item.confirmed]

    if not confirmed:

        return build_match_report(job, [])
    requirements = list(
        dict.fromkeys([*(job.required_skills or []), *(job.preferred_skills or [])])
    )

    experience_payload = [
        {
            "id": item.id,
            "title": item.title,
            "organization": item.organization,
            "description": item.description,
            "skills": item.skills,
            "achievements": item.achievements,
        }
        for item in confirmed
    ]

    rag_block = ""
    if rag_context:
        rag_block = (
            "The following passages were retrieved from the applicant's own stored documents and "
            "experiences (retrieval-augmented context). Prefer them as additional grounding when they "
            "contain stronger evidence for a requirement; do not invent evidence absent from both sources.\n\n"
            f"RETRIEVED CONTEXT:\n{rag_context}\n\n"
        )

    prompt = (
        "Match the job requirements against only the confirmed experiences below. A match requires "
        "direct evidence. For every evidence value, copy an exact quote from that experience; never "
        "paraphrase or invent. Use only the listed experience IDs. Return JSON matching the schema.\n\n"
        f"{rag_block}"
        f"JOB REQUIREMENTS:\n{requirements}\n\nCONFIRMED EXPERIENCES:\n{experience_payload}"
    )

    result = llm.generate_json(prompt, MATCH_SCHEMA)

    by_id = {item.id: item for item in confirmed}

    canonical = {skill.casefold(): skill for skill in requirements}

    evidence: list[Evidence] = []

    evidenced_requirements: set[str] = set()

    raw_evidence = result.get("evidence")

    if not isinstance(raw_evidence, list):

        raise ProviderError("AI evidence field has an invalid type")

    for raw in raw_evidence:

        if not isinstance(raw, dict):

            continue
        item = by_id.get(raw.get("experience_id"))

        requirement = canonical.get(str(raw.get("requirement", "")).strip().casefold())

        quote = str(raw.get("evidence", "")).strip()

        if item and requirement and _is_grounded(quote, _source_text(item)):
            evidence.append(
                Evidence(
                    requirement=requirement,
                    experience_id=item.id,
                    experience_title=item.title,
                    evidence=quote,
                )
            )

            evidenced_requirements.add(requirement.casefold())
    claimed_matches = {value.casefold() for value in _clean_list(result.get("matched_skills"))}

    matched = [
        skill
        for skill in requirements
        if skill.casefold() in claimed_matches and skill.casefold() in evidenced_requirements
    ]

    missing = [skill for skill in requirements if skill not in matched]

    if claimed_matches and not matched:

        raise ProviderError("AI match claims were not supported by exact evidence")
    required = job.required_skills or []

    preferred = job.preferred_skills or []

    required_keys = {skill.casefold() for skill in required}

    matched_required = [skill for skill in matched if skill.casefold() in required_keys]

    matched_preferred = [skill for skill in matched if skill.casefold() not in required_keys]

    missing_required = [
        skill
        for skill in required
        if skill.casefold() not in {item.casefold() for item in matched_required}
    ]

    missing_preferred = [
        skill
        for skill in preferred
        if skill.casefold() not in {item.casefold() for item in matched_preferred}
    ]

    required_matched = len(matched_required)

    preferred_matched = len(matched_preferred)

    score = round(
        (required_matched / max(len(required), 1)) * 80
        + (preferred_matched / max(len(preferred), 1)) * 20
    )

    return MatchReport(
        job=job,
        overall_score=min(score, 100),
        matched_skills=matched,
        missing_skills=missing,
        evidence=evidence,
        considered_experience_ids=list(by_id),
        matched_required_skills=matched_required,
        missing_required_skills=missing_required,
        matched_preferred_skills=matched_preferred,
        missing_preferred_skills=missing_preferred,
        score_breakdown={
            "required_skill_match": round((required_matched / max(len(required), 1)) * 80),
            "preferred_skill_match": (
                round((preferred_matched / max(len(preferred), 1)) * 20) if preferred else 0
            ),
        },
        warnings=[],
    )


def build_match_report_safe(
    job: Job, experiences: list[Experience], db=None, user_id: int | None = None
) -> MatchReport:
    input_size = len(job.description) + sum(len(item.description or "") for item in experiences)

    with ai_trace("job_match", JOB_MATCH, input_size):

        try:
            rag_context = _build_match_rag_context(db, user_id, job)
            result = build_match_report_ai(job, experiences, rag_context=rag_context)

            record_outcome(status="success", provider="llm")

            return result

        except ProviderError as exc:
            result = build_match_report(job, experiences)

            record_outcome(
                status="rule_fallback",
                provider="rules",
                category=error_category(exc),
                fallback_from="llm",
            )

            return result


def _build_match_rag_context(db, user_id: int | None, job: Job) -> str | None:
    """Retrieve the applicant's documents/experiences relevant to the job for match grounding.

    This is the RAG call site inside job matching: it surfaces passages from the
    user's stored data that are most relevant to the target role, injected into the
    match prompt as supplementary evidence.
    """
    if db is None or user_id is None:
        return None
    try:
        query = " ".join(filter(None, [job.title, job.company, job.description or ""]))[:400]
        passages = retrieve_context(db, user_id, query, limit=4)
    except Exception:
        return None
    context = format_context(passages)
    return context or None
