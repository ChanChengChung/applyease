from __future__ import annotations

import re
from typing import Any

from app.ai.providers import ProviderError
from app.models.experience import Experience
from app.schemas.material import SourceCitation


def experience_source_text(item: Experience) -> str:
    achievements = " ".join(
        str(value.get("text", "")) for value in (item.achievements or []) if isinstance(value, dict)
    )

    return " ".join(
        (item.title, item.organization, item.description, " ".join(item.skills or []), achievements)
    )


def _normalize(text: str) -> str:

    return re.sub(r"\s+", " ", text).strip().casefold()


def validate_ai_citations(
    raw_citations: Any, experiences: list[Experience], generated_text: str
) -> list[SourceCitation]:

    if not isinstance(raw_citations, list):

        raise ProviderError("AI citations field has an invalid type")
    by_id = {item.id: item for item in experiences if item.confirmed}

    citations: list[SourceCitation] = []

    seen: set[tuple[int, str]] = set()

    for raw in raw_citations:

        if not isinstance(raw, dict):

            raise ProviderError("AI citation item has an invalid type")
        item = by_id.get(raw.get("experience_id"))

        claim = str(raw.get("claim", "")).strip()

        quote = str(raw.get("evidence_quote", "")).strip()

        if (
            not item
            or len(_normalize(claim)) < 4
            or _normalize(claim) not in _normalize(generated_text)
        ):

            raise ProviderError("AI citation claim is not present in generated material")

        if len(_normalize(quote)) < 8 or _normalize(quote) not in _normalize(
            experience_source_text(item)
        ):

            raise ProviderError("AI material contains an ungrounded citation")
        key = (item.id, _normalize(quote))

        if key not in seen:
            seen.add(key)

            citations.append(
                SourceCitation(
                    experience_id=item.id, experience_title=item.title, text=quote, claim=claim
                )
            )

    if experiences and not citations:

        raise ProviderError("AI material did not cite a confirmed experience")

    return citations


def validate_material_text(
    text: str, experiences: list[Experience], job_text: str = "", language: str = "zh-CN"
) -> tuple[bool, list[str]]:
    evidence = _normalize(
        " ".join(
            [job_text, *(experience_source_text(item) for item in experiences if item.confirmed)]
        )
    )

    warnings: list[str] = []

    for number in dict.fromkeys(re.findall(r"(?<!\w)\d+(?:[.,]\d+)*(?:%|\+)?", text)):

        if _normalize(number) not in evidence:
            if language == "en":
                warnings.append(
                    f"Number {number} is not supported by the job posting or confirmed experience"
                )
            elif language == "zh-TW":
                warnings.append(f"數字 {number} 未見於職位描述或已確認經歷")
            else:
                warnings.append(f"数字 {number} 不在职位描述或已确认经历中")

    return not warnings, warnings


def sources_for_experiences(experiences: list[Experience]) -> list[SourceCitation]:

    return [
        SourceCitation(
            experience_id=item.id,
            experience_title=item.title,
            text=item.description.splitlines()[0] if item.description else item.title,
            claim=item.description.splitlines()[0] if item.description else item.title,
        )
        for item in experiences
        if item.confirmed
    ]
