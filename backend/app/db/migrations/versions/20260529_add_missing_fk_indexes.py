"""Add missing FK and filter indexes for query performance.

Revision ID: 20260529_add_missing_fk_indexes
Revises: a1b2c3d4e5f6
Create Date: 2026-05-29 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision: str = "20260529_add_missing_fk_indexes"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | None = None
depends_on: str | None = None


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {idx["name"] for idx in inspector.get_indexes(table_name) if idx.get("name")}


def _pg_trgm_available(bind) -> bool:
    result = bind.execute(sa.text("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'"))
    return result.scalar() == 1


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "character_relationships" in tables:
        indexes = _index_names(inspector, "character_relationships")
        if "ix_character_relationships_character_a_id" not in indexes:
            op.create_index("ix_character_relationships_character_a_id", "character_relationships", ["character_a_id"])
        if "ix_character_relationships_character_b_id" not in indexes:
            op.create_index("ix_character_relationships_character_b_id", "character_relationships", ["character_b_id"])
        if "ix_character_relationships_from_chapter" not in indexes:
            op.create_index("ix_character_relationships_from_chapter", "character_relationships", ["from_chapter"])
        if "ix_character_relationships_to_chapter" not in indexes:
            op.create_index("ix_character_relationships_to_chapter", "character_relationships", ["to_chapter"])

    if "character_states" in tables:
        indexes = _index_names(inspector, "character_states")
        if "ix_character_states_at_chapter" not in indexes:
            op.create_index("ix_character_states_at_chapter", "character_states", ["at_chapter"])

    if "reading_progress" in tables:
        indexes = _index_names(inspector, "reading_progress")
        if "ix_reading_progress_book_id" not in indexes:
            op.create_index("ix_reading_progress_book_id", "reading_progress", ["book_id"])

    if "reading_sessions" in tables:
        indexes = _index_names(inspector, "reading_sessions")
        if "ix_reading_sessions_book_id" not in indexes:
            op.create_index("ix_reading_sessions_book_id", "reading_sessions", ["book_id"])

    if "characters" in tables:
        indexes = _index_names(inspector, "characters")
        if "ix_characters_name" not in indexes:
            if _pg_trgm_available(bind):
                op.execute(
                    sa.text(
                        "CREATE INDEX IF NOT EXISTS ix_characters_name "
                        "ON characters USING gin (name gin_trgm_ops)"
                    )
                )
            else:
                op.create_index("ix_characters_name", "characters", ["name"])
        if "ix_characters_role" not in indexes:
            op.create_index("ix_characters_role", "characters", ["role"])
        if "ix_characters_first_chapter" not in indexes:
            op.create_index("ix_characters_first_chapter", "characters", ["first_chapter"])
        if "ix_characters_last_seen_chapter" not in indexes:
            op.create_index("ix_characters_last_seen_chapter", "characters", ["last_seen_chapter"])

    if "book_chunks" in tables:
        indexes = _index_names(inspector, "book_chunks")
        if "ix_book_chunks_chunk_index" not in indexes:
            op.create_index("ix_book_chunks_chunk_index", "book_chunks", ["chunk_index"])

    if "wiki_entries" in tables:
        indexes = _index_names(inspector, "wiki_entries")
        if "ix_wiki_entries_entry_type" not in indexes:
            op.create_index("ix_wiki_entries_entry_type", "wiki_entries", ["entry_type"])

    if "world_elements" in tables:
        indexes = _index_names(inspector, "world_elements")
        if "ix_world_elements_book_id_element_type" not in indexes:
            op.create_index("ix_world_elements_book_id_element_type", "world_elements", ["book_id", "element_type"])

    if "novel_scenes" in tables:
        indexes = _index_names(inspector, "novel_scenes")
        if "ix_novel_scenes_book_id_chapter_number_status" not in indexes:
            op.create_index("ix_novel_scenes_book_id_chapter_number_status", "novel_scenes", ["book_id", "chapter_number", "status"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    index_drops: list[tuple[str, str]] = [
        ("character_relationships", "ix_character_relationships_character_a_id"),
        ("character_relationships", "ix_character_relationships_character_b_id"),
        ("character_relationships", "ix_character_relationships_from_chapter"),
        ("character_relationships", "ix_character_relationships_to_chapter"),
        ("character_states", "ix_character_states_at_chapter"),
        ("reading_progress", "ix_reading_progress_book_id"),
        ("reading_sessions", "ix_reading_sessions_book_id"),
        ("characters", "ix_characters_name"),
        ("characters", "ix_characters_role"),
        ("characters", "ix_characters_first_chapter"),
        ("characters", "ix_characters_last_seen_chapter"),
        ("book_chunks", "ix_book_chunks_chunk_index"),
        ("wiki_entries", "ix_wiki_entries_entry_type"),
        ("world_elements", "ix_world_elements_book_id_element_type"),
        ("novel_scenes", "ix_novel_scenes_book_id_chapter_number_status"),
    ]

    for table_name, index_name in index_drops:
        if table_name in tables:
            idx_names = _index_names(inspector, table_name)
            if index_name in idx_names:
                op.drop_index(index_name, table_name=table_name)
