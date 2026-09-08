"""Preserve public posting URLs on analysed jobs."""

from alembic import op
import sqlalchemy as sa

revision = "0032_job_source_url"
down_revision = "0031_research_plan_focuses"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("jobs")}
    if "source_url" not in columns:
        # A direct ALTER keeps PostgreSQL foreign-key dependencies on jobs.id
        # intact; batch table recreation would attempt to drop jobs_pkey.
        op.add_column("jobs", sa.Column("source_url", sa.String(length=2048), nullable=True))
    op.execute(sa.text("UPDATE jobs SET source_url = '' WHERE source_url IS NULL"))


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("jobs")}
    if "source_url" in columns:
        op.drop_column("jobs", "source_url")
