from __future__ import annotations

import re

from app.schemas.application import DetectedFormField, FillPreviewItem

UNSUPPORTED_TYPES = {"password", "file", "hidden", "submit", "button", "reset", "image"}
SENSITIVE_WORDS = {
    "passport",
    "hkid",
    "identity",
    "visa",
    "sponsorship",
    "authorization",
    "authorisation",
    "salary",
    "gender",
    "ethnicity",
    "race",
    "disability",
    "health",
    "date of birth",
    "nationality",
    "citizenship",
}


def _normalize(value: str) -> str:

    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _tokens(value: str) -> set[str]:

    return {token for token in _normalize(value).split() if len(token) > 1}


def _field_text(field: DetectedFormField) -> str:

    return " ".join((field.label, field.name, field.html_id, field.placeholder))


def _question_score(field: DetectedFormField, question) -> int:
    field_text = _field_text(field)

    question_text = question.question

    exact = _normalize(field_text) == _normalize(question_text)

    overlap = len(_tokens(field_text) & _tokens(question_text))

    score = overlap * 10 + (100 if exact else 0)

    metadata = (question.answer or {}).get("metadata", {})

    if metadata.get("field_key") and _normalize(str(metadata["field_key"])) in _normalize(
        field_text
    ):
        score += 25

    if metadata.get("input_type") == field.input_type:
        score += 5

    return score


def build_fill_preview(fields: list[DetectedFormField], questions: list) -> list[FillPreviewItem]:
    results: list[FillPreviewItem] = []

    used_questions: set[int] = set()

    for field in fields:
        base = {"field_id": field.field_id, "label": field.label or field.name or field.html_id}

        if field.input_type.casefold() in UNSUPPORTED_TYPES:
            results.append(
                FillPreviewItem(
                    **base, status="unsupported", warnings=["此字段类型不会被自动填充。"]
                )
            )
            continue
        field_text = _field_text(field).casefold()

        if any(word in field_text for word in SENSITIVE_WORDS):
            results.append(
                FillPreviewItem(
                    **base, status="manual_required", warnings=["敏感字段必须由用户本人填写。"]
                )
            )
            continue
        candidates = sorted(
            (
                (_question_score(field, question), question)
                for question in questions
                if question.id not in used_questions
            ),
            key=lambda pair: pair[0],
            reverse=True,
        )

        if not candidates or candidates[0][0] < 10:
            results.append(
                FillPreviewItem(
                    **base, status="no_match", warnings=["没有找到足够可靠的申请问题匹配。"]
                )
            )
            continue
        score, question = candidates[0]
        metadata = (question.answer or {}).get("metadata", {})

        if metadata.get("requires_user_input") or metadata.get("sensitive"):
            results.append(
                FillPreviewItem(
                    **base,
                    status="manual_required",
                    question_id=question.id,
                    question=question.question,
                    warnings=["此字段需要用户本人确认或填写。"],
                )
            )

            continue
        result = (question.answer or {}).get("result", {})

        answer = str(result.get("text", "")).strip() if isinstance(result, dict) else ""

        if not answer:
            results.append(
                FillPreviewItem(
                    **base,
                    status="needs_generation",
                    question_id=question.id,
                    question=question.question,
                    warnings=["请先在申请表助手中生成答案。"],
                )
            )
            continue
        warnings: list[str] = []

        if field.max_characters and len(answer) > field.max_characters:
            warnings.append(f"答案超过网页字段的 {field.max_characters} 字符限制。")

            status = "needs_review"

        else:
            status = "ready"
        source_ids = [
            int(source.get("experience_id"))
            for source in result.get("sources", [])
            if isinstance(source, dict) and isinstance(source.get("experience_id"), int)
        ]

        used_questions.add(question.id)

        results.append(
            FillPreviewItem(
                **base,
                status=status,
                answer=answer,
                question_id=question.id,
                question=question.question,
                warnings=warnings,
                source_ids=source_ids,
            )
        )

    return results
