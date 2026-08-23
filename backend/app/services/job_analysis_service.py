"""Deterministic job requirement extraction and explainable matching."""

from __future__ import annotations

import re

from app.models.experience import Experience
from app.models.job import Job
from app.schemas.job import Evidence, MatchReport


KNOWN_SKILLS = [
    "Python",
    "SQL",
    "TypeScript",
    "JavaScript",
    "React",
    "FastAPI",
    "PostgreSQL",
    "PyTorch",
    "C++",
    "Docker",
    "Machine Learning",
    "Deep Learning",
    "Transformer",
    "Pandas",
    "NumPy",
    "Git",
    "RNN",
    "Reinforcement Learning",
    "MATLAB",
    "C",
    "Statistics",
    "Probability",
    "Linear Algebra",
    "Risk Management",
    "Quantitative Research",
    "Market Making",
    "Algorithms",
    "Data Structures",
    "NLP",
    "Computer Vision",
    "REST APIs",
]
_STOPWORDS = {
    "the",
    "and",
    "with",
    "for",
    "from",
    "this",
    "that",
    "you",
    "are",
    "will",
    "have",
    "has",
    "our",
    "your",
    "into",
    "using",
    "about",
    "role",
    "work",
    "years",
}


def _contains(text: str, phrase: str) -> bool:

    if phrase in {"C", "C++"}:

        return bool(re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text, re.I))

    return phrase.casefold() in text.casefold()


def _clean_items(values: list[str] | None, limit: int = 30) -> list[str]:
    result: list[str] = []

    seen: set[str] = set()

    for value in values or []:
        text = re.sub(r"\s+", " ", str(value)).strip(" -•●▪\t")[:500]

        if text and text.casefold() not in seen:
            result.append(text)

            seen.add(text.casefold())

    return result[:limit]


def extract_job_requirements(description: str) -> dict[str, list[str]]:
    lines = [
        re.sub(r"\s+", " ", line.strip(" -•●▪\t"))
        for line in description.splitlines()
        if line.strip()
    ]

    skills = [skill for skill in KNOWN_SKILLS if _contains(description, skill)]

    required: list[str] = []

    preferred: list[str] = []

    responsibilities: list[str] = []

    qualifications: list[str] = []

    for line in lines:
        lower = line.casefold()

        if any(
            word in lower for word in ["required", "must have", "must-have", "essential", "minimum"]
        ):
            required.append(line)

        elif any(word in lower for word in ["preferred", "nice to have", "plus", "bonus"]):
            preferred.append(line)

        elif any(
            word in lower
            for word in [
                "responsib",
                "develop",
                "build",
                "design",
                "analy",
                "research",
                "implement",
            ]
        ):
            responsibilities.append(line)

        elif any(
            word in lower
            for word in ["degree", "qualification", "experience", "eligible", "enrolled"]
        ):
            qualifications.append(line)
    required_skill_names = [
        skill for skill in skills if not any(_contains(line, skill) for line in preferred)
    ] or skills.copy()

    preferred_skill_names = [
        skill for skill in skills if any(_contains(line, skill) for line in preferred)
    ]

    return {
        "required_skills": _clean_items(required_skill_names),
        "preferred_skills": _clean_items(preferred_skill_names),
        "responsibilities": _clean_items(responsibilities, 20),
        "qualifications": _clean_items(qualifications, 20),
    }


def _experience_text(item: Experience) -> str:
    achievements = " ".join(
        str(a.get("text", "")) for a in (item.achievements or []) if isinstance(a, dict)
    )

    return " ".join(
        (
            item.title or "",
            item.organization or "",
            item.description or "",
            " ".join(item.skills or []),
            achievements,
        )
    )


def _tokens(text: str) -> set[str]:

    return {
        token
        for token in re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]{1,}", text.casefold())
        if token not in _STOPWORDS
    }


def _evidence_quote(item: Experience, requirement: str) -> str:
    segments = [line.strip() for line in (item.description or "").splitlines() if line.strip()]

    segments.extend(str(skill).strip() for skill in (item.skills or []) if str(skill).strip())

    segments.extend(
        str(a.get("text", "")).strip()
        for a in (item.achievements or [])
        if isinstance(a, dict) and str(a.get("text", "")).strip()
    )

    return next(
        (segment for segment in segments if _contains(segment, requirement)),
        segments[0] if segments else item.title,
    )


