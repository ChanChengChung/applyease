"""Persist starter-plan milestone phase membership."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0025_starter_milestone_sections"
down_revision = "0024_deadline_reminders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("starter_learning_plans")}
    if "milestone_sections" not in columns:
        op.add_column(
            "starter_learning_plans",
            sa.Column("milestone_sections", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        )


def downgrade() -> None:
    columns = {column["name"] for column in inspect(op.get_bind()).get_columns("starter_learning_plans")}
    if "milestone_sections" in columns:
        op.drop_column("starter_learning_plans", "milestone_sections")
