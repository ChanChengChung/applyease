"""Tests that the RAG context is injected into the AI material-generation prompt.

Verifies the real AI call site (material_generator) actually augments the model
prompt with retrieved passages from the user's own data, and that it degrades
gracefully when no retrieval is available.

Note: the test sqlite engine (StaticPool, set by conftest) is shared process-wide,
so we only create tables once (idempotent) and keep seeds isolated via distinct
user_id / primary-key ranges. We never drop_all, which would wipe tables other
test files rely on.
"""

import pytest

from app.ai.material_generator import generate_resume_ai
from app.db.session import Base, SessionLocal
from app.models.document import Document
from app.models.experience import Experience


@pytest.fixture(autouse=True)
def _create_tables():
    Base.metadata.create_all(SessionLocal().bind)
    yield


def test_rag_context_is_injected_into_prompt(monkeypatch):
    captured = {}

    def fake_generate_json(prompt, _schema):
        captured["prompt"] = prompt
        return {
            "text": "Operated a Kubernetes platform",
            "citations": [
                {
                    "experience_id": 7101,
                    "claim": "Operated a Kubernetes platform",
                    "evidence_quote": "Operated a Kubernetes platform",
                }
            ],
        }

    monkeypatch.setattr("app.ai.material_generator.llm.generate_json", fake_generate_json)

    with SessionLocal() as db:
        db.add(
            Experience(
                id=7101,
                user_id=6101,
                title="Kubernetes Platform Engineer",
                organization="Acme Cloud",
                confirmed=True,
                description="Operated a Kubernetes platform and reduced incident MTTR by 40%.",
                skills=["Kubernetes"],
                achievements=[],
            )
        )
        db.add(
            Document(
                id=7151,
                user_id=6101,
                filename="cv.pdf",
                sha256="seed-cv-pdf",
                content_type="application/pdf",
            )
        )
        db.commit()

        job = type(
            "Job",
            (),
            {
                "title": "Platform Intern",
                "company": "Example",
                "description": "Operate Kubernetes clusters.",
                "created_at": None,
                "required_skills": [],
                "preferred_skills": [],
            },
        )()

        seeded = db.get(Experience, 7101)
        generate_resume_ai(job, [seeded], db=db, user_id=6101)

    prompt = captured["prompt"]
    # The retrieved context block must be present and carry the user's own data.
    assert "RETRIEVED CONTEXT" in prompt
    assert "Kubernetes" in prompt


def test_no_rag_context_block_when_db_unavailable(monkeypatch):
    captured = {}

    def fake_generate_json(prompt, _schema):
        captured["prompt"] = prompt
        return {
            "text": "Built a Python data pipeline.",
            "citations": [
                {
                    "experience_id": 7040,
                    "claim": "Built a Python data pipeline.",
                    "evidence_quote": "Built a Python data pipeline.",
                }
            ],
        }

    monkeypatch.setattr("app.ai.material_generator.llm.generate_json", fake_generate_json)

    job = type(
        "Job",
        (),
        {
            "title": "Data Intern",
            "company": "Example",
            "description": "Build data pipelines.",
            "created_at": None,
            "required_skills": [],
            "preferred_skills": [],
        },
    )()
    exp = Experience(
        id=7040,
        title="Python Project",
        organization="CUHK",
        description="Built a Python data pipeline.",
        skills=["Python"],
        achievements=[],
        source_file="CV.pdf",
        confirmed=True,
    )

    generate_resume_ai(job, [exp])  # no db/user_id -> RAG disabled

    assert "RETRIEVED CONTEXT" not in captured["prompt"]
    assert "Python" in captured["prompt"]
