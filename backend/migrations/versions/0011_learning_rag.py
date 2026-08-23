"""Restore the historical RAG migration marker.

The RAG rollout created no relational tables: it uses Milvus for vectors and
existing user-owned records for source data. Some existing databases were
stamped with this revision while the migration file was absent from the source
tree, preventing Alembic from resolving the version chain on a fresh container.
"""

revision = "0011_learning_rag"
down_revision = "0010_resource_feedback"
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
