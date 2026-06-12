"""Make book upload charge timestamps non-null.

Revision ID: 20260612_fix_book_upload_charge_created_at_nullable
Revises: 20260612_fix_data_deletion_requested_at_nullable
Create Date: 2026-06-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260612_fix_book_upload_charge_created_at_nullable"
down_revision: str | Sequence[str] | None = "20260612_fix_data_deletion_requested_at_nullable"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


CHARGES_TABLE = "book_upload_charges"
CREATED_AT_COLUMN = "created_at"


def _column_map(inspector: sa.Inspector) -> dict[str, dict]:
    if CHARGES_TABLE not in set(inspector.get_table_names()):
        return {}
    return {column["name"]: column for column in inspector.get_columns(CHARGES_TABLE)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = _column_map(inspector)
    created_at = columns.get(CREATED_AT_COLUMN)
    if created_at is None:
        return

    op.execute(
        sa.text(
            f"UPDATE {CHARGES_TABLE} "
            f"SET {CREATED_AT_COLUMN} = now() "
            f"WHERE {CREATED_AT_COLUMN} IS NULL"
        )
    )
    if created_at.get("nullable", True):
        op.alter_column(
            CHARGES_TABLE,
            CREATED_AT_COLUMN,
            existing_type=sa.DateTime(timezone=True),
            existing_server_default=sa.text("now()"),
            nullable=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = _column_map(inspector)
    created_at = columns.get(CREATED_AT_COLUMN)
    if created_at is None or created_at.get("nullable", True):
        return

    op.alter_column(
        CHARGES_TABLE,
        CREATED_AT_COLUMN,
        existing_type=sa.DateTime(timezone=True),
        existing_server_default=sa.text("now()"),
        nullable=True,
    )
