"""Career-exploration plans for students with no CV evidence yet.

The plan deliberately recommends *opportunities to create evidence*, rather
than treating a course enrolment or competition entry as an experience. A
student must still complete work and write their own reflection before an
Experience Bank draft can exist.
"""

from __future__ import annotations

from app.ai.providers import ProviderError, llm
from app.config import settings
from app.services.resource_service import recommend_resources

PROFILES = {
    "quant": {
        "skills": ["Python", "Quantitative Research", "Algorithms"],
        "headline": {
            "en": "Build a first research habit, then turn it into a measurable project.",
            "zh-CN": "先建立研究习惯，再把它做成可验证的项目。",
            "zh-TW": "先建立研究習慣，再把它做成可驗證的專案。",
        },
        "first": {
            "en": "Choose one public dataset or market question; write a one-page hypothesis before coding.",
            "zh-CN": "选择一个公开数据集或市场问题，先写一页研究假设，再开始编码。",
            "zh-TW": "選一個公開資料集或市場問題，先寫一頁研究假設，再開始編碼。",
        },
    },
    "business": {
        "skills": ["Business Analysis", "Communication", "Research"],
        "headline": {
            "en": "Use a real problem to practise structured analysis and clear communication.",
            "zh-CN": "用真实问题练习结构化分析和清晰表达。",
            "zh-TW": "用真實問題練習結構化分析與清楚表達。",
        },
        "first": {
            "en": "Pick one competition brief or campus problem and create a one-page problem framing.",
            "zh-CN": "选择一个商赛题目或校园问题，先完成一页问题定义。",
            "zh-TW": "選一個商賽題目或校園問題，先完成一頁問題定義。",
        },
    },
    "software": {
        "skills": ["Python", "FastAPI", "Git", "Docker"],
        "headline": {
            "en": "Ship one small, documented tool before attempting a large portfolio.",
            "zh-CN": "先交付一个小而完整、可说明的工具，再做大型作品集。",
            "zh-TW": "先交付一個小而完整、可說明的工具，再做大型作品集。",
        },
        "first": {
            "en": "Choose one annoying student workflow and write its smallest useful feature in one sentence.",
            "zh-CN": "挑一个令学生困扰的流程，用一句话定义它最小但有用的功能。",
            "zh-TW": "挑一個令學生困擾的流程，用一句話定義它最小但有用的功能。",
        },
    },
    "ai": {
        "skills": ["Python", "Machine Learning", "Pandas"],
        "headline": {
            "en": "Learn AI by evaluating a small model on a real dataset, not by only watching tutorials.",
            "zh-CN": "通过在真实数据集上评估小模型来学习 AI，而不只是看教程。",
            "zh-TW": "透過在真實資料集上評估小模型來學習 AI，而不只是看教學。",
        },
        "first": {
            "en": "Pick a beginner competition or dataset and define one baseline you can reproduce.",
            "zh-CN": "选择一个入门竞赛或数据集，并定义一个你可以复现的 baseline。",
            "zh-TW": "選一個入門競賽或資料集，並定義一個你可以重現的 baseline。",
        },
    },
}


def _keyword_focus(interest: str) -> str:
    value = interest.casefold()
    if any(word in value for word in ("quant", "finance", "trading", "金融", "量化", "交易")):
        return "quant"
    if any(
        word in value
        for word in ("consult", "business", "marketing", "创业", "商赛", "咨询", "商業")
    ):
        return "business"
    if any(
        word in value for word in ("software", "web", "backend", "frontend", "开发", "開發", "程式")
    ):
        return "software"
    return "ai"


def _ai_focus(interest: str) -> tuple[str, bool]:
    """Use the configured local/cloud model only for bounded intent routing."""
    fallback = _keyword_focus(interest)
    if not settings.ai_job_analysis_enabled:
        return fallback, True
    try:
        result = llm.generate_json(
            "Classify this university student's career interest into exactly one allowed focus. "
            "Do not give advice. Allowed values: ai, quant, software, business.\n"
            f"Interest: {interest}",
            {
                "type": "object",
                "properties": {"focus": {"type": "string", "enum": list(PROFILES)}},
                "required": ["focus"],
            },
            feature="starter_plan_routing",
            prompt_version="starter-plan-v1",
        )
        focus = result.get("focus")
        return (focus, False) if focus in PROFILES else (fallback, True)
    except ProviderError:
        return fallback, True


