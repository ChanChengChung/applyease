import re

from app.models.experience import Experience
from app.models.job import Job
from app.schemas.material import MaterialContent, SourceCitation

OutputLanguage = str


def _words(language: OutputLanguage) -> dict[str, str]:
    """Small, deterministic copy layer used when an LLM is unavailable.

    Evidence (titles, organisations, skills, and descriptions) is deliberately
    never translated: changing it could turn a verified CV fact into a claim
    the applicant cannot substantiate.
    """
    if language == "zh-CN":
        return {
            "role": "目标职位",
            "company": "公司",
            "experience": "相关经历",
            "skills": "技能",
            "dear": "招聘团队您好：",
            "apply": "我希望申请",
            "closing": "期待有机会进一步交流这些经历如何为团队作出贡献。\n\n此致\n[您的姓名]",
            "developing": "我正通过系统课程和实践项目培养该职位所需的技能。",
            "star": "情境：",
            "task": "任务：",
            "action": "行动：",
            "result": "结果：",
        }
    if language == "zh-TW":
        return {
            "role": "目標職位",
            "company": "公司",
            "experience": "相關經歷",
            "skills": "技能",
            "dear": "招聘團隊您好：",
            "apply": "我希望申請",
            "closing": "期待有機會進一步交流這些經歷如何為團隊作出貢獻。\n\n此致\n[您的姓名]",
            "developing": "我正透過系統課程和實作專案培養該職位所需的技能。",
            "star": "情境：",
            "task": "任務：",
            "action": "行動：",
            "result": "結果：",
        }
    return {
        "role": "TARGET ROLE",
        "company": "COMPANY",
        "experience": "SELECTED EXPERIENCE",
        "skills": "Skills",
        "dear": "Dear Hiring Team",
        "apply": "I am excited to apply for",
        "closing": "I would welcome the opportunity to discuss how these experiences could contribute to your team.\n\nSincerely,\n[Your Name]",
        "developing": "I am developing the skills required for this role through focused coursework and practical projects.",
        "star": "Situation:",
        "task": "Task:",
        "action": "Action:",
        "result": "Result:",
    }


def _confirmed(experiences: list[Experience]) -> list[Experience]:

    return [item for item in experiences if item.confirmed]


def _source(item: Experience) -> SourceCitation:
    text = item.description.splitlines()[0] if item.description else item.title

    return SourceCitation(experience_id=item.id, experience_title=item.title, text=text, claim=text)


def _fact_check(
    text: str, experiences: list[Experience], language: OutputLanguage = "en"
) -> tuple[bool, list[str]]:
    evidence = " ".join(
        [
            item.title
            + " "
            + item.organization
            + " "
            + item.description
            + " "
            + " ".join(item.skills or [])
            + " "
            + " ".join(
                str(value.get("text", ""))
                for value in (item.achievements or [])
                if isinstance(value, dict)
            )
            for item in experiences
        ]
    ).lower()

    warnings: list[str] = []

    for number in re.findall(r"\b\d+(?:\.\d+)?%?\b", text):

        if number.lower() not in evidence:
            if language == "en":
                warnings.append(f"Number {number} is not supported by confirmed experience")
            elif language == "zh-TW":
                warnings.append(f"數字 {number} 未見於已確認經歷")
            else:
                warnings.append(f"数字 {number} 不在已确认经历中")

    return not warnings, warnings


def generate_resume(
    job: Job, experiences: list[Experience], *, output_language: OutputLanguage = "en"
) -> MaterialContent:
    selected = _confirmed(experiences)
    words = _words(output_language)

    lines = [
        f"{words['role']}: {job.title}",
        f"{words['company']}: {job.company}" if job.company else "",
        "",
        words["experience"],
    ]

    for item in selected[:6]:
        lines.append(f"{item.title} | {item.organization}".strip(" |"))

        if item.description:
            lines.append(item.description.splitlines()[0])

        if item.skills:
            lines.append(f"{words['skills']}: " + ", ".join(item.skills))
    text = "\n".join(line for line in lines if line)

    passed, warnings = _fact_check(text, selected, output_language)

    return MaterialContent(
        material_type="resume",
        text=text,
        character_count=len(text),
        fact_check_passed=passed,
        warnings=warnings,
        sources=[_source(item) for item in selected[:6]],
        output_language=output_language,
    )


def generate_cover_letter(
    job: Job, experiences: list[Experience], *, output_language: OutputLanguage = "en"
) -> MaterialContent:
    selected = _confirmed(experiences)[:2]
    words = _words(output_language)

    skills = list(dict.fromkeys(skill for item in selected for skill in (item.skills or [])))[:8]

    if output_language == "en":
        paragraphs = [
            f"{words['dear']},",
            f"{words['apply']} the {job.title} role. My verified background in {', '.join(skills) or 'practical project work'} is relevant to the skills and responsibilities described in the posting.",
        ]
    else:
        paragraphs = [
            words["dear"],
            f"{words['apply']} {job.company or ''} 的 {job.title} "
            + ("職位。我的 " if output_language == "zh-TW" else "职位。我的 ")
            + (", ".join(skills) or ("技術問題解決" if output_language == "zh-TW" else "技术问题解决"))
            + (" 背景與職位所述需求相符。" if output_language == "zh-TW" else " 背景与职位所述需求相符。"),
        ]

    for item in selected:
        evidence = item.description.splitlines()[0] if item.description else item.title
        if output_language == "en":
            paragraphs.append(
                f"As {item.title}{f' at {item.organization}' if item.organization else ''}, I {evidence[:1].lower() + evidence[1:] if evidence else 'built relevant experience'}. "
                f"This gives me a grounded basis to contribute {', '.join((item.skills or [])[:3]) or 'relevant skills'} to the role."
            )
        elif output_language == "zh-TW":
            paragraphs.append(
                f"在 {item.organization or '相關經歷'} 擔任 {item.title} 時，我曾{evidence}。"
                f"這讓我能以 {', '.join((item.skills or [])[:3]) or '相關能力'} 為這個職位作出貢獻。"
            )
        else:
            paragraphs.append(
                f"在 {item.organization or '相关经历'} 担任 {item.title} 时，我曾{evidence}。"
                f"这让我能够以 {', '.join((item.skills or [])[:3]) or '相关能力'} 为这个职位作出贡献。"
            )
    paragraphs.append(words["closing"])

    text = "\n\n".join(paragraphs)

    passed, warnings = _fact_check(text, selected, output_language)

    return MaterialContent(
        material_type="cover_letter",
        text=text,
        character_count=len(text),
        fact_check_passed=passed,
        warnings=warnings,
        sources=[_source(item) for item in selected],
        output_language=output_language,
    )


