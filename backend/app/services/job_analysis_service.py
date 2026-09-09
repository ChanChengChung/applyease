"""Deterministic job requirement extraction and explainable matching."""

from __future__ import annotations

import re
from datetime import datetime, timezone

from app.models.experience import Experience
from app.models.job import Job
from app.schemas.job import JobAnalyzeRequest
from app.ai.skills import (
    JOB_COMPETENCIES,
    JOB_COMPETENCY_EVIDENCE_TERMS,
    JOB_SKILL_ALIASES,
    JOB_SKILLS,
    applicable_job_competencies,
)
from app.schemas.job import EligibilityCheck, Evidence, JobRead, MatchReport
from app.services.match_level_service import match_level_for_score
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

_ELIGIBILITY_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("work_authorization", ("work authorization", "right to work", "visa", "sponsorship", "工作许可", "签证")),
    ("location", ("location", "based in", "located in", "工作地点", "地点")),
    ("graduation", ("graduat", "class of", "expected graduation", "毕业", "预计毕业")),
    ("education", ("currently enrolled", "undergraduate", "bachelor", "master", "degree", "在读", "本科", "硕士", "学位")),
    ("availability", ("availability", "available", "internship period", "duration", "weeks", "start date", "可实习", "实习周期", "每周", "开始日期")),
]

# These phrases indicate that a technology is part of the role's expected
# toolkit.  Merely mentioning a technology in a company overview or a generic
# example should not turn it into a mandatory skill.  The deterministic rules
# are also used to supplement an older/LLM-saved analysis on match reports.
_REQUIRED_SKILL_CONTEXT = (
    "required",
    "must have",
    "must-have",
    "essential",
    "minimum",
    "proficien",
    "experience with",
    "familiarity with",
    "knowledge of",
    "ability to",
    "skilled in",
    "expertise in",
    "working with",
    "background in",
    "primary development language",
    "programming language",
    "use ",
    "using ",
    "必备",
    "必須",
    "必须",
    "要求",
    "具备",
    "具備",
    "熟悉",
    "经验",
    "經驗",
)


def build_preview_job(
    payload: JobAnalyzeRequest, requirements: dict[str, list[str]], user_id: int | None
) -> Job:
    """Build the non-persisted job used by preview-only analysis routes."""
    return Job(
        id=0,
        user_id=user_id,
        **payload.model_dump(),
        **requirements,
        created_at=datetime.now(timezone.utc),
    )


def _eligibility_kinds(line: str) -> list[str]:
    lower = line.casefold()
    return [
        kind
        for kind, terms in _ELIGIBILITY_PATTERNS
        if any(term in lower for term in terms)
    ]


def _confirmed_eligibility_evidence(
    kind: str, requirement: str, confirmed: list[Experience]
) -> Evidence | None:
    """Only auto-confirm simple, explicit facts; sensitive facts stay manual."""
    requirement_lower = requirement.casefold()
    years = set(re.findall(r"\b20\d{2}\b", requirement))
    for item in confirmed:
        text = _experience_text(item)
        lower = text.casefold()
        matched = False
        if kind == "education":
            matched = (
                (any(word in requirement_lower for word in ("bachelor", "undergraduate", "本科"))
                 and any(word in lower for word in ("bachelor", "bsc", "undergraduate", "本科")))
                or (any(word in requirement_lower for word in ("master", "硕士"))
                    and any(word in lower for word in ("master", "msc", "硕士")))
            )
        elif kind == "graduation" and years:
            matched = bool(years & set(re.findall(r"\b20\d{2}\b", text)))
        elif kind == "location":
            locations = ("hong kong", "singapore", "london", "new york", "shanghai", "beijing", "香港", "上海", "北京")
            matched = any(place in requirement_lower and place in lower for place in locations)

        if matched:
            return Evidence(
                requirement=requirement,
                experience_id=item.id,
                experience_title=item.title,
                evidence=_evidence_quote(item, requirement),
            )
    return None


