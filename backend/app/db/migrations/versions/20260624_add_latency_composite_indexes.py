"""Add composite indexes for latency-critical reads.

Revision ID: 20260624_add_latency_indexes
Revises: 20260623_add_task_dispatch_outbox
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260624_add_latency_indexes"
down_revision: str | Sequence[str] | None = "20260623_add_task_dispatch_outbox"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


INDEXES: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "books": (
        ("ix_books_user_hidden_created", ("user_id", "hidden_at", "created_at")),
    ),
    "book_collaborators": (
        (
            "ix_book_collaborators_email_status_invited",
            ("email", "invite_status", "invited_at"),
        ),
    ),
    "book_chunks": (
        ("ix_book_chunks_book_chunk", ("book_id", "chunk_index")),
    ),
    "book_notes": (
        ("ix_book_notes_book_chapter_updated", ("book_id", "chapter_number", "updated_at")),
        ("ix_book_notes_user_updated", ("user_id", "updated_at")),
    ),
    "characters": (
        ("ix_characters_book_first_name", ("book_id", "first_chapter", "name")),
    ),
    "character_relationships": (
        ("ix_character_relationships_book_from", ("book_id", "from_chapter")),
        (
            "ix_character_relationships_book_a_from",
            ("book_id", "character_a_id", "from_chapter"),
        ),
        (
            "ix_character_relationships_book_b_from",
            ("book_id", "character_b_id", "from_chapter"),
        ),
    ),
    "character_states": (
        ("ix_character_states_character_chapter", ("character_id", "at_chapter")),
    ),
    "chapter_summaries": (
        ("ix_chapter_summaries_chapter_mode", ("chapter_id", "mode")),
    ),
    "manuscript_annotations": (
        (
            "ix_manuscript_annotations_book_chapter_created",
            ("book_id", "chapter_number", "created_at"),
        ),
    ),
    "quote_entries": (
        ("ix_quote_entries_user_created", ("user_id", "created_at")),
    ),
    "series_books": (
        ("ix_series_books_series_position_book", ("series_id", "position", "book_id")),
    ),
    "wiki_entries": (
        ("ix_wiki_entries_book_type_name", ("book_id", "entry_type", "name")),
    ),
    "world_building_documents": (
        (
            "ix_world_building_documents_book_active_updated",
            ("book_id", "is_active", "updated_at", "created_at"),
        ),
    ),
    "world_canonical_identities": (
        (
            "ix_world_canonical_identities_book_updated",
            ("book_id", "updated_at", "created_at"),
        ),
    ),
    "world_elements": (
        ("ix_world_elements_book_usage_name", ("book_id", "usage_count", "name")),
        ("ix_world_elements_book_scope_name", ("book_id", "source_scope", "name")),
    ),
    "world_notes": (
        ("ix_world_notes_book_type_created", ("book_id", "note_type", "created_at")),
        (
            "ix_world_notes_book_chapter_type_created",
            ("book_id", "chapter_number", "note_type", "created_at"),
        ),
    ),
}


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _tables(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _indexes(inspector: sa.Inspector, table: str) -> set[str]:
    return {
        name
        for index in inspector.get_indexes(table)
        if isinstance(name := index.get("name"), str)
    }


def upgrade() -> None:
    inspector = _inspector()
    tables = _tables(inspector)
    for table, definitions in INDEXES.items():
        if table not in tables:
            continue
        existing_indexes = _indexes(inspector, table)
        for name, columns in definitions:
            if name not in existing_indexes:
                op.create_index(name, table, list(columns))


def downgrade() -> None:
    inspector = _inspector()
    tables = _tables(inspector)
    for table, definitions in reversed(tuple(INDEXES.items())):
        if table not in tables:
            continue
        existing_indexes = _indexes(inspector, table)
        for name, _columns in reversed(definitions):
            if name in existing_indexes:
                op.drop_index(name, table_name=table)
