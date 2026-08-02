"""Add indexes omitted from the processing control-plane migration.

Revision ID: 20260622_add_processing_indexes
Revises: 20260622_add_processing_control_plane
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260622_add_processing_indexes"
down_revision: str | Sequence[str] | None = "20260622_add_processing_control_plane"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


INDEXES: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "book_processing_runs": (
        ("ix_book_processing_runs_created_at", ("created_at",)),
        ("ix_book_processing_runs_rebuild_run_id", ("rebuild_run_id",)),
    ),
    "task_executions": (
        ("ix_task_executions_celery_task_id", ("celery_task_id",)),
        ("ix_task_executions_created_at", ("created_at",)),
        ("ix_task_executions_error_category", ("error_category",)),
    ),
}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    for table, indexes_to_create in INDEXES.items():
        if table not in tables:
            continue
        existing_indexes = {index["name"] for index in inspector.get_indexes(table)}
        for name, columns in indexes_to_create:
            if name not in existing_indexes:
                op.create_index(name, table, list(columns))


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    for table, indexes_to_drop in reversed(tuple(INDEXES.items())):
        if table not in tables:
            continue
        existing_indexes = {index["name"] for index in inspector.get_indexes(table)}
        for name, _columns in reversed(indexes_to_drop):
            if name in existing_indexes:
                op.drop_index(name, table_name=table)
