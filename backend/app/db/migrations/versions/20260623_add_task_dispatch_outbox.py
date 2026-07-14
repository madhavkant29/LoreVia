"""Add durable task dispatch outbox and processing state constraints.

Revision ID: 20260623_add_task_dispatch_outbox
Revises: 20260622_add_processing_indexes
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260623_add_task_dispatch_outbox"
down_revision: str | Sequence[str] | None = "20260622_add_processing_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _tables() -> set[str]:
    return set(_inspector().get_table_names())


def _indexes(table: str) -> set[str]:
    if table not in _tables():
        return set()
    return {
        name
        for index in _inspector().get_indexes(table)
        if isinstance(name := index.get("name"), str)
    }


def _checks(table: str) -> set[str]:
    if table not in _tables():
        return set()
    return {
        name
        for check in _inspector().get_check_constraints(table)
        if isinstance(name := check.get("name"), str)
    }


def _create_index_if_missing(name: str, table: str, columns: list[str]) -> None:
    if table in _tables() and name not in _indexes(table):
        op.create_index(name, table, columns)


def _add_check_if_missing(table: str, name: str, condition: str) -> None:
    if table in _tables() and name not in _checks(table):
        op.execute(
            sa.text(
                f"ALTER TABLE {table} "
                f"ADD CONSTRAINT {name} CHECK ({condition}) NOT VALID"
            )
        )


def _drop_constraint_if_present(table: str, name: str) -> None:
    if table in _tables() and name in _checks(table):
        op.drop_constraint(name, table, type_="check")


def upgrade() -> None:
    tables = _tables()
    if "task_dispatch_outbox" not in tables:
        op.create_table(
            "task_dispatch_outbox",
            sa.Column("id", sa.UUID(), primary_key=True),
            sa.Column(
                "execution_id",
                sa.UUID(),
                sa.ForeignKey("task_executions.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("task_name", sa.String(), nullable=False),
            sa.Column("queue", sa.String(), nullable=False),
            sa.Column("payload_json", postgresql.JSONB(), nullable=False, server_default="{}"),
            sa.Column("status", sa.String(), nullable=False, server_default="pending"),
            sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("available_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("lease_until", sa.DateTime(timezone=True)),
            sa.Column("published_at", sa.DateTime(timezone=True)),
            sa.Column("last_error", sa.Text()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.UniqueConstraint("execution_id", name="uq_task_dispatch_outbox_execution_id"),
            sa.CheckConstraint(
                "status IN ('pending', 'publishing', 'published', 'publish_failed', 'cancelled')",
                name="ck_task_dispatch_outbox_status",
            ),
        )
    _create_index_if_missing(
        "ix_task_dispatch_outbox_status_available",
        "task_dispatch_outbox",
        ["status", "available_at"],
    )
    _create_index_if_missing(
        "ix_task_dispatch_outbox_queue_status",
        "task_dispatch_outbox",
        ["queue", "status"],
    )
    _create_index_if_missing(
        "ix_task_dispatch_outbox_lease_until",
        "task_dispatch_outbox",
        ["lease_until"],
    )
    _create_index_if_missing(
        "ix_task_dispatch_outbox_created_at",
        "task_dispatch_outbox",
        ["created_at"],
    )

    _add_check_if_missing(
        "book_processing_runs",
        "ck_book_processing_runs_status",
        "status IN ('queued', 'running', 'paused', 'succeeded', 'failed_terminal', 'dismissed')",
    )
    _add_check_if_missing(
        "task_executions",
        "ck_task_executions_status",
        "status IN ('pending_dispatch', 'queued', 'running', 'paused', 'succeeded', 'failed_terminal', 'dismissed')",
    )
    _add_check_if_missing(
        "task_executions",
        "ck_task_executions_attempt_bounds",
        "attempt_count >= 0 AND max_attempts > 0 AND attempt_count <= max_attempts",
    )
    _add_check_if_missing(
        "support_incidents",
        "ck_support_incidents_status",
        "status IN ('open', 'triaged', 'resolved', 'dismissed')",
    )
    _add_check_if_missing(
        "support_incidents",
        "ck_support_incidents_severity",
        "severity IN ('low', 'medium', 'high', 'critical')",
    )
    _add_check_if_missing(
        "ai_quality_events",
        "ck_ai_quality_events_outcome",
        (
            "outcome IN ("
            "'accepted', 'promoted', 'merged', 'rejected', 'suppressed', 'resolved', "
            "'manual_created', 'corrected', 'corrected_after_promotion'"
            ")"
        ),
    )


def downgrade() -> None:
    for table, constraints in (
        (
            "ai_quality_events",
            ("ck_ai_quality_events_outcome",),
        ),
        (
            "support_incidents",
            ("ck_support_incidents_severity", "ck_support_incidents_status"),
        ),
        (
            "task_executions",
            ("ck_task_executions_attempt_bounds", "ck_task_executions_status"),
        ),
        (
            "book_processing_runs",
            ("ck_book_processing_runs_status",),
        ),
    ):
        for constraint in constraints:
            _drop_constraint_if_present(table, constraint)

    if "task_dispatch_outbox" in _tables():
        op.drop_table("task_dispatch_outbox")
