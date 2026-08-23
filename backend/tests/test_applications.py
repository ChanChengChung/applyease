from fastapi.testclient import TestClient
from app.main import app
from app.ai.providers import llm

client = TestClient(app)


def test_detect_questions_classifies_and_reads_limit():
    job = client.post(
        "/api/v1/jobs/analyze",
        json={"title": "Intern", "description": "Python internship role with research."},
    ).json()

    response = client.post(
        "/api/v1/applications/questions/detect",
        json={
            "job_id": job["id"],
            "raw_text": "Why are you interested in this role? (Maximum 150 characters)\nDescribe a challenging project. (Optional)",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert len(data["questions"]) == 2

    assert data["questions"][0]["question_type"] == "motivation"

    assert data["questions"][0]["max_characters"] == 150

    assert data["questions"][1]["required"] is False


def test_generate_question_answer_and_missing_questions():
    job = client.post(
        "/api/v1/jobs/analyze",
        json={"title": "Intern", "description": "Python internship role with research."},
    ).json()

    application = client.post(
        "/api/v1/applications/questions/detect",
        json={"job_id": job["id"], "raw_text": "Why this role?"},
    ).json()

    question = application["questions"][0]

    response = client.post(
        f"/api/v1/applications/{application['id']}/questions/{question['id']}/answer"
    )

    assert response.status_code == 200

    assert response.json()["character_count"] <= question["max_characters"]

    assert (
        client.post(
            "/api/v1/applications/questions/detect",
            json={"job_id": job["id"], "raw_text": "This text has no question mark"},
        ).status_code
        == 400
    )

    assert (
        client.post(f"/api/v1/applications/999999/questions/{question['id']}/answer").status_code
        == 404
    )


def test_answer_templates_are_recommended_persisted_and_respect_form_limits():
    job = client.post(
        "/api/v1/jobs/analyze",
        json={"title": "Intern", "description": "A role requiring research and teamwork."},
    ).json()
    application = client.post(
        "/api/v1/applications/questions/detect",
        json={
            "job_id": job["id"],
            "raw_text": "Describe a challenging project. Maximum 300 characters\nWhy this role? Maximum 50 characters",
        },
    ).json()
    behavioural, short = application["questions"]

    star = client.post(
        f"/api/v1/applications/{application['id']}/questions/{behavioural['id']}/answer",
        json={"template": "star"},
    )
    assert star.status_code == 200
    assert star.json()["template"] == "star"
    assert star.json()["recommended_template"] == "star"
    assert star.json()["character_count"] <= 300

    auto = client.post(
        f"/api/v1/applications/{application['id']}/questions/{short['id']}/answer",
        json={"template": "auto"},
    )
    assert auto.status_code == 200
    assert auto.json()["template"] == "concise_50"
    assert auto.json()["recommended_template"] == "concise_50"
    assert auto.json()["character_count"] <= 50

    retrieved = client.get(f"/api/v1/applications/{application['id']}")
    assert retrieved.status_code == 200
    assert retrieved.json()["questions"][0]["answer"]["metadata"]["answer_template"] == "star"


def test_answer_template_validation_and_batch_template_selection():
    job = client.post(
        "/api/v1/jobs/analyze",
        json={"title": "Intern", "description": "A valid internship description."},
    ).json()
    application = client.post(
        "/api/v1/applications/questions/detect",
        json={"job_id": job["id"], "raw_text": "Why this role?"},
    ).json()
    question = application["questions"][0]

    invalid = client.post(
        f"/api/v1/applications/{application['id']}/questions/{question['id']}/answer",
        json={"template": "unknown"},
    )
    assert invalid.status_code == 422

    generated = client.post(
        f"/api/v1/applications/{application['id']}/answers/generate-all",
        json={"regenerate": True, "template": "standard_150"},
    )
    assert generated.status_code == 200
    assert generated.json()[0]["template"] == "standard_150"


def test_batch_generation_skips_sensitive_fields_and_saves_manual_answers():
    job = client.post(
        "/api/v1/jobs/analyze",
        json={"title": "Intern", "description": "A software internship requiring teamwork."},
    ).json()

    application = client.post(
        "/api/v1/applications/questions/detect",
        json={
            "job_id": job["id"],
            "raw_text": "Work authorization *\nWhy this role? Maximum 100 words",
        },
    ).json()

    results = client.post(
        f"/api/v1/applications/{application['id']}/answers/generate-all", json={"regenerate": False}
    )

    assert results.status_code == 200

    statuses = {item["question"]: item["status"] for item in results.json()}

    assert statuses["Work authorization *"] == "manual_required"

    assert statuses["Why this role? Maximum 100 words"] == "generated"

    manual_question = application["questions"][0]

    saved = client.patch(
        f"/api/v1/applications/{application['id']}/questions/{manual_question['id']}/answer",
        json={"answer": "User confirmed response"},
    )

    assert saved.status_code == 200

    assert saved.json()["status"] == "user_provided"

    assert saved.json()["fact_check_passed"] is False


def test_answer_edit_enforces_character_and_word_limits():
    job = client.post(
        "/api/v1/jobs/analyze",
        json={"title": "Intern", "description": "A role requiring communication skills."},
    ).json()

    application = client.post(
        "/api/v1/applications/questions/detect",
        json={
            "job_id": job["id"],
            "raw_text": "Why this role? Maximum 3 words",
        },
    ).json()

    question = application["questions"][0]

    too_many_words = client.patch(
        f"/api/v1/applications/{application['id']}/questions/{question['id']}/answer",
        json={"answer": "one two three four"},
    )

    assert too_many_words.status_code == 422

    accepted = client.patch(
        f"/api/v1/applications/{application['id']}/questions/{question['id']}/answer",
        json={"answer": "one two three"},
    )

    assert accepted.status_code == 200

    assert accepted.json()["word_count"] == 3


def test_question_from_another_application_cannot_be_answered():
    job = client.post(
        "/api/v1/jobs/analyze",
        json={"title": "Intern", "description": "A valid internship description."},
    ).json()

    first = client.post(
        "/api/v1/applications/questions/detect",
        json={"job_id": job["id"], "raw_text": "Why this role?"},
    ).json()

    second = client.post(
        "/api/v1/applications/questions/detect",
        json={"job_id": job["id"], "raw_text": "Describe a project?"},
    ).json()

    response = client.post(
        f"/api/v1/applications/{first['id']}/questions/{second['questions'][0]['id']}/answer"
    )

    assert response.status_code == 404


def test_screenshot_ocr_requires_consent_valid_type_and_size(monkeypatch):
    job = client.post(
        "/api/v1/jobs/analyze",
        json={"title": "Intern", "description": "A valid internship description."},
    ).json()

    monkeypatch.setattr("app.api.v1.applications.settings.screenshot_ocr_enabled", True)

    png = b"\x89PNG\r\n\x1a\n" + b"form-bytes"

    no_consent = client.post(
        "/api/v1/applications/questions/detect-screenshot",
        data={"job_id": str(job["id"]), "consent_to_cloud_ocr": "false"},
        files={"file": ("form.png", png, "image/png")},
    )

    assert no_consent.status_code == 400

    monkeypatch.setattr(
        llm.providers["gemini"], "extract_image_text", lambda *_: "Full name *\nWhy this role?"
    )

    success = client.post(
        "/api/v1/applications/questions/detect-screenshot",
        data={"job_id": str(job["id"]), "consent_to_cloud_ocr": "true"},
        files={"file": ("form.png", png, "image/png")},
    )

    assert success.status_code == 200

    assert len(success.json()["questions"]) == 2

    spoofed = client.post(
        "/api/v1/applications/questions/detect-screenshot",
        data={"job_id": str(job["id"]), "consent_to_cloud_ocr": "true"},
        files={"file": ("form.png", b"not-png", "image/png")},
    )

    assert spoofed.status_code == 400
