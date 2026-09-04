"""Add timezone-aware deadline reminder preferences and delivery ledger."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "0024_deadline_reminders"
down_revision = "0023_tracker_interview_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    additions = [
        ("timezone", sa.String(length=64), "'UTC'"),
        ("deadline_reminders_enabled", sa.Boolean(), "TRUE"),
        ("deadline_reminder_days", sa.Integer(), "7"),
        ("deadline_reminder_hour", sa.Integer(), "9"),
    ]
    for name, column_type, default in additions:
        if name not in user_columns:
            op.add_column(
                "users",
                sa.Column(
                    name,
                    column_type,
                    nullable=False,
                    server_default=sa.text(default),
                ),
            )

    if "deadline_reminder_deliveries" not in inspector.get_table_names():
        op.create_table(
            "deadline_reminder_deliveries",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("tracked_application_id", sa.Integer(), nullable=False),
            sa.Column("kind", sa.String(length=32), nullable=False, server_default="deadline"),
            sa.Column("due_date", sa.Date(), nullable=False),
            sa.Column("sent_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["tracked_application_id"],
                ["tracked_applications.id"],
                ondelete="CASCADE",
            ),
            sa.UniqueConstraint(
                "user_id",
                "tracked_application_id",
                "kind",
                "due_date",
                name="uq_deadline_reminder_delivery",
            ),
        )
        op.create_index(
            "ix_deadline_reminder_deliveries_user_id",
            "deadline_reminder_deliveries",
            ["user_id"],
        )
        op.create_index(
            "ix_deadline_reminder_deliveries_tracked_application_id",
            "deadline_reminder_deliveries",
            ["tracked_application_id"],
        )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    if "deadline_reminder_deliveries" in inspector.get_table_names():
        op.drop_table("deadline_reminder_deliveries")
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    for name in (
        "deadline_reminder_hour",
        "deadline_reminder_days",
        "deadline_reminders_enabled",
        "timezone",
    ):
        if name in user_columns:
            op.drop_column("users", name)
