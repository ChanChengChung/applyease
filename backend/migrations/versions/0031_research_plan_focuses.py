"""Persist explicit role reinforcement directions."""

from alembic import op
import sqlalchemy as sa

revision = "0031_research_plan_focuses"
down_revision = "0030_job_library_saved"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("research_plans")}
    if "focuses" not in columns:
        with op.batch_alter_table("research_plans", recreate="always") as batch:
            batch.add_column(sa.Column("focuses", sa.JSON(), nullable=True))
    op.execute(sa.text("UPDATE research_plans SET focuses = '[]' WHERE focuses IS NULL"))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("research_plans")}
    if "focuses" in columns:
        with op.batch_alter_table("research_plans", recreate="always") as batch:
            batch.drop_column("focuses")
