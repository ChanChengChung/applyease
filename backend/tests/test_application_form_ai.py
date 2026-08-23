from app.ai.application_form_analyzer import analyze_form_ai
from app.services.application_question_service import detect_questions


def test_rule_detection_handles_fields_duplicates_sensitive_policy_and_word_limits():
    fields = detect_questions(
        "Full name *\nWork authorization *\nWhy this role? Maximum 75 words\nWhy this role? Maximum 75 words"
    )

    assert len(fields) == 3

    name = fields[0]["answer"]["metadata"]

    authorization = fields[1]["answer"]["metadata"]

    narrative = fields[2]

    assert name["requires_user_input"] is True

    assert authorization["sensitive"] is True and authorization["requires_user_input"] is True

    assert narrative["answer"]["metadata"]["max_words"] == 75

    assert narrative["max_characters"] == 600


def test_ai_detection_enforces_server_sensitive_policy_and_sanitizes_limits(monkeypatch):
    monkeypatch.setattr(
        "app.ai.application_form_analyzer.llm.generate_json",
        lambda *_: {
            "fields": [
                {
                    "question": "Visa status",
                    "question_type": "general",
                    "required": True,
                    "max_length": -20,
                    "limit_unit": "characters",
                    "field_key": "visa status<script>",
                    "input_type": "text",
                    "sensitive": False,
                    "requires_user_input": False,
                },
                {
                    "question": "Why this role?",
                    "question_type": "unknown-type",
                    "required": False,
                    "max_length": 120,
                    "limit_unit": "words",
                    "field_key": "motivation",
                    "input_type": "textarea",
                    "sensitive": False,
                    "requires_user_input": False,
                },
            ]
        },
    )

    fields = analyze_form_ai("A sufficiently long application form text")

    assert fields[0]["answer"]["metadata"]["sensitive"] is True

    assert fields[0]["answer"]["metadata"]["requires_user_input"] is True

    assert "<" not in fields[0]["answer"]["metadata"]["field_key"]

    assert fields[0]["max_characters"] == 20

    assert fields[1]["question_type"] == "motivation"

    assert fields[1]["answer"]["metadata"]["max_words"] == 120
