"""Merge the two migration branches into a single head.

Revision ID: 20260429_merge_migration_heads
Revises: 20260428_cover_processing_fields, f4c9e12a6b31
Create Date: 2026-04-29 00:00:00.000000
"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "20260429_merge_migration_heads"
down_revision: tuple[str, str] | None = (
    "20260428_cover_processing_fields",
    "f4c9e12a6b31",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
