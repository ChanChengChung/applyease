import pytest

from app.services import job_import_service


class _StreamResponse:
    def __init__(self, page: str, *, redirect: bool = False):
        self.is_redirect = redirect
        self.status_code = 302 if redirect else 200

        self.headers = {"content-type": "text/html"}
        self.encoding = "utf-8"
        self.page = page

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def iter_bytes(self):
        yield self.page.encode()


def test_url_import_rejects_non_public_and_non_https_hosts(monkeypatch):
    assert pytest.raises(ValueError, job_import_service._public_https_url, "http://example.com/job")

    monkeypatch.setattr(
        job_import_service.socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(None, None, None, None, ("127.0.0.1", 443))],
    )

    with pytest.raises(ValueError, match="Private"):
        job_import_service._public_https_url("https://localhost/job")

    with pytest.raises(ValueError, match="standard HTTPS port"):
        job_import_service.validate_public_job_url("https://example.com:8443/job")


def test_url_import_extracts_a_reviewable_draft_without_persisting(monkeypatch):
    monkeypatch.setattr(
        job_import_service, "_public_https_url", lambda value: "https://jobs.example.com/role"
    )

    page = """<html><head><meta property='og:title' content='Quantitative Research Intern'></head><body><h1>Quantitative Research Intern</h1><p>Join Jane Street to research markets with Python and statistics.</p><p>Location: Hong Kong</p><p>Apply by: 30 September 2026</p></body></html>"""

    monkeypatch.setattr(
        job_import_service.httpx, "stream", lambda *args, **kwargs: _StreamResponse(page)
    )

    draft = job_import_service.import_public_job_page("https://jobs.example.com/role")

    assert draft["title"] == "Quantitative Research Intern"

    assert "Python" in draft["description"] and draft["location"] == "Hong Kong"

    assert draft["deadline"] == "30 September 2026" and draft["source_url"].startswith("https://")


def test_url_import_prefers_structured_jobposting_title_and_company(monkeypatch):
    monkeypatch.setattr(
        job_import_service, "_public_https_url", lambda value: "https://jobs.example.com/role"
    )
    page = """<html><head><meta property="og:title" content="Careers | ExampleCo"><script type="application/ld+json">{"@context":"https://schema.org","@type":"JobPosting","title":"Machine Learning Intern","hiringOrganization":{"@type":"Organization","name":"ExampleCo"}}</script></head><body><h1>Careers</h1><p>Details appear here.</p></body></html>"""
    monkeypatch.setattr(
        job_import_service.httpx, "stream", lambda *args, **kwargs: _StreamResponse(page)
    )
    draft = job_import_service.import_public_job_page("https://jobs.example.com/role")
    assert draft["title"] == "Machine Learning Intern"
    assert draft["company"] == "ExampleCo"


def test_url_import_prefers_structured_jobposting_description(monkeypatch):
    monkeypatch.setattr(
        job_import_service, "_public_https_url", lambda value: "https://jobs.example.com/role"
    )
    page = """<html><head><script type="application/ld+json">{"@context":"https://schema.org","@type":"JobPosting","title":"Data Intern","hiringOrganization":{"name":"ExampleCo"},"description":"<h2>About the role</h2><p>Build data pipelines and evaluate model quality.</p><h2>About you</h2><p>You communicate findings clearly.</p>"}</script></head><body><p>Accept All cookies</p><p>Company navigation</p></body></html>"""
    monkeypatch.setattr(
        job_import_service.httpx, "stream", lambda *args, **kwargs: _StreamResponse(page)
    )
    draft = job_import_service.import_public_job_page("https://jobs.example.com/role")
    assert "Build data pipelines" in draft["description"]
    assert "cookies" not in draft["description"].casefold()
    assert draft["title"] == "Data Intern"
    assert draft["company"] == "ExampleCo"


def test_llm_job_review_uses_only_grounded_output_and_falls_back(monkeypatch):
    source = "About the Position\nBuild data pipelines for model evaluation.\nAbout You\nCommunicate findings clearly."
    monkeypatch.setattr(job_import_service.settings, "ai_job_analysis_enabled", True)
    monkeypatch.setattr(
        job_import_service.llm,
        "generate_json",
        lambda *args, **kwargs: {
            "job_description": "About the Position\nBuild data pipelines for model evaluation."
        },
    )
    assert job_import_service._grounded_llm_job_body(source).endswith("model evaluation.")
    monkeypatch.setattr(
        job_import_service.llm,
        "generate_json",
        lambda *args, **kwargs: {
            "job_description": "Invented requirement: five years of trading experience."
        },
    )
    assert job_import_service._grounded_llm_job_body(source) == source


