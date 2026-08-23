"""Add user resource feedback."""
from alembic import op
import sqlalchemy as sa

revision = "0010_resource_feedback"
down_revision = "0009_resource_health"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
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
        inspector = sa.inspect(op.get_bind())
    indexes = {item["name"] for item in inspector.get_indexes("resource_feedback")}
    if "ix_resource_feedback_user_id" not in indexes:
        op.create_index("ix_resource_feedback_user_id", "resource_feedback", ["user_id"])
    if "ix_resource_feedback_resource_id" not in indexes:
        op.create_index("ix_resource_feedback_resource_id", "resource_feedback", ["resource_id"])


def downgrade():
    if "resource_feedback" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("resource_feedback")
