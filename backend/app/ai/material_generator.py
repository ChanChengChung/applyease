from __future__ import annotations

import re
from typing import Any, Callable

from app.ai.providers import ProviderError, llm
from app.ai.observability import ai_trace, error_category, record_outcome
from app.ai.prompt_versions import APPLICATION_ANSWER, COVER_LETTER_GENERATION, RESUME_GENERATION
from app.models.experience import Experience
from app.models.job import Job
from app.schemas.material import MaterialContent
from app.services.material_service import generate_answer, generate_cover_letter, generate_resume
from app.services.material_validation_service import validate_ai_citations, validate_material_text
from app.services.rag_service import format_context, retrieve_context

MATERIAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "text": {"type": "string"},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "experience_id": {"type": "integer"},
                    "claim": {"type": "string"},
                    "evidence_quote": {"type": "string"},
                },
                "required": ["experience_id", "claim", "evidence_quote"],
            },
        },
    },
    "required": ["text", "citations"],
}


def _validate_cover_letter_quality(text: str, job: Job, output_language: str) -> None:
    """Reject structurally poor letters even when their facts are supported.

    Citation validation prevents hallucinations, but it cannot distinguish a
    natural letter from a pasted CV.  This small deterministic gate keeps the
    model's promised format reviewable before the user sees or saves it.
    """
    normalized = text.strip()
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    if any(re.match(r"^(?:[-*•▪] |\d+[.)] )", line) for line in lines):
        raise ProviderError("AI cover letter must not contain bullet points")
    if re.search(r"\[(?:your\s+name|name|姓名|您的姓名)\]", normalized, re.I):
        raise ProviderError("AI cover letter must not contain a name placeholder")
    if job.title and job.title.casefold() not in normalized.casefold():
        raise ProviderError("AI cover letter must name the target role")
    if output_language == "en":
        has_greeting = normalized.casefold().startswith("dear ")
        has_closing = bool(
            re.search(r"\b(?:sincerely|best regards|kind regards|yours faithfully)\b", normalized, re.I)
        )
    else:
        has_greeting = normalized.startswith(("招聘团队", "招募团队", "尊敬的", "您好"))
        has_closing = any(marker in normalized for marker in ("此致", "敬礼", "期待"))
    if not has_greeting or not has_closing:
        raise ProviderError("AI cover letter is missing a professional greeting or closing")


def select_relevant_experiences(
    job: Job, experiences: list[Experience], limit: int
) -> list[Experience]:
    confirmed = [item for item in experiences if item.confirmed]

    terms = [
        str(value).casefold()
        for value in [*(job.required_skills or []), *(job.preferred_skills or [])]
        if value
    ]

    def score(item: Experience) -> tuple[int, int]:
        text = " ".join(
            (item.title, item.organization, item.description, " ".join(item.skills or []))
        ).casefold()

        return sum(term in text for term in terms), len(item.achievements or [])

    return sorted(confirmed, key=score, reverse=True)[:limit]


