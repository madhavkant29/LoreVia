"""Remove orphaned indexes and clean up login_activity_dates drift.

Revision ID: 20260530_remove_orphaned_indexes
Revises: ce5d9a8fa579
Create Date: 2026-05-30 00:00:00.000000

Drops indexes that exist in the database but were removed from model definitions.
Also drops the login_activity_dates ARRAY column from users if it still exists
(e.g., after a downgrade that re-added it).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260530_remove_orphaned_indexes"
down_revision: str | Sequence[str] | None = "ce5d9a8fa579"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORPHANED_INDEXES: list[tuple[str, str]] = [
    ("ix_book_chunks_chunk_index", "book_chunks"),
    ("ix_character_relationships_character_a_id", "character_relationships"),
    ("ix_character_relationships_character_b_id", "character_relationships"),
    ("ix_character_relationships_from_chapter", "character_relationships"),
    ("ix_character_relationships_to_chapter", "character_relationships"),
    ("ix_character_states_at_chapter", "character_states"),
    ("ix_characters_book_visibility_approval", "characters"),
    ("ix_characters_first_chapter", "characters"),
    ("ix_characters_last_seen_chapter", "characters"),
    ("ix_characters_name", "characters"),
    ("ix_characters_role", "characters"),
    ("ix_novel_scenes_book_id_chapter_number_status", "novel_scenes"),
    ("ix_reading_progress_book_id", "reading_progress"),
    ("ix_reading_sessions_book_id", "reading_sessions"),
    ("ix_wiki_entries_entry_type", "wiki_entries"),
    ("ix_world_elements_book_id_element_type", "world_elements"),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    for index_name, table_name in ORPHANED_INDEXES:
        if table_name not in tables:
            continue
        indexes = {idx["name"] for idx in inspector.get_indexes(table_name)}
        if index_name in indexes:
            op.drop_index(index_name, table_name=table_name)

    if "users" in tables:
        columns = {col["name"] for col in inspector.get_columns("users")}
        if "login_activity_dates" in columns:
            op.drop_column("users", "login_activity_dates")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    for index_name, table_name in ORPHANED_INDEXES:
        if table_name not in tables:
            continue
        columns = {col["name"] for col in inspector.get_columns(table_name)}
        indexes = {idx["name"] for idx in inspector.get_indexes(table_name)}
        if index_name not in indexes:
            if index_name == "ix_book_chunks_chunk_index" and "chunk_index" in columns:
                op.create_index(index_name, table_name, ["chunk_index"])
            elif index_name == "ix_character_relationships_character_a_id" and "character_a_id" in columns:
                op.create_index(index_name, table_name, ["character_a_id"])
            elif index_name == "ix_character_relationships_character_b_id" and "character_b_id" in columns:
                op.create_index(index_name, table_name, ["character_b_id"])
            elif index_name == "ix_character_relationships_from_chapter" and "from_chapter" in columns:
                op.create_index(index_name, table_name, ["from_chapter"])
            elif index_name == "ix_character_relationships_to_chapter" and "to_chapter" in columns:
                op.create_index(index_name, table_name, ["to_chapter"])
            elif index_name == "ix_character_states_at_chapter" and "at_chapter" in columns:
                op.create_index(index_name, table_name, ["at_chapter"])
            elif index_name == "ix_characters_book_visibility_approval" and "book_id" in columns and "visibility_state" in columns and "approval_state" in columns:
                op.create_index(index_name, table_name, ["book_id", "visibility_state", "approval_state"])
            elif index_name == "ix_characters_first_chapter" and "first_chapter" in columns:
                op.create_index(index_name, table_name, ["first_chapter"])
            elif index_name == "ix_characters_last_seen_chapter" and "last_seen_chapter" in columns:
                op.create_index(index_name, table_name, ["last_seen_chapter"])
            elif index_name == "ix_characters_name" and "name" in columns:
                op.create_index(index_name, table_name, ["name"])
            elif index_name == "ix_characters_role" and "role" in columns:
                op.create_index(index_name, table_name, ["role"])
            elif index_name == "ix_novel_scenes_book_id_chapter_number_status" and "book_id" in columns and "chapter_number" in columns and "status" in columns:
                op.create_index(index_name, table_name, ["book_id", "chapter_number", "status"])
            elif index_name == "ix_reading_progress_book_id" and "book_id" in columns:
                op.create_index(index_name, table_name, ["book_id"])
            elif index_name == "ix_reading_sessions_book_id" and "book_id" in columns:
                op.create_index(index_name, table_name, ["book_id"])
            elif index_name == "ix_wiki_entries_entry_type" and "entry_type" in columns:
                op.create_index(index_name, table_name, ["entry_type"])
            elif index_name == "ix_world_elements_book_id_element_type" and "book_id" in columns and "element_type" in columns:
                op.create_index(index_name, table_name, ["book_id", "element_type"])

    if "users" in tables:
        columns = {col["name"] for col in inspector.get_columns("users")}
        if "login_activity_dates" not in columns:
            op.add_column("users", sa.Column("login_activity_dates", sa.ARRAY(sa.Date()), nullable=True))
