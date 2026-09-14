"""Add durable manuscript import jobs and latency-critical indexes.

Revision ID: 20260909_import_jobs_latency
Revises: 20260805_add_user_ui_preferences
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260909_import_jobs_latency"
down_revision: str | Sequence[str] | None = "20260805_add_user_ui_preferences"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _index_names(inspector: sa.Inspector, table: str) -> set[str]:
    return {
        name
        for index in inspector.get_indexes(table)
        if isinstance(name := index.get("name"), str)
    }


def _column_names(inspector: sa.Inspector, table: str) -> set[str]:
    return {str(column["name"]) for column in inspector.get_columns(table)}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    if "manuscript_import_jobs" not in tables:
        op.create_table(
            "manuscript_import_jobs",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("celery_task_id", sa.String(), nullable=True),
            sa.Column("status", sa.String(), server_default="queued", nullable=False),
            sa.Column(
                "request_json",
                postgresql.JSONB(astext_type=sa.Text()),
                server_default=sa.text("'{}'::jsonb"),
                nullable=False,
            ),
            sa.Column(
                "source_files_json",
                postgresql.JSONB(astext_type=sa.Text()),
                server_default=sa.text("'[]'::jsonb"),
                nullable=False,
            ),
            sa.Column(
                "result_json",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=True,
            ),
            sa.Column("error_detail", sa.Text(), nullable=True),
            sa.Column("progress_completed", sa.Integer(), server_default="0", nullable=False),
            sa.Column("progress_total", sa.Integer(), server_default="0", nullable=False),
            sa.Column("cancel_requested", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.CheckConstraint(
                "status IN ('queued', 'running', 'completed', 'failed', "
                "'cancel_requested', 'cancelled')",
                name="ck_manuscript_import_jobs_status",
            ),
            sa.ForeignKeyConstraint(["book_id"], ["books.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        inspector = sa.inspect(op.get_bind())
        tables = set(inspector.get_table_names())

    required_import_job_columns = {
        "id",
        "user_id",
        "book_id",
        "celery_task_id",
        "status",
        "request_json",
        "source_files_json",
        "result_json",
        "error_detail",
        "progress_completed",
        "progress_total",
        "cancel_requested",
        "started_at",
        "completed_at",
        "created_at",
        "updated_at",
    }
    missing_import_job_columns = required_import_job_columns - _column_names(
        inspector, "manuscript_import_jobs"
    )
    if missing_import_job_columns:
        raise RuntimeError(
            "Refusing manuscript import migration because an incompatible existing table "
            "is missing columns: " + ", ".join(sorted(missing_import_job_columns))
        )
    import_job_indexes = _index_names(inspector, "manuscript_import_jobs")
    if "ix_manuscript_import_jobs_user_updated" not in import_job_indexes:
        op.create_index(
            "ix_manuscript_import_jobs_user_updated",
            "manuscript_import_jobs",
            ["user_id", "updated_at", "id"],
        )
    if "ix_manuscript_import_jobs_status_created" not in import_job_indexes:
        op.create_index(
            "ix_manuscript_import_jobs_status_created",
            "manuscript_import_jobs",
            ["status", "created_at"],
        )

    conventional_indexes: tuple[tuple[str, str, tuple[str, ...]], ...] = (
        (
            "books",
            "ix_books_user_hidden_created_id",
            ("user_id", "hidden_at", "created_at", "id"),
        ),
        (
            "book_collaborators",
            "ix_book_collaborators_email_status_book",
            ("email", "invite_status", "book_id"),
        ),
        (
            "notifications",
            "ix_notifications_user_created_id",
            ("user_id", "created_at", "id"),
        ),
        (
            "chapter_versions",
            "ix_chapter_versions_book_chapter_created_id",
            ("book_id", "chapter_number", "created_at", "id"),
        ),
        (
            "novel_scenes",
            "ix_novel_scenes_book_chapter_sort_created",
            ("book_id", "chapter_number", "sort_order", "created_at"),
        ),
    )
    for table, name, columns in conventional_indexes:
        if table in tables and name not in _index_names(inspector, table):
            op.create_index(name, table, list(columns))

    if "notifications" in tables:
        existing = _index_names(inspector, "notifications")
        if "ix_notifications_user_unread" not in existing:
            op.create_index(
                "ix_notifications_user_unread",
                "notifications",
                ["user_id"],
                postgresql_where=sa.text("read_at IS NULL"),
            )

    if "task_executions" in tables:
        existing = _index_names(inspector, "task_executions")
        if "ix_task_executions_pending_task_created_chapter" not in existing:
            op.create_index(
                "ix_task_executions_pending_task_created_chapter",
                "task_executions",
                ["task_name", "created_at", "chapter_number"],
                postgresql_where=sa.text("status = 'pending_dispatch'"),
            )
        if "ix_task_executions_running_locked_until" not in existing:
            op.create_index(
                "ix_task_executions_running_locked_until",
                "task_executions",
                ["locked_until"],
                postgresql_where=sa.text("status = 'running'"),
            )

    if "book_chunks" in tables:
        existing = _index_names(inspector, "book_chunks")
        if "ix_book_chunks_text_search" not in existing:
            op.create_index(
                "ix_book_chunks_text_search",
                "book_chunks",
                [sa.text("to_tsvector('simple', text)")],
                postgresql_using="gin",
            )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    indexes: tuple[tuple[str, str], ...] = (
        ("book_collaborators", "ix_book_collaborators_email_status_book"),
        ("books", "ix_books_user_hidden_created_id"),
        ("book_chunks", "ix_book_chunks_text_search"),
        ("task_executions", "ix_task_executions_running_locked_until"),
        ("task_executions", "ix_task_executions_pending_task_created_chapter"),
        ("novel_scenes", "ix_novel_scenes_book_chapter_sort_created"),
        ("chapter_versions", "ix_chapter_versions_book_chapter_created_id"),
        ("notifications", "ix_notifications_user_unread"),
        ("notifications", "ix_notifications_user_created_id"),
    )
    for table, name in indexes:
        if table in tables and name in _index_names(inspector, table):
            op.drop_index(name, table_name=table)
    if "manuscript_import_jobs" in tables:
        op.drop_table("manuscript_import_jobs")
