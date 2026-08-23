"""Add durable per-account AI request quota buckets."""

from alembic import op
import sqlalchemy as sa


revision = "0012_ai_usage_buckets"
down_revision = "0011_learning_rag"
branch_labels = None
depends_on = None


def upgrade():
    # ``upgrade_database`` can adopt an old pre-Alembic database by creating
    # missing current-model tables before stamping its baseline.  Keep this
    # migration idempotent for that supported legacy path.
    if "ai_usage_buckets" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "ai_usage_buckets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("window_started_at", sa.DateTime(), nullable=False),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("user_id", "category", name="uq_ai_usage_buckets_user_category"),
    )
    op.create_index("ix_ai_usage_buckets_user_id", "ai_usage_buckets", ["user_id"])
    op.create_index("ix_ai_usage_buckets_window_started_at", "ai_usage_buckets", ["window_started_at"])


def downgrade():
    if "ai_usage_buckets" not in sa.inspect(op.get_bind()).get_table_names():
        return
    op.drop_index("ix_ai_usage_buckets_window_started_at", table_name="ai_usage_buckets")
    op.drop_index("ix_ai_usage_buckets_user_id", table_name="ai_usage_buckets")
    op.drop_table("ai_usage_buckets")
