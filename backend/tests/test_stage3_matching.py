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


def test_saved_analysis_is_augmented_with_explicit_language_requirements():
    """Older saved/LLM output must not hide a required language from the report."""
    job = Job(
        id=102,
        title="Software Engineer Internship",
        company="Jane Street",
        description=(
            "As a Software Engineering intern, you'll use OCaml (our primary development "
            "language) in your day to day work. Some teams also use Python."
        ),
        # Simulate the persisted analysis that previously contained only Python.
        required_skills=["Python"],
        preferred_skills=[],
        responsibilities=[],
        qualifications=[],
    )
    job.created_at = datetime.now(timezone.utc)
    experience = Experience(
        id=202,
        title="Python project",
        organization="HKU",
        description="Built a data pipeline with Python.",
        skills=["Python"],
        achievements=[],
        confirmed=True,
    )

    report = build_match_report(job, [experience])

    assert report.matched_required_skills == ["Python"]
    assert "OCaml" in report.missing_required_skills


def test_skill_matching_uses_english_word_boundaries():
    job = Job(
        id=103,
        title="Data role",
        company="Example",
        description="Python and C++ required.",
        required_skills=["C++", "Python"],
        preferred_skills=[],
        responsibilities=[],
        qualifications=[],
    )
    job.created_at = datetime.now(timezone.utc)
    report = build_match_report(
        job,
        [
            Experience(
                id=203,
                title="Candidate profile",
                organization="Example",
                description="Candidate data analysis experience.",
                skills=[],
                achievements=[],
                confirmed=True,
            )
        ],
    )

    assert report.matched_required_skills == []
    assert set(report.missing_required_skills) == {"C++", "Python"}
