"""Persist the category selected for an opportunity search."""

from alembic import op
import sqlalchemy as sa


revision = "0034_opportunity_search_category"
down_revision = "0033_job_source_url_default"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("opportunity_searches")}
    if "career_category" not in columns:
        op.add_column("opportunity_searches", sa.Column("career_category", sa.String(length=40), nullable=True, server_default=""))
    op.execute(sa.text("UPDATE opportunity_searches SET career_category = '' WHERE career_category IS NULL"))
    if bind.dialect.name != "sqlite":
        op.alter_column("opportunity_searches", "career_category", server_default="")


def downgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in sa.inspect(bind).get_columns("opportunity_searches")}
    if "career_category" in columns:
        op.drop_column("opportunity_searches", "career_category")
