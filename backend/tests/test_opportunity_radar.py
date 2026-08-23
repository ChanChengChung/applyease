import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.ai.providers import RateLimitExceeded
from app.services import opportunity_service


client = TestClient(app)


def _token() -> str:
    response = client.post(
        "/api/v1/auth/register",
        headers={"X-ApplyEase-Client": "browser-extension"},
        json={
            "email": f"radar-{uuid.uuid4().hex[:12]}@example.com",
            "password": "secure-pass-123",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _confirmed_experience(token: str) -> int:
    response = client.post(
        "/api/v1/experiences",
        headers=_headers(token),
        json={
            "title": "Evidence-first Python Project",
            "organization": "HKU",
            "description": "Built and tested a Python data pipeline with clear documentation.",
            "skills": ["Python", "Data Analysis"],
            "achievements": [],
            "source_file": "portfolio",
            "confirmed": True,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_opportunity_radar_requires_consent_and_persists_only_verified_web_results(monkeypatch):
    monkeypatch.setattr(opportunity_service.settings, "bocha_search_api_key", "")
    token = _token()
    experience_id = _confirmed_experience(token)

    rejected = client.post(
        "/api/v1/opportunities/search",
        headers=_headers(token),
        json={"career_goal": "quantitative technology internship", "consent_to_web_search": False},
    )
    assert rejected.status_code == 400

    monkeypatch.setattr(
        opportunity_service,
        "_brave_ats_search",
        lambda *_args, **_kwargs: {
            "opportunities": [
                {
                    "company": "Example Capital",
                    "title": "Quantitative Technology Intern",
                    "location": "Hong Kong",
                    "employment_type": "Internship",
                    "why_match": "Your confirmed Python project is directly relevant.",
                    "evidence_used": ["Evidence-first Python Project · Python"],
                    "gaps_to_address": ["Demonstrate probability knowledge"],
                    "next_step": "Review the official description.",
                    "source_title": "Quantitative Technology Intern | Example Capital Careers",
                    "source_url": "https://jobs.lever.co/example-capital/quant-tech-intern",
                    "source_search_mode": "ai",
                }
            ],
            "sources": [
                {
                    "title": "Quantitative Technology Intern | Example Capital Careers",
                    "url": "https://jobs.lever.co/example-capital/quant-tech-intern",
                }
            ],
            "used_fallback": False,
            "unavailable_reason": "",
        },
    )
    response = client.post(
        "/api/v1/opportunities/search",
        headers=_headers(token),
        json={
            "career_goal": "quantitative technology internship",
            "location": "Hong Kong",
            "work_preference": "hybrid",
            "timing": "Summer 2027",
            "language": "en",
            "experience_ids": [experience_id],
            "consent_to_web_search": True,
            "limit": 5,
        },
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert len(result["opportunities"]) == 1
    assert (
        result["opportunities"][0]["source_url"]
        == "https://jobs.lever.co/example-capital/quant-tech-intern"
    )
    assert result["used_fallback"] is False
    assert result["experience_ids"] == [experience_id]

    recent = client.get("/api/v1/opportunities/searches", headers=_headers(token))
    assert recent.status_code == 200
    assert recent.json()[0]["id"] == result["id"]

    deleted = client.delete(
        f"/api/v1/opportunities/searches/{result['id']}",
        headers=_headers(token),
    )
    assert deleted.status_code == 204, deleted.text
    recent_after_delete = client.get("/api/v1/opportunities/searches", headers=_headers(token))
    assert recent_after_delete.status_code == 200
    assert all(item["id"] != result["id"] for item in recent_after_delete.json())


def test_grounded_source_matching_accepts_domain_title_for_company_careers_page():
    source = opportunity_service._matching_source(
        "Jane Street Careers",
        [{"title": "janestreet.com", "url": "https://example.com/jane-street"}],
    )
    assert source is not None
    assert source["url"] == "https://example.com/jane-street"


def test_brave_search_covers_multiple_official_ats_and_ranks_confirmed_evidence(monkeypatch):
    monkeypatch.setattr(opportunity_service.settings, "brave_search_api_key", "test-token")
    monkeypatch.setattr(opportunity_service.settings, "brave_search_max_requests", 3)

    class Response:
        status_code = 200

        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    calls = []

    def fake_get(_url, *, params, headers, **_kwargs):
        calls.append((params, headers))
        host = params["q"].split()[0]
        jobs = {
            "site:boards.greenhouse.io": (
                "https://boards.greenhouse.io/alpha-capital/jobs/100",
                "Quantitative Research Internship — Alpha Capital",
            ),
            "site:jobs.lever.co": (
                "https://jobs.lever.co/beta-research/quant-intern",
                "Quantitative Trading Internship — Beta Research",
            ),
            "site:jobs.ashbyhq.com": (
                "https://jobs.ashbyhq.com/gamma-labs/abc",
                "Quantitative Technology Internship — Gamma Labs",
            ),
        }
        url, title = jobs[host]
        return Response(
            {
                "web": {
                    "results": [
                        {
                            "title": title,
                            "url": url,
                            "description": "Hong Kong internship building Python research tools.",
                        },
                        {
                            "title": "Aggregator copy",
                            "url": "https://example.org/repost",
                            "description": "Never accept this result.",
                        },
                    ]
                }
            }
        )

    monkeypatch.setattr(opportunity_service.httpx, "get", fake_get)
    result = opportunity_service._brave_ats_search(
        [{"title": "Python research project", "description": "market data", "skills": ["Python", "Statistics"]}],
        career_goal="quantitative research internship",
        location="Hong Kong",
        language="en",
        limit=5,
    )
    assert len(calls) == 3
    assert all(call[1]["X-Subscription-Token"] == "test-token" for call in calls)
    assert len(result["opportunities"]) == 3
    assert all(item["source_url"].startswith("https://") for item in result["opportunities"])
    assert all("example.org" not in item["source_url"] for item in result["opportunities"])
    assert all("Python research project" in item["evidence_used"] for item in result["opportunities"])


def test_bocha_search_uses_its_documented_response_shape_and_filters_to_official_ats(monkeypatch):
    monkeypatch.setattr(opportunity_service.settings, "bocha_search_api_key", "test-token")
    monkeypatch.setattr(opportunity_service.settings, "bocha_search_max_requests", 3)

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
                                "name": "Machine Learning Internship — Example Labs",
                                "url": "https://jobs.lever.co/example-labs/ml-intern",
                                "snippet": "Hong Kong internship for Python and machine learning.",
                            },
                            {
                                "name": "Copied listing",
                                "url": "https://aggregator.example/role",
                                "snippet": "Do not return this source.",
                            },
                        ]
                    }
                }
            }

    calls = []

    def fake_post(_url, *, json, headers, **_kwargs):
        calls.append((json, headers))
        return Response()

    monkeypatch.setattr(opportunity_service.httpx, "post", fake_post)
    result = opportunity_service._bocha_ats_search(
        [{"title": "Python ML project", "description": "built models", "skills": ["Python", "PyTorch"]}],
        career_goal="machine learning internship",
        location="Hong Kong",
        language="en",
        limit=5,
    )
    assert len(calls) == 3
    assert all(call[1]["Authorization"] == "Bearer test-token" for call in calls)
    assert all(call[0]["summary"] is False for call in calls)
    assert {call[0]["include"] for call in calls} == {
        "boards.greenhouse.io",
        "jobs.lever.co",
        "jobs.ashbyhq.com",
    }
    assert len(result["opportunities"]) == 1
    assert result["opportunities"][0]["source_url"] == "https://jobs.lever.co/example-labs/ml-intern"


