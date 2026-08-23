"""Curated learning resources and explainable gap-to-action recommendations."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.resource import LearningResource


RESOURCE_CATALOG = [
    {
        "title": "Kaggle Learn: Python",
        "url": "https://www.kaggle.com/learn/python",
        "provider": "Kaggle",
        "skills": ["Python"],
        "difficulty": "beginner",
        "duration_hours": 5,
        "description": "Interactive Python exercises for data work.",
        "project": {
            "title": "Python data analysis notebook",
            "task": "Clean a public dataset and explain three findings.",
            "estimated_days": 7,
            "deliverables": ["Notebook", "README", "One chart"],
            "completion_criteria": ["Reproducible notebook", "Data cleaning explained"],
            "cv_bullet_template": "Built a reproducible Python data analysis notebook with data cleaning and visualization.",
        },
    },
    {
        "title": "Kaggle Competitions",
        "url": "https://www.kaggle.com/competitions",
        "provider": "Kaggle",
        "skills": ["Machine Learning", "Python", "Pandas"],
        "difficulty": "intermediate",
        "duration_hours": 15,
        "description": "Practice modeling and validation on public datasets.",
        "project": {
            "title": "Competition modeling report",
            "task": "Enter a beginner competition and compare two baselines.",
            "estimated_days": 14,
            "deliverables": ["Notebook", "Validation table", "README"],
            "completion_criteria": ["Train two baselines", "Explain validation choice"],
            "cv_bullet_template": "Compared two machine learning baselines on a public competition dataset with reproducible validation.",
        },
    },
    {
        "title": "Hult Prize Challenge",
        "url": "https://www.hultprize.org/",
        "provider": "Hult Prize",
        "skills": ["Business Analysis", "Communication", "Research"],
        "difficulty": "beginner",
        "duration_hours": 8,
        "description": "A public social-enterprise challenge for practising problem framing, research and pitching.",
        "project": {
            "title": "One-page problem and solution brief",
            "task": "Frame one real problem, cite public evidence and propose a testable first solution.",
            "estimated_days": 7,
            "deliverables": ["One-page brief", "Evidence links", "Three-minute pitch"],
            "completion_criteria": [
                "State the user problem",
                "Cite sources",
                "Name one testable assumption",
            ],
            "cv_bullet_template": "Developed and pitched an evidence-backed solution brief for a real-world problem.",
        },
    },
    {
        "title": "QuantConnect Learning Center",
        "url": "https://www.quantconnect.com/learning",
        "provider": "QuantConnect",
        "skills": ["Quantitative Research", "Python", "Algorithms"],
        "difficulty": "intermediate",
        "duration_hours": 12,
        "description": "Learn research, backtesting and algorithmic trading workflows.",
        "project": {
            "title": "Event study pipeline",
            "task": "Measure post-event returns using public market data and document limitations.",
            "estimated_days": 10,
            "deliverables": ["Research notebook", "Return chart", "Limitations section"],
            "completion_criteria": [
                "No look-ahead bias",
                "Include a baseline",
                "State limitations",
            ],
            "cv_bullet_template": "Built an event-study pipeline with public market data, baseline comparison and documented limitations.",
        },
    },
    {
        "title": "PyTorch Tutorials",
        "url": "https://pytorch.org/tutorials/",
        "provider": "PyTorch",
        "skills": ["PyTorch", "Deep Learning", "Transformer"],
        "difficulty": "intermediate",
        "duration_hours": 10,
        "description": "Official tutorials for model training and deep learning engineering.",
        "project": {
            "title": "Model comparison experiment",
            "task": "Compare two neural architectures and report accuracy, latency and trade-offs.",
            "estimated_days": 10,
            "deliverables": ["Training code", "Experiment table", "README"],
            "completion_criteria": [
                "Fixed evaluation split",
                "Report latency",
                "Reproducible seed",
            ],
            "cv_bullet_template": "Implemented and evaluated two PyTorch model architectures with accuracy and latency comparisons.",
        },
    },
    {
        "title": "fast.ai Practical Deep Learning",
        "url": "https://course.fast.ai/",
        "provider": "fast.ai",
        "skills": ["Deep Learning", "Python", "Machine Learning"],
        "difficulty": "intermediate",
        "duration_hours": 20,
        "description": "Practical deep learning course with end-to-end projects.",
        "project": {
            "title": "End-to-end deep learning demo",
            "task": "Train, evaluate and deploy a small model with an error analysis section.",
            "estimated_days": 14,
            "deliverables": ["Notebook", "Demo", "Error analysis"],
            "completion_criteria": ["Held-out evaluation", "At least five error cases"],
            "cv_bullet_template": "Built an end-to-end deep learning prototype with held-out evaluation and error analysis.",
        },
    },
    {
        "title": "FastAPI Documentation",
        "url": "https://fastapi.tiangolo.com/",
        "provider": "FastAPI",
        "skills": ["FastAPI", "Python"],
        "difficulty": "beginner",
        "duration_hours": 6,
        "description": "Official guide to typed Python APIs and validation.",
        "project": {
            "title": "Deployable ML API",
            "task": "Wrap a model or data pipeline in a documented API with validation.",
            "estimated_days": 7,
            "deliverables": ["API", "OpenAPI docs", "Tests"],
            "completion_criteria": ["Validation errors handled", "At least three API tests"],
            "cv_bullet_template": "Wrapped a data pipeline in a typed FastAPI service with validation and automated API tests.",
        },
    },
    {
        "title": "Hugging Face Learn",
        "url": "https://huggingface.co/learn",
        "provider": "Hugging Face",
        "skills": ["NLP", "Transformer", "Deep Learning"],
        "difficulty": "intermediate",
        "duration_hours": 12,
        "description": "Official courses covering NLP, agents and transformer workflows.",
        "project": {
            "title": "Evidence-grounded text classifier",
            "task": "Train a small classifier, evaluate errors and document dataset limitations.",
            "estimated_days": 12,
            "deliverables": ["Training script", "Evaluation report", "Error analysis"],
            "completion_criteria": [
                "Hold-out evaluation",
                "Five categorized errors",
                "Reproducible setup",
            ],
            "cv_bullet_template": "Built and evaluated an evidence-grounded transformer text classifier with reproducible error analysis.",
        },
    },
    {
        "title": "Docker Get Started",
        "url": "https://docs.docker.com/get-started/",
        "provider": "Docker",
        "skills": ["Docker"],
        "difficulty": "beginner",
        "duration_hours": 4,
        "description": "Official container fundamentals and multi-container application workflow.",
        "project": {
            "title": "Containerized service",
            "task": "Containerize a small API and add a health check with a reproducible README.",
            "estimated_days": 5,
            "deliverables": ["Dockerfile", "Compose file", "README"],
            "completion_criteria": ["Health check passes", "Fresh machine setup documented"],
            "cv_bullet_template": "Containerized an API with Docker, health checks and reproducible local setup documentation.",
        },
    },
    {
        "title": "GitHub Skills",
        "url": "https://skills.github.com/",
        "provider": "GitHub",
        "skills": ["Git"],
        "difficulty": "beginner",
        "duration_hours": 4,
        "description": "Interactive official exercises for GitHub collaboration and delivery workflows.",
        "project": {
            "title": "Collaborative delivery workflow",
            "task": "Use issues, pull requests and a project board to ship a small improvement.",
            "estimated_days": 5,
            "deliverables": ["Pull request", "Issue trail", "Project board"],
            "completion_criteria": ["Review feedback addressed", "Change linked to an issue"],
            "cv_bullet_template": "Delivered a reviewed software improvement using GitHub issues, pull requests and project tracking.",
        },
    },
]

DIFFICULTY_RANK = {"beginner": 0, "intermediate": 1, "advanced": 2}
PLAN_GOALS = {"skills", "project", "interview"}


@dataclass(frozen=True)
class ResourceRecommendation:
    resource: LearningResource

    match_score: int

    matched_skills: list[str]

    recommendation_reason: str


def recommend_resources(
    missing_skills: list[str],
    resources: list[LearningResource],
    *,
    level: str | None = None,
    max_total_hours: int | None = None,
    free_only: bool = False,
    limit: int = 8,
    goal: str = "skills",
    language: str = "zh-CN",
) -> list[ResourceRecommendation]:
    missing = {str(skill).strip().casefold() for skill in missing_skills if str(skill).strip()}

    requested_rank = DIFFICULTY_RANK.get(level) if level else None

    selected_goal = goal if goal in PLAN_GOALS else "skills"

    def reason_for(matched: list[str], resource: LearningResource) -> str:
        focus = {
            "skills": {
                "en": "Skill-building focus",
                "zh-CN": "技能补强重点",
                "zh-TW": "技能補強重點",
            },
            "project": {
                "en": "Portfolio-project focus",
                "zh-CN": "作品集项目重点",
                "zh-TW": "作品集專案重點",
            },
            "interview": {
                "en": "Interview-story focus",
                "zh-CN": "面试项目故事重点",
                "zh-TW": "面試專案故事重點",
            },
        }[selected_goal].get(language, "Skill-building focus")
        if language == "zh-TW":
            return (
                f"補強技能：{', '.join(matched)}；{resource.duration_hours} 小時，"
                f"適合 {resource.difficulty} 程度。{focus}。"
            )
        if language == "zh-CN":
            return (
                f"补强技能：{', '.join(matched)}；{resource.duration_hours} 小时，"
                f"适合 {resource.difficulty} 水平。{focus}。"
            )
        return (
            f"Addresses skill gaps: {', '.join(matched)}; {resource.duration_hours} hours; "
            f"suited to {resource.difficulty}. {focus}."
        )

    def collect(
        *,
        respect_budget: bool,
        respect_level: bool,
        require_skill_match: bool,
    ) -> list[ResourceRecommendation]:
        collected: list[ResourceRecommendation] = []
        for resource in resources:
            if free_only and not resource.free:
                continue
            if (
                respect_budget
                and max_total_hours is not None
                and resource.duration_hours > max_total_hours
            ):
                continue

            resource_rank = DIFFICULTY_RANK.get(
                (resource.difficulty or "beginner").casefold(), 1
            )
            if respect_level and requested_rank is not None and resource_rank > requested_rank:
                continue

            matched = [
                skill
                for skill in (resource.skills or [])
                if str(skill).casefold() in missing
            ]
            if require_skill_match and not matched:
                continue

            skill_points = min(len(matched) / max(len(missing), 1), 1.0) * 70
            level_points = 20 if requested_rank is None or resource_rank == requested_rank else 10
            time_points = (
                10
                if max_total_hours is None
                else max(0, round((1 - resource.duration_hours / max(max_total_hours, 1)) * 10))
            )
            deliverable_count = len((resource.project or {}).get("deliverables", []))
            if selected_goal == "project":
                goal_points = min(12, deliverable_count * 3 + min(resource.duration_hours, 6))
            elif selected_goal == "interview":
                goal_points = max(0, 12 - min(resource.duration_hours, 12)) + min(
                    6, deliverable_count * 2
                )
            else:
                goal_points = 0

            score = max(1, min(100, round(skill_points + level_points + time_points + goal_points)))
            collected.append(
                ResourceRecommendation(resource, score, matched, reason_for(matched, resource))
            )
        return collected

    # First honour every preference. If that set is empty, degrade only the
    # filters (not factual provenance): a student should get a real, reviewed
    # starting resource rather than an unhelpful empty state.
    recommendations = collect(
        respect_budget=True,
        respect_level=True,
        require_skill_match=True,
    )
    if not recommendations:
        recommendations = collect(
            respect_budget=False,
            respect_level=False,
            require_skill_match=True,
        )
    if not recommendations:
        recommendations = collect(
            respect_budget=False,
            respect_level=False,
            require_skill_match=False,
        )
    recommendations.sort(
        key=lambda item: (-item.match_score, item.resource.duration_hours, item.resource.id)
    )

    if max_total_hours is None:
        return recommendations[:limit]

    # A time budget applies to the entire plan, not merely to each card.
    plan: list[ResourceRecommendation] = []
    remaining = max_total_hours
    for recommendation in recommendations:
        duration = recommendation.resource.duration_hours
        if duration <= remaining:
            plan.append(recommendation)
            remaining -= duration
        if len(plan) >= limit:
            break
    if not plan and recommendations:
        # A first trusted resource is more useful than a blank plan when the
        # student's total time budget is smaller than every reviewed resource.
        plan.append(recommendations[0])
    return plan
