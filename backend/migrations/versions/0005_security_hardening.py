"""Add revocable auth sessions and privacy-preserving security audit events."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_security_hardening"
down_revision: Union[str, None] = "0004_ai_observability"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _indexes(table: str) -> set[str]:
    return {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "auth_sessions" not in tables:
        op.create_table("auth_sessions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("csrf_hash", sa.String(64), nullable=False),
            sa.Column("user_agent_hash", sa.String(64), nullable=False, server_default=""),
            sa.Column("ip_hash", sa.String(64), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("revoked_at", sa.DateTime(), nullable=True))
    existing = _indexes("auth_sessions")
    for column in ("user_id", "token_hash", "expires_at"):
        name = f"ix_auth_sessions_{column}"
        if name not in existing:
            op.create_index(name, "auth_sessions", [column], unique=column == "token_hash")
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "security_audits" not in tables:
        op.create_table("security_audits",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("event_type", sa.String(48), nullable=False),
            sa.Column("outcome", sa.String(24), nullable=False),
            sa.Column("subject_hash", sa.String(64), nullable=False, server_default=""),
            sa.Column("ip_hash", sa.String(64), nullable=False, server_default=""),
            sa.Column("user_agent_hash", sa.String(64), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False))
    existing = _indexes("security_audits")
    for column in ("user_id", "event_type", "outcome", "subject_hash", "ip_hash", "created_at"):
        name = f"ix_security_audits_{column}"
        if name not in existing:
            op.create_index(name, "security_audits", [column])


def downgrade() -> None:
    op.drop_table("security_audits")
    op.drop_table("auth_sessions")
