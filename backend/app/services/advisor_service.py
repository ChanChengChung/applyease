"""Evidence-grounded application strategy assistant.

The assistant deliberately receives only the current user's confirmed facts and
application workflow state. It never invents achievements and returns the
human-readable source labels used to ground the answer.
"""

from __future__ import annotations

import json
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.providers import ProviderError, llm
from app.models import (
    Application,
    ApplicationQuestion,
    Experience,
    GeneratedMaterial,
    Job,
    TrackedApplication,
)


def _clip(value: object, limit: int = 900) -> str:
    text = str(value or "").strip()
    return text[:limit] + ("…" if len(text) > limit else "")


def _snapshot(
    db: Session,
    user_id: int,
    active_page: str = "dashboard",
    active_job_id: int | None = None,
) -> tuple[dict, list[str]]:
    experiences = db.scalars(
        select(Experience).where(Experience.user_id == user_id, Experience.confirmed.is_(True))
    ).all()
    jobs = db.scalars(
        select(Job).where(Job.user_id == user_id).order_by(Job.created_at.desc()).limit(4)
    ).all()
    active_job = None
    if active_job_id is not None:
        active_job = db.scalar(
            select(Job).where(Job.id == active_job_id, Job.user_id == user_id)
        )
        if active_job is not None:
            jobs = [active_job, *[item for item in jobs if item.id != active_job.id]][:4]
    materials = db.scalars(
        select(GeneratedMaterial)
        .where(GeneratedMaterial.user_id == user_id)
        .order_by(GeneratedMaterial.created_at.desc())
        .limit(12)
    ).all()
    applications = db.scalars(
        select(Application)
        .where(Application.user_id == user_id)
        .order_by(Application.created_at.desc())
        .limit(4)
    ).all()
    trackers = db.scalars(
        select(TrackedApplication)
        .where(TrackedApplication.user_id == user_id)
        .order_by(TrackedApplication.created_at.desc())
        .limit(8)
    ).all()
    question_count = len(
        db.scalars(select(ApplicationQuestion).where(ApplicationQuestion.user_id == user_id)).all()
    )
    sources: list[str] = []
    experience_rows = []
    for item in experiences[:8]:
        label = f"Experience: {item.title} @ {item.organization or 'n/a'}"
        sources.append(label)
        experience_rows.append(
            {"source": label, "description": _clip(item.description), "skills": item.skills[:12]}
        )
    job_rows = []
    for item in jobs:
        label = f"Job: {item.company or 'Company'} · {item.title}"
        sources.append(label)
        job_rows.append(
            {
                "source": label,
                "required_skills": item.required_skills[:16],
                "preferred_skills": item.preferred_skills[:12],
                "description": _clip(item.description, 650),
            }
        )
    snapshot = {
        "active_context": {
            "screen": _clip(active_page, 64),
            "selected_job": (
                f"{active_job.company or 'Company'} · {active_job.title}"
                if active_job is not None
                else None
            ),
        },
        "confirmed_experiences": experience_rows,
        "jobs": job_rows,
        "material_types": [item.material_type for item in materials],
        "application_forms": len(applications),
        "detected_questions": question_count,
        "tracked_applications": [
            {
                "company": item.company,
                "role": item.role,
                "status": item.status,
                "deadline": str(item.deadline or ""),
                "follow_up": str(item.follow_up_at or ""),
            }
            for item in trackers
        ],
    }
    return snapshot, list(dict.fromkeys(sources))


def _fallback(snapshot: dict, language: str) -> tuple[str, list[str]]:
    facts = snapshot["confirmed_experiences"]
    jobs = snapshot["jobs"]
    selected_job = snapshot.get("active_context", {}).get("selected_job")
    target = f" for {selected_job}" if selected_job else ""
    if language == "en":
        answer = f"You are currently working{target}. Start by confirming evidence before tailoring an application. "
        answer += f"You currently have {len(facts)} confirmed experience(s) and {len(jobs)} analysed role(s). "
        answer += "Choose one target role, verify its required skills against your confirmed experience, then generate and review the resume and cover letter."
    elif language == "zh-CN":
        context = f"你当前正在处理「{selected_job}」。" if selected_job else ""
        answer = f"{context}建议先完成事实核对，再定制申请材料。你目前有 {len(facts)} 条已确认经历、{len(jobs)} 个已分析职位。请选择一个目标职位，核对必备技能与已确认经历的证据，再生成并审核 Resume 和 Cover Letter。"
    else:
        context = f"你目前正在處理「{selected_job}」。" if selected_job else ""
        answer = f"{context}建議先完成事實核對，再客製申請材料。你目前有 {len(facts)} 項已確認經歷、{len(jobs)} 個已分析職位。請選定一個目標職位，核對必備技能與已確認經歷的證據，再生成並審核 Resume 和 Cover Letter。"
    return answer, [row["source"] for row in facts[:3]] + [row["source"] for row in jobs[:2]]


def answer_advisor(
    db: Session,
    user_id: int,
    message: str,
    history: list[dict],
    language: str,
    active_page: str = "dashboard",
    active_job_id: int | None = None,
) -> dict:
    snapshot, all_sources = _snapshot(db, user_id, active_page, active_job_id)
    prompt = f"""You are ApplyEase, an evidence-grounded internship application strategy assistant.
Reply in {language}. All human-readable text must use only the requested interface language (English, Simplified Chinese, or Traditional Chinese). Give concise, practical guidance for a university student.
Focus first on ACTIVE CONTEXT, including the selected role when one is present. It is supplied by the app shell, but role ownership is verified server-side.
Only make factual claims that appear verbatim in USER WORKSPACE. Do not use outside/web knowledge, including company-specific hiring practices, interview formats, deadlines, or job requirements not shown below. Never infer a skill from an employer name. Never invent projects, metrics, skills, deadlines or applications. If evidence is missing, explicitly say it is not in the workspace and give a safe next action.
Return JSON with exactly: answer (string, max 900 chars), sources (array of source labels from USER WORKSPACE only), suggested_prompts (array of 3 short next questions).

USER WORKSPACE:
{json.dumps(snapshot, ensure_ascii=False)}

RECENT CONVERSATION:
{json.dumps(history[-8:], ensure_ascii=False)}

USER QUESTION:
{message}
"""
    try:
        result = llm.generate_json(
            prompt,
            {
                "type": "object",
                "properties": {
                    "answer": {"type": "string"},
                    "sources": {"type": "array", "items": {"type": "string"}},
                    "suggested_prompts": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["answer", "sources", "suggested_prompts"],
            },
            feature="application_advisor",
            prompt_version="advisor-v2-contextual",
        )
        answer = _clip(result.get("answer"), 900)
        sources = [item for item in result.get("sources", []) if item in all_sources][:5]
        prompts = [
            _clip(item, 100) for item in result.get("suggested_prompts", []) if str(item).strip()
        ][:3]
        if not answer:
            raise ProviderError("Empty advisor answer")
        return {
            "answer": answer,
            "sources": sources,
            "suggested_prompts": prompts,
            "used_fallback": False,
        }
    except ProviderError:
        answer, sources = _fallback(snapshot, language)
        return {
            "answer": answer,
            "sources": sources[:5],
            "suggested_prompts": [],
            "used_fallback": True,
        }
