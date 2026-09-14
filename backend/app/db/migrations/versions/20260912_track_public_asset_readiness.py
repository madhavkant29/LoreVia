"""Track the uploaded public asset version for each chapter.

Revision ID: 20260912_public_asset_ready
Revises: 20260912_add_manuscript_export_jobs
Create Date: 2026-09-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260912_public_asset_ready"
down_revision: str | Sequence[str] | None = "20260912_add_manuscript_export_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "chapters"
COLUMN_NAME = "public_asset_version"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE_NAME not in set(inspector.get_table_names()):
        return
    columns = {column["name"] for column in inspector.get_columns(TABLE_NAME)}
    if COLUMN_NAME not in columns:
        op.add_column(TABLE_NAME, sa.Column(COLUMN_NAME, sa.Integer(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if TABLE_NAME not in set(inspector.get_table_names()):
        return
    columns = {column["name"] for column in inspector.get_columns(TABLE_NAME)}
    if COLUMN_NAME in columns:
        op.drop_column(TABLE_NAME, COLUMN_NAME)
