"""Persist user-owned advisor conversation history.

Revision ID: 0014_advisor_history
Revises: 0013_research_plans
"""
from alembic import op
import sqlalchemy as sa


revision = "0014_advisor_history"
down_revision = "0013_research_plans"
branch_labels = None
depends_on = None


def upgrade():
    if "advisor_conversation_messages" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "advisor_conversation_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("suggested_prompts", sa.JSON(), nullable=False),
        sa.Column("used_fallback", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_advisor_conversation_messages_user_id", "advisor_conversation_messages", ["user_id"])


def downgrade():
    if "advisor_conversation_messages" not in sa.inspect(op.get_bind()).get_table_names():
        return
    op.drop_index("ix_advisor_conversation_messages_user_id", table_name="advisor_conversation_messages")
    op.drop_table("advisor_conversation_messages")
