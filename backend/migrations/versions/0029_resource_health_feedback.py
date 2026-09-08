"""Restore curated-resource health and feedback persistence for deployed APIs."""

from alembic import op
import sqlalchemy as sa


revision = "0029_resource_health_feedback"
down_revision = "0028_advisor_structured_replies"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {item["name"] for item in inspector.get_columns("learning_resources")}
    if "link_status" not in columns:
        op.add_column(
            "learning_resources",
            sa.Column("link_status", sa.String(length=20), nullable=False, server_default="unchecked"),
        )
    if "last_checked_at" not in columns:
        op.add_column("learning_resources", sa.Column("last_checked_at", sa.DateTime(), nullable=True))
    inspector = sa.inspect(bind)
    if "resource_feedback" not in inspector.get_table_names():
        op.create_table(
            "resource_feedback",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("resource_id", sa.Integer(), sa.ForeignKey("learning_resources.id", ondelete="CASCADE"), nullable=False),
            sa.Column("category", sa.String(length=30), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
    indexes = {item["name"] for item in sa.inspect(bind).get_indexes("resource_feedback")}
    if "ix_resource_feedback_user_id" not in indexes:
        op.create_index("ix_resource_feedback_user_id", "resource_feedback", ["user_id"])
    if "ix_resource_feedback_resource_id" not in indexes:
        op.create_index("ix_resource_feedback_resource_id", "resource_feedback", ["resource_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "resource_feedback" in inspector.get_table_names():
        for name in ("ix_resource_feedback_resource_id", "ix_resource_feedback_user_id"):
            if name in {item["name"] for item in inspector.get_indexes("resource_feedback")}:
                op.drop_index(name, table_name="resource_feedback")
        op.drop_table("resource_feedback")
    columns = {item["name"] for item in sa.inspect(bind).get_columns("learning_resources")}
    if "last_checked_at" in columns:
        op.drop_column("learning_resources", "last_checked_at")
    if "link_status" in columns:
        op.drop_column("learning_resources", "link_status")
