"""Replace fixed IVFFlat vector indexes with HNSW indexes.

Revision ID: 20260620_replace_vector_indexes_hnsw
Revises: 20260620_add_processing_allowances

The upgrade intentionally removes the obsolete IVFFlat indexes only after the
replacement HNSW indexes exist. Run the pgvector version preflight and review
the destructive index operations before applying this migration remotely.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260620_replace_vector_indexes_hnsw"
down_revision: str | Sequence[str] | None = "20260620_add_processing_allowances"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _parse_vector_version(raw: str) -> tuple[int, int, int]:
    parts = tuple(int(part) for part in raw.split(".") if part.isdigit())
    return (parts + (0, 0, 0))[:3]


def _vector_version() -> tuple[int, int, int]:
    raw = str(
        op.get_bind()
        .execute(sa.text("SELECT extversion FROM pg_extension WHERE extname = 'vector'"))
        .scalar()
        or "0"
    )
    return _parse_vector_version(raw)


def _index_names() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {
        index["name"]
        for table_name in ("book_chunks", "characters")
        for index in inspector.get_indexes(table_name)
        if index.get("name")
    }


def upgrade() -> None:
    if _vector_version() < (0, 5, 0):
        raise RuntimeError("pgvector 0.5.0 or newer is required for HNSW indexes")

    names = _index_names()
    with op.get_context().autocommit_block():
        if "ix_book_chunks_embedding_hnsw" not in names:
            op.execute(
                "CREATE INDEX CONCURRENTLY ix_book_chunks_embedding_hnsw "
                "ON book_chunks USING hnsw (embedding vector_cosine_ops) "
                "WITH (m = 16, ef_construction = 64)"
            )
        if "ix_characters_embedding_hnsw" not in names:
            op.execute(
                "CREATE INDEX CONCURRENTLY ix_characters_embedding_hnsw "
                "ON characters USING hnsw (embedding vector_cosine_ops) "
                "WITH (m = 16, ef_construction = 64)"
            )
        if "ix_book_chunks_embedding_ivfflat" in names:
            op.execute("DROP INDEX CONCURRENTLY ix_book_chunks_embedding_ivfflat")
        if "ix_characters_embedding_ivfflat" in names:
            op.execute("DROP INDEX CONCURRENTLY ix_characters_embedding_ivfflat")
    op.execute("ANALYZE book_chunks")
    op.execute("ANALYZE characters")


def downgrade() -> None:
    names = _index_names()
    with op.get_context().autocommit_block():
        if "ix_book_chunks_embedding_ivfflat" not in names:
            op.execute(
                "CREATE INDEX CONCURRENTLY ix_book_chunks_embedding_ivfflat "
                "ON book_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
            )
        if "ix_characters_embedding_ivfflat" not in names:
            op.execute(
                "CREATE INDEX CONCURRENTLY ix_characters_embedding_ivfflat "
                "ON characters USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
            )
        if "ix_book_chunks_embedding_hnsw" in names:
            op.execute("DROP INDEX CONCURRENTLY ix_book_chunks_embedding_hnsw")
        if "ix_characters_embedding_hnsw" in names:
            op.execute("DROP INDEX CONCURRENTLY ix_characters_embedding_hnsw")
    op.execute("ANALYZE book_chunks")
    op.execute("ANALYZE characters")
