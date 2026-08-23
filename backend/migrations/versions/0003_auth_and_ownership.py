"""Add users and ownership columns for multi-user isolation."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003_auth_ownership"
down_revision: Union[str, None] = "0002_experience_document_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OWNED = ("documents", "experiences", "jobs", "generated_materials", "applications", "application_questions", "resource_progress", "tracked_applications")


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "users" not in inspector.get_table_names():
        op.create_table("users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("email", sa.String(320), nullable=False),
            sa.Column("password_hash", sa.String(255), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("email", name="uq_users_email"))
    if not any(index["name"] == "ix_users_email" for index in sa.inspect(op.get_bind()).get_indexes("users")):
        op.create_index("ix_users_email", "users", ["email"])
    bind = op.get_bind()
    # Preserve existing local single-user data under a deterministic owner.
    if bind.execute(sa.text("SELECT id FROM users WHERE email='local@applyease.dev'")).first() is None:
        bind.execute(sa.text("INSERT INTO users (email, password_hash, is_active, created_at) VALUES ('local@applyease.dev', 'legacy-account', TRUE, CURRENT_TIMESTAMP)"))
    owner_id = bind.execute(sa.text("SELECT id FROM users WHERE email='local@applyease.dev'")).scalar_one()
    for table in OWNED:
        columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}
        if "user_id" not in columns:
            with op.batch_alter_table(table) as batch:
                batch.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table)}
        with op.batch_alter_table(table) as batch:
            if f"ix_{table}_user_id" not in indexes:
                batch.create_index(f"ix_{table}_user_id", ["user_id"])
            foreign_keys = sa.inspect(op.get_bind()).get_foreign_keys(table)
            if not any(key.get("name") == f"fk_{table}_user_id_users" for key in foreign_keys):
                batch.create_foreign_key(f"fk_{table}_user_id_users", "users", ["user_id"], ["id"], ondelete="CASCADE")
        bind.execute(sa.text(f"UPDATE {table} SET user_id = :owner WHERE user_id IS NULL"), {"owner": owner_id})
        with op.batch_alter_table(table) as batch:
            batch.alter_column("user_id", existing_type=sa.Integer(), nullable=False)
    constraints = {item.get("name") for item in sa.inspect(op.get_bind()).get_unique_constraints("documents")}
    with op.batch_alter_table("documents") as batch:
        if "uq_documents_sha256" in constraints:
            batch.drop_constraint("uq_documents_sha256", type_="unique")
        if "uq_documents_user_sha256" not in constraints:
            batch.create_unique_constraint("uq_documents_user_sha256", ["user_id", "sha256"])
    progress_constraints = {item.get("name") for item in sa.inspect(op.get_bind()).get_unique_constraints("resource_progress")}
    if "uq_resource_progress_user_resource" not in progress_constraints:
        with op.batch_alter_table("resource_progress") as batch:
            batch.create_unique_constraint("uq_resource_progress_user_resource", ["user_id", "resource_id"])


def downgrade() -> None:
    with op.batch_alter_table("resource_progress") as batch:
        batch.drop_constraint("uq_resource_progress_user_resource", type_="unique")
    with op.batch_alter_table("documents") as batch:
        batch.drop_constraint("uq_documents_user_sha256", type_="unique")
        batch.create_unique_constraint("uq_documents_sha256", ["sha256"])
    for table in reversed(OWNED):
        with op.batch_alter_table(table) as batch:
            batch.alter_column("user_id", existing_type=sa.Integer(), nullable=True)
            batch.drop_constraint(f"fk_{table}_user_id_users", type_="foreignkey")
            batch.drop_index(f"ix_{table}_user_id")
            batch.drop_column("user_id")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
