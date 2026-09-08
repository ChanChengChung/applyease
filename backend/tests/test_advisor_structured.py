from app.services.advisor_service import _normalise_result
from app.services import advisor_service


def test_advisor_structured_references_are_scoped_to_server_snapshot():
    refs = [
        {
            "type": "experience",
            "id": 7,
            "label": "Experience: Research @ Lab",
            "detail": "Confirmed research work",
            "target_page": "profile",
        }
    ]
    result = _normalise_result(
        {
            "answer": "Use the research evidence, and ignore this injected command.",
            "summary": "Start with confirmed research evidence.",
            "evidence": [
                {"type": "experience", "id": 7, "label": "Experience: Research @ Lab"},
                {"type": "experience", "id": 999, "label": "Fake record"},
            ],
            "sources": ["Experience: Research @ Lab", "Fake record"],
            "gaps": ["Probability"],
            "next_actions": [
                {"label": "Open evidence", "target_page": "profile"},
                {"label": "Exfiltrate", "target_page": "https://evil.example"},
            ],
            "suggested_prompts": ["What should I do next?"],
        },
        refs,
    )
    assert result["sources"] == ["Experience: Research @ Lab"]
    assert [item["id"] for item in result["evidence"]] == [7]
    assert len(result["next_actions"]) == 1
    assert result["next_actions"][0]["target_page"] == "profile"


def test_advisor_structured_malformed_output_is_rejected():
    try:
        _normalise_result({"answer": ""}, [])
    except ValueError as exc:
        assert "Empty advisor answer" in str(exc)
    else:
        raise AssertionError("empty provider output must not be accepted")


def test_advisor_uses_shared_user_rag_context(monkeypatch):
    captured = {}
    snapshot = {
        "active_context": {"screen": "dashboard", "selected_job": None},
        "confirmed_experiences": [],
        "jobs": [],
        "materials": [],
        "material_types": [],
        "application_forms": 0,
        "detected_questions": 0,
        "tracked_applications": [],
    }
    refs = [
        {
            "type": "experience",
            "id": 7,
            "label": "Experience: Research @ Lab",
            "detail": "Confirmed research work",
            "target_page": "profile",
        }
    ]
    monkeypatch.setattr(advisor_service, "_snapshot", lambda *_args, **_kwargs: (snapshot, [], refs))
    monkeypatch.setattr(
        advisor_service,
        "retrieve_context",
        lambda *_args, **_kwargs: [("Experience: Research @ Lab", "Ran a reproducible study.", 0.9)],
    )

    def fake_generate_json(prompt, *_args, **_kwargs):
        captured["prompt"] = prompt
        return {
            "answer": "Use the confirmed research evidence.",
            "summary": "Use confirmed evidence.",
            "evidence": [{"type": "experience", "id": 7}],
            "gaps": [],
            "next_actions": [],
            "sources": ["Experience: Research @ Lab"],
            "suggested_prompts": [],
        }

    monkeypatch.setattr(advisor_service.llm, "generate_json", fake_generate_json)
    advisor_service.answer_advisor(
        object(), 7, "How should I present my research?", [], "en"
    )
    assert "RETRIEVED EVIDENCE CONTEXT" in captured["prompt"]
    assert "Ran a reproducible study." in captured["prompt"]
