"""Persist structured, evidence-grounded advisor reply metadata."""

from alembic import op
import sqlalchemy as sa


revision = "0028_advisor_structured_replies"
down_revision = "0027_research_plan_starter_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = {column["name"] for column in inspector.get_columns("advisor_conversation_messages")}
    additions = [
        ("summary", sa.Text(), ""),
        ("evidence", sa.JSON(), "[]"),
        ("gaps", sa.JSON(), "[]"),
        ("next_actions", sa.JSON(), "[]"),
        ("mode", sa.String(length=16), "ai"),
    ]
    missing = [(name, column, default) for name, column, default in additions if name not in existing]
    if missing:
        # Batch mode works for SQLite demo databases and PostgreSQL alike.
        with op.batch_alter_table("advisor_conversation_messages", recreate="always") as batch:
            for name, column, default in missing:
                batch.add_column(
                    sa.Column(name, column, nullable=False, server_default=sa.text(repr(default)))
                )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("advisor_conversation_messages")}
    removable = [name for name in ("mode", "next_actions", "gaps", "evidence", "summary") if name in columns]
    if removable:
        with op.batch_alter_table("advisor_conversation_messages", recreate="always") as batch:
            for name in removable:
                batch.drop_column(name)
