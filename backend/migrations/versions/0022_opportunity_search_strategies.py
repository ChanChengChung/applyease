"""Persist Opportunity Radar strategy choices and outcomes.

Revision ID: 0022_opportunity_search_strategies
Revises: 0021_starter_learning_plans
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0022_opportunity_modes"
down_revision = "0021_starter_learning_plans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {
        column["name"]
        for column in inspect(op.get_bind()).get_columns("opportunity_searches")
    }
    if "search_modes" not in columns:
        op.add_column("opportunity_searches", sa.Column("search_modes", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))
    if "strategy_outcomes" not in columns:
        op.add_column("opportunity_searches", sa.Column("strategy_outcomes", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))


def downgrade() -> None:
    op.drop_column("opportunity_searches", "strategy_outcomes")
    op.drop_column("opportunity_searches", "search_modes")
