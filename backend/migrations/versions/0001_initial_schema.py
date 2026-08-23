"""Create the complete ApplyEase schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-08-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table("documents",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False), sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("text_length", sa.Integer(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("sha256", name="uq_documents_sha256"))
    op.create_index("ix_documents_sha256", "documents", ["sha256"])

    op.create_table("experiences",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("title", sa.String(200), nullable=False),
        sa.Column("organization", sa.String(200), nullable=False), sa.Column("description", sa.Text(), nullable=False),
        sa.Column("skills", sa.JSON(), nullable=False), sa.Column("achievements", sa.JSON(), nullable=False),
        sa.Column("source_file", sa.String(255), nullable=False), sa.Column("confirmed", sa.Boolean(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=True), sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"))
    op.create_index("ix_experiences_document_id", "experiences", ["document_id"])

    op.create_table("jobs",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("title", sa.String(200), nullable=False),
        sa.Column("company", sa.String(200), nullable=False), sa.Column("description", sa.Text(), nullable=False),
        sa.Column("required_skills", sa.JSON(), nullable=False), sa.Column("preferred_skills", sa.JSON(), nullable=False),
        sa.Column("responsibilities", sa.JSON(), nullable=False), sa.Column("qualifications", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False))

    op.create_table("generated_materials",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("material_type", sa.String(40), nullable=False), sa.Column("content", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_generated_materials_job_id", "generated_materials", ["job_id"])

    op.create_table("applications",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_applications_job_id", "applications", ["job_id"])

    op.create_table("application_questions",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False), sa.Column("question_type", sa.Text(), nullable=False),
        sa.Column("max_characters", sa.Integer(), nullable=False), sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("answer", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_application_questions_application_id", "application_questions", ["application_id"])

    op.create_table("learning_resources",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("title", sa.String(250), nullable=False),
        sa.Column("url", sa.String(500), nullable=False), sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("skills", sa.JSON(), nullable=False), sa.Column("difficulty", sa.String(30), nullable=False),
        sa.Column("duration_hours", sa.Integer(), nullable=False), sa.Column("free", sa.Boolean(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False), sa.Column("project", sa.JSON(), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False))

    op.create_table("resource_progress",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("resource_id", sa.Integer(), nullable=False),
        sa.Column("completed", sa.Boolean(), nullable=False), sa.Column("completed_at", sa.DateTime(), nullable=True))
    op.create_index("ix_resource_progress_resource_id", "resource_progress", ["resource_id"])

    op.create_table("tracked_applications",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("company", sa.String(200), nullable=False),
        sa.Column("role", sa.String(200), nullable=False), sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("deadline", sa.Date(), nullable=True), sa.Column("status", sa.String(40), nullable=False),
        sa.Column("interview_date", sa.Date(), nullable=True), sa.Column("follow_up_at", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_tracked_applications_job_id", "tracked_applications", ["job_id"])


def downgrade() -> None:
    op.drop_index("ix_tracked_applications_job_id", table_name="tracked_applications"); op.drop_table("tracked_applications")
    op.drop_index("ix_resource_progress_resource_id", table_name="resource_progress"); op.drop_table("resource_progress")
    op.drop_table("learning_resources")
    op.drop_index("ix_application_questions_application_id", table_name="application_questions"); op.drop_table("application_questions")
    op.drop_index("ix_applications_job_id", table_name="applications"); op.drop_table("applications")
    op.drop_index("ix_generated_materials_job_id", table_name="generated_materials"); op.drop_table("generated_materials")
    op.drop_table("jobs")
    op.drop_index("ix_experiences_document_id", table_name="experiences"); op.drop_table("experiences")
    op.drop_index("ix_documents_sha256", table_name="documents"); op.drop_table("documents")
