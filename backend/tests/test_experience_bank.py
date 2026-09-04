from fastapi.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200

    assert response.json() == {"status": "ok"}


def test_upload_text_extracts_and_persists_multiple_records():
    content = b"""WORK EXPERIENCE\nAI Developer | Novelflow\nBuilt a React and FastAPI platform.\nImproved conversion by 8%.\n\nRESEARCH EXPERIENCE\nResearch Assistant | CUHK\nImplemented PyTorch Transformer experiments.\nWon a scholarship.\n"""

    response = client.post(
        "/api/v1/documents/upload", files={"file": ("cv.txt", content, "text/plain")}
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["text_length"] > 0

    assert len(payload["experiences"]) >= 2

    assert all(item["confirmed"] is False for item in payload["experiences"])

    assert all(item["source_file"] == "cv.txt" for item in payload["experiences"])

    assert payload["duplicate"] is False

    assert payload["document_id"] > 0


def test_upload_extracts_an_editable_personal_profile_record():
    content = b"""CHEN PERSONALTEST\nEmail: chen.personaltest@example.com\nPhone: +852 9123 4567\nLocation: Hong Kong\nAddress: Sha Tin, New Territories\nLinkedIn: https://www.linkedin.com/in/chen-personaltest\nGitHub: https://github.com/chen-personaltest\n\nEDUCATION\nExample University\nBSc Computer Science\n"""

    response = client.post(
        "/api/v1/documents/upload",
        files={"file": ("personal-profile-cv.txt", content, "text/plain")},
    )

    assert response.status_code == 200

    profile = next(
        item
        for item in response.json()["experiences"]
        if item["category"] == "personal"
    )

    assert profile["confirmed"] is False
    assert profile["title"] == "CHEN PERSONALTEST"
    assert "chen.personaltest@example.com" in profile["description"]
    assert "+852 9123 4567" in profile["description"]
    assert "Hong Kong" in profile["description"]
    assert "Sha Tin, New Territories" in profile["description"]
    assert "linkedin.com/in/chen-personaltest" in profile["description"]
    assert "github.com/chen-personaltest" in profile["description"]


def test_duplicate_upload_is_idempotent():
    content = b"EDUCATION\nTest University\nBSc 2025"

    first = client.post(
        "/api/v1/documents/upload", files={"file": ("same.txt", content, "text/plain")}
    )

    second = client.post(
        "/api/v1/documents/upload", files={"file": ("renamed.txt", content, "text/plain")}
    )

    assert first.status_code == 200 and second.status_code == 200

    assert first.json()["duplicate"] is False

    assert second.json()["duplicate"] is True

    assert second.json()["restored"] is False

    assert second.json()["reused"] is True

    assert second.json()["document_id"] == first.json()["document_id"]


def test_reupload_restores_deleted_experiences_for_existing_document():
    content = b"""WORK EXPERIENCE
Reparse Engineer | Recovery Lab
Built a deterministic CV re-upload recovery workflow using Python.
Improved recovery reliability for deleted experience records.
"""

    first = client.post(
        "/api/v1/documents/upload",
        files={"file": ("reparse-original.txt", content, "text/plain")},
    )
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["experiences"]

    for experience in first_body["experiences"]:
        response = client.delete(f"/api/v1/experiences/{experience['id']}")
        assert response.status_code == 204

    second = client.post(
        "/api/v1/documents/upload",
        files={"file": ("reparse-renamed.txt", content, "text/plain")},
    )
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["duplicate"] is True
    assert second_body["restored"] is True
    assert second_body["reused"] is False
    assert second_body["document_id"] == first_body["document_id"]
    assert len(second_body["experiences"]) == len(first_body["experiences"])

    third = client.post(
        "/api/v1/documents/upload",
        files={"file": ("reparse-third.txt", content, "text/plain")},
    )
    assert third.status_code == 200
    third_body = third.json()
    assert third_body["duplicate"] is True
    assert third_body["restored"] is False
    assert third_body["reused"] is True
    assert len(third_body["experiences"]) == len(second_body["experiences"])


def test_edit_and_confirm_experience():
    items = client.get("/api/v1/experiences").json()

    item = items[0]

    response = client.patch(
        f"/api/v1/experiences/{item['id']}",
        json={
            "title": "Edited title",
            "organization": "Edited org",
            "confirmed": True,
            "skills": ["Python", "Python", "React"],
        },
    )

    assert response.status_code == 200

    result = response.json()

    assert result["title"] == "Edited title"

    assert result["confirmed"] is True

    assert result["skills"] == ["Python", "React"]

    # A duplicate-resolution replacement uses this same PATCH path.  Verify it
    # is persisted by reading the original record back from the API, rather
    # than only trusting the response returned by the update call.
    persisted = next(
        record
        for record in client.get("/api/v1/experiences").json()
        if record["id"] == item["id"]
    )
    assert persisted["title"] == "Edited title"
    assert persisted["organization"] == "Edited org"
    assert persisted["skills"] == ["Python", "React"]


def test_delete_experience():
    items = client.get("/api/v1/experiences").json()

    experience_id = items[0]["id"]

    assert client.delete(f"/api/v1/experiences/{experience_id}").status_code == 204

    assert client.delete(f"/api/v1/experiences/{experience_id}").status_code == 404


def test_rejects_unsupported_empty_and_oversized_files():
    assert (
        client.post("/api/v1/documents/upload", files={"file": ("cv.exe", b"x")}).status_code == 400
    )

    assert (
        client.post("/api/v1/documents/upload", files={"file": ("empty.txt", b"")}).status_code
        == 400
    )

    too_large = b"x" * (10 * 1024 * 1024 + 1)

    assert (
        client.post(
            "/api/v1/documents/upload", files={"file": ("large.txt", too_large)}
        ).status_code
        == 413
    )


def test_rejects_malformed_docx():
    response = client.post("/api/v1/documents/upload", files={"file": ("bad.docx", b"not-a-docx")})

    assert response.status_code == 400