def test_discovery_prefers_bocha_over_brave_when_both_keys_are_configured(monkeypatch):
    monkeypatch.setattr(opportunity_service.settings, "bocha_search_api_key", "bocha-token")
    monkeypatch.setattr(opportunity_service.settings, "brave_search_api_key", "brave-token")
    monkeypatch.setattr(
        opportunity_service,
        "_bocha_ats_search",
        lambda *_args, **_kwargs: {
            "opportunities": [], "sources": [], "used_fallback": False, "unavailable_reason": ""
        },
    )
    monkeypatch.setattr(
        opportunity_service,
        "_brave_ats_search",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Brave must be standby only")),
    )
    monkeypatch.setattr(
        opportunity_service,
        "_direct_ats_search",
        lambda *_args, **_kwargs: {
            "opportunities": [], "sources": [], "used_fallback": True, "unavailable_reason": "ats_fallback"
        },
    )
    result = opportunity_service.discover_opportunities(
        [],
        career_goal="data internship",
        location="Hong Kong",
        work_preference="any",
        timing="",
        language="en",
        limit=5,
        search_modes=["ai"],
    )
    assert result["strategy_outcomes"] == [{"mode": "ai", "status": "failed", "count": 0}]


def test_discovery_uses_official_ats_when_bocha_has_no_fresh_verified_result(monkeypatch):
    monkeypatch.setattr(opportunity_service.settings, "bocha_search_api_key", "bocha-token")
    monkeypatch.setattr(
        opportunity_service,
        "_bocha_ats_search",
        lambda *_args, **_kwargs: {
            "opportunities": [], "sources": [], "used_fallback": False, "unavailable_reason": ""
        },
    )
    monkeypatch.setattr(
        opportunity_service,
        "_direct_ats_search",
        lambda *_args, **_kwargs: {
            "opportunities": [
                {
                    "company": "Point72",
                    "title": "Quantitative Researcher Intern",
                    "location": "Hong Kong",
                    "employment_type": "Internship",
                    "why_match": "Evidence-backed match.",
                    "evidence_used": ["Python project"],
                    "gaps_to_address": [],
                    "next_step": "Review the official page.",
                    "source_title": "Point72 careers",
                    "source_url": "https://boards.greenhouse.io/point72/jobs/123",
                    "source_search_mode": "official_ats",
                }
            ],
            "sources": [{"title": "Point72 careers", "url": "https://boards.greenhouse.io/point72/jobs/123"}],
            "used_fallback": True,
            "unavailable_reason": "ats_fallback",
        },
    )
    result = opportunity_service.discover_opportunities(
        [], career_goal="quant research internship", location="Hong Kong", work_preference="any",
        timing="", language="en", limit=5, search_modes=["ai"],
    )
    assert result["used_fallback"] is True
    assert result["opportunities"][0]["source_search_mode"] == "official_ats"
    assert result["strategy_outcomes"] == [{"mode": "ai", "status": "success", "count": 1}]