def test_url_import_splits_role_and_company_from_standard_page_title(monkeypatch):
    monkeypatch.setattr(
        job_import_service, "_public_https_url", lambda value: "https://jobs.example.com/role"
    )
    page = """<html><head><meta property='og:title' content='Quantitative Research Intern | Jane Street'></head><body><h1>Apply now</h1><p>Research markets with Python and statistics.</p></body></html>"""
    monkeypatch.setattr(
        job_import_service.httpx, "stream", lambda *args, **kwargs: _StreamResponse(page)
    )
    draft = job_import_service.import_public_job_page("https://jobs.example.com/role")
    assert draft["title"] == "Quantitative Research Intern"
    assert draft["company"] == "Jane Street"


def test_url_import_reads_greenhouse_double_colon_title_and_strips_location(monkeypatch):
    monkeypatch.setattr(
        job_import_service, "_public_https_url", lambda value: "https://jobs.example.com/role"
    )
    page = """<html><head><title>Quantitative Trader Internship, Hong Kong :: Jane Street</title></head><body><h1>Quantitative Trader Internship</h1><p>Use mathematical thinking to solve real market problems.</p></body></html>"""
    monkeypatch.setattr(
        job_import_service.httpx, "stream", lambda *args, **kwargs: _StreamResponse(page)
    )

    draft = job_import_service.import_public_job_page("https://jobs.example.com/role")

    assert draft["title"] == "Quantitative Trader Internship"
    assert draft["company"] == "Jane Street"
    assert "Jane Street" not in draft["description"]


def test_url_import_keeps_jane_street_job_body_and_removes_site_chrome(monkeypatch):
    monkeypatch.setattr(
        job_import_service, "_public_https_url", lambda value: "https://www.janestreet.com/role"
    )
    page = """<html><head><title>Quantitative Trader Internship, Hong Kong :: Jane Street</title></head><body>
    <p>Jane Street Group uses cookies. Accept All Reject All</p><p>WHO WE ARE</p><p>JOIN JANE STREET</p>
    <h2>Job description</h2><h1>Quantitative Trader Internship, December-February</h1><p>LOCATION</p><p>HKG</p>
    <h2>About the Position</h2><p>You'll identify market signals, analyze strategies, construct quantitative models, and conduct statistical analysis.</p>
    <h2>About You</h2><p>You are a strong quantitative thinker and a clear communicator.</p>
    <p>If you'd like to learn more, read about our interview process and internship programme.</p><p>Please note: flights are provided.</p>
    <p>Jane Street is an Equal Opportunity Employer</p><p>Disclosures and Policies</p></body></html>"""
    monkeypatch.setattr(
        job_import_service.httpx, "stream", lambda *args, **kwargs: _StreamResponse(page)
    )

    draft = job_import_service.import_public_job_page("https://www.janestreet.com/role")

    assert draft["title"] == "Quantitative Trader Internship"
    assert draft["company"] == "Jane Street"
    assert "identify market signals" in draft["description"]
    assert "strong quantitative thinker" in draft["description"]
    assert "cookies" not in draft["description"].casefold()
    assert "WHO WE ARE" not in draft["description"]
    assert "Equal Opportunity Employer" not in draft["description"]
    assert "interview process" not in draft["description"].casefold()
    assert "flights are provided" not in draft["description"].casefold()


def test_url_import_blocks_redirects(monkeypatch):
    monkeypatch.setattr(
        job_import_service, "_public_https_url", lambda value: "https://jobs.example.com/role"
    )

    monkeypatch.setattr(
        job_import_service.httpx,
        "stream",
        lambda *args, **kwargs: _StreamResponse("", redirect=True),
    )

    with pytest.raises(ValueError, match="Redirecting"):
        job_import_service.import_public_job_page("https://jobs.example.com/role")


def test_url_import_rejects_a_private_connected_peer_in_production(monkeypatch):
    class _Stream:
        def get_extra_info(self, _name):
            return ("127.0.0.1", 443)

    class _Response:
        extensions = {"network_stream": _Stream()}

    monkeypatch.setattr(job_import_service.settings, "app_env", "production")
    with pytest.raises(ValueError, match="private or reserved"):
        job_import_service._verify_connected_peer(_Response())
