"""Record curated resource link health."""
from alembic import op
import sqlalchemy as sa

revision = "0009_resource_health"
down_revision = "0008_mfa"
branch_labels = None
depends_on = None


def upgrade():
    columns = {item["name"] for item in sa.inspect(op.get_bind()).get_columns("learning_resources")}
    if "link_status" not in columns:
        op.add_column("learning_resources", sa.Column("link_status", sa.String(length=20), nullable=False, server_default="unchecked"))
    if "last_checked_at" not in columns:
        op.add_column("learning_resources", sa.Column("last_checked_at", sa.DateTime(), nullable=True))


def downgrade():
    op.drop_column("learning_resources", "last_checked_at")
    op.drop_column("learning_resources", "link_status")
