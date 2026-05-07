"""Remove processed cover fields from books.

Revision ID: 20260506_remove_cover_processing_fields
Revises: 20260505_update_device_trial_index
Create Date: 2026-05-06 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "20260506_remove_cover_processing_fields"
down_revision: str | None = "20260505_update_device_trial_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "books" not in tables:
        return

    columns = {col["name"] for col in inspector.get_columns("books")}
    if "cover_crop_bounds" in columns:
        op.drop_column("books", "cover_crop_bounds")
    if "cover_processed_at" in columns:
        op.drop_column("books", "cover_processed_at")
    if "cover_edge_colors" in columns:
        op.drop_column("books", "cover_edge_colors")
    if "cover_processed_url" in columns:
        op.drop_column("books", "cover_processed_url")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "books" not in tables:
        return

    columns = {col["name"] for col in inspector.get_columns("books")}
    if "cover_processed_url" not in columns:
        op.add_column("books", sa.Column("cover_processed_url", sa.String(), nullable=True))
    if "cover_edge_colors" not in columns:
        op.add_column("books", sa.Column("cover_edge_colors", postgresql.JSONB(), nullable=True))
    if "cover_processed_at" not in columns:
        op.add_column("books", sa.Column("cover_processed_at", sa.DateTime(timezone=True), nullable=True))
    if "cover_crop_bounds" not in columns:
        op.add_column("books", sa.Column("cover_crop_bounds", postgresql.JSONB(), nullable=True))