def _ai_tailor_plan(
    *, context: str, language: str, headline: str, first_action: str, milestones: list[str]
) -> tuple[dict, bool]:
    """Tailor advice to all questionnaire answers without creating experience claims."""
    fallback = {
        "headline": headline,
        "first_action": first_action,
        "milestones": milestones,
    }
    if not settings.ai_job_analysis_enabled:
        return fallback, True
    try:
        result = llm.generate_json(
            "Act as a supportive university career mentor. Tailor the starting plan to every "
            "answer in CONTEXT. Return practical, small actions within the stated time budget. "
            "Do not claim the student has completed anything and do not invent awards, projects, "
            "skills, deadlines, or links. Use language code "
            f"{language}.\nCONTEXT:\n{context}\nSAFE DEFAULT PLAN:\n"
            f"Headline: {headline}\nFirst action: {first_action}\nMilestones: {milestones}",
            {
                "type": "object",
                "properties": {
                    "headline": {"type": "string"},
                    "first_action": {"type": "string"},
                    "milestones": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 2,
                        "maxItems": 6,
                    },
                },
                "required": ["headline", "first_action", "milestones"],
            },
            feature="starter_plan_generation",
            prompt_version="starter-plan-v2",
        )
        if not all(
            (
                isinstance(result.get("headline"), str),
                isinstance(result.get("first_action"), str),
                isinstance(result.get("milestones"), list),
                all(isinstance(item, str) and item.strip() for item in result.get("milestones", [])),
            )
        ):
            return fallback, True
        return {
            "headline": result["headline"].strip(),
            "first_action": result["first_action"].strip(),
            "milestones": [item.strip() for item in result["milestones"]],
        }, False
    except ProviderError:
        return fallback, True


def build_starter_plan(
    interest: str,
    resources: list,
    *,
    max_total_hours: int,
    language: str,
    goal: str = "explore",
    experience_level: str = "none",
    preferred_formats: list[str] | None = None,
    experience_level_other: str = "",
    goal_other: str = "",
    preferred_format_other: str = "",
) -> dict:
    # Free-text answers are deliberately included in the bounded AI routing
    # context. They refine the recommendation without being misrepresented as
    # completed experience evidence.
    context = "\n".join(
        part
        for part in (
            interest,
            f"Current stage: {experience_level}; {experience_level_other}",
            f"Desired outcome: {goal}; {goal_other}",
            f"Learning preference: {', '.join(preferred_formats or [])}; {preferred_format_other}",
        )
        if part.strip(" ;")
    )
    focus, used_fallback = _ai_focus(context)
    profile = PROFILES[focus]
    recommendation_goal = "project" if goal in {"portfolio", "competition"} else "skills"
    recommended = recommend_resources(
        profile["skills"],
        resources,
        level="beginner",
        max_total_hours=max_total_hours,
        free_only=True,
        limit=4,
        goal=recommendation_goal,
        language=language,
    )
    # Competition preference promotes concrete public challenge links already
    # present in the curated catalogue; it never fabricates a live deadline.
    formats = set(preferred_formats or [])
    if "competition" in formats or goal == "competition":
        recommended.sort(
            key=lambda item: (
                "competition" not in item.resource.title.casefold()
                and "prize" not in item.resource.title.casefold(),
                -item.match_score,
            )
        )
    labels = {
        "en": {
            "quant": "Quant research starter",
            "business": "Business problem solver",
            "software": "Software builder",
            "ai": "AI project starter",
        },
        "zh-CN": {
            "quant": "量化研究起步",
            "business": "商业问题解决起步",
            "software": "软件开发起步",
            "ai": "AI 项目起步",
        },
        "zh-TW": {
            "quant": "量化研究起步",
            "business": "商業問題解決起步",
            "software": "軟體開發起步",
            "ai": "AI 專案起步",
        },
    }
    milestone = {
        "en": [
            "Explore one official resource",
            "Finish a small public deliverable",
            "Write your own reflection before adding it as an experience draft",
        ],
        "zh-CN": [
            "探索一个官方资源",
            "完成一个小型公开交付物",
            "在创建经历草稿前，先写下你自己的完成反思",
        ],
        "zh-TW": [
            "探索一個官方資源",
            "完成一個小型公開交付物",
            "在建立經歷草稿前，先寫下你自己的完成反思",
        ],
    }
    lang = language if language in labels else "en"
    default_milestones = milestone[lang][:-1] + (
        [
            {
                "en": "Start with one reproducible baseline, not a polished claim.",
                "zh-CN": "先完成一个可复现的 baseline，而不是包装成成果。",
                "zh-TW": "先完成一個可重現的 baseline，而不是包裝成成果。",
            }[lang]
        ]
        if experience_level == "none"
        else []
    ) + [milestone[lang][-1]]
    tailored, tailoring_fallback = _ai_tailor_plan(
        context=f"{context}\nTotal time budget: {max_total_hours} hours",
        language=lang,
        headline=profile["headline"][lang],
        first_action=profile["first"][lang],
        milestones=default_milestones,
    )
    return {
        "focus": focus,
        **tailored,
        "resources": recommended,
        "used_fallback": used_fallback or tailoring_fallback,
        "label": labels[lang][focus],
    }
