"""Build review-only Experience Bank drafts from completed learning projects."""

from app.models.resource import LearningResource


def experience_values_from_completed_resource(resource: LearningResource, reflection: str) -> dict:
    project = resource.project or {}
    project_title = str(project.get("title") or resource.title).strip()[:200]
    task = str(project.get("task") or "").strip()
    source = f"Learning resource: {resource.title}"[:255]
    context = f"Completed a self-directed project using {resource.title} ({resource.url})."
    description_parts = [context]
    if task:
        description_parts.append(f"Planned task: {task}")
    description_parts.append(f"My completed work: {reflection.strip()}")
    return {
        "title": project_title or resource.title,
        "organization": "Self-directed project",
        "description": "\n".join(description_parts),
        "skills": [str(skill).strip() for skill in (resource.skills or []) if str(skill).strip()],
        "achievements": [],
        "source_file": source,
        # A resource catalogue can propose a project; it cannot prove the student did it.
        "confirmed": False,
    }
