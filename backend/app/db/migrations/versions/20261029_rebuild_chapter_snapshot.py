"""Keep prior chapter readiness while a derived-data rebuild is staged.

Revision ID: 20261029_rebuild_chapter_snapshot
Revises: 20261028_vault_source_unique
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20261029_rebuild_chapter_snapshot"
down_revision: str | Sequence[str] | None = "20261028_vault_source_unique"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "book_data_generations"
COLUMN_NAME = "chapter_state_snapshot"


def _columns() -> set[str] | None:
    inspector = sa.inspect(op.get_bind())
    if TABLE_NAME not in inspector.get_table_names():
        return None
    return {column["name"] for column in inspector.get_columns(TABLE_NAME)}


def upgrade() -> None:
    columns = _columns()
    if columns is not None and COLUMN_NAME not in columns:
        op.add_column(TABLE_NAME, sa.Column(COLUMN_NAME, JSONB(), nullable=True))


def downgrade() -> None:
    columns = _columns()
    if columns is not None and COLUMN_NAME in columns:
        op.drop_column(TABLE_NAME, COLUMN_NAME)
