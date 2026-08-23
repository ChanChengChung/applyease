"""Explain how a confirmed experience is actually used across ApplyEase."""

from app.models.experience import Experience
from app.models.job import Job
from app.models.material import GeneratedMaterial
from app.services.job_analysis_service import build_match_report


def _material_cites_experience(material: GeneratedMaterial, experience_id: int) -> bool:
    content = material.content if isinstance(material.content, dict) else {}
    sources = content.get("sources", []) if isinstance(content, dict) else []
    return any(
        isinstance(source, dict) and int(source.get("experience_id", -1)) == experience_id
        for source in sources
    )


def build_experience_impacts(
    experiences: list[Experience], jobs: list[Job], materials: list[GeneratedMaterial]
) -> list[dict]:
    confirmed = [item for item in experiences if item.confirmed]
    results: list[dict] = []
    for experience in confirmed:
        supported_jobs = []
        for job in jobs[:40]:
            report = build_match_report(job, experiences)
            matched = [e for e in report.evidence if e.experience_id == experience.id]
            if matched:
                supported_jobs.append(
                    {
                        "job_id": job.id,
                        "title": job.title,
                        "company": job.company,
                        "requirements_supported": len(matched),
                    }
                )
        cited_materials = [
            {
                "material_id": material.id,
                "job_id": material.job_id,
                "material_type": material.material_type,
            }
            for material in materials
            if _material_cites_experience(material, experience.id)
        ]
        results.append(
            {
                "experience_id": experience.id,
                "confirmed": True,
                "skills_available": list(experience.skills or []),
                "supported_jobs": supported_jobs[:6],
                "material_references": cited_materials[:12],
            }
        )
    return results
