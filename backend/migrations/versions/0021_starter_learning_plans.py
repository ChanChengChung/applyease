"""Persist no-CV starter learning plans.

Revision ID: 0021_starter_learning_plans
Revises: 0020_export_profile
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0021_starter_learning_plans"
down_revision = "0020_export_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Legacy database adoption may materialize tables from the current ORM
    # metadata before Alembic replays post-baseline repair migrations. Keep
    # this migration safe to replay in that path.
    if "starter_learning_plans" in inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "starter_learning_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("interest", sa.Text(), nullable=False),
        sa.Column("focus", sa.String(length=300), nullable=False),
        sa.Column("headline", sa.Text(), nullable=False),
        sa.Column("first_action", sa.Text(), nullable=False),
        sa.Column("milestones", sa.JSON(), nullable=False),
        sa.Column("resource_ids", sa.JSON(), nullable=False),
        sa.Column("used_fallback", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_starter_learning_plans_user_id"),
    )
    op.create_index("ix_starter_learning_plans_user_id", "starter_learning_plans", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_starter_learning_plans_user_id", table_name="starter_learning_plans")
    op.drop_table("starter_learning_plans")
