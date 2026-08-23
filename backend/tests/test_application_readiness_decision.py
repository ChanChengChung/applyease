from datetime import datetime
from types import SimpleNamespace

from app.services.application_readiness_service import build_application_readiness


def test_readiness_decision_holds_when_evidence_and_resume_are_missing():
    job = SimpleNamespace(
        id=1,
        title="Quant Intern",
        company="Polymer",
        description="Python is required for quantitative research work.",
        created_at=datetime.now(),
        required_skills=["Python"],
        preferred_skills=[],
        responsibilities=[],
        qualifications=[],
    )

    result = build_application_readiness(job, [], [], [])

    assert result["verdict"] == "hold"
    assert result["ready_to_submit"] is False
    assert result["primary_action"]["code"] == "confirmed_experience"


def test_readiness_decision_prepares_when_only_required_skill_evidence_is_missing():
    job = SimpleNamespace(
        id=1,
        title="Quant Intern",
        company="Polymer",
        description="Python and C++ are required for quantitative research work.",
        created_at=datetime.now(),
        required_skills=["Python", "C++"],
        preferred_skills=[],
        responsibilities=[],
        qualifications=[],
    )
    experience = SimpleNamespace(
        id=1,
        confirmed=True,
        title="Python research",
        organization="HKU",
        description="Built a Python pipeline",
        skills=["Python"],
        achievements=[],
    )
    resume = SimpleNamespace(material_type="resume", content={"fact_check_passed": True})

    result = build_application_readiness(job, [experience], [resume], [])

    assert result["verdict"] == "prepare"
    assert result["primary_action"]["code"] == "skill_gaps"
    assert result["verdict_reason_code"] == "skill_gaps"
    assert result["primary_action"]["params"]["skills"] == ["C++"]


def test_readiness_uses_latest_fact_checked_resume_when_newer_draft_needs_review():
    job = SimpleNamespace(
        id=1,
        title="Quant Intern",
        company="Polymer",
        description="Python is required for quantitative research work.",
        created_at=datetime.now(),
        required_skills=["Python"],
        preferred_skills=[],
        responsibilities=[],
        qualifications=[],
    )
    experience = SimpleNamespace(
        id=1,
        confirmed=True,
        title="Python research",
        organization="HKU",
        description="Built a Python pipeline",
        skills=["Python"],
        achievements=[],
    )
    newest_draft = SimpleNamespace(
        id=12, material_type="resume", content={"fact_check_passed": False}
    )
    verified_version = SimpleNamespace(
        id=11, material_type="resume", content={"fact_check_passed": True}
    )

    result = build_application_readiness(
        job, [experience], [newest_draft, verified_version], []
    )

    resume_item = next(item for item in result["items"] if item["code"] == "resume")
    assert resume_item["severity"] == "pass"
    assert resume_item["params"] == {"version_id": 11, "has_draft": True}
    assert result["ready_to_submit"] is True
