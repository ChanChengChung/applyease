from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, create_engine, inspect, text

from app.db.session import Base
from app import models  # noqa: F401 - populate Base.metadata


BACKEND_DIR = Path(__file__).resolve().parents[2]


def alembic_config(database_url: str) -> Config:
    config = Config(str(BACKEND_DIR / "alembic.ini"))

    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))

    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))

    return config


def migration_status(engine: Engine) -> dict[str, str | bool | None]:
    config = alembic_config(str(engine.url))

    head = ScriptDirectory.from_config(config).get_current_head()

    with engine.connect() as connection:
        current = MigrationContext.configure(connection).get_current_revision()

    return {"current": current, "head": head, "up_to_date": current == head}


def _validate_legacy_schema(engine: Engine) -> None:
    inspector = inspect(engine)

    # Legacy databases may predate ownership. Add nullable columns so the

    # ownership migration can backfill them without rebuilding user data.

    with engine.begin() as connection:

        for table_name in (
            "documents",
            "experiences",
            "jobs",
            "generated_materials",
            "applications",
            "application_questions",
            "resource_progress",
            "tracked_applications",
        ):

            if table_name in inspector.get_table_names() and "user_id" not in {
                column["name"] for column in inspector.get_columns(table_name)
            }:
                connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN user_id INTEGER"))
    inspector = inspect(engine)

    actual_tables = set(inspector.get_table_names())

    expected_tables = set(Base.metadata.tables)

    missing_tables = expected_tables - actual_tables

    if missing_tables:
        Base.metadata.create_all(
            bind=engine, tables=[Base.metadata.tables[name] for name in sorted(missing_tables)]
        )

    inspector = inspect(engine)

    if "experiences" in inspector.get_table_names():
        columns = {column["name"] for column in inspector.get_columns("experiences")}

        if "document_id" not in columns:

            with engine.begin() as connection:
                connection.execute(text("ALTER TABLE experiences ADD COLUMN document_id INTEGER"))

                connection.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_experiences_document_id ON experiences (document_id)"
                    )
                )

        # Category was introduced after the first MVP schema.  Add a safe
        # project default before Alembic is stamped so an older local database
        # can be upgraded without dropping any user evidence.
        if "category" not in columns:
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "ALTER TABLE experiences ADD COLUMN category VARCHAR(40) "
                        "NOT NULL DEFAULT 'project'"
                    )
                )

    inspector = inspect(engine)

    incompatible: list[str] = []

    for table_name, table in Base.metadata.tables.items():

        if table_name not in inspector.get_table_names():
            incompatible.append(f"missing table {table_name}")

            continue
        actual_columns = {column["name"] for column in inspector.get_columns(table_name)}

        missing_columns = set(table.columns.keys()) - actual_columns

        if missing_columns:
            incompatible.append(
                f"{table_name} missing columns: {', '.join(sorted(missing_columns))}"
            )

    if incompatible:

        raise RuntimeError("Legacy database cannot be adopted safely: " + "; ".join(incompatible))


def upgrade_database(database_url: str) -> dict[str, str | bool | None]:
    engine = create_engine(database_url, pool_pre_ping=True)

    try:
        tables = set(inspect(engine).get_table_names())

        if tables and "alembic_version" not in tables:
            _validate_legacy_schema(engine)

            # Existing MVP tables represent the initial schema. Stamp only the

            # baseline so later repair migrations still run against legacy DBs.

            command.stamp(alembic_config(database_url), "0001_initial_schema")
        command.upgrade(alembic_config(database_url), "head")

        return migration_status(engine)

    finally:
        engine.dispose()


def check_database(database_url: str) -> dict[str, str | bool | None]:
    engine = create_engine(database_url, pool_pre_ping=True)

    try:

        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        return migration_status(engine)

    finally:
        engine.dispose()
