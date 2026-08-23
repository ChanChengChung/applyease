"""Generate deterministic local resume exports for render QA; never reads user data."""
from pathlib import Path
import sys
from types import SimpleNamespace

BACKEND_ROOT = Path(__file__).resolve().parents[1]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.resume_export_service import build_resume_docx, build_resume_pdf


def main() -> None:
    output = Path(__file__).resolve().parents[2] / "tmp" / "resume-qa"

    output.mkdir(parents=True, exist_ok=True)

    job = SimpleNamespace(title="AI Engineering Intern", company="Polymer Capital")

    record = SimpleNamespace(content={
        "text": """TARGET ROLE: AI Engineering Intern
COMPANY: Polymer Capital

SELECTED EXPERIENCE
AI Developer | Student Innovation Lab
Built an evidence-grounded internship application assistant using React, FastAPI and PostgreSQL.
Skills: Python, React, FastAPI, PostgreSQL
- Designed structured AI outputs with deterministic fallback and source validation.
- Added automated tests for document parsing, job matching and application workflows.

QUANTITATIVE PROJECT
Research Project | University Course
Analyzed financial time series and documented reproducible experiments.
Skills: Python, pandas, data analysis""",
        "sources": [
            {"experience_id": 1, "experience_title": "AI Developer", "text": "Built an evidence-grounded internship application assistant."},

            {"experience_id": 2, "experience_title": "Research Project", "text": "Analyzed financial time series and documented reproducible experiments."},
        ],
    })

    for template in ("classic", "modern", "compact"):
        header = {"display_name": "Chen Zhengzhong", "contact_line": "chen@example.com · Hong Kong · github.com/chen"}

        (output / f"resume-{template}.docx").write_bytes(build_resume_docx(record, job, template, include_sources=True, **header))

        (output / f"resume-{template}.pdf").write_bytes(build_resume_pdf(record, job, template, include_sources=True, **header))


if __name__ == "__main__":
    main()
