"""Add encrypted TOTP MFA configuration and hashed recovery codes."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0008_mfa"
down_revision: Union[str, None] = "0007_applicant_profile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "mfa_configurations" not in inspector.get_table_names():
        op.create_table("mfa_configurations",
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("encrypted_secret", sa.String(length=512), nullable=False),
            sa.Column("enabled_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False))
    if "mfa_recovery_codes" not in inspector.get_table_names():
        op.create_table("mfa_recovery_codes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("code_hash", sa.String(length=64), nullable=False, unique=True),
            sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("consumed_at", sa.DateTime(), nullable=True))
        op.create_index("ix_mfa_recovery_codes_user_id", "mfa_recovery_codes", ["user_id"])
        op.create_index("ix_mfa_recovery_codes_code_hash", "mfa_recovery_codes", ["code_hash"], unique=True)


def downgrade() -> None:
    op.drop_table("mfa_recovery_codes")
    op.drop_table("mfa_configurations")
