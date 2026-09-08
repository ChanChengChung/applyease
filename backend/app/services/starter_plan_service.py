"""Career-exploration plans for students with no CV evidence yet.

The plan deliberately recommends *opportunities to create evidence*, rather
than treating a course enrolment or competition entry as an experience. A
student must still complete work and write their own reflection before an
Experience Bank draft can exist.
"""

from __future__ import annotations

import re

from app.ai.providers import ProviderError, llm
from app.config import settings
from app.services.resource_service import recommend_resources
from app.services.resource_web_search_service import search_and_persist_resources


TRADITIONAL_CHARACTERS = set(
    "學習計畫專實務經歷開發軟體導覽與這個為國門從們會說對還現場電腦網頁點擊選擇確認關聯單業進階應職稱類別問題內線時間後優補強語讀寫輸產變動見長標準資簡轉錄參議證據萬舊來兩無將讓風雲氣東邊遠過連適當靜啟閉談論觀視聽記詞張項種樣構織統設編質釋調測試驗際領域啟閉規則準備選擇替換刪除顯示隱藏變化內容編輯版本歸屬戶帳號登錄碼誠值減換續週復兒級繁體"
)
SIMPLIFIED_CHARACTERS = set(
    "学习计划专实务经历开发软体导览与这个为国门从们会说对还现场电脑网页点击选择确认关联单业进阶应职称类别问题内线时间后优补强语读写输产变动见长标准资简转录参议证据万旧来两无将让风云气东边远过连适当静启闭谈论观视听记词张项种样构织统设编质释调测测试际领域启闭规则准备选择替换删除显示隐藏变化内容编辑版本归属户账号登录码诚值减换续周复儿级繁体"
)


def detect_plan_language(value: str) -> str:
    """Choose starter-plan output language from the student's own intent.

    This is intentionally independent of the browser locale.  Chinese input
    with Traditional markers uses ``zh-TW``; other CJK input uses ``zh-CN``;
    input without CJK characters uses English.
    """
    text = str(value or "").strip()
    if not re.search(r"[\u3400-\u9fff]", text):
        return "en"
    traditional = sum(character in TRADITIONAL_CHARACTERS for character in text)
    simplified = sum(character in SIMPLIFIED_CHARACTERS for character in text)
    return "zh-TW" if traditional > simplified else "zh-CN"


