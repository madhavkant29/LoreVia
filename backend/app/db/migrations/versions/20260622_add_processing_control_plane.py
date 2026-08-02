"""Add durable processing, task, quality, support, and cost records.

Revision ID: 20260622_add_processing_control_plane
Revises: 20260620_replace_vector_indexes_hnsw
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260622_add_processing_control_plane"
down_revision: str | Sequence[str] | None = "20260620_replace_vector_indexes_hnsw"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def _indexes(table: str) -> set[str]:
    return {index["name"] for index in sa.inspect(op.get_bind()).get_indexes(table)}


def upgrade() -> None:
    tables = _tables()
    if "book_processing_runs" not in tables:
        op.create_table(
            "book_processing_runs",
            sa.Column("id", sa.UUID(), primary_key=True),
            sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("book_id", sa.UUID(), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
            sa.Column("run_kind", sa.String(), nullable=False, server_default="initial_ingestion"),
            sa.Column("status", sa.String(), nullable=False, server_default="queued"),
            sa.Column("pause_reason", sa.String()),
            sa.Column("resume_blockers", postgresql.JSONB(), nullable=False, server_default="[]"),
            sa.Column("next_chapter_number", sa.Integer()),
            sa.Column("chapters_total", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("chapters_completed", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("rebuild_run_id", sa.String()),
            sa.Column("pipeline_version", sa.String(), nullable=False, server_default="2026-06"),
            sa.Column("started_at", sa.DateTime(timezone=True)),
            sa.Column("paused_at", sa.DateTime(timezone=True)),
            sa.Column("completed_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_book_processing_runs_user_id", "book_processing_runs", ["user_id"])
        op.create_index("ix_book_processing_runs_book_id", "book_processing_runs", ["book_id"])
        op.create_index("ix_book_processing_runs_status", "book_processing_runs", ["status"])
        op.create_index("ix_book_processing_runs_book_status", "book_processing_runs", ["book_id", "status"])
        tables.add("book_processing_runs")

    if "task_executions" not in tables:
        op.create_table(
            "task_executions",
            sa.Column("id", sa.UUID(), primary_key=True),
            sa.Column("identity_key", sa.String(64), nullable=False),
            sa.Column("task_name", sa.String(), nullable=False),
            sa.Column("feature", sa.String(), nullable=False, server_default="processing"),
            sa.Column("processing_run_id", sa.UUID(), sa.ForeignKey("book_processing_runs.id", ondelete="CASCADE")),
            sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE")),
            sa.Column("book_id", sa.UUID(), sa.ForeignKey("books.id", ondelete="CASCADE")),
            sa.Column("chapter_id", sa.UUID(), sa.ForeignKey("chapters.id", ondelete="SET NULL")),
            sa.Column("chapter_number", sa.Integer()),
            sa.Column("chapter_version_id", sa.UUID(), sa.ForeignKey("chapter_versions.id", ondelete="SET NULL")),
            sa.Column("rebuild_run_id", sa.String()),
            sa.Column("celery_task_id", sa.String()),
            sa.Column("status", sa.String(), nullable=False, server_default="pending_dispatch"),
            sa.Column("arguments_json", postgresql.JSONB(), nullable=False, server_default="{}"),
            sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("error_category", sa.String()),
            sa.Column("error_detail", sa.Text()),
            sa.Column("first_failed_at", sa.DateTime(timezone=True)),
            sa.Column("last_failed_at", sa.DateTime(timezone=True)),
            sa.Column("queued_at", sa.DateTime(timezone=True)),
            sa.Column("started_at", sa.DateTime(timezone=True)),
            sa.Column("locked_until", sa.DateTime(timezone=True)),
            sa.Column("completed_at", sa.DateTime(timezone=True)),
            sa.Column("dismissed_at", sa.DateTime(timezone=True)),
            sa.Column("dismissed_by_user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("dismissal_reason", sa.Text()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("identity_key", name="uq_task_executions_identity_key"),
        )
        for name, columns in (
            ("ix_task_executions_task_name", ["task_name"]),
            ("ix_task_executions_processing_run_id", ["processing_run_id"]),
            ("ix_task_executions_user_id", ["user_id"]),
            ("ix_task_executions_book_id", ["book_id"]),
            ("ix_task_executions_chapter_id", ["chapter_id"]),
            ("ix_task_executions_status", ["status"]),
            ("ix_task_executions_locked_until", ["locked_until"]),
            ("ix_task_executions_status_created", ["status", "created_at"]),
            ("ix_task_executions_user_status", ["user_id", "status"]),
        ):
            op.create_index(name, "task_executions", columns)
        tables.add("task_executions")

    if "ai_quality_events" not in tables:
        op.create_table(
            "ai_quality_events",
            sa.Column("id", sa.UUID(), primary_key=True),
            sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("book_id", sa.UUID(), sa.ForeignKey("books.id", ondelete="CASCADE"), nullable=False),
            sa.Column("task_execution_id", sa.UUID(), sa.ForeignKey("task_executions.id", ondelete="SET NULL")),
            sa.Column("entity_type", sa.String(), nullable=False),
            sa.Column("entity_id", sa.String()),
            sa.Column("outcome", sa.String(), nullable=False),
            sa.Column("model", sa.String()),
            sa.Column("extractor_version", sa.String()),
            sa.Column("actor_user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        for name, columns in (
            ("ix_ai_quality_events_user_id", ["user_id"]), ("ix_ai_quality_events_book_id", ["book_id"]),
            ("ix_ai_quality_events_entity_type", ["entity_type"]), ("ix_ai_quality_events_outcome", ["outcome"]),
            ("ix_ai_quality_events_model", ["model"]), ("ix_ai_quality_events_extractor_version", ["extractor_version"]),
            ("ix_ai_quality_events_created_at", ["created_at"]), ("ix_ai_quality_events_book_created", ["book_id", "created_at"]),
        ):
            op.create_index(name, "ai_quality_events", columns)
        tables.add("ai_quality_events")

    if "support_incidents" not in tables:
        op.create_table(
            "support_incidents",
            sa.Column("id", sa.UUID(), primary_key=True),
            sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("book_id", sa.UUID(), sa.ForeignKey("books.id", ondelete="SET NULL")),
            sa.Column("task_execution_id", sa.UUID(), sa.ForeignKey("task_executions.id", ondelete="SET NULL")),
            sa.Column("category", sa.String(), nullable=False), sa.Column("feature", sa.String()),
            sa.Column("severity", sa.String(), nullable=False, server_default="medium"),
            sa.Column("status", sa.String(), nullable=False, server_default="open"),
            sa.Column("summary", sa.String(), nullable=False), sa.Column("resolution", sa.Text()),
            sa.Column("created_by_user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("resolved_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        for name, columns in (
            ("ix_support_incidents_user_id", ["user_id"]), ("ix_support_incidents_book_id", ["book_id"]),
            ("ix_support_incidents_category", ["category"]), ("ix_support_incidents_feature", ["feature"]),
            ("ix_support_incidents_status", ["status"]), ("ix_support_incidents_created_at", ["created_at"]),
            ("ix_support_incidents_status_created", ["status", "created_at"]),
        ):
            op.create_index(name, "support_incidents", columns)
        tables.add("support_incidents")

    if "revenue_ledger_events" not in tables:
        op.create_table(
            "revenue_ledger_events",
            sa.Column("id", sa.UUID(), primary_key=True),
            sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("source_event_id", sa.String(), nullable=False), sa.Column("plan", sa.String(), nullable=False),
            sa.Column("transaction_id", sa.String()),
            sa.Column("billing_interval", sa.String(), nullable=False), sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
            sa.Column("gross_amount", sa.Numeric(14, 6), nullable=False), sa.Column("fee_amount", sa.Numeric(14, 6), nullable=False),
            sa.Column("net_amount", sa.Numeric(14, 6), nullable=False), sa.Column("pricing_version", sa.String(), nullable=False),
            sa.Column("service_period_start", sa.DateTime(timezone=True), nullable=False),
            sa.Column("service_period_end", sa.DateTime(timezone=True), nullable=False),
            sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("source_event_id", name="uq_revenue_ledger_events_source"),
        )
        for name, columns in (("ix_revenue_ledger_events_user_id", ["user_id"]), ("ix_revenue_ledger_events_transaction_id", ["transaction_id"]), ("ix_revenue_ledger_events_plan", ["plan"]), ("ix_revenue_ledger_events_service_period_start", ["service_period_start"]), ("ix_revenue_ledger_events_service_period_end", ["service_period_end"])):
            op.create_index(name, "revenue_ledger_events", columns)

    llm_columns = _columns("llm_usage_events")
    llm_additions = (
        ("reservation_id", sa.Column("reservation_id", sa.String())),
        ("status", sa.Column("status", sa.String(), nullable=False, server_default="succeeded")),
        ("estimated_tokens", sa.Column("estimated_tokens", sa.Integer(), nullable=False, server_default="0")),
        ("cached_prompt_tokens", sa.Column("cached_prompt_tokens", sa.Integer(), nullable=False, server_default="0")),
        ("provider_attempts", sa.Column("provider_attempts", sa.Integer(), nullable=False, server_default="1")),
        ("input_cost_usd", sa.Column("input_cost_usd", sa.Numeric(14, 8))),
        ("output_cost_usd", sa.Column("output_cost_usd", sa.Numeric(14, 8))),
        ("total_cost_usd", sa.Column("total_cost_usd", sa.Numeric(14, 8))),
        ("pricing_version", sa.Column("pricing_version", sa.String())),
        ("processing_run_id", sa.Column("processing_run_id", sa.UUID(), sa.ForeignKey("book_processing_runs.id", ondelete="SET NULL"))),
        ("task_execution_id", sa.Column("task_execution_id", sa.UUID(), sa.ForeignKey("task_executions.id", ondelete="SET NULL"))),
        ("extractor_version", sa.Column("extractor_version", sa.String())),
    )
    for name, column in llm_additions:
        if name not in llm_columns:
            op.add_column("llm_usage_events", column)
    indexes = _indexes("llm_usage_events")
    for name, columns, unique in (
        ("ix_llm_usage_events_reservation_id", ["reservation_id"], True),
        ("ix_llm_usage_events_status", ["status"], False),
        ("ix_llm_usage_events_total_cost_usd", ["total_cost_usd"], False),
        ("ix_llm_usage_events_processing_run_id", ["processing_run_id"], False),
        ("ix_llm_usage_events_task_execution_id", ["task_execution_id"], False),
        ("ix_llm_usage_events_extractor_version", ["extractor_version"], False),
    ):
        if name not in indexes:
            op.create_index(name, "llm_usage_events", columns, unique=unique)

    op.execute(sa.text("""
        INSERT INTO book_processing_runs (
            id, user_id, book_id, run_kind, status, chapters_total,
            chapters_completed, pipeline_version, created_at, updated_at
        )
        SELECT md5(b.id::text || '-legacy-processing')::uuid, b.user_id, b.id,
               'legacy_recovery',
               CASE WHEN b.status = 'failed' THEN 'failed_terminal' ELSE 'running' END,
               COALESCE(b.total_chapters, 0),
               COALESCE((SELECT count(*) FROM chapters c WHERE c.book_id = b.id AND c.processed = true), 0),
               'legacy', now(), now()
        FROM books b
        WHERE b.status IN ('processing', 'failed')
          AND NOT EXISTS (SELECT 1 FROM book_processing_runs r WHERE r.book_id = b.id)
    """))


def downgrade() -> None:
    tables = _tables()
    if "llm_usage_events" in tables:
        indexes = _indexes("llm_usage_events")
        for name in (
            "ix_llm_usage_events_extractor_version", "ix_llm_usage_events_task_execution_id",
            "ix_llm_usage_events_processing_run_id", "ix_llm_usage_events_total_cost_usd",
            "ix_llm_usage_events_status", "ix_llm_usage_events_reservation_id",
        ):
            if name in indexes:
                op.drop_index(name, table_name="llm_usage_events")
        columns = _columns("llm_usage_events")
        for name in (
            "extractor_version", "task_execution_id", "processing_run_id", "pricing_version",
            "total_cost_usd", "output_cost_usd", "input_cost_usd", "provider_attempts",
            "cached_prompt_tokens", "estimated_tokens", "status", "reservation_id",
        ):
            if name in columns:
                op.drop_column("llm_usage_events", name)
    for table in ("revenue_ledger_events", "support_incidents", "ai_quality_events", "task_executions", "book_processing_runs"):
        if table in _tables():
            op.drop_table(table)
