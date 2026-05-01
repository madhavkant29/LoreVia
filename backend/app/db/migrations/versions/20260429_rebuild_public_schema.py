"""Rebuild the application schema in public.

Revision ID: 20260429_rebuild_public_schema
Revises: 20260429_merge_all_heads
Create Date: 2026-04-29 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

from app.core.database import Base
from app.db import base  # noqa: F401

revision: str = "20260429_rebuild_public_schema"
down_revision: str | None = "20260429_merge_all_heads"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)")
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    raise RuntimeError(
        "Rebuild-public-schema downgrade is disabled because it would drop the full application "
        "schema. Restore from backup or create a fresh database instead."
    )
