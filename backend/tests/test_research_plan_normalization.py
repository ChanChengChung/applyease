from app.models.job import Job
from app.services.research_plan_service import (
    _bocha_learning_sources,
    _clean_items,
    _profile_summary,
)


def test_grounded_plan_objects_are_rendered_as_plain_human_text():
    gaps = _clean_items(
        [
            {
                "capability_gap": "OCaml / functional programming",
                "explanation": "Learn the core syntax and immutable data patterns.",
            }
        ],
        purpose="gap",
        limit=300,
        max_items=5,
    )
    method = _clean_items(
        [
            {
                "action": "Practice probability interviews",
                "description": "Solve conditional expectation questions for two hours.",
            }
        ],
        purpose="method",
        limit=500,
        max_items=5,
    )

    assert gaps == [
        "OCaml / functional programming — Learn the core syntax and immutable data patterns."
    ]
    assert method == [
        "Practice probability interviews — Solve conditional expectation questions for two hours."
    ]
    assert "{'" not in gaps[0]


def test_profile_summary_is_concise_even_when_model_is_verbose():
    summary = _profile_summary(
        "First relevant sentence. Second relevant sentence. Third sentence must not display."
    )
    assert summary == "First relevant sentence. Second relevant sentence."


def test_bocha_learning_search_returns_only_safe_https_source_metadata(monkeypatch):
    class Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": {
                    "webPages": {
                        "value": [
                            {
                                "name": "Official Python documentation",
                                "url": "https://docs.python.org/3/",
                                "snippet": "The official Python documentation.",
                            },
                            {
                                "name": "Unsafe source",
                                "url": "http://example.com/",
                                "snippet": "Must be discarded.",
                            },
                        ]
                    }
                }
            }

    monkeypatch.setattr(
        "app.services.research_plan_service.settings.bocha_search_api_key", "test-key"
    )
    monkeypatch.setattr(
        "app.services.research_plan_service.httpx.post", lambda *_args, **_kwargs: Response()
    )
    job = Job(title="Software Engineering Intern", required_skills=["Python"])

    assert _bocha_learning_sources(job) == [
        {
            "title": "Official Python documentation",
            "url": "https://docs.python.org/3/",
            "snippet": "The official Python documentation.",
        }
    ]
