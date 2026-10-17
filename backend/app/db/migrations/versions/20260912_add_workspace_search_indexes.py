"""Add text indexes for bounded workspace search.

Revision ID: 20260912_workspace_search_indexes
Revises: 20260909_book_data_generations

The indexes back author-workspace search projections only. They are backend
tables and intentionally receive no Supabase Data API grants.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260912_workspace_search_indexes"
down_revision: str | Sequence[str] | None = "20260909_book_data_generations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


SEARCH_INDEXES: tuple[tuple[str, str, str], ...] = (
    (
        "novel_scenes",
        "ix_novel_scenes_text_search",
        "to_tsvector('simple', coalesce(title, '') || ' ' || "
        "coalesce(description, '') || ' ' || coalesce(body, ''))",
    ),
    (
        "book_vault_notes",
        "ix_book_vault_notes_text_search",
        "to_tsvector('simple', coalesce(path, '') || ' ' || coalesce(content, ''))",
    ),
)


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        name
        for index in inspector.get_indexes(table_name)
        if isinstance(name := index.get("name"), str)
    }


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    for table_name, index_name, expression in SEARCH_INDEXES:
        if table_name not in tables or index_name in _index_names(inspector, table_name):
            continue
        op.create_index(
            index_name,
            table_name,
            [sa.text(expression)],
            postgresql_using="gin",
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())
    for table_name, index_name, _expression in SEARCH_INDEXES:
        if table_name in tables and index_name in _index_names(inspector, table_name):
            op.drop_index(index_name, table_name=table_name)
