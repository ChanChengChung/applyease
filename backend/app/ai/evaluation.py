from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.ai.application_form_analyzer import ALLOWED_TYPES, FORM_SCHEMA
from app.ai.job_analyzer import JOB_SCHEMA, _clean_list
from app.ai.providers import GeminiProvider, OllamaProvider, ProviderError
from app.services.application_question_service import (
    MANUAL_TYPES,
    classify_question,
    detect_questions,
)
from app.services.job_analysis_service import extract_job_requirements


DATASET = Path(__file__).resolve().parents[2] / "evals" / "stage10_cases.json"


def _recall(expected: list[str], actual: list[str]) -> float:
    haystack = " ".join(actual).casefold()

    return (
        round(sum(value.casefold() in haystack for value in expected) / len(expected), 4)
        if expected
        else 1.0
    )


def _job_prompt(text: str) -> str:

    return (
        "Analyze this job posting. Extract only explicitly stated or clearly required information. "
        "Do not invent technologies. Separate mandatory and preferred skills. Copy responsibilities "
        "and qualifications concisely. Return JSON matching the supplied schema.\n\nJOB POSTING:\n"
        + text
    )


def _form_prompt(text: str) -> str:

    return (
        "Extract every user-entered field and narrative question from this internship application form text. "
        "Do not treat instructions, navigation, privacy notices, or button labels as questions. Classify fields. "
        "Mark identity documents, nationality/citizenship, contact, work authorization/visa, salary, demographic, health, and availability fields as "
        "requires_user_input; never suggest that AI should guess them. Return JSON matching the schema.\n\nFORM TEXT:\n"
        + text
    )


def _provider(name: str):

    if name == "ollama":

        return OllamaProvider()

    if name == "gemini":

        return GeminiProvider()

    raise ValueError("provider must be rules, ollama or gemini")


def _evaluate_job(case: dict[str, Any], provider_name: str, provider=None) -> dict:

    if provider_name == "rules":
        output = extract_job_requirements(case["input"])

    else:
        raw = provider.generate_json(_job_prompt(case["input"]), JOB_SCHEMA)

        output = {
            key: _clean_list(raw.get(key))
            for key in ("required_skills", "preferred_skills", "responsibilities", "qualifications")
        }
    required_recall = _recall(case["expected_required"], output["required_skills"])

    any_values = [
        *output["required_skills"],
        *output["preferred_skills"],
        *output["responsibilities"],
        *output["qualifications"],
    ]
    coverage = _recall(case["expected_any"], any_values)

    return {
        "id": case["id"],
        "passed": required_recall == 1 and coverage >= 0.5,
        "required_recall": required_recall,
        "coverage": coverage,
    }


def _evaluate_form(case: dict[str, Any], provider_name: str, provider=None) -> dict:

    if provider_name == "rules":
        fields = detect_questions(case["input"])

        types = [field["question_type"] for field in fields]

        manual = [
            field["question_type"]
            for field in fields
            if field["answer"]["metadata"].get("requires_user_input")
        ]

    else:
        raw = provider.generate_json(_form_prompt(case["input"]), FORM_SCHEMA)

        raw_fields = raw.get("fields")

        if not isinstance(raw_fields, list):

            raise ProviderError("Provider evaluation fields must be an array")
        types, manual = [], []

        for field in raw_fields:

            if not isinstance(field, dict):

                continue
            question = str(field.get("question", ""))

            kind = str(field.get("question_type", "general")).casefold()

            server_kind = classify_question(question)

            kind = (
                server_kind
                if server_kind != "general"
                else kind if kind in ALLOWED_TYPES else "general"
            )

            types.append(kind)

            # Server policy overrides unsafe provider claims.

            if kind in MANUAL_TYPES:
                manual.append(kind)
    type_recall = _recall(case["expected_types"], types)

    manual_recall = _recall(case["expected_manual_types"], manual)

    return {
        "id": case["id"],
        "passed": type_recall == 1 and manual_recall == 1,
        "type_recall": type_recall,
        "manual_safety_recall": manual_recall,
    }


def run_evaluation(provider: str = "rules", dataset: Path = DATASET) -> dict:

    if provider not in {"rules", "ollama", "gemini"}:

        raise ValueError("provider must be rules, ollama or gemini")
    cases = json.loads(dataset.read_text(encoding="utf-8"))

    if not isinstance(cases, list) or not cases:

        raise ValueError("evaluation dataset must be a non-empty JSON array")
    provider_client = None if provider == "rules" else _provider(provider)

    results = []

    for case in cases:
        results.append(
            _evaluate_job(case, provider, provider_client)
            if case.get("kind") == "job"
            else _evaluate_form(case, provider, provider_client)
        )
    passed = sum(result["passed"] for result in results)

    return {
        "provider": provider,
        "dataset": dataset.name,
        "case_count": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "pass_rate": round(passed / len(results), 4),
        "cases": results,
    }