def test_direct_ats_search_parses_duckduckgo_redirects_without_an_ai_provider(monkeypatch):
    class Response:
        text = """
          <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fjobs.lever.co%2Fexample-capital%2Fabc123">Quantitative Research Intern | Example Capital</a>
          <a class="result__a" href="https://untrusted.example/role">Untrusted role</a>
        """

        def raise_for_status(self):
            return None

    monkeypatch.setattr(opportunity_service.httpx, "get", lambda *_args, **_kwargs: Response())
    result = opportunity_service._direct_ats_search(
        [{"title": "Python project", "skills": ["Python", "statistics"]}],
        career_goal="quant research internship",
        location="Hong Kong",
        language="en",
        limit=3,
    )
    assert result["unavailable_reason"] == "ats_fallback"
    assert result["opportunities"][0]["company"] == "Example Capital"
    assert (
        result["opportunities"][0]["source_url"] == "https://jobs.lever.co/example-capital/abc123"
    )


def test_direct_ats_search_reports_a_search_challenge_instead_of_false_empty_result(monkeypatch):
    monkeypatch.setattr(opportunity_service, "_LEVER_PUBLIC_FEEDS", {"ekimetrics": "Ekimetrics"})
    class FeedResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return []

    class ChallengeResponse:
        status_code = 202
        text = "challenge"

        def raise_for_status(self):
            raise AssertionError("202 must be handled before raise_for_status")

    responses = iter([FeedResponse(), ChallengeResponse()])
    monkeypatch.setattr(
        opportunity_service,
        "_greenhouse_public_board_search",
        lambda *_args, **_kwargs: {
            "opportunities": [],
            "sources": [],
            "used_fallback": True,
            "unavailable_reason": "ats_fallback",
        },
    )
    monkeypatch.setattr(
        opportunity_service.httpx,
        "get",
        lambda *_args, **_kwargs: next(responses),
    )
    result = opportunity_service._direct_ats_search(
        [],
        career_goal="data internship",
        location="Hong Kong",
        language="en",
        limit=5,
    )
    assert result["opportunities"] == []
    assert result["unavailable_reason"] == "provider_unavailable"


