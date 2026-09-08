"""Make analysed-job defaults safe for direct and legacy inserts."""

from alembic import op
import sqlalchemy as sa


revision = "0033_job_source_url_default"
down_revision = "0032_job_source_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("jobs")}
    if "source_url" not in columns:
        op.add_column(
            "jobs",
            sa.Column("source_url", sa.String(length=2048), nullable=True, server_default=""),
        )
    op.execute(sa.text("UPDATE jobs SET source_url = '' WHERE source_url IS NULL"))
    op.execute(sa.text("UPDATE jobs SET library_saved = FALSE WHERE library_saved IS NULL"))
    # Keep legacy databases readable without a table rewrite.  New ORM rows
    # and fresh schemas use the server default; response serialization also
    # normalises any externally-created legacy NULL value to an empty string.
    if bind.dialect.name != "sqlite":
        op.alter_column("jobs", "source_url", server_default="")
        op.alter_column("jobs", "library_saved", server_default=sa.text("false"))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.alter_column("jobs", "source_url", server_default=None)
