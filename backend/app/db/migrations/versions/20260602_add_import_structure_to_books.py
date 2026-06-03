"""Add import_structure JSONB column to books.

Stores a snapshot of the ImportPreview (sections, confidence, warnings) after
the initial manuscript parse, so it can be re-displayed later without
re-parsing the original file.

Revision ID: 20260602_add_import_structure_to_books
Revises: 20260602_enforce_device_trial_user_uniqueness
Create Date: 2026-06-02 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260602_add_import_structure_to_books"
down_revision: str | Sequence[str] | None = "20260602_enforce_device_trial_user_uniqueness"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "books" in tables:
        columns = {column["name"] for column in inspector.get_columns("books")}
        if "import_structure" not in columns:
            op.add_column(
                "books",
                sa.Column(
                    "import_structure",
                    JSONB(),
                    nullable=True,
                ),
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "books" in tables:
        columns = {column["name"] for column in inspector.get_columns("books")}
        if "import_structure" in columns:
            op.drop_column("books", "import_structure")