def build_eligibility_checks(job: Job, confirmed: list[Experience]) -> list[EligibilityCheck]:
    """Extract hard constraints separately from the skill-match score."""
    source_lines = [*job.qualifications, *job.description.splitlines()]
    checks: list[EligibilityCheck] = []
    seen: set[tuple[str, str]] = set()
    for raw_line in source_lines:
        requirement = re.sub(r"\s+", " ", raw_line.strip(" -•●▪\t"))
        for kind in _eligibility_kinds(requirement):
            key = (kind, requirement.casefold())
            if not requirement or key in seen:
                continue
            seen.add(key)
            evidence = _confirmed_eligibility_evidence(kind, requirement, confirmed)
            checks.append(
                EligibilityCheck(
                    kind=kind,
                    requirement=requirement,
                    status="met" if evidence else "needs_confirmation",
                    evidence=evidence.evidence if evidence else "",
                )
            )
    return checks[:8]


def _contains(text: str, phrase: str) -> bool:
    """Match a skill as a token, not as an arbitrary substring.

    The old substring check made ``data`` match ``candidate`` and ``C`` match
    ``C++``.  ASCII skill names use English word boundaries while non-ASCII
    phrases retain a case-insensitive substring match for Chinese text.
    """
    value = str(phrase).strip()
    if not value:
        return False

    if value == "C":
        # C is a special case because + and # are not word characters, yet
        # they are part of neighbouring language names (C++/C#).
        return bool(re.search(r"(?<![A-Za-z0-9+#])C(?![A-Za-z0-9+#])", text, re.I))

    if re.fullmatch(r"[A-Za-z0-9+#.\- ]+", value):
        pattern = r"\s+".join(re.escape(part) for part in value.split())
        return bool(
            re.search(
                rf"(?<![A-Za-z0-9]){pattern}(?![A-Za-z0-9])",
                text,
                re.I,
            )
        )

    return value.casefold() in text.casefold()


def _clean_items(values: list[str] | None, limit: int = 30) -> list[str]:
    result: list[str] = []

    seen: set[str] = set()

    for value in values or []:
        text = re.sub(r"\s+", " ", str(value)).strip(" -•●▪\t")[:500]

        if text and text.casefold() not in seen:
            result.append(text)

            seen.add(text.casefold())

    return result[:limit]


def _skill_in_preferred_context(line: str, skill: str) -> bool:
    """Return whether a skill occurs in the preferred portion of a line."""
    lower = line.casefold()
    for marker in ("preferred", "nice to have", "plus", "bonus"):
        start = lower.find(marker)
        if start < 0:
            continue
        # Handle both “Preferred: Python” and “Python preferred”.  Restrict
        # the before-marker check to the current semicolon/pipe clause so a
        # preceding required skill is not accidentally reclassified.
        after = line[start + len(marker) :]
        before = re.split(r"[;|\n]", line[:start])[-1]
        if "required" in before.casefold() and "," in before:
            before = before.rsplit(",", 1)[-1]
        if _contains(after, skill) or _contains(before, skill):
            return True
    return False


def _requirement_is_stated(text: str, requirement: str) -> bool:
    """Check the wording used in the posting for a canonical requirement."""
    terms = (*JOB_SKILL_ALIASES.get(requirement, ()), *JOB_COMPETENCIES.get(requirement, (requirement,)))
    return any(_contains(text, term) for term in terms)


