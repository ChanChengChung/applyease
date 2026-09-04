"""Persist structured interview reflections on tracker records."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0023_tracker_interview_review"
down_revision = "0022_opportunity_modes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {
        column["name"]
        for column in inspect(op.get_bind()).get_columns("tracked_applications")
    }
    if "interview_review" in columns:
        return
    op.add_column(
        "tracked_applications",
        sa.Column("interview_review", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tracked_applications", "interview_review")
