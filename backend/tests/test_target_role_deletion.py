from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.session import SessionLocal
from app.main import app
from app.models.application import Application, ApplicationQuestion
from app.models.material import GeneratedMaterial
from app.models.research_plan import ResearchPlan
from app.models.tracker import TrackedApplication
from app.models.user import User


def _register(client: TestClient, email: str) -> str:
    response = client.post(
        "/api/v1/auth/register",
        headers={"X-ApplyEase-Client": "browser-extension"},
        json={"email": email, "password": "secure-pass-123"},
    )
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def _create_job(client: TestClient, token: str, title: str) -> int:
    response = client.post(
        "/api/v1/jobs/analyze",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": title,
            "company": "Target Role Co",
            "description": "Build Python services and analyse data for a research team.",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["id"]


def test_dashboard_target_role_can_be_deleted_only_by_its_owner():
    owner = TestClient(app)
    other = TestClient(app)
    owner_token = _register(owner, "target-delete-owner@example.com")
    other_token = _register(other, "target-delete-other@example.com")
    job_id = _create_job(owner, owner_token, "Disposable AI Internship")

    # Seed every kind of derived artifact. Deleting a target role must not
    # leave any role-specific data behind.
    with SessionLocal() as db:
        user_id = db.scalar(select(User.id).where(User.email == "target-delete-owner@example.com"))
        assert user_id is not None
        application = Application(user_id=user_id, job_id=job_id, raw_text="Why this role?")
        db.add(application)
        db.flush()
        question = ApplicationQuestion(
            user_id=user_id,
            application_id=application.id,
            question="Why this role?",
            answer={},
        )
        material = GeneratedMaterial(
            user_id=user_id,
            job_id=job_id,
            material_type="resume",
            content={"content": "role-specific resume"},
        )
        plan = ResearchPlan(
            user_id=user_id,
            job_id=job_id,
            profile_summary="role-specific research plan",
            gaps=[],
            method=[],
            sources=[],
        )
        tracked = TrackedApplication(
            user_id=user_id,
            job_id=job_id,
            company="Target Role Co",
            role="Disposable AI Internship",
        )
        db.add_all([question, material, plan, tracked])
        db.commit()
        application_id, material_id, plan_id, tracked_id = (
            application.id,
            material.id,
            plan.id,
            tracked.id,
        )

    forbidden = other.delete(
        f"/api/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {other_token}"}
    )
    assert forbidden.status_code == 404

    deleted = owner.delete(
        f"/api/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {owner_token}"}
    )
    assert deleted.status_code == 204

    assert (
        owner.get(
            f"/api/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {owner_token}"}
        ).status_code
        == 404
    )

    remaining = owner.get("/api/v1/jobs", headers={"Authorization": f"Bearer {owner_token}"})
    assert remaining.status_code == 200
    assert job_id not in {item["id"] for item in remaining.json()}

    with SessionLocal() as db:
        assert db.get(Application, application_id) is None
        assert (
            db.scalar(
                select(ApplicationQuestion).where(
                    ApplicationQuestion.application_id == application_id
                )
            )
            is None
        )
        assert db.get(GeneratedMaterial, material_id) is None
        assert db.get(ResearchPlan, plan_id) is None
        assert db.get(TrackedApplication, tracked_id) is None
