from typing import Any

from app.ai.mock_extractor import extract_experiences
from app.ai.providers import ProviderError, llm
from app.ai.observability import ai_trace, error_category, record_outcome
from app.ai.prompt_versions import EXPERIENCE_EXTRACTION


EXPERIENCE_CATEGORIES = {"education", "internship", "leadership", "research", "project"}

CATEGORY_CLASSIFICATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "classifications": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "category": {
                        "type": "string",
                        "enum": ["education", "internship", "leadership", "research", "project"],
                    },
                },
                "required": ["index", "category"],
            },
        }
    },
    "required": ["classifications"],
}


def _infer_category(title: str, description: str, supplied: object) -> str:
    """Keep parsing resilient when a local model omits or misspells a category."""
    normalized = str(supplied or "").strip().lower().replace(" ", "_")
    aliases = {
        "internship_experience": "internship",
        "work_experience": "internship",
        "leadership_experience": "leadership",
        "research_experience": "research",
        "education_experience": "education",
        "projects": "project",
        "competition": "project",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized in EXPERIENCE_CATEGORIES:
        return normalized

    text = f"{title} {description}".lower()
    if any(
        word in text for word in ("university", "bachelor", "master", "gpa", "degree", "education")
    ):
        return "education"
    if any(word in text for word in ("intern", "work experience", "employed", "developer at")):
        return "internship"
    if any(word in text for word in ("president", "chair", "leader", "leadership", "committee")):
        return "leadership"
    if any(word in text for word in ("research", "laboratory", "lab ", "research assistant")):
        return "research"
    return "project"


EXPERIENCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "experiences": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "organization": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": ["education", "internship", "leadership", "research", "project"],
                    },
                    "description": {"type": "string"},
                    "skills": {"type": "array", "items": {"type": "string"}},
                    "achievements": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "text": {"type": "string"},
                                "source": {"type": "string"},
                                "verified": {"type": "boolean"},
                            },
                            "required": ["text", "source", "verified"],
                        },
                    },
                },
                "required": [
                    "title",
                    "organization",
                    "category",
                    "description",
                    "skills",
                    "achievements",
                ],
            },
        }
    },
    "required": ["experiences"],
}


def classify_experience_categories(experiences: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Classify extracted evidence using the complete record, not headings/keywords.

    The category is a presentation and organisation aid, never a claim about
    the student's seniority.  We keep the five values intentionally closed so
    an LLM cannot create a new, unfilterable category in the Experience Bank.
    """
    if not experiences:
        return experiences

    candidates = [
        {
            "index": index,
            "title": str(item.get("title", ""))[:200],
            "organization": str(item.get("organization", ""))[:200],
            "description": str(item.get("description", ""))[:1200],
            "skills": [str(skill)[:80] for skill in item.get("skills", [])[:20]],
        }
        for index, item in enumerate(experiences)
    ]
    prompt = (
        "Classify each extracted CV record into exactly one evidence category. "
        "Use the complete record meaning, not only title keywords or a CV section heading. "
        "Allowed categories: education (degree/course enrolment), internship (paid or formal work placement), "
        "leadership (student society, volunteering, organising or leading people), "
        "research (academic or independent research activity), project (a build, competition, hackathon, or other deliverable). "
        "Do not infer facts not present. Return one classification for every input index and only valid JSON.\n"
        f"RECORDS:\n{candidates}"
    )
    result = llm.generate_json(
        prompt,
        CATEGORY_CLASSIFICATION_SCHEMA,
        feature="experience_category_classification",
        prompt_version="experience-category-v1",
    )
    rows = result.get("classifications")
    if not isinstance(rows, list):
        raise ProviderError("LLM classifications field must be an array")

    by_index: dict[int, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        index = row.get("index")
        category = str(row.get("category", "")).strip().lower()
        if isinstance(index, int) and 0 <= index < len(experiences) and category in EXPERIENCE_CATEGORIES:
            by_index[index] = category
    if len(by_index) != len(experiences):
        raise ProviderError("LLM did not classify every extracted experience")

    for index, item in enumerate(experiences):
        item["category"] = by_index[index]
    return experiences


def extract_with_llm(text: str, source_file: str) -> list[dict[str, Any]]:
    prompt = (
        "Extract only factual work, project, research, education, leadership, or competition "
        "experiences from this CV. Assign exactly one category: education, internship, leadership, "
        "research, or project (projects and competitions use project). Do not invent facts. Keep achievement source as the filename "
        f"'{source_file}'. Return an empty array if none are present.\n\nCV:\n{text}"
    )

    result = llm.generate_json(prompt, EXPERIENCE_SCHEMA)

    experiences = result.get("experiences")

    if not isinstance(experiences, list):

        raise ProviderError("LLM experiences field must be an array")
    normalized: list[dict[str, Any]] = []

    for item in experiences:

        if not isinstance(item, dict) or not str(item.get("title", "")).strip():

            continue
        item = dict(item)

        item["title"] = str(item["title"]).strip()[:200]

        item["organization"] = str(item.get("organization", ""))[:200]

        item["description"] = str(item.get("description", ""))[:10000]

        item["category"] = _infer_category(item["title"], item["description"], item.get("category"))

        item["skills"] = [
            str(skill).strip() for skill in item.get("skills", []) if str(skill).strip()
        ]

        item["achievements"] = [
            {
                "text": str(a.get("text", "")).strip(),
                "source": str(a.get("source") or source_file),
                "verified": False,
            }
            for a in item.get("achievements", [])
            if isinstance(a, dict) and str(a.get("text", "")).strip()
        ][:10]

        item["source_file"] = source_file

        item["confirmed"] = False

        normalized.append(item)

    return normalized


def extract_experiences_safe(text: str, source_file: str) -> tuple[list[dict[str, Any]], str]:
    """Use configured providers, preserving deterministic offline extraction as a final safety net."""

    with ai_trace("experience_extraction", EXPERIENCE_EXTRACTION, len(text)):

        try:
            result = extract_with_llm(text, source_file)
        except ProviderError as exc:
            result = extract_experiences(text, source_file)

            # The parser's section heuristics preserve an offline demo path,
            # but an available provider still gets the final decision over the
            # full record rather than leaving categories as string matches.
            try:
                result = classify_experience_categories(result)
            except ProviderError:
                pass

            record_outcome(
                status="rule_fallback",
                provider="rules",
                category=error_category(exc),
                fallback_from="llm",
            )

            return result, "rules"

        # Extraction and classification intentionally degrade separately. A
        # transient category request must never discard an otherwise complete
        # AI extraction and replace it with the less detailed section parser.
        try:
            result = classify_experience_categories(result)
        except ProviderError as exc:
            record_outcome(
                status="partial_fallback",
                provider="llm",
                category=error_category(exc),
                fallback_from="category_classifier",
            )
            return result, "llm_category_fallback"

        record_outcome(status="success", provider="llm")
        return result, "llm"
