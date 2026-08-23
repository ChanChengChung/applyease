"""persist research plans

Revision ID: 0013_research_plans
Revises: 0012_ai_usage_buckets
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_research_plans"
down_revision = "0012_ai_usage_buckets"
branch_labels = None
depends_on = None

def upgrade():
    # ``upgrade_database`` can adopt a pre-Alembic database by creating
    # current-model tables before stamping the baseline. Keep this migration
    # safe for that supported upgrade path as well as fresh installations.
    if "research_plans" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table("research_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profile_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("gaps", sa.JSON(), nullable=False), sa.Column("method", sa.JSON(), nullable=False), sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("used_fallback", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("searched_at", sa.DateTime(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_research_plans_user_id", "research_plans", ["user_id"])
    op.create_index("ix_research_plans_job_id", "research_plans", ["job_id"])
def downgrade():
    if "research_plans" not in sa.inspect(op.get_bind()).get_table_names():
        return
    op.drop_index("ix_research_plans_job_id", table_name="research_plans")
    op.drop_index("ix_research_plans_user_id", table_name="research_plans")
    op.drop_table("research_plans")
