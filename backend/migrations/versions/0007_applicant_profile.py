"""Add per-user applicant profile for resume headers."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007_applicant_profile"
down_revision: Union[str, None] = "0006_account_lifecycle"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if "applicant_profiles" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "applicant_profiles",
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("display_name", sa.String(length=100), nullable=False),
            sa.Column("contact_line", sa.String(length=300), nullable=False, server_default=""),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )


def downgrade() -> None:
    op.drop_table("applicant_profiles")
