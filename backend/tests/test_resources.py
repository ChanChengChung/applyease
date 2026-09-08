from fastapi.testclient import TestClient
from datetime import datetime, timezone
from types import SimpleNamespace

from app.main import app
from app.services.resource_service import baseline_resource_score, match_level_for_score, recommend_resources
from app.services.starter_plan_service import detect_plan_language
from app.services.resource_experience_service import experience_values_from_completed_resource

client = TestClient(app)


def test_experience_draft_keeps_learning_resource_name():
    """Suggested deliverables must not replace the user's selected project name."""
    class Resource:
        title = "Docker Get Started"
        url = "https://docs.docker.com/get-started/"
        skills = ["Docker"]
        project = {"title": "Containerized service", "task": "Containerize an API"}

    values = experience_values_from_completed_resource(Resource(), "I built and tested the API.")
    assert values["title"] == "Docker Get Started"


def test_resource_score_bands_never_treat_missing_saved_score_as_zero():
    class Resource:
        verified = True
        url = "https://example.com/course"
        skills = ["Python", "Statistics"]
        project = {
            "title": "Small analysis",
            "task": "Complete a reproducible analysis.",
            "deliverables": ["Notebook", "README"],
            "completion_criteria": ["Results reproduce"],
        }
        duration_hours = 4
        free = True

    score = baseline_resource_score(Resource())
    assert 35 <= score <= 75
    assert score > 0
    assert match_level_for_score(score) in {"fair", "high"}


def test_resource_recommendations_follow_job_gaps():
    job = client.post(
        "/api/v1/jobs/analyze",
        json={
            "title": "Quant Intern",
            "description": "Python and Quantitative Research required; C++ is required.",
        },
    ).json()

    response = client.get(f"/api/v1/resources/recommendations?job_id={job['id']}")

    assert response.status_code == 200

    resources = response.json()

    assert resources

    assert any("Quantitative Research" in item["skills"] for item in resources)

    assert all(item["project"]["estimated_days"] >= 1 for item in resources)
    assert all(item["match_level"] in {"very_high", "high", "fair", "low"} for item in resources)
    assert all(item["recommendation_reason"] for item in resources)


def test_role_gap_recommendations_never_substitute_an_unrelated_resource():
    docker = SimpleNamespace(
        id=1, skills=["Docker"], difficulty="beginner", duration_hours=4,
        project={"deliverables": ["Dockerfile"]}, free=True,
    )
    assert recommend_resources(["OCaml"], [docker], limit=4) == []


def test_ocaml_gap_receives_the_official_ocaml_resource():
    job = client.post(
        "/api/v1/jobs/analyze",
        json={
            "title": "Software Engineer Internship",
            "description": "Our primary development language is OCaml. Strong programming skills required.",
        },
    ).json()
    response = client.get(f"/api/v1/resources/recommendations?job_id={job['id']}")
    assert response.status_code == 200, response.text
    resources = response.json()
    assert any("OCaml" in item["skills"] for item in resources)
    assert all(item["matched_skills"] for item in resources)