def _matched(
    requirements: list[str], confirmed: list[Experience]
) -> tuple[list[str], list[str], list[Evidence]]:
    matched: list[str] = []

    evidence: list[Evidence] = []

    for requirement in requirements:
        item = next(
            (
                candidate
                for candidate in confirmed
                if _contains(_experience_text(candidate), requirement)
            ),
            None,
        )

        if item:
            matched.append(requirement)

            evidence.append(
                Evidence(
                    requirement=requirement,
                    experience_id=item.id,
                    experience_title=item.title,
                    evidence=_evidence_quote(item, requirement),
                )
            )

    return (
        matched,
        [requirement for requirement in requirements if requirement not in matched],
        evidence,
    )


def _relevance_score(job: Job, confirmed: list[Experience]) -> int:
    job_tokens = _tokens(
        " ".join((job.title or "", job.description or "", *(job.responsibilities or [])))
    )

    if not job_tokens or not confirmed:

        return 0
    values = []

    for item in confirmed:
        overlap = len(job_tokens & _tokens(_experience_text(item)))

        values.append(min(overlap / max(len(job_tokens), 1), 1.0))

    return round(max(values, default=0) * 25)


def build_match_report(job: Job, experiences: list[Experience]) -> MatchReport:
    confirmed = [item for item in experiences if item.confirmed]

    required = _clean_items(job.required_skills) or _clean_items(
        extract_job_requirements(job.description)["required_skills"]
    )

    preferred = [
        skill
        for skill in _clean_items(job.preferred_skills)
        if skill.casefold() not in {item.casefold() for item in required}
    ]

    matched_required, missing_required, required_evidence = _matched(required, confirmed)

    matched_preferred, missing_preferred, preferred_evidence = _matched(preferred, confirmed)

    evidence = required_evidence + preferred_evidence

    quantified = min(sum(bool(item.achievements) for item in confirmed), 1)

    education = (
        10
        if any(
            _contains(_experience_text(item), "university")
            or _contains(_experience_text(item), "degree")
            for item in confirmed
        )
        else 0
    )

    breakdown = {
        "required_skill_match": round(len(matched_required) / max(len(required), 1) * 40),
        "preferred_skill_match": (
            round(len(matched_preferred) / max(len(preferred), 1) * 10) if preferred else 0
        ),
        "experience_relevance": _relevance_score(job, confirmed),
        "quantified_evidence": quantified * 15,
        "education_background": education,
        "qualification_coverage": 0,
    }

    warnings: list[str] = []

    if not confirmed:
        warnings.append("没有已确认经历；匹配结果不会使用待核对内容。")

    if not required:
        warnings.append("未识别到明确技能要求，分数仅供参考。")
    overall = min(sum(breakdown.values()), 100)

    return MatchReport(
        job=job,
        overall_score=overall,
        matched_skills=matched_required + matched_preferred,
        missing_skills=missing_required + missing_preferred,
        evidence=evidence,
        considered_experience_ids=[item.id for item in confirmed],
        matched_required_skills=matched_required,
        missing_required_skills=missing_required,
        matched_preferred_skills=matched_preferred,
        missing_preferred_skills=missing_preferred,
        score_breakdown=breakdown,
        warnings=warnings,
    )


def analyze_job_requirements(description: str, *, ai_enabled: bool) -> dict[str, list[str]]:

    if ai_enabled:
        from app.ai.job_analyzer import extract_job_requirements_safe

        return extract_job_requirements_safe(description)

    return extract_job_requirements(description)


def match_job(
    job: Job,
    experiences: list[Experience],
    *,
    ai_enabled: bool,
    db=None,
    user_id: int | None = None,
) -> MatchReport:

    if ai_enabled:
        from app.ai.job_analyzer import build_match_report_safe

        return build_match_report_safe(job, experiences, db=db, user_id=user_id)

    return build_match_report(job, experiences)
