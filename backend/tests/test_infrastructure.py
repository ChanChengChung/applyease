from sqlalchemy import create_engine, inspect, text
from fastapi.testclient import TestClient
import pytest

from app.config import Settings
from app.db.migrations import check_database, upgrade_database
from app.db.session import Base
from app import models  # noqa: F401
from app.main import app


def test_settings_reject_invalid_and_unsafe_production_configuration():

    with pytest.raises(ValueError, match="PostgreSQL"):
        Settings(_env_file=None, app_env="production", database_url="sqlite:///prod.db")

    with pytest.raises(ValueError, match="default development credentials"):
        Settings(
            _env_file=None,
            app_env="production",
            database_url="postgresql+psycopg://applyease:applyease@db/applyease",
        )

    with pytest.raises(ValueError, match="HTTP"):
        Settings(_env_file=None, cors_origins="chrome-extension://unsafe")
    secure_database = "postgresql+psycopg://user:strong-password@db/applyease"

    with pytest.raises(ValueError, match="AUTH_COOKIE_SECURE"):
        Settings(
            _env_file=None,
            app_env="production",
            database_url=secure_database,
            auth_secret="x" * 32,
            cors_origins="https://app.example.com",
        )

    with pytest.raises(ValueError, match="ENFORCE_HTTPS"):
        Settings(
            _env_file=None,
            app_env="production",
            database_url=secure_database,
            auth_secret="x" * 32,
            auth_cookie_secure=True,
            cors_origins="https://app.example.com",
        )

    with pytest.raises(ValueError, match="ALLOWED_HOSTS"):
        Settings(
            _env_file=None,
            app_env="production",
            database_url=secure_database,
            auth_secret="x" * 32,
            auth_cookie_secure=True,
            enforce_https=True,
            allowed_hosts="*",
            cors_origins="https://app.example.com",
        )

    with pytest.raises(ValueError, match="SCREENSHOT_OCR_ENABLED"):
        Settings(
            _env_file=None,
            app_env="production",
            database_url=secure_database,
            auth_secret="x" * 32,
            auth_cookie_secure=True,
            enforce_https=True,
            allowed_hosts="app.example.com",
            cors_origins="https://app.example.com",
            frontend_base_url="https://app.example.com",
            mail_delivery_mode="smtp",
            smtp_host="smtp.example.com",
            auth_require_verified_email=True,
            app_version="v1.0.0",
            screenshot_ocr_enabled=True,
            gemini_api_key="",
        )

    with pytest.raises(ValueError, match="APP_VERSION"):
        Settings(
            _env_file=None,
            app_env="production",
            database_url=secure_database,
            auth_secret="x" * 32,
            auth_cookie_secure=True,
            enforce_https=True,
            allowed_hosts="app.example.com",
            cors_origins="https://app.example.com",
            frontend_base_url="https://app.example.com",
            mail_delivery_mode="smtp",
            smtp_host="smtp.example.com",
            auth_require_verified_email=True,
            app_version="unversioned",
        )


def test_empty_database_upgrades_to_head(tmp_path):
    url = f"sqlite:///{tmp_path / 'empty.db'}"

    result = upgrade_database(url)

    assert result["up_to_date"] is True

    engine = create_engine(url)

    assert set(Base.metadata.tables).issubset(inspect(engine).get_table_names())

    assert check_database(url)["current"] == "0022_opportunity_modes"

    engine.dispose()


def test_legacy_database_is_adopted_without_losing_data(tmp_path):
    url = f"sqlite:///{tmp_path / 'legacy.db'}"

    engine = create_engine(url)

    Base.metadata.create_all(engine)

    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (email, password_hash, is_active, created_at) VALUES ('legacy@example.com', 'legacy', 1, CURRENT_TIMESTAMP)"
            )
        )

        connection.execute(
            text(
                "INSERT INTO jobs (user_id, title, company, description, required_skills, preferred_skills, responsibilities, qualifications, created_at) VALUES (1, 'AI Intern', 'Polymer', 'Demo role', '[]', '[]', '[]', '[]', CURRENT_TIMESTAMP)"
            )
        )
    engine.dispose()

    result = upgrade_database(url)

    assert result["up_to_date"] is True

    engine = create_engine(url)

    with engine.connect() as connection:
        assert connection.execute(text("SELECT title FROM jobs")).scalar_one() == "AI Intern"
    assert any(
        key.get("referred_table") == "documents"
        for key in inspect(engine).get_foreign_keys("experiences")
    )

    engine.dispose()


def test_older_legacy_database_gets_document_link_without_rebuilding_experiences(tmp_path):
    url = f"sqlite:///{tmp_path / 'older-legacy.db'}"

    engine = create_engine(url)

    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE experiences (id INTEGER PRIMARY KEY, title VARCHAR(200) NOT NULL, organization VARCHAR(200) NOT NULL, description TEXT NOT NULL, skills JSON NOT NULL, achievements JSON NOT NULL, source_file VARCHAR(255) NOT NULL, confirmed BOOLEAN NOT NULL, created_at DATETIME NOT NULL)"
            )
        )

        connection.execute(
            text(
                "INSERT INTO experiences VALUES (1, 'Project', 'HKU', 'Built a tool', '[]', '[]', 'CV.pdf', 1, CURRENT_TIMESTAMP)"
            )
        )
    engine.dispose()

    assert upgrade_database(url)["up_to_date"] is True

    engine = create_engine(url)

    assert "document_id" in {
        column["name"] for column in inspect(engine).get_columns("experiences")
    }

    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT title FROM experiences WHERE id=1")).scalar_one()
            == "Project"
        )
    assert any(
        key.get("referred_table") == "documents"
        for key in inspect(engine).get_foreign_keys("experiences")
    )

    engine.dispose()


def test_health_endpoints_separate_liveness_and_readiness():
    client = TestClient(app)

    assert client.get("/health").json() == {"status": "ok"}

    assert client.get("/health/live").status_code == 200

    assert client.head("/health/live").status_code == 200

    # Test databases are intentionally created without stamping a production migration.

    response = client.get("/health/ready")

    assert response.status_code == 503

    assert "migration" in response.json()["detail"].lower()
