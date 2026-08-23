"""Store a durable category for each piece of application evidence.

Revision ID: 0016_experience_categories
Revises: 0015_opportunity_radar
"""
from alembic import op
import sqlalchemy as sa


revision = "0016_experience_categories"
down_revision = "0015_opportunity_radar"
branch_labels = None
depends_on = None


def upgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("experiences")}
    if "category" not in columns:
        op.add_column(
            "experiences",
            sa.Column("category", sa.String(length=40), nullable=False, server_default="project"),
        )


def downgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("experiences")}
    if "category" in columns:
        op.drop_column("experiences", "category")
