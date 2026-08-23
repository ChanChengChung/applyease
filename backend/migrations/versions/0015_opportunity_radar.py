"""Persist user-owned, source-audited opportunity research.

Revision ID: 0015_opportunity_radar
Revises: 0014_advisor_history
"""
from alembic import op
import sqlalchemy as sa


revision = "0015_opportunity_radar"
down_revision = "0014_advisor_history"
branch_labels = None
depends_on = None


def upgrade():
    if "opportunity_searches" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "opportunity_searches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("career_goal", sa.Text(), nullable=False),
        sa.Column("location", sa.String(length=160), nullable=False),
        sa.Column("work_preference", sa.String(length=40), nullable=False),
        sa.Column("timing", sa.String(length=160), nullable=False),
        sa.Column("language", sa.String(length=12), nullable=False),
        sa.Column("opportunities", sa.JSON(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("used_fallback", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_opportunity_searches_user_id", "opportunity_searches", ["user_id"])


def downgrade():
    if "opportunity_searches" not in sa.inspect(op.get_bind()).get_table_names():
        return
    op.drop_index("ix_opportunity_searches_user_id", table_name="opportunity_searches")
    op.drop_table("opportunity_searches")
