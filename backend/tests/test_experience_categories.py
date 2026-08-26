from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.ai.experience_extractor import (
    ProviderError,
    classify_experience_categories,
    extract_experiences_safe,
)
from app.ai.mock_extractor import extract_experiences
from app.main import app


client = TestClient(app)


def test_category_classifier_uses_complete_record_not_title_keyword(monkeypatch):
    captured = {}

    def fake_generate_json(prompt, schema, *, feature, prompt_version):
        captured.update({"prompt": prompt, "schema": schema, "feature": feature})
        return {
            "classifications": [
                {"index": 0, "category": "leadership"},
                {"index": 1, "category": "research"},
            ]
        }

    monkeypatch.setattr(
        "app.ai.experience_extractor.llm.generate_json", fake_generate_json
    )
    records = [
        {
            "title": "Campus Technology Initiative",
            "organization": "Computing Society",
            "description": "Coordinated a 12-person committee and ran a faculty showcase.",
            "skills": ["Communication"],
            # Deliberately wrong section-derived input: AI should override it.
            "category": "project",
        },
        {
            "title": "Summer Assistant",
            "organization": "Mathematics Department",
            "description": "Designed experiments and evaluated reproducibility for a faculty study.",
            "skills": ["Python"],
            "category": "internship",
        },
    ]

    result = classify_experience_categories(records)

    assert [item["category"] for item in result] == ["leadership", "research"]
    assert captured["feature"] == "experience_category_classification"
    assert "complete record meaning" in captured["prompt"]


def test_category_failure_preserves_successful_ai_extraction(monkeypatch):
    extracted = [
        {
            "title": "Detailed AI Extraction",
            "organization": "Example Lab",
            "description": "A detailed description that the rule parser must not replace.",
            "skills": ["Python", "Statistics"],
            "category": "research",
            "achievements": [],
        }
    ]

    monkeypatch.setattr(
        "app.ai.experience_extractor.extract_with_llm", lambda *_args: extracted
    )

    def category_outage(_records):
        raise ProviderError("temporary provider outage")

    monkeypatch.setattr(
        "app.ai.experience_extractor.classify_experience_categories", category_outage
    )
    monkeypatch.setattr(
        "app.ai.experience_extractor.extract_experiences",
        lambda *_args: pytest.fail("A category outage must not rerun the rule parser"),
    )

    result, mode = extract_experiences_safe("CV text", "resume.txt")

    assert mode == "llm_category_fallback"
    assert result == extracted


def test_category_classifier_batches_long_experience_lists(monkeypatch):
    calls = []

    def fake_generate_json(prompt, _schema, *, feature, prompt_version):
        calls.append((prompt, feature, prompt_version))
        indices = list(range(0, 10)) if len(calls) == 1 else [10]
        return {
            "classifications": [
                {"index": index, "category": "project"} for index in indices
            ]
        }

    monkeypatch.setattr(
        "app.ai.experience_extractor.llm.generate_json", fake_generate_json
    )
    records = [
        {
            "title": f"Record {index}",
            "organization": "Example",
            "description": "x" * 1200,
            "skills": [],
        }
        for index in range(11)
    ]

    result = classify_experience_categories(records)

    assert len(calls) == 2
    assert all(feature == "experience_category_classification" for _, feature, _ in calls)
    assert all(version == "experience-category-v2" for _, _, version in calls)
    assert [item["category"] for item in result] == ["project"] * 11


def test_rule_extractor_assigns_durable_evidence_categories():
    records = extract_experiences(
        """EDUCATION
The University of Hong Kong
BSc Mathematics

INTERNSHIP EXPERIENCE
Analyst Intern | Example Capital
06/2025 - 08/2025
Built Python research tooling.

LEADERSHIP
President | Computing Society
09/2024 - present
Led a student team.

RESEARCH EXPERIENCE
Research Assistant | HKU Lab
06/2024 - 08/2024
Tested statistical models.

PROJECTS
Application Copilot
Built a FastAPI application.
""",
        "category-cv.txt",
    )

    categories = {record["category"] for record in records}

    assert {"education", "internship", "leadership", "research", "project"}.issubset(categories)


def test_category_is_created_returned_and_can_be_edited():
    suffix = uuid4().hex
    response = client.post(
        "/api/v1/experiences",
        json={
            "title": f"Categorised {suffix}",
            "organization": "HKU",
            "description": "Built an applied machine learning project.",
            "skills": ["Python"],
            "achievements": [],
            "category": "project",
        },
    )

    assert response.status_code == 200, response.text
    created = response.json()
    assert created["category"] == "project"

    updated = client.patch(f"/api/v1/experiences/{created['id']}", json={"category": "research"})

    assert updated.status_code == 200, updated.text
    assert updated.json()["category"] == "research"

    invalid = client.patch(f"/api/v1/experiences/{created['id']}", json={"category": "misc"})
    assert invalid.status_code == 422
