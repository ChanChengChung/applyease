from io import BytesIO
from uuid import uuid4

from docx import Document
from fastapi.testclient import TestClient

from app.main import app


def _token(client: TestClient, label: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        headers={"X-ApplyEase-Client": "browser-extension"},
        json={
            "email": f"stage14-{label}-{uuid4()}@example.com",
            "password": "stage14-secure-password",
        },
    )

    assert response.status_code == 201

    return response.json()["access_token"]


def test_applicant_profile_is_validated_isolated_and_deletable():
    one, two = TestClient(app), TestClient(app)

    first, second = _token(one, "one"), _token(two, "two")

    headers = {"Authorization": f"Bearer {first}"}

    saved = one.put(
        "/api/v1/applicant-profile",
        headers=headers,
        json={
            "display_name": "  Chen   Zhengzhong ",
            "contact_line": " chen@example.com  · Hong Kong ",
            "email": " chen@example.com ",
            "phone": " +852 6406 1561 ",
            "location": " Hong Kong SAR ",
            "linkedin_url": " https://linkedin.com/in/chen ",
            "github_url": " https://github.com/chen ",
        },
    )

    assert saved.status_code == 200 and saved.json()["display_name"] == "Chen Zhengzhong"

    assert saved.json()["contact_line"] == "chen@example.com · Hong Kong"
    assert saved.json()["email"] == "chen@example.com"
    assert saved.json()["phone"] == "+852 6406 1561"
    assert saved.json()["linkedin_url"] == "https://linkedin.com/in/chen"

    assert (
        two.get(
            "/api/v1/applicant-profile", headers={"Authorization": f"Bearer {second}"}
        ).status_code
        == 404
    )

    assert (
        one.put(
            "/api/v1/applicant-profile",
            headers=headers,
            json={"display_name": "   ", "contact_line": ""},
        ).status_code
        == 422
    )

    assert one.delete("/api/v1/applicant-profile", headers=headers).status_code == 204

    assert one.get("/api/v1/applicant-profile", headers=headers).status_code == 404


def test_export_applies_section_order_and_never_exports_no_sections():
    client = TestClient(app)
    token = _token(client, "export")
    headers = {"Authorization": f"Bearer {token}"}

    suffix = uuid4().hex[:8]

    experience = client.post(
        "/api/v1/experiences",
        headers=headers,
        json={
            "title": f"Project {suffix}",
            "organization": "Lab",
            "description": "Built Python research tools.",
            "skills": ["Python"],
            "achievements": [],
            "source_file": "manual",
            "confirmed": True,
        },
    )

    job = client.post(
        "/api/v1/jobs/analyze",
        headers=headers,
        json={
            "title": "Research Intern",
            "company": "Polymer",
            "description": "Build Python research tools.",
        },
    )

    resume = client.post(
        f"/api/v1/materials/resume/generate?job_id={job.json()['id']}", headers=headers
    ).json()

    payload = {
        "format": "docx",
        "template": "modern",
        "display_name": "Test User",
        "section_order": ["SELECTED EXPERIENCE", "TARGET ROLE"],
        "hidden_sections": [],
    }

    exported = client.post(
        f"/api/v1/materials/{resume['id']}/export", headers=headers, json=payload
    )

    assert exported.status_code == 200

    text = "\n".join(item.text for item in Document(BytesIO(exported.content)).paragraphs)

    assert text.index("SELECTED EXPERIENCE") < text.index("TARGET ROLE")

    payload["hidden_sections"] = ["Resume summary", "SELECTED EXPERIENCE"]

    assert (
        client.post(
            f"/api/v1/materials/{resume['id']}/export", headers=headers, json=payload
        ).status_code
        == 422
    )
