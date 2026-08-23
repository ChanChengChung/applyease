from app.services.job_analysis_service import build_match_report


def build_application_readiness(job, experiences, materials, applications) -> dict:
    report = build_match_report(job, experiences)
    items: list[dict] = []
    confirmed = [item for item in experiences if item.confirmed]
    latest = {}
    for material in materials:
        latest.setdefault(material.material_type, material)

    latest_fact_checked = {}
    for material in materials:
        content = material.content if isinstance(material.content, dict) else {}
        if content.get("fact_check_passed"):
            latest_fact_checked.setdefault(material.material_type, material)

    def add(code, severity, title, detail, target, **params):
        items.append(
            {
                "code": code,
                "severity": severity,
                "title": title,
                "detail": detail,
                "target": target,
                "params": params,
            }
        )

    add(
        "confirmed_experience",
        "pass" if confirmed else "blocker",
        "Confirmed experience",
        (
            "Confirmed Experience Bank evidence is available."
            if confirmed
            else "Confirm at least one accurate experience before submitting AI-assisted material."
        ),
        "profile",
        count=len(confirmed),
    )
    resume = latest_fact_checked.get("resume")
    newest_resume = latest.get("resume")
    add(
        "resume",
        "pass" if resume else "blocker",
        "Targeted resume",
        (
            "A fact-checked resume is ready."
            if resume
            else "Generate or fix a fact-checked resume for this job."
        ),
        "builder",
        version_id=getattr(resume, "id", None),
        has_draft=bool(newest_resume),
    )
    cover = latest_fact_checked.get("cover_letter")
    newest_cover = latest.get("cover_letter")
    add(
        "cover_letter",
        "pass" if cover else "warning",
        "Cover letter",
        (
            "A fact-checked cover letter is ready."
            if cover
            else "Generate a cover letter if this application requests one."
        ),
        "builder",
        version_id=getattr(cover, "id", None),
        has_draft=bool(newest_cover),
    )
    app = applications[0] if applications else None
    if not app:
        add(
            "application_form",
            "warning",
            "Application form",
            "No form questions have been reviewed for this job yet.",
            "form",
            application_exists=False,
        )
    else:
        required = [q for q in app.questions if q.required]
        unanswered = [
            q
            for q in required
            if not isinstance(q.answer, dict) or not (q.answer.get("result") or {}).get("text")
        ]
        unsafe = [
            q
            for q in required
            if (q.answer or {}).get("result")
            and not (q.answer.get("result") or {}).get("fact_check_passed")
            and q.question_type
            not in {
                "identity",
                "eligibility",
                "salary",
                "demographic",
                "personal_info",
                "availability",
            }
        ]
        add(
            "required_answers",
            "blocker" if unanswered or unsafe else "pass",
            "Required application answers",
            (
                f"{len(unanswered)} required answer(s) missing; {len(unsafe)} answer(s) need fact review."
                if unanswered or unsafe
                else "All required answers are present and fact-checked."
            ),
            "form",
            missing=len(unanswered),
            unsafe=len(unsafe),
            application_exists=True,
        )
    if report.missing_required_skills:
        add(
            "skill_gaps",
            "warning",
            "Required skill gaps",
            "Missing: " + ", ".join(report.missing_required_skills[:6]),
            "resources",
            skills=report.missing_required_skills[:6],
        )
    else:
        add(
            "skill_gaps",
            "pass",
            "Required skill coverage",
            "Confirmed evidence covers the extracted required skills.",
            "jobs",
        )
    blockers = sum(item["severity"] == "blocker" for item in items)
    warnings = sum(item["severity"] == "warning" for item in items)
    primary = next((item for item in items if item["severity"] == "blocker"), None)
    if primary:
        verdict, reason = "hold", primary["detail"]
        reason_code, reason_params = primary["code"], primary.get("params", {})
    elif report.missing_required_skills:
        primary = next(item for item in items if item["code"] == "skill_gaps")
        verdict, reason = "prepare", "Strengthen the highest-impact evidence gap before applying."
        reason_code, reason_params = "skill_gaps", primary.get("params", {})
    else:
        primary = next((item for item in items if item["severity"] == "warning"), None)
        verdict = "ready" if not primary else "review"
        reason = "Evidence and required material are ready." if not primary else primary["detail"]
        reason_code = primary["code"] if primary else "ready"
        reason_params = primary.get("params", {}) if primary else {}
    return {
        "job_id": job.id,
        "ready_to_submit": blockers == 0,
        "blockers": blockers,
        "warnings": warnings,
        "match_score": report.overall_score,
        "missing_required_skills": report.missing_required_skills,
        "items": items,
        "verdict": verdict,
        "verdict_reason": reason,
        "verdict_reason_code": reason_code,
        "verdict_reason_params": reason_params,
        "primary_action": primary,
    }
