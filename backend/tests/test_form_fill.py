from app.schemas.application import DetectedFormField
from app.services.form_fill_service import build_fill_preview


class Question:
    def __init__(self, question_id, text, metadata, result):
        self.id = question_id
        self.question = text
        self.answer = {"metadata": metadata, "result": result}


def test_fill_preview_matches_only_ready_answers_and_blocks_sensitive_fields():
    questions = [
        Question(
            1,
            "Why this role?",
            {"field_key": "why_this_role", "input_type": "textarea"},
            {"text": "Grounded answer", "sources": [{"experience_id": 8}]},
        ),
        Question(
            2,
            "Work authorization",
            {"field_key": "work_authorization", "sensitive": True, "requires_user_input": True},
            {"text": "Yes"},
        ),
    ]

    fields = [
        DetectedFormField(
            field_id="f1", label="Why this role?", input_type="textarea", max_characters=100
        ),
        DetectedFormField(field_id="f2", label="Work authorization", input_type="text"),
        DetectedFormField(field_id="f3", label="Password", input_type="password"),
    ]

    result = build_fill_preview(fields, questions)

    assert result[0].status == "ready" and result[0].source_ids == [8]

    assert result[1].status == "manual_required"

    assert result[2].status == "unsupported"


def test_fill_preview_marks_length_mismatch_and_avoids_duplicate_question_use():
    questions = [
        Question(1, "Why this role?", {}, {"text": "A long grounded answer", "sources": []})
    ]

    fields = [
        DetectedFormField(
            field_id="one", label="Why this role?", input_type="textarea", max_characters=4
        ),
        DetectedFormField(
            field_id="two", label="Why this role?", input_type="textarea", max_characters=100
        ),
        DetectedFormField(field_id="three", label="Unknown field", input_type="text"),
    ]

    result = build_fill_preview(fields, questions)

    assert result[0].status == "needs_review"

    assert result[1].status == "no_match"

    assert result[2].status == "no_match"


def test_fill_preview_endpoint_is_scoped_to_application():
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)

    job = client.post(
        "/api/v1/jobs/analyze",
        json={"title": "Intern", "description": "A role requiring communication skills."},
    ).json()

    application = client.post(
        "/api/v1/applications/questions/detect",
        json={"job_id": job["id"], "raw_text": "Why this role?"},
    ).json()

    response = client.post(
        f"/api/v1/applications/{application['id']}/fill-preview",
        json={"fields": [{"field_id": "x", "label": "Why this role?", "input_type": "textarea"}]},
    )

    assert response.status_code == 200

    assert response.json()["application_id"] == application["id"]

    assert (
        client.post(
            "/api/v1/applications/999999/fill-preview",
            json={"fields": [{"field_id": "x", "label": "Why?"}]},
        ).status_code
        == 404
    )