def test_greenhouse_official_boards_add_a_broad_current_student_role_pool(monkeypatch):
    monkeypatch.setattr(
        opportunity_service,
        "_GREENHOUSE_PUBLIC_BOARDS",
        {"point72": "Point72"},
    )

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    def fake_get(url, **_kwargs):
        if url.endswith("/jobs"):
            return Response(
                {
                    "jobs": [
                        {
                            "id": 10,
                            "title": "2027 Quantitative Research Internship",
                            "company_name": "Point72",
                            "location": {"name": "Hong Kong"},
                            "absolute_url": "https://careers.point72.com/quant-intern",
                        },
                        {
                            "id": 11,
                            "title": "2026-07 Quantitative Research Internship",
                            "company_name": "Point72",
                            "location": {"name": "Hong Kong"},
                            "absolute_url": "https://careers.point72.com/expired",
                        },
                    ]
                }
            )
        return Response(
            {
                "content": "<p>Research market data, statistics and quantitative models.</p>"
            }
        )

    monkeypatch.setattr(opportunity_service.httpx, "get", fake_get)
    result = opportunity_service._greenhouse_public_board_search(
        [{"title": "Statistics project", "description": "Modelled data", "skills": ["Python"]}],
        career_goal="量化研究实习",
        location="Hong Kong",
        language="zh-CN",
        limit=5,
    )
    assert [row["title"] for row in result["opportunities"]] == [
        "2027 Quantitative Research Internship"
    ]
    assert result["opportunities"][0]["source_url"].startswith(
        "https://careers.point72.com/"
    )
    assert result["opportunities"][0]["gaps_to_address"]


def test_official_feed_ranks_requested_city_above_other_cities_and_excludes_expired_internships(monkeypatch):
    monkeypatch.setattr(opportunity_service, "_LEVER_PUBLIC_FEEDS", {"ekimetrics": "Ekimetrics"})
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {
                    "text": "Strategy & Data Science Internship - Shanghai",
                    "hostedUrl": "https://jobs.lever.co/ekimetrics/shanghai",
                    "categories": {"location": "Shanghai", "commitment": "Internship"},
                    "descriptionPlain": "Current data internship",
                },
                {
                    "text": "Data Science Internship - Hong Kong",
                    "hostedUrl": "https://jobs.lever.co/ekimetrics/hong-kong",
                    "categories": {"location": "Hong Kong", "commitment": "Internship"},
                    "descriptionPlain": "Current data internship",
                },
                {
                    "text": "Summer 2026 Data Internship - Hong Kong",
                    "hostedUrl": "https://jobs.lever.co/ekimetrics/expired",
                    "categories": {"location": "Hong Kong", "commitment": "Internship"},
                    "descriptionPlain": "Program starts July 2026",
                },
            ]

    monkeypatch.setattr(opportunity_service.httpx, "get", lambda *_args, **_kwargs: Response())
    result = opportunity_service._lever_public_feed_search(
        [{"title": "Python project", "description": "Data pipeline", "skills": ["Python"]}],
        career_goal="data science internship",
        location="Hong Kong",
        language="zh-TW",
        limit=5,
    )
    assert [item["title"] for item in result["opportunities"]] == [
        "Data Science Internship - Hong Kong",
        "Strategy & Data Science Internship - Shanghai",
    ]
    row = result["opportunities"][0]
    assert "Shanghai" not in row["location"]
    assert "官方招聘系統" not in row["why_match"]
    assert "Data Science Internship" in row["why_match"]
    assert row["gaps_to_address"]


def test_location_ranking_prefers_requested_office_without_hiding_verified_alternatives():
    rows = [
        {"company": "Example", "title": "Quant Research Internship - Shanghai", "location": "Shanghai"},
        {"company": "Example", "title": "Quant Trading Internship - Hong Kong", "location": "Hong Kong"},
    ]
    result = opportunity_service._dedupe_and_rank(
        rows, career_goal="quant internship", location="Hong Kong", limit=5
    )
    assert len(result) == 2
    assert result[0]["location"] == "Hong Kong"

    new_york_result = opportunity_service._dedupe_and_rank(
        rows,
        career_goal="quant internship",
        location="New York",
        limit=5,
    )
    assert len(new_york_result) == 2


