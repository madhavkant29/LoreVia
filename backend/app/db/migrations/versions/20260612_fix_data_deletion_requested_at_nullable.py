"""Make data deletion request timestamps non-null.

Revision ID: 20260612_fix_data_deletion_requested_at_nullable
Revises: 20260611_merge_adjudication_and_privacy_heads
Create Date: 2026-06-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260612_fix_data_deletion_requested_at_nullable"
down_revision: str | Sequence[str] | None = "20260611_merge_adjudication_and_privacy_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


REQUESTS_TABLE = "data_deletion_requests"
REQUESTED_AT_COLUMN = "requested_at"


def _column_map(inspector: sa.Inspector) -> dict[str, dict]:
    if REQUESTS_TABLE not in set(inspector.get_table_names()):
        return {}
    return {column["name"]: column for column in inspector.get_columns(REQUESTS_TABLE)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = _column_map(inspector)
    requested_at = columns.get(REQUESTED_AT_COLUMN)
    if requested_at is None:
        return

    op.execute(
        sa.text(
            f"UPDATE {REQUESTS_TABLE} "
            f"SET {REQUESTED_AT_COLUMN} = now() "
            f"WHERE {REQUESTED_AT_COLUMN} IS NULL"
        )
    )
    if requested_at.get("nullable", True):
        op.alter_column(
            REQUESTS_TABLE,
            REQUESTED_AT_COLUMN,
            existing_type=sa.DateTime(timezone=True),
            existing_server_default=sa.text("now()"),
            nullable=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = _column_map(inspector)
    requested_at = columns.get(REQUESTED_AT_COLUMN)
    if requested_at is None or requested_at.get("nullable", True):
        return

    op.alter_column(
        REQUESTS_TABLE,
        REQUESTED_AT_COLUMN,
        existing_type=sa.DateTime(timezone=True),
        existing_server_default=sa.text("now()"),
        nullable=True,
    )
