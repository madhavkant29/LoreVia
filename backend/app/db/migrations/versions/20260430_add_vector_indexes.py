"""Add IVFFlat vector indexes for character deduplication and semantic search.

Revision ID: 20260430_add_vector_indexes
Revises: 20260430_obsidian_note_source
Create Date: 2026-04-30 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260430_add_vector_indexes"
down_revision: str | None = "20260430_obsidian_note_source"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        index_name
        for index in inspector.get_indexes(table_name)
        if (index_name := index.get("name")) is not None
    }


def _create_ivfflat_index(table_name: str, index_name: str, lists: int) -> None:
    op.create_index(
        index_name,
        table_name,
        ["embedding"],
        postgresql_using="ivfflat",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_with={"lists": lists},
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "characters" in tables:
        indexes = _index_names(inspector, "characters")
        if "ix_characters_embedding_ivfflat" not in indexes:
            _create_ivfflat_index("characters", "ix_characters_embedding_ivfflat", lists=100)

    if "book_chunks" in tables:
        indexes = _index_names(inspector, "book_chunks")
        if "ix_book_chunks_embedding_ivfflat" not in indexes:
            _create_ivfflat_index("book_chunks", "ix_book_chunks_embedding_ivfflat", lists=100)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "book_chunks" in tables:
        indexes = _index_names(inspector, "book_chunks")
        if "ix_book_chunks_embedding_ivfflat" in indexes:
            op.drop_index("ix_book_chunks_embedding_ivfflat", table_name="book_chunks")

    if "characters" in tables:
        indexes = _index_names(inspector, "characters")
        if "ix_characters_embedding_ivfflat" in indexes:
            op.drop_index("ix_characters_embedding_ivfflat", table_name="characters")