def test_role_copy_and_honest_gaps_follow_selected_language():
    evidence = [
        {"title": "Python Project", "description": "Built a data pipeline", "skills": ["Python"]}
    ]
    reason = opportunity_service._localized_role_reason(
        "zh-TW",
        company="Example Capital",
        title="Quant Trading Internship",
        career_goal="量化交易實習",
        evidence=evidence,
    )
    gaps = opportunity_service._honest_gaps(evidence, "Quant Trading Internship", "zh-TW")
    assert "Example Capital" in reason
    assert "你設定的" in reason
    assert gaps
    assert all("真实" not in gap for gap in gaps)


def test_opportunity_radar_records_a_transparent_quota_status_without_running_an_unselected_fallback(
    monkeypatch,
):
    monkeypatch.setattr(opportunity_service.settings, "bocha_search_api_key", "")
    token = _token()
    _confirmed_experience(token)

    def quota_exhausted(*_args, **_kwargs):
        raise RateLimitExceeded("Gemini web research quota is temporarily exhausted")

    monkeypatch.setattr(opportunity_service, "_brave_ats_search", quota_exhausted)
    response = client.post(
        "/api/v1/opportunities/search",
        headers=_headers(token),
        json={"consent_to_web_search": True, "language": "en"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["opportunities"] == []
    assert payload["unavailable_reason"] == "quota_exhausted"
    assert payload["strategy_outcomes"] == [{"mode": "ai", "status": "quota_exhausted", "count": 0}]

    recent = client.get("/api/v1/opportunities/searches", headers=_headers(token))
    assert recent.status_code == 200
    assert recent.json()[0]["unavailable_reason"] == "quota_exhausted"


def test_importing_a_web_research_opportunity_creates_a_real_analysed_job(monkeypatch):
    monkeypatch.setattr(opportunity_service.settings, "bocha_search_api_key", "")
    token = _token()
    _confirmed_experience(token)

    monkeypatch.setattr(
        opportunity_service,
        "_brave_ats_search",
        lambda *_args, **_kwargs: {
            "opportunities": [
                {
                    "company": "Example Capital",
                    "title": "Quantitative Technology Intern",
                    "location": "Hong Kong",
                    "employment_type": "Internship",
                    "why_match": "Python evidence is relevant.",
                    "evidence_used": ["Python"],
                    "gaps_to_address": [],
                    "next_step": "Review.",
                    "source_title": "Official opening",
                    "source_url": "https://jobs.lever.co/example-capital/role",
                    "source_search_mode": "ai",
                }
            ],
            "sources": [{"title": "Official opening", "url": "https://jobs.lever.co/example-capital/role"}],
            "used_fallback": False,
            "unavailable_reason": "",
        },
    )
    search = client.post(
        "/api/v1/opportunities/search",
        headers=_headers(token),
        json={"consent_to_web_search": True, "language": "en"},
    )
    assert search.status_code == 200, search.text

    from app.api.v1 import opportunities as opportunity_api

    monkeypatch.setattr(opportunity_api, "validate_public_job_url", lambda url: url)
    monkeypatch.setattr(
        opportunity_api,
        "import_public_job_page",
        lambda _url: type(
            "Draft",
            (),
            {
                "title": "Quantitative Technology Intern",
                "company": "Example Capital",
                "description": "Build Python tools for quantitative research and test reliable data systems.",
            },
        )(),
    )
    imported = client.post(
        f"/api/v1/opportunities/searches/{search.json()['id']}/import/0",
        headers=_headers(token),
    )
    assert imported.status_code == 200, imported.text
    assert imported.json()["company"] == "Example Capital"
    assert "Python" in imported.json()["required_skills"]

    tracked = client.post(
        f"/api/v1/opportunities/searches/{search.json()['id']}/import-and-track/0",
        headers=_headers(token),
    )
    assert tracked.status_code == 200, tracked.text
    payload = tracked.json()
    assert payload["job"]["company"] == "Example Capital"
    assert payload["tracker"]["job_id"] == payload["job"]["id"]
    assert payload["tracker"]["status"] == "saved"


def test_opportunity_radar_rejects_unconfirmed_or_unknown_selected_evidence():
    token = _token()
    _confirmed_experience(token)
    rejected = client.post(
        "/api/v1/opportunities/search",
        headers=_headers(token),
        json={"consent_to_web_search": True, "experience_ids": [999999]},
    )
    assert rejected.status_code == 422
