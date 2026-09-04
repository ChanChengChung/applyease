from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def _experience(title: str, organization: str, confirmed: bool = False):
    response = client.post(
        "/api/v1/experiences",
        json={
            "title": title,
            "organization": organization,
            "description": f"Description for {title}",
            "skills": ["Python", "Python"],
            "achievements": [],
            "confirmed": confirmed,
        },
    )

    assert response.status_code == 200, response.text

    return response.json()


def test_manual_create_normalizes_and_rejects_duplicate_identity():
    suffix = uuid4().hex

    first = _experience(f"  Project {suffix}  ", "  HKU  ")

    assert first["title"] == f"Project {suffix}"

    assert first["organization"] == "HKU"

    assert first["skills"] == ["Python"]

    duplicate = client.post(
        "/api/v1/experiences", json={"title": f"project {suffix}", "organization": "hku"}
    )

    assert duplicate.status_code == 409

    assert str(first["id"]) in duplicate.json()["detail"]


def test_search_status_filter_and_pagination():
    suffix = uuid4().hex

    pending = _experience(f"Searchable {suffix}", "Org A", False)

    confirmed = _experience(f"Searchable confirmed {suffix}", "Org B", True)

    response = client.get(
        "/api/v1/experiences", params={"query": suffix, "confirmed": "false", "limit": 1}
    )

    assert response.status_code == 200

    assert [item["id"] for item in response.json()] == [pending["id"]]

    response = client.get(
        "/api/v1/experiences", params={"query": suffix, "confirmed": "true", "offset": 1}
    )

    assert response.status_code == 200

    assert response.json() == []

    response = client.get("/api/v1/experiences", params={"query": suffix, "confirmed": "true"})

    assert [item["id"] for item in response.json()] == [confirmed["id"]]


def test_bulk_confirm_reports_missing_ids_and_updates_records():
    suffix = uuid4().hex

    first = _experience(f"Bulk A {suffix}", "Org", False)

    second = _experience(f"Bulk B {suffix}", "Org", False)

    response = client.post(
        "/api/v1/experiences/bulk-confirm",
        json={"ids": [first["id"], second["id"], 999999], "confirmed": True},
    )

    assert response.status_code == 200

    assert response.json() == {"updated": 2, "missing_ids": [999999]}

    records = client.get("/api/v1/experiences", params={"query": suffix}).json()

    assert all(record["confirmed"] for record in records)


def test_update_rejects_duplicate_identity_and_bulk_requires_ids():
    suffix = uuid4().hex

    first = _experience(f"Update A {suffix}", "Org")

    second = _experience(f"Update B {suffix}", "Org")

    response = client.patch(f"/api/v1/experiences/{second['id']}", json={"title": first["title"]})

    assert response.status_code == 409

    assert client.post("/api/v1/experiences/bulk-confirm", json={"ids": []}).status_code == 422


def test_replace_endpoint_persists_reviewed_duplicate_content():
    suffix = uuid4().hex
    original = _experience(f"Original {suffix}", "Original org", confirmed=True)

    replacement = client.put(
        f"/api/v1/experiences/{original['id']}/replace",
        json={
            "title": f"Replacement {suffix}",
            "organization": "Replacement org",
            "description": "Reviewed replacement description",
            "skills": ["TypeScript", "FastAPI"],
            "achievements": [],
            "category": "project",
            "source_file": "manual-entry",
            "confirmed": True,
        },
    )

    assert replacement.status_code == 200
    assert replacement.json()["id"] == original["id"]
    assert replacement.json()["confirmed"] is False
    assert replacement.json()["description"] == "Reviewed replacement description"

    persisted = next(
        item
        for item in client.get("/api/v1/experiences", params={"query": suffix}).json()
        if item["id"] == original["id"]
    )
    assert persisted["organization"] == "Replacement org"
    assert persisted["skills"] == ["TypeScript", "FastAPI"]
