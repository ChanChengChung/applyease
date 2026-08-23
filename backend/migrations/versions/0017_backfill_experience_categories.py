"""Classify pre-category Experience Bank records conservatively.

Revision ID: 0017_exp_category_backfill
Revises: 0016_experience_categories
"""
from alembic import op
import sqlalchemy as sa


revision = "0017_exp_category_backfill"
down_revision = "0016_experience_categories"
branch_labels = None
depends_on = None


def upgrade():
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("experiences")}
    if "category" not in columns:
        return

    # Existing records received the safe 'project' default in 0016.  Reclassify
    # only when the stored evidence contains an unambiguous factual cue; every
    # uncertain record deliberately remains a project for user review.
    op.execute(
        sa.text(
            """
            UPDATE experiences
            SET category = CASE
              WHEN lower(coalesce(title, '') || ' ' || coalesce(organization, '') || ' ' || coalesce(description, ''))
                   LIKE '%university%'
                OR lower(coalesce(title, '') || ' ' || coalesce(organization, '') || ' ' || coalesce(description, ''))
                   LIKE '%bachelor%'
                OR lower(coalesce(title, '') || ' ' || coalesce(organization, '') || ' ' || coalesce(description, ''))
                   LIKE '%master%'
                OR lower(coalesce(title, '') || ' ' || coalesce(organization, '') || ' ' || coalesce(description, ''))
                   LIKE '%bsc%'
                OR lower(coalesce(title, '') || ' ' || coalesce(organization, '') || ' ' || coalesce(description, ''))
                   LIKE '%education%' THEN 'education'
              WHEN lower(coalesce(title, '') || ' ' || coalesce(organization, '') || ' ' || coalesce(description, ''))
                   LIKE '%research%'
                OR lower(coalesce(title, '') || ' ' || coalesce(organization, '') || ' ' || coalesce(description, ''))
                   LIKE '%laboratory%'
                OR lower(coalesce(title, '') || ' ' || coalesce(organization, '') || ' ' || coalesce(description, ''))
                   LIKE '%research assistant%' THEN 'research'
              WHEN lower(coalesce(title, '') || ' ' || coalesce(organization, '') || ' ' || coalesce(description, ''))
                   LIKE '%intern%'
                OR lower(coalesce(title, '') || ' ' || coalesce(organization, '') || ' ' || coalesce(description, ''))
                   LIKE '%work experience%' THEN 'internship'
              WHEN lower(coalesce(title, '') || ' ' || coalesce(organization, '') || ' ' || coalesce(description, ''))
                   LIKE '%leadership%'
                OR lower(coalesce(title, '') || ' ' || coalesce(organization, '') || ' ' || coalesce(description, ''))
                   LIKE '%president%'
                OR lower(coalesce(title, '') || ' ' || coalesce(organization, '') || ' ' || coalesce(description, ''))
                   LIKE '%committee%' THEN 'leadership'
              ELSE 'project'
            END
            WHERE category = 'project'
            """
        )
    )


def downgrade():
    # Category changes are intentionally retained; a downgrade must not erase
    # user-reviewable organization of the evidence library.
    pass
