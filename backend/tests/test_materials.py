from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_material_generation_is_evidence_grounded():
    experience = client.post(
        "/api/v1/experiences",
        json={
            "title": "Confirmed Python Project",
            "organization": "CUHK",
            "description": "Built a Python data pipeline.",
            "skills": ["Python"],
            "confirmed": True,
            "achievements": [
                {"text": "Improved speed by 20%", "source": "report", "verified": True}
            ],
        },
    ).json()

    job = client.post(
        "/api/v1/jobs/analyze",
        json={"title": "Data Intern", "description": "Python data analysis role with teamwork."},
    ).json()

    resume = client.post(f"/api/v1/materials/resume/generate?job_id={job['id']}")

    assert resume.status_code == 200

    data = resume.json()

    assert "Confirmed Python Project" in data["text"]

    assert data["fact_check_passed"] is True

    assert any(source["experience_id"] == experience["id"] for source in data["sources"])

    cover = client.post(f"/api/v1/materials/cover-letter/generate?job_id={job['id']}").json()

    assert "Confirmed Python Project" in cover["text"]


def test_answer_respects_character_limit_and_missing_job():
    job = client.post(
        "/api/v1/jobs/analyze",
        json={
            "title": "Intern",
            "description": "A role requiring communication and teamwork skills.",
        },
    ).json()

    response = client.post(
        f"/api/v1/materials/answer/generate?job_id={job['id']}",
        json={"question": "Why this role?", "max_characters": 50},
    )

    assert response.status_code == 200

    assert response.json()["character_count"] <= 50

    assert client.post("/api/v1/materials/resume/generate?job_id=999999").status_code == 404


def test_answer_preferences_are_validated_and_accepted():
    job = client.post(
        "/api/v1/jobs/analyze",
        json={"title": "Research Intern", "description": "Research and write clearly."},
    ).json()

    response = client.post(
        f"/api/v1/materials/answer/generate?job_id={job['id']}",
        json={
            "question": "Why are you interested in this role?",
            "max_characters": 300,
            "answer_tone": "technical",
            "desired_content": " my research mindset and collaboration ",
        },
    )

    assert response.status_code == 200
    assert response.json()["material_type"] == "application_answer"

    invalid = client.post(
        f"/api/v1/materials/answer/generate?job_id={job['id']}",
        json={"question": "Why this role?", "answer_tone": "unbounded"},
    )
    assert invalid.status_code == 422


def test_materials_generate_in_requested_language():
    client.post(
        "/api/v1/experiences",
        json={
            "title": "Data Project",
            "organization": "HKU",
            "description": "Built a Python data pipeline.",
            "skills": ["Python"],
            "confirmed": True,
        },
    )
    job = client.post(
        "/api/v1/jobs/analyze",
        json={"title": "Data Intern", "description": "Python data analysis role."},
    ).json()

    resume = client.post(
        f"/api/v1/materials/resume/generate?job_id={job['id']}&output_language=zh-CN"
    )
    assert resume.status_code == 200
    assert resume.json()["output_language"] == "zh-CN"
    assert "目标职位" in resume.json()["text"]

    answer = client.post(
        f"/api/v1/materials/answer/generate?job_id={job['id']}",
        json={
            "question": "Why are you interested in this role?",
            "max_characters": 300,
            "output_language": "zh-TW",
        },
    )
    assert answer.status_code == 200
    assert answer.json()["output_language"] == "zh-TW"
