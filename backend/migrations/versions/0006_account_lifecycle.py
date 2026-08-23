"""Add email verification and one-time account lifecycle tokens."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_account_lifecycle"
down_revision: Union[str, None] = "0005_security_hardening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "email_verified_at" not in user_columns:
        with op.batch_alter_table("users") as batch:
            batch.add_column(sa.Column("email_verified_at", sa.DateTime(), nullable=True))
    # Accounts predating verification remain usable after the migration.
    op.execute("UPDATE users SET email_verified_at = created_at WHERE email_verified_at IS NULL")

    if "account_tokens" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "account_tokens",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("purpose", sa.String(32), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("consumed_at", sa.DateTime(), nullable=True),
        )
    existing = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes("account_tokens")}
    for column in ("user_id", "purpose", "token_hash", "expires_at"):
        name = f"ix_account_tokens_{column}"
        if name not in existing:
            op.create_index(name, "account_tokens", [column], unique=column == "token_hash")


def downgrade() -> None:
    op.drop_table("account_tokens")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("email_verified_at")
