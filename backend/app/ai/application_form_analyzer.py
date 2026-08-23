from __future__ import annotations

import re
from typing import Any

from app.ai.providers import ProviderError, llm
from app.ai.observability import ai_trace, error_category, record_outcome
from app.ai.prompt_versions import FORM_ANALYSIS
from app.services.application_question_service import (
    classify_question,
    detect_questions,
    field_metadata,
)

ALLOWED_TYPES = {
    "motivation",
    "company_interest",
    "project",
    "teamwork",
    "leadership",
    "challenge",
    "technical",
    "education",
    "identity",
    "personal_info",
    "eligibility",
    "salary",
    "demographic",
    "availability",
    "general",
}
FORM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "fields": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "question_type": {"type": "string"},
                    "required": {"type": "boolean"},
                    "max_length": {"type": "integer"},
                    "limit_unit": {"type": "string"},
                    "field_key": {"type": "string"},
                    "input_type": {"type": "string"},
                    "sensitive": {"type": "boolean"},
                    "requires_user_input": {"type": "boolean"},
                },
                "required": [
                    "question",
                    "question_type",
                    "required",
                    "max_length",
                    "limit_unit",
                    "field_key",
                    "input_type",
                    "sensitive",
                    "requires_user_input",
                ],
            },
        }
    },
    "required": ["fields"],
}


def analyze_form_ai(raw_text: str) -> list[dict]:
    prompt = (
        "Extract every user-entered field and narrative question from this internship application form text. "
        "Do not treat instructions, navigation, privacy notices, or button labels as questions. Classify fields. "
        "Mark identity documents, nationality/citizenship, contact, work authorization/visa, salary, demographic, health, and availability fields as "
        "requires_user_input; never suggest that AI should guess them. Preserve explicit required/optional status and "
        "character/word limits. Use max_length=300 when absent and limit_unit=characters. Return JSON matching the schema.\n\nFORM TEXT:\n"
        + raw_text
    )

    result = llm.generate_json(prompt, FORM_SCHEMA)

    fields = result.get("fields")

    if not isinstance(fields, list):
        raise ProviderError("AI fields value must be an array")

    parsed: list[dict] = []
    seen: set[str] = set()

    for raw in fields[:100]:

        if not isinstance(raw, dict):
            continue

        question = re.sub(r"\s+", " ", str(raw.get("question", ""))).strip()[:3000]

        key = re.sub(r"\W+", "", question.casefold())

        if not question or not key or key in seen:
            continue

        seen.add(key)

        question_type = str(raw.get("question_type", "general")).casefold()

        if question_type not in ALLOWED_TYPES:
            question_type = "general"

        server_type = classify_question(question)

        if server_type != "general":
            question_type = server_type

        unit = "words" if str(raw.get("limit_unit", "")).casefold() == "words" else "characters"

        value = raw.get("max_length", 300)

        value = value if isinstance(value, int) and not isinstance(value, bool) else 300

        max_words = min(max(value, 1), 1000) if unit == "words" else None

        max_characters = min(max(value * 8, 50), 5000) if max_words else min(max(value, 20), 5000)

        metadata = field_metadata(question, question_type, unit, max_words)

        # The server, not the model, owns the sensitive/manual policy.

        if question_type in {
            "identity",
            "personal_info",
            "eligibility",
            "salary",
            "demographic",
            "availability",
        }:
            metadata["requires_user_input"] = True

        if question_type in {"identity", "eligibility", "salary", "demographic"}:
            metadata["sensitive"] = True
        metadata["field_key"] = re.sub(
            r"[^a-zA-Z0-9_.-]", "_", str(raw.get("field_key") or metadata["field_key"])
        )[:80]

        requested_input = str(raw.get("input_type") or metadata["input_type"]).casefold()

        metadata["input_type"] = (
            requested_input
            if requested_input
            in {"text", "textarea", "email", "tel", "number", "date", "select", "radio", "checkbox"}
            else metadata["input_type"]
        )

        parsed.append(
            {
                "question": question,
                "question_type": question_type,
                "max_characters": max_characters,
                "required": bool(raw.get("required", True)),
                "answer": {"metadata": metadata},
            }
        )

    if not parsed:
        raise ProviderError("AI found no usable form fields")

    return parsed[:50]


def analyze_form_safe(raw_text: str) -> list[dict]:

    with ai_trace("form_analysis", FORM_ANALYSIS, len(raw_text)):

        try:
            ai_fields = analyze_form_ai(raw_text)

        except ProviderError as exc:
            result = detect_questions(raw_text)

            record_outcome(
                status="rule_fallback",
                provider="rules",
                category=error_category(exc),
                fallback_from="llm",
            )

            return result

        try:
            rule_fields = detect_questions(raw_text)

        except ValueError:
            record_outcome(status="success", provider="llm")

            return ai_fields
        merged = list(ai_fields)
        seen = {re.sub(r"\W+", "", item["question"].casefold()) for item in ai_fields}

        for item in rule_fields:
            key = re.sub(r"\W+", "", item["question"].casefold())

            if key not in seen:
                merged.append(item)
                seen.add(key)
        record_outcome(status="success", provider="llm")

        return merged[:50]
