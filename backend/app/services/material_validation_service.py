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
    by_id = {item.id: item for item in experiences if item.confirmed}

    citations: list[SourceCitation] = []

    seen: set[tuple[int, str]] = set()

    # Some providers serialise integer IDs as strings and occasionally emit a
    # malformed citation alongside otherwise grounded ones. Normalize the ID
    # and skip only the malformed item; the generated text still has to expose
    # a verifiable phrase before it can be accepted below.
    for raw in raw_citations if isinstance(raw_citations, list) else []:
        if not isinstance(raw, dict):
            continue
        raw_id = raw.get("experience_id")
        try:
            experience_id = int(raw_id)
        except (TypeError, ValueError):
            continue
        item = by_id.get(experience_id)

        claim = str(raw.get("claim", "")).strip()

        quote = str(raw.get("evidence_quote", "")).strip()

        if not item or len(_normalize(claim)) < 4 or _normalize(claim) not in _normalize(generated_text):
            continue

        if len(_normalize(quote)) < 8 or _normalize(quote) not in _normalize(experience_source_text(item)):
            continue
        key = (item.id, _normalize(quote))

        if key not in seen:
            seen.add(key)

            citations.append(
                SourceCitation(
                    experience_id=item.id, experience_title=item.title, text=quote, claim=claim
                )
            )

    # If the provider's citation envelope is imperfect, recover citations from
    # exact evidence phrases that visibly survived in the generated material.
    # This keeps the strict grounding rule while avoiding an unnecessary full
    # fallback for a JSON formatting mistake.
    if experiences and not citations:
        generated_normalized = _normalize(generated_text)
        for item in by_id.values():
            phrases = [
                item.title,
                item.organization,
                *(item.description.splitlines() if item.description else []),
                *(item.skills or []),
                *(
                    str(value.get("text", ""))
                    for value in (item.achievements or [])
                    if isinstance(value, dict)
                ),
            ]
            for phrase in sorted(
                {str(value).strip() for value in phrases if str(value).strip()},
                key=len,
                reverse=True,
            ):
                normalized_phrase = _normalize(phrase)
                if len(normalized_phrase) < 8 or normalized_phrase not in generated_normalized:
                    continue
                citations.append(
                    SourceCitation(
                        experience_id=item.id,
                        experience_title=item.title,
                        text=phrase,
                        claim=phrase,
                    )
                )
                break

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

    number_pattern = r"(?<!\w)\d+(?:[.,]\d+)*(?:%|\+)?"
    # Compare whole numeric tokens instead of using a substring search: the
    # previous check considered "10" supported whenever evidence contained
    # "100", which undermined the fact-check badge.
    evidence_numbers = {_normalize(number) for number in re.findall(number_pattern, evidence)}
    for number in dict.fromkeys(re.findall(number_pattern, text)):
        if _normalize(number) not in evidence_numbers:
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
