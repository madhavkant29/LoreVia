"""Verify composite indexes created by 20260624_add_latency_composite_indexes.py."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine

import tests.conftest as _conftest

MIGRATION_FILE = "20260624_add_latency_composite_indexes.py"

EXPECTED_INDEXES: list[tuple[str, str]] = [
    ("books", "ix_books_user_hidden_created"),
    ("book_collaborators", "ix_book_collaborators_email_status_invited"),
    ("book_notes", "ix_book_notes_book_chapter_updated"),
    ("book_notes", "ix_book_notes_user_updated"),
    ("manuscript_annotations", "ix_manuscript_annotations_book_chapter_created"),
    ("series_books", "ix_series_books_series_position_book"),
    ("characters", "ix_characters_book_first_name"),
    ("character_states", "ix_character_states_character_chapter"),
    ("book_chunks", "ix_book_chunks_book_chunk"),
    ("character_relationships", "ix_character_relationships_book_from"),
    ("character_relationships", "ix_character_relationships_book_a_from"),
    ("character_relationships", "ix_character_relationships_book_b_from"),
    ("chapter_summaries", "ix_chapter_summaries_chapter_mode"),
    ("wiki_entries", "ix_wiki_entries_book_type_name"),
    ("quote_entries", "ix_quote_entries_user_created"),
    ("world_building_documents", "ix_world_building_documents_book_active_updated"),
    ("world_elements", "ix_world_elements_book_usage_name"),
    ("world_elements", "ix_world_elements_book_scope_name"),
    ("world_canonical_identities", "ix_world_canonical_identities_book_updated"),
    ("world_notes", "ix_world_notes_book_type_created"),
    ("world_notes", "ix_world_notes_book_chapter_type_created"),
]


def _load_migration_module():
    module_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "db"
        / "migrations"
        / "versions"
        / MIGRATION_FILE
    )
    spec = spec_from_file_location("add_latency_composite_indexes", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sync_engine():
    return create_engine(_conftest.TEST_DB, echo=False)


async def _get_existing_indexes(engine) -> set[str]:
    async with engine.connect() as conn:
        result = await conn.execute(
            sa.text(
                """SELECT indexname FROM pg_indexes
                   WHERE schemaname = 'public'
                     AND tablename = ANY(:tables)"""
            ),
            {"tables": sorted({table for table, _ in EXPECTED_INDEXES})},
        )
        return {row[0] for row in result}


@pytest.mark.asyncio
async def test_latency_indexes_upgrade_is_idempotent(setup_engine, setup_db, monkeypatch) -> None:
    migration = _load_migration_module()
    engine = _sync_engine()
    try:
        with engine.connect() as sync_conn:
            ctx = MigrationContext.configure(sync_conn)
            monkeypatch.setattr(migration, "op", Operations(ctx))
            migration.upgrade()
            sync_conn.commit()

        existing_first = await _get_existing_indexes(_conftest.engine_test)

        with engine.connect() as sync_conn:
            ctx = MigrationContext.configure(sync_conn)
            monkeypatch.setattr(migration, "op", Operations(ctx))
            migration.upgrade()
            sync_conn.commit()

        existing_second = await _get_existing_indexes(_conftest.engine_test)
        expected_names = {name for _, name in EXPECTED_INDEXES}
        assert expected_names <= existing_first
        assert existing_first == existing_second
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_latency_indexes_downgrade_removes_created_indexes(
    setup_engine, setup_db, monkeypatch
) -> None:
    migration = _load_migration_module()
    engine = _sync_engine()
    try:
        with engine.connect() as sync_conn:
            ctx = MigrationContext.configure(sync_conn)
            monkeypatch.setattr(migration, "op", Operations(ctx))
            migration.upgrade()
            sync_conn.commit()

        with engine.connect() as sync_conn:
            ctx = MigrationContext.configure(sync_conn)
            monkeypatch.setattr(migration, "op", Operations(ctx))
            migration.downgrade()
            sync_conn.commit()

        existing = await _get_existing_indexes(_conftest.engine_test)
        expected_names = {name for _, name in EXPECTED_INDEXES}
        leftover = expected_names & existing
        assert not leftover, f"Indexes not cleaned up by downgrade: {leftover}"
    finally:
        engine.dispose()
