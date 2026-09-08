"""Link role research plans to the starter plan used to generate them."""

from alembic import op
import sqlalchemy as sa


revision = "0027_research_plan_starter_link"
down_revision = "0026_multiple_starter_plans"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("research_plans")}
    if "starter_plan_id" not in columns:
        # batch mode keeps this migration compatible with the SQLite database
        # used by local demos and the test suite.
        with op.batch_alter_table("research_plans", recreate="always") as batch:
            batch.add_column(sa.Column("starter_plan_id", sa.Integer(), nullable=True))
            batch.create_foreign_key(
                "fk_research_plans_starter_plan_id",
                "starter_learning_plans",
                ["starter_plan_id"],
                ["id"],
                ondelete="SET NULL",
            )
    else:
        foreign_keys = {
            constraint.get("name")
            for constraint in inspector.get_foreign_keys("research_plans")
        }
        if "fk_research_plans_starter_plan_id" not in foreign_keys:
            with op.batch_alter_table("research_plans") as batch:
                batch.create_foreign_key(
                    "fk_research_plans_starter_plan_id",
                    "starter_learning_plans",
                    ["starter_plan_id"],
                    ["id"],
                    ondelete="SET NULL",
                )
    indexes = {index.get("name") for index in inspector.get_indexes("research_plans")}
    if "ix_research_plans_starter_plan_id" not in indexes:
        op.create_index(
            "ix_research_plans_starter_plan_id",
            "research_plans",
            ["starter_plan_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {index.get("name") for index in inspector.get_indexes("research_plans")}
    if "ix_research_plans_starter_plan_id" in indexes:
        op.drop_index("ix_research_plans_starter_plan_id", table_name="research_plans")
    foreign_keys = {
        constraint.get("name")
        for constraint in inspector.get_foreign_keys("research_plans")
    }
    if "fk_research_plans_starter_plan_id" in foreign_keys:
        with op.batch_alter_table("research_plans") as batch:
            batch.drop_constraint("fk_research_plans_starter_plan_id", type_="foreignkey")
    columns = {column["name"] for column in inspector.get_columns("research_plans")}
    if "starter_plan_id" in columns:
        op.drop_column("research_plans", "starter_plan_id")
