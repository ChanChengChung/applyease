from datetime import date
from app.services.job_analysis_service import build_match_report


ACTIVE_STATUSES = {"saved", "applied", "assessment", "interview", "offer"}
EXPECTED_MATERIALS = {"resume", "cover_letter"}


def _has_answer(question) -> bool:
    answer = question.answer if isinstance(question.answer, dict) else {}

    result = answer.get("result") if isinstance(answer, dict) else None

    return isinstance(result, dict) and bool(str(result.get("text") or "").strip())


# The application readiness funnel is always the same five stages, but the
# percentage only makes sense *per job*: a user applies to many roles, and each
# role has its own materials, questions and tracker entry. `build_dashboard_summary`
# still computes a global next-action for the hero, while `_job_progress` returns
# the completion (0-100) and per-stage status for a single target job.
STEP_DEFINITIONS = [
    ("profile", "经历库", "上传、核对并确认事实"),
    ("jobs", "职位分析", "提取要求与匹配证据"),
    ("builder", "申请材料", "生成 Resume 与 Cover Letter"),
    ("form", "申请问题", "识别并审核表单答案"),
    ("tracker", "申请追踪", "保存状态与下一步日期"),
]
STEP_ORDER = [item[0] for item in STEP_DEFINITIONS]


def _job_progress(
    *,
    has_confirmed_experience: bool,
    job_analyzed: bool,
    material_types: set[str],
    has_application: bool,
    required_unanswered: int,
    linked: bool,
) -> tuple[int, list[dict]]:
    """Return (progress_percent, steps) for a single target job.

    A stage is "complete" once its prerequisite data exists for that job;
    "current" marks the first not-yet-complete stage; everything after is
    "pending". The tracker stage is also complete when the job is already
    linked in the tracker.
    """
    flags = {
        "profile": has_confirmed_experience,
        "jobs": job_analyzed,
        "builder": EXPECTED_MATERIALS.issubset(material_types),
        "form": has_application and required_unanswered == 0,
        "tracker": bool(linked),
    }
    # Find the first incomplete stage.
    current_key = next((key for key in STEP_ORDER if not flags[key]), None)

    steps = []
    for index, (key, label, description) in enumerate(STEP_DEFINITIONS):
        if flags[key]:
            status = "complete"
        elif key == current_key:
            status = "current"
        else:
            status = "pending"
        steps.append(
            {
                "key": key,
                "label": label,
                "description": description,
                "status": status,
                "target": key,
            }
        )

    completed = sum(1 for key in STEP_ORDER if flags[key])
    progress = round((completed / len(STEP_ORDER)) * 100)
    return progress, steps