def _plan_output_matches_language(plan: dict, language: str) -> bool:
    """Reject provider output that visibly ignores the requested language."""
    text = " ".join(
        [str(plan.get("headline", "")), str(plan.get("first_action", ""))]
        + [str(item) for item in plan.get("milestones", [])]
    )
    has_cjk = bool(re.search(r"[\u3400-\u9fff]", text))
    if language == "en":
        return not has_cjk
    return has_cjk

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
    "other": {
        "skills": [],
        "headline": {
            "en": "Explore your direction through one small, source-backed piece of work.",
            "zh-CN": "用一个有来源支撑的小成果，逐步探索你的方向。",
            "zh-TW": "用一個有來源支撐的小成果，逐步探索你的方向。",
        },
        "first": {
            "en": "Choose one beginner-friendly question in your field and write down what you want to find out before studying.",
            "zh-CN": "在你的领域选一个适合初学者的问题，先写下你想弄明白什么，再开始学习。",
            "zh-TW": "在你的領域選一個適合初學者的問題，先寫下你想弄明白什麼，再開始學習。",
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
    # Unknown or non-technical interests must not be silently routed to AI.
    return "other"


def _ai_focus(interest: str) -> tuple[str, bool, dict]:
    """Extract an open-ended domain while retaining legacy focus labels."""
    fallback = _keyword_focus(interest)
    if not settings.ai_job_analysis_enabled:
        return fallback, True, {"domain": interest, "subdomains": [], "search_terms": [interest]}
    try:
        result = llm.generate_json(
            "Extract this university student's career exploration intent. Do not give advice and "
            "do not force a technical category. Use focus=ai, quant, software, business only "
            "when clearly applicable; otherwise use focus=other. Preserve the user's subject "
            "(for example mathematics, law, psychology, design, education, media, biology, "
            "languages or public policy) in domain. Return 2-8 search terms that can retrieve "
            "beginner learning resources for that subject.\n"
            f"Interest: {interest}",
            {
                "type": "object",
                "properties": {
                    "focus": {"type": "string", "enum": [*PROFILES]},
                    "domain": {"type": "string"},
                    "subdomains": {"type": "array", "items": {"type": "string"}, "maxItems": 4},
                    "search_terms": {"type": "array", "items": {"type": "string"}, "minItems": 2, "maxItems": 8},
                },
                "required": ["focus", "domain", "search_terms"],
            },
            feature="starter_plan_routing",
            prompt_version="starter-plan-v1",
        )
        focus = result.get("focus")
        if focus not in PROFILES:
            focus = fallback
        routing = {
            "domain": str(result.get("domain") or interest).strip()[:300],
            "subdomains": [str(item).strip() for item in result.get("subdomains", []) if str(item).strip()][:4],
            "search_terms": [str(item).strip() for item in result.get("search_terms", []) if str(item).strip()][:8],
        }
        if not routing["search_terms"]:
            routing["search_terms"] = [interest]
        return focus, False, routing
    except ProviderError:
        return fallback, True, {"domain": interest, "subdomains": [], "search_terms": [interest]}


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
            "Keep the user's subject and career domain central; do not assume Python, coding, "
            "data science, finance, or any other technical path unless the user requested it. "
            "Do not claim the student has completed anything and do not invent awards, projects, "
            "skills, deadlines, or links. Use language code "
            f"{language}.\nCONTEXT:\n{context}\nSAFE DEFAULT PLAN:\n"
            f"Generic safe defaults (use only if they fit the subject):\nHeadline: {headline}\n"
            f"First action: {first_action}\nMilestones: {milestones}",
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
        tailored = {
            "headline": result["headline"].strip(),
            "first_action": result["first_action"].strip(),
            "milestones": [item.strip() for item in result["milestones"]],
        }
        if not _plan_output_matches_language(tailored, language):
            return fallback, True
        return tailored, False
    except ProviderError:
        return fallback, True


def build_starter_plan(
    interest: str,
    resources: list,
    *,
    db=None,
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
    focus, used_fallback, routing = _ai_focus(context)
    profile = PROFILES.get(focus, PROFILES["other"])
    retrieval_query = " ".join(
        [
            interest,
            routing.get("domain", ""),
            " ".join(routing.get("subdomains", [])),
            " ".join(routing.get("search_terms", [])),
            "beginner learning resources course project",
        ]
    ).strip()
    recommendation_goal = "project" if goal in {"portfolio", "competition"} else "skills"
    # Open-web retrieval is the primary path. It is intentionally independent
    # of the old four-profile skill vocabulary, so any discipline can produce
    # relevant resources. The curated catalogue remains a transparent fallback
    # for offline demos or exhausted search providers.
    recommended, web_fallback = (
        search_and_persist_resources(
            db,
            retrieval_query,
            max_total_hours=max_total_hours,
            limit=4,
        )
        if db is not None
        else ([], True)
    )
    if web_fallback:
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
    used_fallback = used_fallback or web_fallback
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
            "other": "Explore your direction",
        },
        "zh-CN": {
            "quant": "量化研究起步",
            "business": "商业问题解决起步",
            "software": "软件开发起步",
            "ai": "AI 项目起步",
            "other": "探索你的方向",
        },
        "zh-TW": {
            "quant": "量化研究起步",
            "business": "商業問題解決起步",
            "software": "軟體開發起步",
            "ai": "AI 專案起步",
            "other": "探索你的方向",
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
                    "en": "Start with one small, repeatable observation or exercise, not a polished claim.",
                    "zh-CN": "先完成一个可重复的小观察或练习，而不是包装成成果。",
                    "zh-TW": "先完成一個可重複的小觀察或練習，而不是包裝成成果。",
            }[lang]
        ]
        if experience_level == "none"
        else []
    ) + [milestone[lang][-1]]
    tailored, tailoring_fallback = _ai_tailor_plan(
        context=(
            f"{context}\nDetected subject domain: {routing.get('domain', interest)}\n"
            f"Suggested exploration terms: {', '.join(routing.get('search_terms', []))}\n"
            f"Total time budget: {max_total_hours} hours"
        ),
        language=lang,
        headline=profile["headline"][lang],
        first_action=profile["first"][lang],
        milestones=default_milestones,
    )
    # Keep the three learning phases explicit so edits can add/remove a step
    # inside a selected phase without re-bucketing existing steps on reload.
    first_cut = max(1, (len(tailored["milestones"]) + 2) // 3)
    second_cut = max(first_cut + 1, (len(tailored["milestones"]) * 2 + 2) // 3)
    milestone_sections = {
        "foundation": tailored["milestones"][:first_cut],
        "practice": tailored["milestones"][first_cut:second_cut],
        "reflection": tailored["milestones"][second_cut:],
    }
    return {
        "focus": focus,
        **tailored,
        "milestone_sections": milestone_sections,
        "resources": recommended,
        "used_fallback": used_fallback or tailoring_fallback,
        "label": labels[lang][focus],
    }
