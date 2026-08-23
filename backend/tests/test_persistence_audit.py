"""Regression coverage for user-facing state that must survive a page refresh."""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_saved_application_form_and_answers_can_be_restored():
    job = client.post(
        "/api/v1/jobs/analyze",
        json={
            "title": "AI Intern",
            "description": "Build and evaluate Python systems for machine learning.",
        },
    ).json()
    created = client.post(
        "/api/v1/applications/questions/detect",
        json={
            "job_id": job["id"],
            "raw_text": "Why are you interested in this role? Maximum 300 characters",
        },
    )
    assert created.status_code == 200, created.text
    application = created.json()
    question = application["questions"][0]

    saved = client.patch(
        f"/api/v1/applications/{application['id']}/questions/{question['id']}/answer",
        json={"answer": "I want to build careful, evidence-grounded AI systems."},
    )
    assert saved.status_code == 200, saved.text

    restored = client.get(f"/api/v1/applications/latest?job_id={job['id']}")
    assert restored.status_code == 200
    assert restored.json()["id"] == application["id"]
    answers = client.get(f"/api/v1/applications/{application['id']}/answers")
    assert answers.status_code == 200
    assert answers.json()[0]["answer"] == "I want to build careful, evidence-grounded AI systems."


def test_advisor_history_is_durable_and_user_can_clear_it(monkeypatch):
    from app.api.v1 import advisor as advisor_api

    monkeypatch.setattr(advisor_api, "reserve_ai_generation", lambda _db: None)
    monkeypatch.setattr(
        advisor_api,
        "answer_advisor",
        lambda *_args, **_kwargs: {
            "answer": "Start with your confirmed evidence.",
            "sources": ["Experience: AI project @ HKU"],
            "suggested_prompts": ["Which role should I prioritise?"],
            "used_fallback": False,
        },
    )

    sent = client.post(
        "/api/v1/advisor/chat",
        json={"message": "What should I improve?", "language": "en", "history": []},
    )
    assert sent.status_code == 200, sent.text
    history = client.get("/api/v1/advisor/history")
    assert history.status_code == 200
    assert [item["role"] for item in history.json()][-2:] == ["user", "assistant"]
    assert history.json()[-1]["content"] == "Start with your confirmed evidence."

    assert client.delete("/api/v1/advisor/history").status_code == 204
    assert client.get("/api/v1/advisor/history").json() == []


def test_advisor_passes_view_context_to_the_grounded_service(monkeypatch):
    from app.api.v1 import advisor as advisor_api

    captured = {}
    monkeypatch.setattr(advisor_api, "reserve_ai_generation", lambda _db: None)

    def fake_answer(*args):
        captured["active_page"] = args[5]
        captured["active_job_id"] = args[6]
        return {
            "answer": "Context-aware guidance",
            "sources": [],
            "suggested_prompts": [],
            "used_fallback": True,
        }

    monkeypatch.setattr(advisor_api, "answer_advisor", fake_answer)
    response = client.post(
        "/api/v1/advisor/chat",
        json={
            "message": "What should I do next?",
            "language": "zh-TW",
            "active_page": "builder",
            "active_job_id": 42,
        },
    )
    assert response.status_code == 200, response.text
    assert captured == {"active_page": "builder", "active_job_id": 42}
