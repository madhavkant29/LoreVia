"""Merge the outstanding migration heads into a single Alembic head.

Revision ID: 20260501_merge_book_migration_heads
Revises: 20260429_add_world_building_documents, 20260501_add_preserve_chapter_numbers, 20260501_add_writer_workspace_to_books
Create Date: 2026-05-01 00:00:00.000000
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "20260501_merge_book_migration_heads"
down_revision: tuple[str, ...] | None = (
    "20260429_add_world_building_documents",
    "20260501_add_preserve_chapter_numbers",
    "20260501_add_writer_workspace_to_books",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
