"""Record the exact evidence selected for Opportunity Radar searches.

Revision ID: 0018_opp_evidence_ids
Revises: 0017_exp_category_backfill
"""

from alembic import op
import sqlalchemy as sa


revision = "0018_opp_evidence_ids"
down_revision = "0017_exp_category_backfill"
branch_labels = None
depends_on = None


def upgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("opportunity_searches")}
    if "experience_ids" not in columns:
        op.add_column(
            "opportunity_searches",
            sa.Column("experience_ids", sa.JSON(), nullable=False, server_default="[]"),
        )


def downgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("opportunity_searches")}
    if "experience_ids" in columns:
        op.drop_column("opportunity_searches", "experience_ids")
