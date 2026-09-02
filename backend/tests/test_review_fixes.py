"""Regression tests for the 2026-08-31 review fixes.

Covers four changes:

1. ``app/ai/skills.py``: one shared skill vocabulary instead of two drifting
   hard-coded lists.
2. ``app/ai/mock_extractor.py``: broadened section headings (generic
   "EXPERIENCE"/"PROFESSIONAL EXPERIENCE"), Chinese CV headings, dated
   GENERAL-section fallback and cleaner record titles.
3. ``app/ai/material_generator.py``: the deterministic fallback is no longer
   silent -- a warning explains that the AI attempt failed.
4. ``app/services/job_analysis_service.py``: ``experience_relevance`` is an
   average over confirmed evidence and the constant-0 ``qualification_coverage``
   dimension was removed.
"""

from datetime import datetime, timezone

from app.ai.mock_extractor import extract_experiences
from app.ai.skills import KNOWN_SKILLS
from app.ai.material_generator import ProviderError, generate_resume_safe
from app.services.job_analysis_service import build_match_report
from app.services.material_validation_service import validate_material_text
from app.models.experience import Experience
from app.models.job import Job


def _job() -> Job:
    job = Job(
        id=1,
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


def _experience(item_id: int, title: str, description: str) -> Experience:
    item = Experience(
        id=item_id,
        title=title,
        organization="CUHK",
        description=description,
        skills=["Python"],
        achievements=[],
        source_file="CV.pdf",
        confirmed=True,
    )
    item.created_at = datetime.now(timezone.utc)
    return item


def test_skill_vocabulary_is_shared_and_superset():
    """The CV parser and job analysis must agree on the same skill list."""
    # Skills that previously existed only in the job-analysis list.
    for previously_missing in ("Market Making", "Statistics", "Quantitative Research"):
        assert previously_missing in KNOWN_SKILLS
    # Skills that previously existed only in the CV parser list are retained.
    assert "Python" in KNOWN_SKILLS and "C" in KNOWN_SKILLS


def test_extractor_keeps_generic_experience_headings():
    text = """PROFESSIONAL EXPERIENCE
Software Engineer | Example Corp
06/2024 - 08/2024
Built Python services.

EDUCATION
The University of Hong Kong
BSc Mathematics
"""
    records = extract_experiences(text, "cv.txt")
    titles = " ".join(record["title"] for record in records).lower()

    # The professional experience section must not be silently dropped.
    assert "software engineer" in titles or "example corp" in " ".join(
        record["organization"] for record in records
    )
    categories = {record["category"] for record in records}
    assert "education" in categories
    internship = next(record for record in records if record["category"] == "internship")
    assert internship["title"] == "Software Engineer"
    assert internship["organization"] == "Example Corp"
    assert "Built Python services." in internship["description"]


def test_extractor_handles_chinese_cv_headings():
    text = """教育经历
香港中文大学
数学学士

工作经历
数据分析实习生 | 某科技公司
06/2025 - 08/2025
使用 Python 完成数据清洗。
"""
    records = extract_experiences(text, "cv-cn.txt")

    assert records, "Chinese CV sections must produce records"
    categories = {record["category"] for record in records}
    assert "education" in categories
    assert "internship" in categories


def test_extractor_handles_traditional_chinese_cv_headings():
    text = """教育經歷
香港中文大學
數學學士

實習經歷
數據分析實習生 | 某科技公司
06/2025 - 08/2025
使用 Python 完成數據清洗。

專題研究
AI 申請助手
建構 FastAPI 服務。
"""
    records = extract_experiences(text, "cv-tw.txt")

    assert records, "Traditional Chinese CV sections must produce records"
    categories = {record["category"] for record in records}
    assert "education" in categories
    assert "internship" in categories
    assert "research" in categories
    # The role title should be extracted without the date range.
    internship = next(r for r in records if r["category"] == "internship")
    assert "數據分析實習生" in internship["title"]


def test_extractor_recovers_dated_general_content():
    """A CV with no recognised headings still yields its dated entries."""
    text = """Freelance Developer | Self-employed
01/2025 - 03/2025
Shipped a Python dashboard.
"""
    records = extract_experiences(text, "cv-free.txt")

    assert records
    assert records[0]["title"] != "Uncategorized Experience"
    assert "Python dashboard" in records[0]["description"]


def test_extractor_strips_dates_from_titles_when_content_remains():
    records = extract_experiences(
        """INTERNSHIP EXPERIENCE
Research Assistant, 06/2024 - 08/2024
Cleaned datasets with Pandas.
""",
        "cv-title.txt",
    )

    assert records
    title = records[0]["title"]
    assert "06/2024" not in title
    assert "Research Assistant" in title


def test_skill_union_reaches_matching(monkeypatch):
    """A CV skill only the old job-analysis list knew must now attach to records."""
    records = extract_experiences(
        """PROJECTS
Market Making Simulator
Simulated a market making strategy.
""",
        "cv-mm.txt",
    )

    assert "Market Making" in records[0]["skills"]


def test_fallback_material_reports_that_ai_was_not_used(monkeypatch):
    def _fail(*_args, **_kwargs):
        raise ProviderError("AI material contains an ungrounded citation")

    monkeypatch.setattr("app.ai.material_generator.llm.generate_json", _fail)

    material = generate_resume_safe(_job(), [_experience(40, "Python Project", "Built a Python data pipeline.")])

    assert material.generation_method == "rules"
    assert material.warnings
    assert "回退" in material.warnings[-1] or "fallback" in material.warnings[-1].lower()


def test_match_report_relevance_uses_best_three_records_and_dead_dimension_removed():
    job = _job()
    job.description = "Build Python data products with statistics and probability."
    strong = _experience(1, "Data Project", "Python statistics probability analysis " * 20)
    weak = _experience(2, "Music Club", "Organised concerts and rehearsals")
    weak.skills = []
    unrelated = [
        _experience(index, f"Unrelated activity {index}", "Organised an event")
        for index in range(3, 12)
    ]
    for item in unrelated:
        item.skills = []

    report = build_match_report(job, [strong, weak, *unrelated])

    assert "qualification_coverage" not in report.score_breakdown
    # Adding many unrelated records must not collapse the role relevance. The
    # score is the average of at most the three most relevant records.
    assert report.score_breakdown["experience_relevance"] >= 8


def test_fact_check_compares_whole_numeric_tokens_not_substrings():
    supported, warnings = validate_material_text(
        "Improved throughput by 10%.", [], "Improved throughput by 100%."
    )

    assert supported is False
    assert any("10" in warning for warning in warnings)
