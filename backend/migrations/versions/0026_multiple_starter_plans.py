"""Allow users to keep more than one starter learning plan."""

from alembic import op
from sqlalchemy import inspect


revision = "0026_multiple_starter_plans"
down_revision = "0025_starter_milestone_sections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    constraints = inspect(op.get_bind()).get_unique_constraints("starter_learning_plans")
    if any(item.get("name") == "uq_starter_learning_plans_user_id" for item in constraints):
        # SQLite cannot ALTER a table constraint in place.  Alembic's batch
        # implementation performs the safe copy-and-move operation there and
        # remains a no-op-compatible path on PostgreSQL.
        with op.batch_alter_table("starter_learning_plans", recreate="always") as batch:
            batch.drop_constraint("uq_starter_learning_plans_user_id", type_="unique")


def downgrade() -> None:
    constraints = inspect(op.get_bind()).get_unique_constraints("starter_learning_plans")
    if not any(item.get("name") == "uq_starter_learning_plans_user_id" for item in constraints):
        with op.batch_alter_table("starter_learning_plans", recreate="always") as batch:
            batch.create_unique_constraint(
                "uq_starter_learning_plans_user_id",
                ["user_id"],
            )
