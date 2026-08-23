"""Store a transparent reason when an opportunity web search cannot run."""

from alembic import op
import sqlalchemy as sa


revision = "0019_opp_unavailable"
down_revision = "0018_opp_evidence_ids"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Some development databases were created directly from the current ORM
    # metadata before Alembic was introduced.  Guarding this migration keeps
    # both those databases and a fresh SQLite test database upgradeable.
    bind = op.get_bind()
    columns = {
        column["name"]
        for column in sa.inspect(bind).get_columns("opportunity_searches")
    }
    if "unavailable_reason" not in columns:
        op.add_column(
            "opportunity_searches",
            sa.Column(
                "unavailable_reason",
                sa.String(length=80),
                nullable=False,
                server_default="",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    columns = {
        column["name"]
        for column in sa.inspect(bind).get_columns("opportunity_searches")
    }
    if "unavailable_reason" in columns:
        op.drop_column("opportunity_searches", "unavailable_reason")