def extract_job_requirements(description: str) -> dict[str, list[str]]:
    lines = [
        re.sub(r"\s+", " ", line.strip(" -•●▪\t"))
        for line in description.splitlines()
        if line.strip()
    ]
    skills = [
        skill
        for skill in JOB_SKILLS
        if any(_contains(description, term) for term in JOB_SKILL_ALIASES.get(skill, (skill,)))
    ]
    applicable_competencies = applicable_job_competencies(description)
    skills.extend(
        competency
        for competency, posting_terms in applicable_competencies.items()
        if any(_contains(description, term) for term in posting_terms)
    )
    required: list[str] = []
    preferred: list[str] = []
    responsibilities: list[str] = []
    qualifications: list[str] = []

    for line in lines:
        # Required, preferred and responsibility content frequently share a
        # line. Splitting clauses prevents a later “preferred” from demoting
        # an earlier “required” skill.
        clauses = [
            clause.strip()
            for clause in re.split(r"(?<=[.!?。！？])\s*|[;；|]", line)
            if clause.strip()
        ]
        for clause in clauses:
            lower = clause.casefold()
            is_required = any(
                word in lower
                for word in (
                    "required",
                    "must have",
                    "must-have",
                    "essential",
                    "minimum",
                    "必备",
                    "必備",
                    "必須",
                    "必须",
                    "任职要求",
                    "職位要求",
                )
            )
            is_preferred = any(
                word in lower
                for word in (
                    "preferred",
                    "nice to have",
                    "plus",
                    "bonus",
                    "加分",
                    "优先",
                    "優先",
                    "加分项",
                    "加分項",
                )
            )
            if is_required:
                required.append(clause)
            if is_preferred:
                preferred.append(clause)
            if not is_required and not is_preferred and any(
                word in lower
                for word in (
                    "responsib", "develop", "build", "design", "analy", "research", "implement"
                )
            ):
                responsibilities.append(clause)
            elif not is_required and not is_preferred and any(
                word in lower
                for word in ("degree", "qualification", "experience", "eligible", "enrolled")
            ):
                qualifications.append(clause)

    preferred_skill_names = [
        skill for skill in skills if any(_requirement_is_stated(clause, skill) for clause in preferred)
    ]
    required_context_lines = [
        clause
        for clause in [*required, *responsibilities, *qualifications]
        if any(marker in clause.casefold() for marker in _REQUIRED_SKILL_CONTEXT)
    ]
    required_skill_names = [
        skill
        for skill in skills
        if any(_requirement_is_stated(clause, skill) for clause in required_context_lines)
        and skill not in preferred_skill_names
    ]
    # A single qualifications sentence often contains several requirements.
    # Do not stop after finding the first one (for example, “supply chain”)
    # or a later “project management experience” requirement is silently
    # discarded. These are still grounded in a structured job section, not a
    # company overview or arbitrary prose.
    structured_lines = [*required, *qualifications, *responsibilities]
    required_skill_names.extend(
        skill
        for skill in skills
        if any(_requirement_is_stated(clause, skill) for clause in structured_lines)
        and skill not in preferred_skill_names
    )

    return {
        "required_skills": _clean_items(required_skill_names),
        "preferred_skills": _clean_items(preferred_skill_names),
        "responsibilities": _clean_items(responsibilities, 20),
        "qualifications": _clean_items(qualifications, 20),
    }


def _resolved_job_skills(job: Job) -> tuple[list[str], list[str]]:
    """Resolve persisted and deterministic requirements on the server.

    Analyses saved before the stricter extractor (or produced by an LLM that
    omitted a technology) must not permanently lose requirements.  Merge the
    persisted values with grounded rule extraction, then keep preferred skills
    out of the mandatory list.
    """
    extracted = extract_job_requirements(job.description or "")
    required = _clean_items([*(job.required_skills or []), *extracted["required_skills"]])
    preferred = _clean_items([*(job.preferred_skills or []), *extracted["preferred_skills"]])
    required_keys = {item.casefold() for item in required}
    return required, [item for item in preferred if item.casefold() not in required_keys]


def _job_read_with_resolved_skills(
    job: Job, required: list[str], preferred: list[str]
) -> JobRead:
    """Expose the same server-resolved skills that the report uses.

    The UI renders the skill chips from ``report.job``.  Returning the original
    persisted JSON there would make the report say “OCaml is missing” while the
    required-skills section still showed only the stale Python list.
    """
    payload = JobRead.model_validate(
        {
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "description": job.description,
            "source_url": getattr(job, "source_url", None) or "",
            "required_skills": job.required_skills or [],
            "preferred_skills": job.preferred_skills or [],
            "responsibilities": job.responsibilities or [],
            "qualifications": job.qualifications or [],
            "library_saved": getattr(job, "library_saved", False),
            "created_at": job.created_at,
        }
    )
    payload.required_skills = required
    payload.preferred_skills = preferred
    return payload


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


