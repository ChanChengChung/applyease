from datetime import datetime, timezone

from app.models.experience import Experience
from app.models.job import Job
from app.services.job_analysis_service import build_match_report, extract_job_requirements


def _job() -> Job:
    job = Job(
        id=101,
        title="Research Intern",
        company="Example",
        description="Build reliable models and analyze experiments.",
        required_skills=["Scala", "Distributed Systems"],
        preferred_skills=["Kubernetes"],
        responsibilities=["Build reliable models"],
        qualifications=["Currently enrolled"],
    )
    job.created_at = datetime.now(timezone.utc)

    return job


def _experience(
    confirmed: bool, description: str = "Implemented Scala data pipelines."
) -> Experience:
    item = Experience(
        id=201,
        title="Data Project",
        organization="HKU",
        description=description,
        skills=["Scala"],
        achievements=[{"text": "Reduced latency by 20%", "source": "CV.pdf", "verified": False}],
        source_file="CV.pdf",
        confirmed=confirmed,
    )
    item.created_at = datetime.now(timezone.utc)

    return item


def test_matching_supports_non_catalog_skills_and_separates_required_preferred():
    report = build_match_report(_job(), [_experience(True)])

    assert report.matched_required_skills == ["Scala"]

    assert report.missing_required_skills == ["Distributed Systems"]

    assert report.missing_preferred_skills == ["Kubernetes"]

    assert report.matched_skills == ["Scala"]

    assert report.evidence[0].evidence == "Implemented Scala data pipelines."

    assert report.score_breakdown["required_skill_match"] == 20


def test_unconfirmed_only_match_is_excluded_and_explained():
    report = build_match_report(_job(), [_experience(False)])

    assert report.considered_experience_ids == []

    assert report.evidence == []

    assert "没有已确认经历" in report.warnings[0]


def test_rule_extractor_deduplicates_and_classifies_preferred_lines():
    result = extract_job_requirements(
        "Required: Python and SQL\nPreferred: Docker and Python\nBuild data pipelines"
    )

    assert result["required_skills"] == ["SQL"]

    assert result["preferred_skills"] == ["Python", "Docker"]

    assert result["responsibilities"] == ["Build data pipelines"]