def _generate(
    job: Job,
    experiences: list[Experience],
    material_type: str,
    instruction: str,
    max_characters: int | None = None,
    output_language: str = "en",
    rag_context: str | None = None,
) -> MaterialContent:
    payload = [
        {
            "id": item.id,
            "title": item.title,
            "organization": item.organization,
            "description": item.description,
            "skills": item.skills,
            "achievements": item.achievements,
        }
        for item in experiences
    ]

    length_rule = (
        f"The final text must be at most {max_characters} characters. " if max_characters else ""
    )
    language_names = {
        "en": "English",
        "zh-CN": "Simplified Chinese",
        "zh-TW": "Traditional Chinese",
    }
    language_rule = language_names.get(output_language, "English")

    rag_block = ""
    if rag_context:
        rag_block = (
            "The following passages were retrieved from the applicant's own stored experiences and documents "
            "(retrieval-augmented context). Prefer grounding claims in these passages when relevant, but you may "
            "still use the CONFIRMED EXPERIENCES below. Never invent facts that are absent from both sources.\n\n"
            f"RETRIEVED CONTEXT:\n{rag_context}\n\n"
        )

    prompt = (
        "Create application material using only the confirmed experiences supplied below and facts in the job posting. "
        "Never invent employment, metrics, awards, dates, skills, or responsibilities. Every factual experience claim "
        "must have a citation whose claim is copied from the generated text and whose evidence_quote is an exact quote copied from the corresponding experience. "
        f"Write the final material in {language_rule}. Do not translate organisation names, job titles, quoted evidence, or technical terms when that would alter a verified fact. "
        f"{length_rule}{instruction} Return JSON matching the supplied schema.\n\n"
        f"TARGET JOB: {job.title} at {job.company}\nJOB POSTING:\n{job.description}\n\n"
        f"{rag_block}"
        f"CONFIRMED EXPERIENCES:\n{payload}"
    )

    result = llm.generate_json(prompt, MATERIAL_SCHEMA)

    text = str(result.get("text", "")).strip()

    if not text:

        raise ProviderError("AI returned empty material")

    if max_characters and len(text) > max_characters:

        raise ProviderError("AI material exceeded the requested character limit")

    if material_type == "cover_letter":
        _validate_cover_letter_quality(text, job, output_language)
    sources = validate_ai_citations(result.get("citations"), experiences, text)

    passed, warnings = validate_material_text(
        text,
        experiences,
        f"{job.title} {job.company} {job.description}",
        output_language,
    )

    if not passed:

        raise ProviderError("AI material contains unsupported numeric claims")

    return MaterialContent(
        material_type=material_type,
        text=text,
        character_count=len(text),
        fact_check_passed=True,
        warnings=warnings,
        sources=sources,
        generation_method="ai",
        max_characters=max_characters,
    )


def generate_resume_ai(
    job: Job,
    experiences: list[Experience],
    *,
    output_language: str = "en",
    db=None,
    user_id: int | None = None,
) -> MaterialContent:
    selected = select_relevant_experiences(job, experiences, 6)
    rag_context = _build_rag_context(db, user_id, f"{job.title} {job.company} resume")

    return _generate(
        job,
        selected,
        "resume",
        (
            "Write a concise ATS-friendly targeted resume. This must be a tailored rewrite, not a copy of the experience bank. "
            "For every selected experience, retain its verified title and organisation, then rewrite its supported work into one to three action-led bullets that foreground only the skills, methods and outcomes relevant to this target job. "
            "Reorder and compress verified details for relevance; do not add metrics, tools, responsibilities, dates or outcomes. "
            "Use job keywords only where the corresponding confirmed experience actually supports them. "
            "Use clear SELECTED EXPERIENCE headings so the applicant can review each tailored experience before export."
        ),
        output_language=output_language,
        rag_context=rag_context,
    ).model_copy(update={"output_language": output_language})


def generate_cover_letter_ai(
    job: Job,
    experiences: list[Experience],
    *,
    output_language: str = "en",
    db=None,
    user_id: int | None = None,
) -> MaterialContent:
    selected = select_relevant_experiences(job, experiences, 3)
    rag_context = _build_rag_context(db, user_id, f"{job.title} {job.company} cover letter")

    return _generate(
        job,
        selected,
        "cover_letter",
        (
            "Write a focused, natural cover letter of three short paragraphs plus a closing. "
            "Start with 'Dear Hiring Team,' (or the equivalent in the requested language), state the exact target role, "
            "and connect one or two concrete requirements from the job posting to the applicant's verified evidence. "
            "Use the middle paragraph to develop at most two selected experiences: name the verified role and organisation, "
            "then explain the relevant work in clear prose rather than pasting a CV bullet or listing every experience. "
            "End by stating the specific contribution the applicant is prepared to make, limited to skills supported by the evidence. "
            "Do not use placeholders, headings, bullet points, an experience dump, generic enthusiasm, or unsupported praise about the company. "
            "Do not invent a motivation, company fact, metric, tool, responsibility, or outcome. Keep it concise (roughly 180–300 words when the evidence supports that length)."
        ),
        output_language=output_language,
        rag_context=rag_context,
    ).model_copy(update={"output_language": output_language})