def _matches_requirement(text: str, requirement: str) -> bool:
    """Match a stated requirement with explicit, reviewable experience text."""
    terms = (
        requirement,
        *JOB_SKILL_ALIASES.get(requirement, ()),
        *JOB_COMPETENCY_EVIDENCE_TERMS.get(requirement, ()),
    )
    return any(_contains(text, term) for term in terms)


def _evidence_quote(item: Experience, requirement: str) -> str:
    segments = [line.strip() for line in (item.description or "").splitlines() if line.strip()]

    segments.extend(str(skill).strip() for skill in (item.skills or []) if str(skill).strip())

    segments.extend(
        str(a.get("text", "")).strip()
        for a in (item.achievements or [])
        if isinstance(a, dict) and str(a.get("text", "")).strip()
    )

    return next(
        (segment for segment in segments if _matches_requirement(segment, requirement)),
        item.title,
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
                if _matches_requirement(_experience_text(candidate), requirement)
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


def _relevance_score(job: Job, confirmed: list[Experience], requirements: list[str]) -> int:
    # Do not dilute experience relevance with a long employer introduction.
    # Title, responsibilities and qualifications are the applicant-facing part
    # of the role; explicit requirement coverage is scored separately below.
    job_tokens = _tokens(
        " ".join(
            (
                job.title or "",
                *(job.responsibilities or []),
                *(job.qualifications or []),
            )
        )
    )

    if not job_tokens or not confirmed:

        return 0
    values = []

    for item in confirmed:
        experience_text = _experience_text(item)
        overlap = len(job_tokens & _tokens(experience_text))
        lexical = min(overlap / max(min(len(job_tokens), 20), 1), 1.0)
        competency_coverage = (
            sum(_matches_requirement(experience_text, requirement) for requirement in requirements)
            / len(requirements)
            if requirements
            else 0
        )
        values.append(min(lexical * 0.3 + competency_coverage * 0.7, 1.0))

    # Use the best small set of records rather than a single record or every
    # record. A single maximum hides whether the applicant has more than one
    # relevant example; averaging every confirmed record unfairly penalises a
    # student who has also recorded unrelated clubs or coursework.
    top_values = sorted((value for value in values if value > 0), reverse=True)[:3]
    if not top_values:
        return 0
    return round(sum(top_values) / len(top_values) * 25)


def build_match_report(job: Job, experiences: list[Experience]) -> MatchReport:
    confirmed = [item for item in experiences if item.confirmed]

    required, preferred = _resolved_job_skills(job)

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
        "experience_relevance": _relevance_score(job, confirmed, [*required, *preferred]),
        "quantified_evidence": quantified * 15,
        "education_background": education,
    }

    warnings: list[str] = []

    if not confirmed:
        warnings.append("没有已确认经历；匹配结果不会使用待核对内容。")

    if not required:
        warnings.append("未识别到明确技能要求，分数仅供参考。")
    overall = min(sum(breakdown.values()), 100)

    return MatchReport(
        job=_job_read_with_resolved_skills(job, required, preferred),
        overall_score=overall,
        match_level=match_level_for_score(overall),
        matched_skills=matched_required + matched_preferred,
        missing_skills=missing_required + missing_preferred,
        evidence=evidence,
        considered_experience_ids=[item.id for item in confirmed],
        confirmed_experience_count=len(confirmed),
        matched_required_skills=matched_required,
        missing_required_skills=missing_required,
        matched_preferred_skills=matched_preferred,
        missing_preferred_skills=missing_preferred,
        score_breakdown=breakdown,
        eligibility_checks=build_eligibility_checks(job, confirmed),
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
