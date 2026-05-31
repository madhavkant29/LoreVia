"""Create the baseline application schema.

Revision ID: 20260425_baseline_schema
Revises: None
Create Date: 2026-04-25 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.schema import CreateIndex, CreateTable

from app.core.database import Base
from app.db import base  # noqa: F401
from app.utils.migration_utils import drop_orphan_table_rowtype_if_present

# revision identifiers, used by Alembic.
revision: str = "20260425_baseline_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _create_missing_metadata_schema() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_tables = set(inspector.get_table_names())
    tables = [table for table in Base.metadata.sorted_tables if table.schema in (None, "public")]

    for table in tables:
        if table.name in existing_tables:
            continue
        drop_orphan_table_rowtype_if_present(table.name, schema=table.schema or "public")
        op.execute(CreateTable(table))
        existing_tables.add(table.name)

    inspector = sa.inspect(bind)

    for table in tables:
        if table.name not in existing_tables:
            continue
        existing_indexes = {index["name"] for index in inspector.get_indexes(table.name)}
        for index in table.indexes:
            if index.name and index.name not in existing_indexes:
                op.execute(CreateIndex(index))


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    _create_missing_metadata_schema()


def downgrade() -> None:
    raise RuntimeError(
        "Baseline schema downgrade is disabled because it would drop the full application schema. "
        "Restore from backup or create a fresh database instead."
    )
