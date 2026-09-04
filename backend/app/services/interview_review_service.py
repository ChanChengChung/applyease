"""Evidence-grounded interview debrief coaching.

The service treats the student's own debrief as the primary source.  AI may
organise that reflection into actionable coaching, but it is not allowed to
invent an answer, achievement, metric, or requirement.  A deterministic path
keeps the feature useful in offline/demo deployments and clearly labels the
fallback in the saved record.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.providers import ProviderError, llm
from app.config import settings
from app.models.experience import Experience
from app.models.job import Job
from app.models.tracker import TrackedApplication


COACH_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "strengths": {"type": "array", "items": {"type": "string"}},
        "improvements": {"type": "array", "items": {"type": "string"}},
        "suggested_answer_points": {"type": "array", "items": {"type": "string"}},
        "follow_up_questions": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "summary",
        "strengths",
        "improvements",
        "suggested_answer_points",
        "follow_up_questions",
    ],
}


def _clip(value: object, limit: int) -> str:
    text = str(value or "").strip()
    return text[:limit] + ("…" if len(text) > limit else "")


def _clean_list(value: object, limit: int = 6, item_limit: int = 500) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        text = _clip(item, item_limit)
        if text:
            result.append(text)
    return result[:limit]


def _fallback(review: dict[str, str], language: str) -> dict[str, Any]:
    improvements = review.get("improvements", "")
    strengths = review.get("strengths", "")
    questions = review.get("questions", "")
    if language == "zh-CN":
        summary = "先把面试官的问题拆成具体能力，再用一条已确认经历准备可复述的证据。"
        strength_items = ["保留你记录的做得好的地方，并在下一次回答中继续使用。"]
        improvement_items = [
            "把需要改进的地方改写成一个可观察的行动，例如补充背景、行动和结果。"
        ]
        point_items = [
            "用‘情境—行动—结果—复盘’结构回答；没有真实数字时不要临时补数字。"
        ]
        follow_items = ["下次回答时，哪一条已确认经历最能证明你的行动？"]
    elif language == "zh-TW":
        summary = "先把面試官的問題拆成具體能力，再用一項已確認經歷準備可複述的證據。"
        strength_items = ["保留你記錄的做得好的地方，並在下一次回答中繼續使用。"]
        improvement_items = [
            "把需要改進的地方改寫成一個可觀察的行動，例如補充背景、行動和結果。"
        ]
        point_items = [
            "用『情境—行動—結果—複盤』結構回答；沒有真實數字時不要臨時補數字。"
        ]
        follow_items = ["下次回答時，哪一項已確認經歷最能證明你的行動？"]
    else:
        summary = "Break each question into a capability, then prepare one confirmed experience you can explain precisely."
        strength_items = ["Keep the strengths you recorded and repeat the behaviours that worked."]
        improvement_items = [
            "Turn each improvement into an observable action, such as adding context, action, and result."
        ]
        point_items = [
            "Use a Situation–Action–Result–Reflection structure; never add a number that is not in your evidence."
        ]
        follow_items = ["Which confirmed experience best proves the action in your next answer?"]

    if strengths:
        strength_items.insert(0, _clip(strengths, 500))
    if improvements:
        improvement_items.insert(0, _clip(improvements, 500))
    if questions:
        point_items.insert(0, _clip(questions, 500))
    return {
        "summary": summary,
        "strengths": strength_items[:6],
        "improvements": improvement_items[:6],
        "suggested_answer_points": point_items[:6],
        "follow_up_questions": follow_items[:6],
        "generation_method": "rules",
        "warnings": [
            "AI 复盘教练未启用或暂不可用，已提供确定性建议。 / "
            "AI coaching was disabled or unavailable; deterministic guidance was provided."
        ],
    }


def _evidence_rows(db: Session) -> list[dict[str, Any]]:
    rows = db.scalars(
        select(Experience).where(Experience.confirmed.is_(True)).order_by(Experience.id.asc())
    ).all()
    return [
        {
            "id": item.id,
            "title": item.title,
            "organization": item.organization,
            "description": _clip(item.description, 900),
            "skills": (item.skills or [])[:12],
        }
        for item in rows[:20]
    ]


def coach_review(
    db: Session,
    item: TrackedApplication,
    review: dict[str, str],
    *,
    output_language: str = "en",
) -> dict[str, Any]:
    job: Job | None = None
    if item.job_id:
        job = db.scalar(select(Job).where(Job.id == item.job_id))

    fallback = _fallback(review, output_language)
    if not settings.ai_interview_review_enabled:
        return fallback

    target = {
        "company": item.company,
        "role": item.role,
        "job_description": _clip(job.description, 3000) if job else "",
    }
    prompt = (
        "You are an evidence-grounded interview coach. Return only JSON matching the schema. "
        f"Write all text in {output_language}. Use the student's DEBRIEF as the primary source. "
        "Use CONFIRMED EXPERIENCES only to suggest evidence the student can explain. "
        "Never invent a project, metric, employer fact, skill, deadline, or answer. "
        "If the debrief does not contain enough information, say what is missing and suggest a question. "
        "Keep each list concise and practical.\n\n"
        f"TARGET: {json.dumps(target, ensure_ascii=False)}\n"
        f"DEBRIEF: {json.dumps(review, ensure_ascii=False)}\n"
        f"CONFIRMED EXPERIENCES: {json.dumps(_evidence_rows(db), ensure_ascii=False)}"
    )
    try:
        result = llm.generate_json(
            prompt,
            COACH_SCHEMA,
            feature="interview_review_coaching",
            prompt_version="interview-review-v1",
        )
        summary = _clip(result.get("summary"), 1200)
        if not summary:
            raise ProviderError("AI interview coaching returned an empty summary")
        return {
            "summary": summary,
            "strengths": _clean_list(result.get("strengths")),
            "improvements": _clean_list(result.get("improvements")),
            "suggested_answer_points": _clean_list(result.get("suggested_answer_points")),
            "follow_up_questions": _clean_list(result.get("follow_up_questions")),
            "generation_method": "ai",
            "warnings": [],
        }
    except ProviderError:
        return fallback
