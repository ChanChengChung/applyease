"""Add privacy-preserving AI invocation telemetry."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_ai_observability"
down_revision: Union[str, None] = "0003_auth_ownership"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "ai_invocations" not in inspector.get_table_names():
        op.create_table(
            "ai_invocations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("request_id", sa.String(36), nullable=False),
            sa.Column("event_type", sa.String(32), nullable=False),
            sa.Column("feature", sa.String(64), nullable=False),
            sa.Column("provider", sa.String(32), nullable=False),
            sa.Column("model", sa.String(120), nullable=False, server_default=""),
            sa.Column("prompt_version", sa.String(64), nullable=False),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("input_characters", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("output_characters", sa.Integer(), nullable=True),
            sa.Column("error_category", sa.String(64), nullable=True),
            sa.Column("fallback_from", sa.String(32), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
    existing_indexes = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("ai_invocations")}
    for column in ("user_id", "request_id", "feature", "status", "created_at"):
        if f"ix_ai_invocations_{column}" not in existing_indexes:
            op.create_index(f"ix_ai_invocations_{column}", "ai_invocations", [column])


def downgrade() -> None:
    op.drop_table("ai_invocations")