def generate_answer(
    job: Job,
    question: str,
    max_characters: int,
    experiences: list[Experience],
    *,
    template: str = "detailed_300",
    output_language: OutputLanguage = "en",
    answer_tone: str = "professional",
    desired_content: str = "",
) -> MaterialContent:
    selected = _confirmed(experiences)[:2]
    words = _words(output_language)

    if selected:
        body = (
            (
                "I would draw on my experience as "
                if output_language == "en"
                else "我会结合自己担任 "
            )
            + " and ".join(item.title for item in selected)
            + (". " if output_language == "en" else " 的经历。")
            + " ".join(" ".join(item.description.splitlines()[:2]) for item in selected)
        )

    else:
        body = words["developing"]
    if template == "star" and selected:
        item = selected[0]
        evidence = item.description.splitlines()[0] if item.description else item.title
        skills = ", ".join((item.skills or [])[:3])
        if output_language == "en":
            body = (
                f"{words['star']} {item.title} at {item.organization}, {evidence} "
                f"{words['task']} I focused on delivering the assigned work. "
                f"{words['action']} I applied {skills or 'the relevant skills'}. "
                f"{words['result']} The experience prepared me to contribute thoughtfully in a similar role."
            )
        else:
            task_text = (
                "我專注於完成既定工作。" if output_language == "zh-TW" else "我专注于完成既定工作。"
            )
            related_skills = "相關技能" if output_language == "zh-TW" else "相关技能"
            action_text = "我運用了" if output_language == "zh-TW" else "我运用了"
            result_text = (
                "這段經歷讓我能以有依據的方式貢獻於類似職位。"
                if output_language == "zh-TW"
                else "这段经历让我能以有依据的方式贡献于类似职位。"
            )
            body = (
                f"{words['star']} {item.title}，{item.organization}，{evidence} "
                f"{words['task']} {task_text}"
                f"{words['action']} {action_text} {skills or related_skills}。"
                f"{words['result']} {result_text}"
            )
    # A fallback must remain grounded, but it can still respect a user's
    # requested emphasis without inventing new facts.
    preference = ""
    if desired_content:
        preference = (
            f" {desired_content}" if output_language == "en" else f" 并重点回应：{desired_content}"
        )
    if answer_tone == "concise":
        body = body.split(". ")[0] + "."
    text = (body + preference)[:max_characters].rstrip()

    passed, warnings = _fact_check(text, selected, output_language)

    return MaterialContent(
        material_type="application_answer",
        text=text,
        character_count=len(text),
        fact_check_passed=passed,
        warnings=warnings,
        sources=[_source(item) for item in selected],
        max_characters=max_characters,
        output_language=output_language,
    )


def generate_material(
    job: Job,
    experiences: list[Experience],
    material_type: str,
    *,
    ai_enabled: bool,
    question: str | None = None,
    max_characters: int = 300,
    answer_template: str = "detailed_300",
    answer_tone: str = "professional",
    desired_content: str = "",
    output_language: OutputLanguage = "en",
    db=None,
    user_id: int | None = None,
) -> MaterialContent:
    """Application-facing generation boundary; provider selection stays out of the API router.

    `db` and `user_id` are forwarded to the AI generator so it can run RAG retrieval
    over the applicant's own experiences/documents before calling the model.
    """

    if material_type == "resume":

        if ai_enabled:
            from app.ai.material_generator import generate_resume_safe

            return generate_resume_safe(
                job, experiences, output_language=output_language, db=db, user_id=user_id
            )

        return generate_resume(job, experiences, output_language=output_language)

    if material_type == "cover_letter":

        if ai_enabled:
            from app.ai.material_generator import generate_cover_letter_safe

            return generate_cover_letter_safe(
                job, experiences, output_language=output_language, db=db, user_id=user_id
            )

        return generate_cover_letter(job, experiences, output_language=output_language)

    if material_type == "application_answer" and question is not None:

        if ai_enabled:
            from app.ai.material_generator import generate_answer_safe

            return generate_answer_safe(
                job,
                question,
                max_characters,
                experiences,
                template=answer_template,
                answer_tone=answer_tone,
                desired_content=desired_content,
                output_language=output_language,
                db=db,
                user_id=user_id,
            )

        return generate_answer(
            job,
            question,
            max_characters,
            experiences,
            template=answer_template,
            output_language=output_language,
            answer_tone=answer_tone,
            desired_content=desired_content,
        )

    raise ValueError("Unsupported material type or missing question")
