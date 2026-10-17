"""Align reader and world-intelligence indexes with ORM metadata.

Revision ID: 20261018_reconcile_reported_indexes
Revises: 20261017_book_sections
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261018_reconcile_reported_indexes"
down_revision: str | Sequence[str] | None = "20261017_book_sections"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


INDEXES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("reader_events", "ix_reader_events_character_id", ("character_id",)),
    ("reader_events", "ix_reader_events_generation_id", ("generation_id",)),
    (
        "world_analysis_states",
        "ix_world_analysis_states_completed_at",
        ("completed_at",),
    ),
    ("world_analysis_states", "ix_world_analysis_states_error_code", ("error_code",)),
    ("world_analysis_states", "ix_world_analysis_states_failed_at", ("failed_at",)),
    (
        "world_analysis_states",
        "ix_world_analysis_states_input_fingerprint",
        ("input_fingerprint",),
    ),
    (
        "world_analysis_states",
        "ix_world_analysis_states_refresh_job_id",
        ("refresh_job_id",),
    ),
    ("world_analysis_states", "ix_world_analysis_states_stale_at", ("stale_at",)),
    (
        "world_source_observations",
        "ix_world_source_observations_chapter_id",
        ("chapter_id",),
    ),
    (
        "world_source_observations",
        "ix_world_source_observations_generation_id",
        ("generation_id",),
    ),
)


def _indexes(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        name
        for index in inspector.get_indexes(table_name)
        if isinstance(name := index.get("name"), str)
    }


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    for table_name, index_name, columns in INDEXES:
        if table_name not in tables or index_name in _indexes(inspector, table_name):
            continue
        op.create_index(index_name, table_name, list(columns))
        inspector = sa.inspect(bind)


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    for table_name, index_name, _columns in reversed(INDEXES):
        if table_name in tables and index_name in _indexes(inspector, table_name):
            op.drop_index(index_name, table_name=table_name)
            inspector = sa.inspect(op.get_bind())