def build_dashboard_summary(snapshot: dict, today: date | None = None) -> dict:
    today = today or date.today()

    experiences = snapshot["experiences"]

    confirmed = [item for item in experiences if item.confirmed]

    pending = [item for item in experiences if not item.confirmed]

    jobs = snapshot["jobs"]

    job = snapshot["latest_job"]

    materials = snapshot["materials"]

    material_types = sorted({item.material_type for item in materials})

    questions = snapshot["questions"]

    answered = sum(1 for item in questions if _has_answer(item))

    required_unanswered = sum(1 for item in questions if item.required and not _has_answer(item))

    tracked = snapshot["tracked"]

    # Per-role cards form a command center instead of forcing users to infer
    # readiness from scattered pages. Scores only use confirmed experience.
    job_workspaces = []
    for candidate in jobs[:6]:
        # Unit-level snapshots and imported legacy jobs can omit structured
        # requirements. Keep the command center available with safe zeroes.
        report = (
            build_match_report(candidate, experiences)
            if hasattr(candidate, "required_skills")
            else None
        )
        candidate_materials = [
            item
            for item in snapshot.get("all_materials", materials)
            if getattr(item, "job_id", candidate.id) == candidate.id
        ]
        candidate_app = next(
            (
                item
                for item in snapshot.get("all_applications", [snapshot.get("application")])
                if item and getattr(item, "job_id", candidate.id) == candidate.id
            ),
            None,
        )
        candidate_questions = [
            item
            for item in snapshot.get("all_questions", questions)
            if candidate_app
            and getattr(item, "application_id", candidate_app.id) == candidate_app.id
        ]
        candidate_tracked = next((item for item in tracked if item.job_id == candidate.id), None)
        candidate_material_types = sorted({item.material_type for item in candidate_materials})
        candidate_required_unanswered = sum(
            1 for q in candidate_questions if q.required and not _has_answer(q)
        )
        progress, job_steps = _job_progress(
            has_confirmed_experience=bool(confirmed),
            job_analyzed=True,
            material_types=set(candidate_material_types),
            has_application=bool(candidate_app),
            required_unanswered=candidate_required_unanswered,
            linked=bool(candidate_tracked),
        )
        next_target = (
            "builder"
            if not candidate_materials
            else (
                "form"
                if candidate_questions and any(not _has_answer(q) for q in candidate_questions)
                else "tracker"
            )
        )
        job_workspaces.append(
            {
                "id": candidate.id,
                "title": candidate.title,
                "company": candidate.company,
                "match_score": report.overall_score if report else 0,
                "evidence_count": len(report.evidence) if report else 0,
                "missing_skills": report.missing_skills[:3] if report else [],
                "material_count": len(candidate_materials),
                "answers_ready": sum(1 for q in candidate_questions if _has_answer(q)),
                "questions_total": len(candidate_questions),
                "progress": progress,
                "steps": job_steps,
                "tracker_status": candidate_tracked.status if candidate_tracked else None,
                "next_target": next_target,
            }
        )

    linked = next((item for item in tracked if job and item.job_id == job.id), None)

    date_events = []

    for item in tracked:
        if item.status not in ACTIVE_STATUSES:
            continue

        # The dashboard is a reminder surface, not a narrow 14-day filter.
        # A user-entered deadline/interview/follow-up must not silently vanish
        # just because it is more than two weeks away.  Show the closest dated
        # milestones first, including overdue items, and let the Tracker remain
        # the full record of every application.
        for event_date, kind in (
            (getattr(item, "deadline", None), "deadline"),
            (getattr(item, "interview_date", None), "interview"),
            (getattr(item, "follow_up_at", None), "follow_up"),
        ):
            if event_date:
                date_events.append((event_date, item, kind))
    date_events.sort(key=lambda event: (event[0] < today, event[0]))

    upcoming = date_events[:5]

    if not experiences:
        current, action = "profile", (
            "上传你的 CV",
            "建立可验证的个人经历库，后续生成内容才有事实依据。",
            "profile",
        )

    elif pending:
        current, action = "profile", (
            "确认个人经历",
            f"还有 {len(pending)} 条经历等待核对。",
            "profile",
        )

    elif not job:
        current, action = "jobs", ("分析目标职位", "粘贴职位描述，找出匹配证据和技能缺口。", "jobs")

    elif not EXPECTED_MATERIALS.issubset(material_types):
        current, action = "builder", (
            "生成申请材料",
            "为最新职位生成 Resume 和 Cover Letter。",
            "builder",
        )

    elif not snapshot["application"]:
        current, action = "form", (
            "识别申请表问题",
            "粘贴表单文本或上传截图，建立可审核答案。",
            "form",
        )

    elif required_unanswered:
        current, action = "form", (
            "完成申请问题",
            f"还有 {required_unanswered} 个必填问题需要生成或人工填写。",
            "form",
        )

    elif not linked:
        current, action = "tracker", (
            "加入申请追踪",
            "保存截止日期和申请状态，避免遗漏 follow-up。",
            "tracker",
        )

    else:
        current, action = "tracker", (
            "检查申请进度",
            "材料准备流程已完成，请核对投递状态和近期日期。",
            "tracker",
        )

    definitions = [
        ("profile", "经历库", "上传、核对并确认事实"),
        ("jobs", "职位分析", "提取要求与匹配证据"),
        ("builder", "申请材料", "生成 Resume 与 Cover Letter"),
        ("form", "申请问题", "识别并审核表单答案"),
        ("tracker", "申请追踪", "保存状态与下一步日期"),
    ]

    order = [item[0] for item in definitions]

    current_index = order.index(current)

    steps = [
        {
            "key": key,
            "label": label,
            "description": description,
            "status": (
                "complete"
                if index < current_index or (key == "tracker" and linked)
                else "current" if index == current_index else "pending"
            ),
            "target": key,
        }
        for index, (key, label, description) in enumerate(definitions)
    ]

    return {
        "experience_total": len(experiences),
        "confirmed_experiences": len(confirmed),
        "pending_experiences": len(pending),
        "job_total": len(jobs),
        "latest_job": {"id": job.id, "title": job.title, "company": job.company} if job else None,
        "material_count": len(materials),
        "material_types": material_types,
        "latest_material_type": materials[0].material_type if materials else None,
        "application_id": snapshot["application"].id if snapshot["application"] else None,
        "questions_total": len(questions),
        "answers_ready": answered,
        "tracker_total": len(tracked),
        "active_applications": sum(1 for item in tracked if item.status in ACTIVE_STATUSES),
        "upcoming_deadlines": [
            {
                "id": item.id,
                "job_id": item.job_id,
                "company": item.company,
                "role": item.role,
                "deadline": event_date,
                "status": item.status,
                "kind": kind,
                "is_overdue": event_date < today,
            }
            for event_date, item, kind in upcoming
        ],
        "steps": steps,
        "next_action": {"title": action[0], "description": action[1], "target": action[2]},
        "job_workspaces": job_workspaces,
    }
