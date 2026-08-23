"""Add structured contact fields to a user's optional resume export profile."""

from alembic import op
import sqlalchemy as sa


revision = "0020_export_profile"
down_revision = "0019_opp_unavailable"
branch_labels = None
depends_on = None


_COLUMNS = (
    ("email", 320),
    ("phone", 80),
    ("location", 160),
    ("linkedin_url", 500),
    ("github_url", 500),
)


def upgrade() -> None:
    # Existing developer databases may already be created from current ORM
    # metadata. Guard each addition to support both those databases and fresh
    # SQLite/PostgreSQL installations without destructive rebuilds.
    bind = op.get_bind()
    columns = {
        column["name"] for column in sa.inspect(bind).get_columns("applicant_profiles")
    }
    for name, length in _COLUMNS:
        if name not in columns:
            op.add_column(
                "applicant_profiles",
                sa.Column(name, sa.String(length=length), nullable=False, server_default=""),
            )


def downgrade() -> None:
    bind = op.get_bind()
    columns = {
        column["name"] for column in sa.inspect(bind).get_columns("applicant_profiles")
    }
    for name, _length in reversed(_COLUMNS):
        if name in columns:
            op.drop_column("applicant_profiles", name)
