from uuid import uuid4

from fastapi.testclient import TestClient

from app.ai.mock_extractor import extract_experiences
from app.main import app


client = TestClient(app)


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
