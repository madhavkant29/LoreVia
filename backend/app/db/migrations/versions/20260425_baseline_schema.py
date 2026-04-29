"""Create the baseline application schema.

Revision ID: 20260425_baseline_schema
Revises: None
Create Date: 2026-04-25 00:00:00.000000
"""

from collections.abc import Sequence
import os

from alembic import op

from app.core.database import Base
from app.db import base  # noqa: F401

# revision identifiers, used by Alembic.
revision: str = "20260425_baseline_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    if os.getenv("ALLOW_DESTRUCTIVE_DOWNGRADE") != "1":
        raise RuntimeError(
            "Refusing to drop the full schema without ALLOW_DESTRUCTIVE_DOWNGRADE=1"
        )

    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