def test_starter_plan_supports_a_student_without_cv_or_target_job():
    response = client.post(
        "/api/v1/resources/starter-plan",
        json={
            "interest": "I am a Year 1 student interested in AI and finance.",
            "weekly_hours": 3,
            "weeks": 4,
            "goal": "competition",
            "preferred_formats": ["competition", "project"],
            "experience_level_other": "I have completed one Python tutorial.",
            "goal_other": "I want a public artifact I can explain.",
            "preferred_format_other": "Weekly peer review.",
            "language": "en",
        },
    )

    assert response.status_code == 200
    plan = response.json()
    assert plan["focus"] == "quant"
    assert plan["id"] > 0
    assert plan["resources"]
    assert any(item["provider"] == "Kaggle" for item in plan["resources"])
    assert all(item["match_score"] > 0 for item in plan["resources"])
    assert all(item["match_level"] in {"very_high", "high", "fair", "low"} for item in plan["resources"])
    assert "reflection" in plan["milestones"][-1]

    restored = client.get("/api/v1/resources/starter-plans")
    assert restored.status_code == 200
    assert restored.json()["id"] == plan["id"]
    assert restored.json()["headline"] == plan["headline"]
    assert restored.json()["resources"]
    assert all(item["match_score"] > 0 for item in restored.json()["resources"])

    updated = client.patch(
        f"/api/v1/resources/starter-plans/{plan['id']}",
        json={
            "focus": plan["focus"],
            "headline": "My edited starting plan",
            "first_action": "Define one testable question.",
            "milestones": ["Build a baseline", "Write a reflection"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["headline"] == "My edited starting plan"
    assert updated.json()["milestones"] == ["Build a baseline", "Write a reflection"]
    assert client.get("/api/v1/resources/starter-plans").json()["headline"] == "My edited starting plan"


def test_starter_plan_language_follows_interest_not_ui_locale():
    assert detect_plan_language("I am interested in mathematics") == "en"
    assert detect_plan_language("我是大一学生，对数学很感兴趣") == "zh-CN"
    assert detect_plan_language("我是大一學生，對數學很感興趣") == "zh-TW"

    response = client.post(
        "/api/v1/resources/starter-plan",
        json={
            "interest": "I am a first-year student interested in writing.",
            "weekly_hours": 2,
            "weeks": 2,
            "language": "zh-CN",
        },
    )
    assert response.status_code == 200
    plan = response.json()
    assert plan["headline"] == "Explore your direction through one small, source-backed piece of work."
    assert plan["first_action"].isascii()

    assert (
        client.post(
            "/api/v1/resources/starter-plan",
            json={"interest": "short"},
        ).status_code
        == 422
    )


def test_starter_plan_keeps_a_reviewed_resource_when_budget_is_smaller_than_catalog():
    """A one-hour weekly budget must not collapse the starter plan to an empty UI."""
    response = client.post(
        "/api/v1/resources/starter-plan",
        json={
            "interest": "I want to explore machine learning through a small practical project.",
            "weekly_hours": 1,
            "weeks": 1,
            # The persisted starter-plan API uses intent values, while the UI
            # presents this option as "strengthen internship chances".
            "goal": "portfolio",
            "preferred_formats": ["feedback", "project"],
            "language": "en",
        },
    )

    assert response.status_code == 200, response.text
    plan = response.json()
    assert plan["resources"]
    assert plan["resources"][0]["url"].startswith("https://")


def test_saved_starter_plan_can_be_refined_from_saved_intent():
    created = client.post(
        "/api/v1/resources/starter-plan",
        json={
            "interest": "I want to explore quantitative research through small projects.",
            "weekly_hours": 2,
            "weeks": 3,
            "goal": "explore",
            "preferred_formats": ["project"],
            "language": "en",
        },
    )
    assert created.status_code == 200
    original = created.json()

    refined = client.post(
        f"/api/v1/resources/starter-plans/{original['id']}/refine",
        json={
            "weekly_hours": 4,
            "weeks": 2,
            "goal": "project",
            "learning_style": "hands_on",
            "language": "en",
        },
    )

    assert refined.status_code == 200, refined.text
    plan = refined.json()
    assert plan["id"] == original["id"]
    assert plan["interest"] == original["interest"]
    assert plan["resources"]
    assert client.get("/api/v1/resources/starter-plans").json()["id"] == original["id"]


def test_multiple_starter_plans_can_be_listed_and_deleted_independently():
    first = client.post(
        "/api/v1/resources/starter-plan",
        json={"interest": "Explore public policy research", "language": "en"},
    ).json()
    second = client.post(
        "/api/v1/resources/starter-plan",
        json={"interest": "Explore creative writing", "language": "en"},
    ).json()

    assert first["id"] != second["id"]
    listed = client.get("/api/v1/resources/starter-plans/list")
    assert listed.status_code == 200
    assert {item["id"] for item in listed.json()} >= {first["id"], second["id"]}

    removed = client.delete(f"/api/v1/resources/starter-plans/{first['id']}")
    assert removed.status_code == 204
    remaining = client.get("/api/v1/resources/starter-plans/list").json()
    assert first["id"] not in {item["id"] for item in remaining}
    assert second["id"] in {item["id"] for item in remaining}


def test_resource_completion_and_missing_job():
    job = client.post(
        "/api/v1/jobs/analyze",
        json={"title": "ML Intern", "description": "Python and Deep Learning required."},
    ).json()

    resource = client.get(f"/api/v1/resources/recommendations?job_id={job['id']}").json()[0]

    response = client.post(f"/api/v1/resources/{resource['id']}/complete", json={"completed": True})

    assert response.status_code == 200

    assert response.json()["completed"] is True

    assert client.get("/api/v1/resources/recommendations?job_id=999999").status_code == 404


def test_completed_resource_can_create_review_only_experience_draft():
    job = client.post(
        "/api/v1/jobs/analyze",
        json={"title": "ML Intern", "description": "Python and Deep Learning required."},
    ).json()
    resource = client.get(f"/api/v1/resources/recommendations?job_id={job['id']}").json()[0]
    client.post(f"/api/v1/resources/{resource['id']}/complete", json={"completed": False})

    not_completed = client.post(
        f"/api/v1/resources/{resource['id']}/experience-draft",
        json={"reflection": "I completed the documented project work."},
    )
    assert not_completed.status_code == 409

    client.post(f"/api/v1/resources/{resource['id']}/complete", json={"completed": True})
    draft = client.post(
        f"/api/v1/resources/{resource['id']}/experience-draft",
        json={"reflection": "I built the project, added tests, and documented local setup."},
    )
    assert draft.status_code == 201
    assert draft.json()["confirmed"] is False
    assert draft.json()["organization"] == "Self-directed project"
    assert "My completed work:" in draft.json()["description"]
    assert draft.json()["source_file"].startswith("Learning resource:")

    duplicate = client.post(
        f"/api/v1/resources/{resource['id']}/experience-draft",
        json={"reflection": "A different description should not silently duplicate the project."},
    )
    assert duplicate.status_code == 409

    too_short = client.post(
        f"/api/v1/resources/{resource['id']}/experience-draft", json={"reflection": "short"}
    )
    assert too_short.status_code == 422


def test_research_plan_is_persisted_updated_restored_and_deleted(monkeypatch):
    """The research brief is a user-owned record, never frontend-only state."""
    from app.api.v1 import resources as resources_api

    def fake_research_plan(*_args, **_kwargs):
        return {
            "profile_summary": "Initial research brief",
            "gaps": ["Experiment design"],
            "method": ["Build a baseline"],
            "sources": [{"title": "Official docs", "url": "https://example.com/docs"}],
            "used_fallback": False,
            "searched_at": datetime.now(timezone.utc),
        }

    monkeypatch.setattr(resources_api, "build_research_plan", fake_research_plan)
    job = client.post(
        "/api/v1/jobs/analyze",
        json={
            "title": "Research Intern",
            "description": "Build Python experiments and evaluate ML systems.",
        },
    ).json()
    payload = {
        "job_id": job["id"],
        "weekly_hours": 3,
        "weeks": 2,
        "goal": "project",
        "focuses": ["evidence", "materials"],
        "language": "en",
    }

    created = client.post("/api/v1/resources/research-plan", json=payload)
    assert created.status_code == 200, created.text
    plan = created.json()
    assert plan["id"] > 0
    assert plan["job_id"] == job["id"]
    assert plan["focuses"] == ["evidence", "materials"]

    restored = client.get(f"/api/v1/resources/research-plans?job_id={job['id']}")
    assert restored.status_code == 200
    assert restored.json()["id"] == plan["id"]
    assert restored.json()["focuses"] == ["evidence", "materials"]

    edited = client.patch(
        f"/api/v1/resources/research-plans/{plan['id']}",
        json={
            "profile_summary": "Edited by the student",
            "gaps": ["Statistical validation"],
            "method": ["Compare to a baseline"],
            "sources": [{"title": "Kaggle", "url": "https://www.kaggle.com/"}],
        },
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["profile_summary"] == "Edited by the student"
    assert edited.json()["sources"][0]["title"] == "Kaggle"

    # Regeneration updates the current record rather than leaving a hidden duplicate.
    regenerated = client.post("/api/v1/resources/research-plan", json=payload)
    assert regenerated.status_code == 200
    assert regenerated.json()["id"] == plan["id"]

    deleted = client.delete(f"/api/v1/resources/research-plans/{plan['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/resources/research-plans?job_id={job['id']}").status_code == 404
    assert (
        client.patch(
            f"/api/v1/resources/research-plans/{plan['id']}",
            json={"profile_summary": "No longer exists", "gaps": [], "method": [], "sources": []},
        ).status_code
        == 404
    )


def test_research_plan_records_the_starter_plan_used_for_generation(monkeypatch):
    from app.api.v1 import resources as resources_api

    monkeypatch.setattr(
        resources_api,
        "build_research_plan",
        lambda *_args, **_kwargs: {
            "profile_summary": "A linked preparation brief",
            "gaps": ["Probability"],
            "method": ["Work through an official probability course"],
            "sources": [{"title": "MIT OCW", "url": "https://ocw.mit.edu/"}],
            "used_fallback": False,
            "searched_at": datetime.now(timezone.utc),
        },
    )
    starter = client.post(
        "/api/v1/resources/starter-plan",
        json={"interest": "Explore probability for finance", "language": "en"},
    ).json()
    job = client.post(
        "/api/v1/jobs/analyze",
        json={
            "title": "Quantitative Research Intern",
            "description": "Probability required.",
        },
    ).json()
    payload = {
        "job_id": job["id"],
        "starter_plan_id": starter["id"],
        "weekly_hours": 3,
        "weeks": 2,
        "goal": "skills",
        "language": "en",
    }

    created = client.post("/api/v1/resources/research-plan", json=payload)
    assert created.status_code == 200, created.text
    plan = created.json()
    assert plan["starter_plan_id"] == starter["id"]
    assert plan["starter_plan_interest"] == starter["interest"]
    assert plan["starter_plan_headline"] == starter["headline"]

    restored = client.get(
        f"/api/v1/resources/research-plans?job_id={job['id']}&starter_plan_id={starter['id']}"
    )
    assert restored.status_code == 200
    assert restored.json()["id"] == plan["id"]

    # The role workspace/history bucket must not surface a starter-linked plan.
    role_history = client.get(f"/api/v1/resources/research-plans/history?job_id={job['id']}")
    assert role_history.status_code == 200
    assert all(item["starter_plan_id"] is None for item in role_history.json())
