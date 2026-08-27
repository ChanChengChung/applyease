from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.ai.material_generator import (
    ProviderError,
    generate_cover_letter_ai,
    generate_cover_letter_safe,
    generate_resume_ai,
    generate_resume_safe,
)
from app.main import app
from app.models.experience import Experience
from app.models.job import Job


def make_job() -> Job:
    job = Job(
        id=50,
        title="Data Intern",
        company="Example",
        description="Build Python data products.",
        required_skills=["Python"],
        preferred_skills=[],
        responsibilities=[],
        qualifications=[],
    )
    job.created_at = datetime.now(timezone.utc)

    return job


def make_experience(confirmed: bool = True, item_id: int = 40) -> Experience:
    item = Experience(
        id=item_id,
        title="Python Project",
        organization="CUHK",
        description="Built a Python data pipeline.",
        skills=["Python"],
        achievements=[{"text": "Improved speed by 20%", "source": "CV.pdf", "verified": True}],
        source_file="CV.pdf",
        confirmed=confirmed,
    )
    item.created_at = datetime.now(timezone.utc)

    return item


def test_ai_resume_requires_exact_confirmed_citations(monkeypatch):
    monkeypatch.setattr(
        "app.ai.material_generator.llm.generate_json",
        lambda *_: {
            "text": "Python Project — Built a Python data pipeline and improved speed by 20%.",
            "citations": [
                {
                    "experience_id": 40,
                    "claim": "improved speed by 20%",
                    "evidence_quote": "Improved speed by 20%",
                }
            ],
        },
    )

    material = generate_resume_ai(make_job(), [make_experience()])

    assert material.generation_method == "ai"

    assert material.fact_check_passed is True

    assert material.sources[0].experience_id == 40


def test_unconfirmed_experiences_are_not_sent_to_material_model(monkeypatch):
    captured = {}

    def fake(prompt, _schema):
        captured["prompt"] = prompt

        return {
            "text": "Built a Python data pipeline.",
            "citations": [
                {
                    "experience_id": 40,
                    "claim": "Built a Python data pipeline.",
                    "evidence_quote": "Built a Python data pipeline.",
                }
            ],
        }

    monkeypatch.setattr("app.ai.material_generator.llm.generate_json", fake)

    generate_resume_ai(
        make_job(),
        [
            make_experience(),
            Experience(
                id=41,
                title="Secret Unconfirmed Role",
                organization="",
                description="Never send this",
                skills=[],
                achievements=[],
                source_file="CV.pdf",
                confirmed=False,
            ),
        ],
    )

    assert "Secret Unconfirmed Role" not in captured["prompt"]

    assert "Never send this" not in captured["prompt"]


def test_ai_resume_prompt_requires_a_role_specific_rewrite(monkeypatch):
    captured = {}

    def fake(prompt, _schema):
        captured["prompt"] = prompt
        return {
            "text": "Python Project | CUHK\n• Built a Python data pipeline.",
            "citations": [
                {
                    "experience_id": 40,
                    "claim": "Built a Python data pipeline.",
                    "evidence_quote": "Built a Python data pipeline.",
                }
            ],
        }

    monkeypatch.setattr("app.ai.material_generator.llm.generate_json", fake)

    generate_resume_ai(make_job(), [make_experience()])

    assert "tailored rewrite, not a copy of the experience bank" in captured["prompt"]
    assert "action-led bullets" in captured["prompt"]


def test_ai_cover_letter_prompt_requires_a_grounded_letter_structure(monkeypatch):
    captured = {}

    def fake(prompt, _schema):
        captured["prompt"] = prompt
        return {
            "text": "Dear Hiring Team,\n\nI am applying for the Data Intern role. Built a Python data pipeline.\n\nSincerely,\nName",
            "citations": [
                {
                    "experience_id": 40,
                    "claim": "Built a Python data pipeline.",
                    "evidence_quote": "Built a Python data pipeline.",
                }
            ],
        }

    monkeypatch.setattr("app.ai.material_generator.llm.generate_json", fake)
    generate_cover_letter_ai(make_job(), [make_experience()])

    assert "three short paragraphs plus a closing" in captured["prompt"]
    assert "Do not use placeholders, headings, bullet points" in captured["prompt"]


