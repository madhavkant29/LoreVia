"""Add durable manuscript export jobs.

Revision ID: 20260912_add_manuscript_export_jobs
Revises: 20260912_add_forum_cursor_indexes
Create Date: 2026-09-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260912_add_manuscript_export_jobs"
down_revision: str | Sequence[str] | None = "20260912_add_forum_cursor_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "manuscript_export_jobs"
INDEXES: tuple[tuple[str, list[str]], ...] = (
    ("ix_manuscript_export_jobs_user_updated", ["user_id", "updated_at", "id"]),
    ("ix_manuscript_export_jobs_status_created", ["status", "created_at"]),
    ("ix_manuscript_export_jobs_expires_at", ["expires_at"]),
)
ACTIVE_REQUEST_INDEX = "uq_manuscript_export_jobs_active_request"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if TABLE_NAME not in tables:
        op.create_table(
            TABLE_NAME,
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("celery_task_id", sa.String(), nullable=True),
            sa.Column("status", sa.String(), server_default="queued", nullable=False),
            sa.Column("export_kind", sa.String(), nullable=False),
            sa.Column("export_format", sa.String(), nullable=False),
            sa.Column(
                "options_json",
                postgresql.JSONB(astext_type=sa.Text()),
                server_default=sa.text("'{}'::jsonb"),
                nullable=False,
            ),
            sa.Column("artifact_storage_key", sa.String(), nullable=True),
            sa.Column("artifact_filename", sa.String(), nullable=True),
            sa.Column("artifact_media_type", sa.String(), nullable=True),
            sa.Column("artifact_size_bytes", sa.BigInteger(), nullable=True),
            sa.Column("error_detail", sa.Text(), nullable=True),
            sa.Column("progress_completed", sa.Integer(), server_default="0", nullable=False),
            sa.Column("progress_total", sa.Integer(), server_default="0", nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
            ),
            sa.CheckConstraint(
                "status IN ('queued', 'running', 'completed', 'failed', 'expired')",
                name="ck_manuscript_export_jobs_status",
            ),
            sa.CheckConstraint(
                "export_kind IN ('manuscript', 'novel')",
                name="ck_manuscript_export_jobs_kind",
            ),
            sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        inspector = sa.inspect(bind)

    existing_indexes = {index["name"] for index in inspector.get_indexes(TABLE_NAME)}
    for index_name, columns in INDEXES:
        if index_name not in existing_indexes:
            op.create_index(index_name, TABLE_NAME, columns)
    if ACTIVE_REQUEST_INDEX not in existing_indexes:
        op.create_index(
            ACTIVE_REQUEST_INDEX,
            TABLE_NAME,
            ["user_id", "book_id", "export_kind", "export_format", "options_json"],
            unique=True,
            postgresql_where=sa.text("status IN ('queued', 'running')"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE_NAME in set(inspector.get_table_names()):
        op.drop_table(TABLE_NAME)