def generate_answer_ai(
    job: Job,
    question: str,
    max_characters: int,
    experiences: list[Experience],
    *,
    template: str = "detailed_300",
    output_language: str = "en",
    answer_tone: str = "professional",
    desired_content: str = "",
    db=None,
    user_id: int | None = None,
) -> MaterialContent:
    selected = select_relevant_experiences(job, experiences, 2)
    rag_context = _build_rag_context(
        db, user_id, f"{job.title} {job.company} {question} application answer"
    )

    from app.services.answer_template_service import template_instruction

    return _generate(
        job,
        selected,
        "application_answer",
        (
            f"Answer this application question directly: {question} "
            f"Use a {answer_tone} tone. "
            f"The applicant asks you to emphasize: {desired_content or 'the most relevant confirmed evidence'}. "
            "Treat this preference as framing only: do not claim anything that is not supported by the confirmed evidence. "
            f"{template_instruction(template)}"
        ),
        max_characters,
        output_language,
        rag_context=rag_context,
    ).model_copy(update={"output_language": output_language})


def _build_rag_context(db, user_id: int | None, query: str, limit: int = 4) -> str | None:
    """Retrieve the user's own experiences/documents for grounding AI generation.

    Returns a formatted context block, or None when retrieval is unavailable
    (e.g. offline, no db/user_id, or the user has no stored data). This is the
    single RAG call site for material generation.
    """
    if db is None or user_id is None:
        return None
    try:
        passages = retrieve_context(db, user_id, query, limit=limit)
    except Exception:
        return None
    context = format_context(passages)
    return context or None


def _safe(
    ai_call: Callable[[], MaterialContent],
    fallback_call: Callable[[], MaterialContent],
    *,
    feature: str,
    prompt_version: str,
    input_characters: int,
) -> MaterialContent:

    with ai_trace(feature, prompt_version, input_characters):

        try:
            result = ai_call()

            record_outcome(status="success", provider="llm")

            return result

        except ProviderError as exc:
            result = fallback_call()

            # The fallback must never pass silently as if it were AI output.
            # Surfaces in the UI (warnings list) that the AI attempt failed
            # validation/connectivity and a deterministic template was used.
            result = result.model_copy(
                update={
                    "warnings": [
                        *result.warnings,
                        "AI 生成未通过证据校验或模型不可用，已回退到确定性模板。"
                        " / AI generation failed validation or was unavailable; "
                        "a deterministic template was used instead.",
                    ]
                }
            )

            record_outcome(
                status="rule_fallback",
                provider="rules",
                category=error_category(exc),
                fallback_from="llm",
            )

            return result


def generate_resume_safe(
    job: Job,
    experiences: list[Experience],
    *,
    output_language: str = "en",
    db=None,
    user_id: int | None = None,
) -> MaterialContent:

    return _safe(
        lambda: generate_resume_ai(
            job, experiences, output_language=output_language, db=db, user_id=user_id
        ),
        lambda: generate_resume(job, experiences, output_language=output_language),
        feature="resume",
        prompt_version=RESUME_GENERATION,
        input_characters=len(job.description)
        + sum(len(item.description or "") for item in experiences),
    )


def generate_cover_letter_safe(
    job: Job,
    experiences: list[Experience],
    *,
    output_language: str = "en",
    db=None,
    user_id: int | None = None,
) -> MaterialContent:

    return _safe(
        lambda: generate_cover_letter_ai(
            job, experiences, output_language=output_language, db=db, user_id=user_id
        ),
        lambda: generate_cover_letter(job, experiences, output_language=output_language),
        feature="cover_letter",
        prompt_version=COVER_LETTER_GENERATION,
        input_characters=len(job.description)
        + sum(len(item.description or "") for item in experiences),
    )


def generate_answer_safe(
    job: Job,
    question: str,
    max_characters: int,
    experiences: list[Experience],
    *,
    template: str = "detailed_300",
    output_language: str = "en",
    answer_tone: str = "professional",
    desired_content: str = "",
    db=None,
    user_id: int | None = None,
) -> MaterialContent:

    return _safe(
        lambda: generate_answer_ai(
            job,
            question,
            max_characters,
            experiences,
            template=template,
            output_language=output_language,
            answer_tone=answer_tone,
            desired_content=desired_content,
            db=db,
            user_id=user_id,
        ),
        lambda: generate_answer(
            job,
            question,
            max_characters,
            experiences,
            template=template,
            output_language=output_language,
            answer_tone=answer_tone,
            desired_content=desired_content,
        ),
        feature="application_answer",
        prompt_version=APPLICATION_ANSWER,
        input_characters=len(job.description)
        + len(question)
        + sum(len(item.description or "") for item in experiences),
    )
