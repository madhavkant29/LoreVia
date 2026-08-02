"""Add missing continuity created-at indexes.

Revision ID: 20260802_continuity_created_idx
Revises: 20260724_continuity_ledger
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260802_continuity_created_idx"
down_revision: str | Sequence[str] | None = "20260724_continuity_ledger"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


INDEXES: dict[str, tuple[str, tuple[str, ...]]] = {
    "continuity_scans": (
        "ix_continuity_scans_created_at",
        ("created_at",),
    ),
    "continuity_observations": (
        "ix_continuity_observations_created_at",
        ("created_at",),
    ),
    "continuity_findings": (
        "ix_continuity_findings_created_at",
        ("created_at",),
    ),
}


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _index_names(inspector: sa.Inspector, table: str) -> set[str]:
    return {
        name
        for index in inspector.get_indexes(table)
        if isinstance(name := index.get("name"), str)
    }


def upgrade() -> None:
    inspector = _inspector()
    tables = set(inspector.get_table_names())
    for table, (name, columns) in INDEXES.items():
        if table in tables and name not in _index_names(inspector, table):
            op.create_index(name, table, list(columns))


def downgrade() -> None:
    inspector = _inspector()
    tables = set(inspector.get_table_names())
    for table, (name, _columns) in reversed(tuple(INDEXES.items())):
        if table in tables and name in _index_names(inspector, table):
            op.drop_index(name, table_name=table)
