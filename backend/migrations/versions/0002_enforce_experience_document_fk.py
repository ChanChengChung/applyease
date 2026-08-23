"""Ensure legacy experience records have the document foreign key.

Revision ID: 0002_experience_document_fk
Revises: 0001_initial_schema
Create Date: 2026-08-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_experience_document_fk"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_document_fk() -> bool:
    foreign_keys = sa.inspect(op.get_bind()).get_foreign_keys("experiences")
    return any(key.get("referred_table") == "documents" and key.get("constrained_columns") == ["document_id"] for key in foreign_keys)


def upgrade() -> None:
    if not _has_document_fk():
        with op.batch_alter_table("experiences") as batch:
            batch.create_foreign_key("fk_experiences_document_id_documents", "documents", ["document_id"], ["id"], ondelete="CASCADE")


def downgrade() -> None:
    foreign_keys = sa.inspect(op.get_bind()).get_foreign_keys("experiences")
    if any(key.get("name") == "fk_experiences_document_id_documents" for key in foreign_keys):
        with op.batch_alter_table("experiences") as batch:
            batch.drop_constraint("fk_experiences_document_id_documents", type_="foreignkey")
