"""Tests that job matching injects the RAG context (user documents/experiences)."""

import pytest
from datetime import datetime, timezone

from app.ai.job_analyzer import build_match_report_ai
from app.db.session import Base, SessionLocal
from app.models.document import Document
from app.models.experience import Experience


@pytest.fixture(autouse=True)
def _create_tables():
    # Shared process-wide sqlite engine: create once (idempotent), never drop_all.
    Base.metadata.create_all(SessionLocal().bind)
    yield


def _mock_job():
    return type(
        "Job",
        (),
        {
            "id": 1,
            "title": "Platform Engineer",
            "company": "Example",
            "description": "Operate Kubernetes clusters.",
            "required_skills": ["Kubernetes"],
            "preferred_skills": [],
            "responsibilities": [],
            "qualifications": [],
            "created_at": datetime.now(timezone.utc),
        },
    )()


def test_match_prompt_injects_retrieved_context(monkeypatch):
    captured = {}

    def fake_generate_json(prompt, _schema):
        captured["prompt"] = prompt
        return {"matched_skills": [], "missing_skills": [], "evidence": []}

    monkeypatch.setattr("app.ai.job_analyzer.llm.generate_json", fake_generate_json)

    with SessionLocal() as db:
        db.add(
            Experience(
                id=8201,
                user_id=6201,
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
                id=8301,
                user_id=6201,
                filename="cv.pdf",
                sha256="seed-cv",
                content_type="application/pdf",
            )
        )
        db.commit()

        job = _mock_job()

        build_match_report_ai(
            job,
            [db.get(Experience, 8201)],
            rag_context="Experience: Kubernetes Platform Engineer\nOperated a Kubernetes platform.",
        )

    prompt = captured["prompt"]
    assert "RETRIEVED CONTEXT" in prompt
    assert "Kubernetes" in prompt


def test_match_prompt_has_no_rag_block_when_context_none(monkeypatch):
    captured = {}

    def fake_generate_json(prompt, _schema):
        captured["prompt"] = prompt
        return {"matched_skills": [], "missing_skills": [], "evidence": []}

    monkeypatch.setattr("app.ai.job_analyzer.llm.generate_json", fake_generate_json)

    job = _mock_job()
    exp = Experience(
        id=9401,
        title="Python Project",
        organization="CUHK",
        description="Built a Python data pipeline.",
        skills=["Python"],
        achievements=[],
        confirmed=True,
    )

    build_match_report_ai(job, [exp])  # no rag_context

    assert "RETRIEVED CONTEXT" not in captured["prompt"]
