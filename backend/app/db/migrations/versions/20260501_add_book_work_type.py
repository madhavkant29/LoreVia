"""Add work_type to books.

Revision ID: 20260501_add_book_work_type
Revises: 20260501_merge_book_migration_heads
Create Date: 2026-05-01 10:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260501_add_book_work_type"
down_revision: str | None = "20260501_merge_book_migration_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "books" not in tables:
        return

    columns = {column["name"]: column for column in inspector.get_columns("books")}
    if "work_type" not in columns:
        op.add_column(
            "books",
            sa.Column(
                "work_type",
                sa.String(),
                nullable=True,
                server_default="novel",
            ),
        )
        columns = {column["name"]: column for column in sa.inspect(bind).get_columns("books")}

    op.execute(
        sa.text(
            """
            UPDATE books
            SET work_type = CASE
                WHEN format IN ('screenplay', 'fountain') THEN 'screenplay'
                WHEN id IN (SELECT DISTINCT book_id FROM scenes) THEN 'screenplay'
                ELSE COALESCE(work_type, 'novel')
            END
            WHERE work_type IS NULL OR work_type = '' OR work_type NOT IN ('novel', 'screenplay', 'other')
            """
        )
    )
    op.execute(sa.text("UPDATE books SET work_type = 'novel' WHERE work_type IS NULL OR work_type = ''"))

    if columns.get("work_type", {}).get("nullable", True):
        op.alter_column("books", "work_type", existing_type=sa.String(), nullable=False, server_default="novel")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "books" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("books")}
    if "work_type" in columns:
        op.drop_column("books", "work_type")
