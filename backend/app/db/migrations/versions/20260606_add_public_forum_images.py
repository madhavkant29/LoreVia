"""Add optional images to public forum posts and comments.

Revision ID: 20260606_add_public_forum_images
Revises: 20260604_repair_vault_constraint_rename
Create Date: 2026-06-06 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260606_add_public_forum_images"
down_revision: str | None = "20260604_repair_vault_constraint_rename"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FORUM_IMAGE_COLUMNS = (
    ("image_s3_key", sa.String()),
    ("image_content_type", sa.String()),
    ("image_filename", sa.String()),
)


def _column_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    for table_name in ("book_forum_posts", "book_forum_comments"):
        if table_name not in tables:
            continue
        columns = _column_names(inspector, table_name)
        for column_name, column_type in FORUM_IMAGE_COLUMNS:
            if column_name not in columns:
                op.add_column(table_name, sa.Column(column_name, column_type, nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    for table_name in ("book_forum_comments", "book_forum_posts"):
        if table_name not in tables:
            continue
        columns = _column_names(inspector, table_name)
        for column_name, _column_type in reversed(FORUM_IMAGE_COLUMNS):
            if column_name in columns:
                op.drop_column(table_name, column_name)
