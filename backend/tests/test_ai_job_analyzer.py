from datetime import datetime, timezone

from app.ai.job_analyzer import (
    build_match_report_ai,
    build_match_report_safe,
    extract_job_requirements_ai,
)
from app.models.experience import Experience
from app.models.job import Job
from app.main import app
from fastapi.testclient import TestClient


def make_job() -> Job:
    job = Job(
        id=10,
        title="AI Intern",
        company="Example",
        description="Python required; Docker preferred.",
        required_skills=["Python"],
        preferred_skills=["Docker"],
        responsibilities=[],
        qualifications=[],
    )
    job.created_at = datetime.now(timezone.utc)

    return job


def make_experience(confirmed: bool = True) -> Experience:
    item = Experience(
        id=7,
        title="ML Project",
        organization="CUHK",
        description="Built a forecasting model with Python.",
        skills=["Python"],
        achievements=[],
        source_file="CV.pdf",
        confirmed=confirmed,
    )
    item.created_at = datetime.now(timezone.utc)

    return item


def test_ai_job_analysis_sanitizes_and_deduplicates(monkeypatch):
    monkeypatch.setattr(
        "app.ai.job_analyzer.llm.generate_json",
        lambda *_: {
            "required_skills": [" Python ", "python"],
            "preferred_skills": ["Docker"],
            "responsibilities": [" Build models "],
            "qualifications": ["Enrolled in university"],
        },
    )

    result = extract_job_requirements_ai("A sufficiently long job description for testing.")

    assert result["required_skills"] == ["Python"]

    assert result["responsibilities"] == ["Build models"]


def test_ai_match_accepts_only_exact_grounded_confirmed_evidence(monkeypatch):
    monkeypatch.setattr(
        "app.ai.job_analyzer.llm.generate_json",
        lambda *_: {
            "matched_skills": ["Python"],
            "missing_skills": ["Docker"],
            "evidence": [
                {
                    "requirement": "Python",
                    "experience_id": 7,
                    "evidence": "Built a forecasting model with Python.",
                }
            ],
        },
    )

    report = build_match_report_ai(make_job(), [make_experience(), make_experience(False)])

    assert report.matched_skills == ["Python"]

    assert report.missing_skills == ["Docker"]

    assert report.considered_experience_ids == [7]

    assert report.evidence[0].experience_title == "ML Project"

    assert report.overall_score == 80


def test_hallucinated_ai_evidence_falls_back_to_rules(monkeypatch):
    monkeypatch.setattr(
        "app.ai.job_analyzer.llm.generate_json",
        lambda *_: {
            "matched_skills": ["Python"],
            "missing_skills": [],
            "evidence": [
                {
                    "requirement": "Python",
                    "experience_id": 7,
                    "evidence": "Won an international Python competition.",
                }
            ],
        },
    )

    report = build_match_report_safe(make_job(), [make_experience()])

    assert "Python" in report.matched_skills

    assert report.evidence

    assert "international" not in report.evidence[0].evidence


def test_job_endpoints_use_ai_analysis_and_grounded_matching(monkeypatch):
    client = TestClient(app)

    experience = client.post(
        "/api/v1/experiences",
        json={
            "title": "API Project",
            "organization": "CUHK",
            "description": "Built typed APIs using FastAPI.",
            "skills": ["FastAPI"],
            "confirmed": True,
        },
    ).json()

    responses = iter(
        [
            {
                "required_skills": ["FastAPI"],
                "preferred_skills": [],
                "responsibilities": ["Build APIs"],
                "qualifications": [],
            },
            {
                "matched_skills": ["FastAPI"],
                "missing_skills": [],
                "evidence": [
                    {
                        "requirement": "FastAPI",
                        "experience_id": experience["id"],
                        "evidence": "Built typed APIs using FastAPI.",
                    }
                ],
            },
        ]
    )

    monkeypatch.setattr("app.ai.job_analyzer.llm.generate_json", lambda *_: next(responses))

    monkeypatch.setattr("app.api.v1.jobs.settings.ai_job_analysis_enabled", True)

    job = client.post(
        "/api/v1/jobs/analyze",
        json={
            "title": "Backend Intern",
            "company": "Example",
            "description": "The successful intern will build production APIs for our platform.",
        },
    )

    assert job.status_code == 200

    assert job.json()["required_skills"] == ["FastAPI"]

    report = client.get(f"/api/v1/jobs/{job.json()['id']}/match-report")

    assert report.status_code == 200

    assert report.json()["matched_skills"] == ["FastAPI"]

    assert report.json()["evidence"][0]["experience_id"] == experience["id"]
