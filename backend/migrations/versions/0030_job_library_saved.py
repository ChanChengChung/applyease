"""Track explicit promotion of reviewed roles into the role library."""

from alembic import op
import sqlalchemy as sa

revision = "0030_job_library_saved"
down_revision = "0029_resource_health_feedback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "library_saved" not in {item["name"] for item in inspector.get_columns("jobs")}:
        op.add_column(
            "jobs",
            sa.Column("library_saved", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "library_saved" in {item["name"] for item in inspector.get_columns("jobs")}:
        op.drop_column("jobs", "library_saved")