def test_ai_cover_letter_rejects_a_cv_style_bullet_dump(monkeypatch):
    monkeypatch.setattr(
        "app.ai.material_generator.llm.generate_json",
        lambda *_: {
            "text": "Dear Hiring Team,\n\nData Intern\n- Built a Python data pipeline.\n\nSincerely,\nName",
            "citations": [
                {
                    "experience_id": 40,
                    "claim": "Built a Python data pipeline.",
                    "evidence_quote": "Built a Python data pipeline.",
                }
            ],
        },
    )

    try:
        generate_cover_letter_ai(make_job(), [make_experience()])
        assert False, "A CV-style letter must be rejected"
    except ProviderError as exc:
        assert "bullet" in str(exc).casefold()


def test_invalid_ai_cover_letter_uses_grounded_rule_fallback(monkeypatch):
    monkeypatch.setattr(
        "app.ai.material_generator.llm.generate_json",
        lambda *_: {"text": "Dear Hiring Team,\n- Built a Python data pipeline.", "citations": []},
    )

    material = generate_cover_letter_safe(make_job(), [make_experience()])

    assert material.generation_method == "rules"
    assert "- Built a Python data pipeline." not in material.text


def test_hallucinated_ai_material_falls_back_to_rules(monkeypatch):
    monkeypatch.setattr(
        "app.ai.material_generator.llm.generate_json",
        lambda *_: {
            "text": "Won 99 international awards.",
            "citations": [
                {
                    "experience_id": 40,
                    "claim": "Won 99 international awards.",
                    "evidence_quote": "Won 99 international awards",
                }
            ],
        },
    )

    material = generate_resume_safe(make_job(), [make_experience()])

    assert material.generation_method == "rules"

    assert "99" not in material.text

    assert "Python Project" in material.text


def test_material_history_and_user_edit_fact_check():
    client = TestClient(app)

    client.post(
        "/api/v1/experiences",
        json={
            "title": "Editing Source",
            "description": "Built a Python service.",
            "skills": ["Python"],
            "confirmed": True,
            "achievements": [],
        },
    )

    job = client.post(
        "/api/v1/jobs/analyze",
        json={
            "title": "Python Intern",
            "description": "A Python internship building software services.",
        },
    ).json()

    generated = client.post(f"/api/v1/materials/resume/generate?job_id={job['id']}").json()

    edited = client.patch(
        f"/api/v1/materials/{generated['id']}", json={"text": "Improved output by 999%."}
    )

    assert edited.status_code == 200

    assert edited.json()["generation_method"] == "user_edited"

    assert edited.json()["fact_check_passed"] is False

    assert any("999%" in warning for warning in edited.json()["warnings"])

    history = client.get(f"/api/v1/materials?job_id={job['id']}")

    assert history.status_code == 200

    assert any(item["id"] == generated["id"] for item in history.json())


def test_material_endpoint_uses_ai_path_when_enabled(monkeypatch):
    client = TestClient(app)

    experience = client.post(
        "/api/v1/experiences",
        json={
            "title": "Grounded API Experience",
            "description": "Implemented a FastAPI service.",
            "skills": ["FastAPI"],
            "confirmed": True,
            "achievements": [],
        },
    ).json()

    job = client.post(
        "/api/v1/jobs/analyze",
        json={
            "title": "Backend Intern",
            "description": "Build backend services using FastAPI and Python.",
        },
    ).json()

    monkeypatch.setattr("app.api.v1.materials.settings.ai_material_generation_enabled", True)

    monkeypatch.setattr(
        "app.ai.material_generator.llm.generate_json",
        lambda *_: {
            "text": "Implemented a FastAPI service.",
            "citations": [
                {
                    "experience_id": experience["id"],
                    "claim": "Implemented a FastAPI service.",
                    "evidence_quote": "Implemented a FastAPI service.",
                }
            ],
        },
    )

    response = client.post(f"/api/v1/materials/resume/generate?job_id={job['id']}")

    assert response.status_code == 200

    assert response.json()["generation_method"] == "ai"

    assert response.json()["sources"][0]["experience_id"] == experience["id"]
