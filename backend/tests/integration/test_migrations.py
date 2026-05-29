"""Verify FK and filter indexes created by 20260529_add_missing_fk_indexes.py."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine

import tests.conftest as _conftest


MIGRATION_FILE = "20260529_add_missing_fk_indexes.py"

EXPECTED_INDEXES: list[tuple[str, str]] = [
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


def _load_migration_module():
    module_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "db"
        / "migrations"
        / "versions"
        / MIGRATION_FILE
    )
    spec = spec_from_file_location("add_missing_fk_indexes", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sync_engine():
    """Create a sync engine for alembic operations.

    _conftest.engine_test is an AsyncEngine whose sync_engine attribute
    can raise MissingGreenlet when called inside an async test.  Build a
    standalone sync engine from the same connection URL instead.
    """
    url = _conftest.TEST_DB
    return create_engine(url, echo=False)


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
async def test_fk_indexes_exist_after_upgrade(setup_engine, setup_db, monkeypatch) -> None:
    """Upgrade() creates all expected indexes and they appear in pg_indexes."""
    migration = _load_migration_module()

    engine = _sync_engine()
    try:
        with engine.connect() as sync_conn:
            ctx = MigrationContext.configure(sync_conn)
            real_op = Operations(ctx)
            monkeypatch.setattr(migration, "op", real_op)

            migration.upgrade()
            sync_conn.commit()

        existing = await _get_existing_indexes(_conftest.engine_test)
        expected_names = {name for _, name in EXPECTED_INDEXES}
        missing = expected_names - existing
        assert not missing, f"Missing indexes after upgrade: {missing}"
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_fk_indexes_gone_after_downgrade(setup_engine, setup_db, monkeypatch) -> None:
    """Downgrade() removes all indexes created by this migration."""
    migration = _load_migration_module()

    engine = _sync_engine()
    try:
        with engine.connect() as sync_conn:
            ctx = MigrationContext.configure(sync_conn)
            real_op = Operations(ctx)
            monkeypatch.setattr(migration, "op", real_op)

            migration.upgrade()
            sync_conn.commit()

        with engine.connect() as sync_conn:
            ctx = MigrationContext.configure(sync_conn)
            real_op = Operations(ctx)
            monkeypatch.setattr(migration, "op", real_op)

            migration.downgrade()
            sync_conn.commit()

        existing = await _get_existing_indexes(_conftest.engine_test)
        expected_names = {name for _, name in EXPECTED_INDEXES}
        leftover = expected_names & existing
        assert not leftover, f"Indexes not cleaned up by downgrade: {leftover}"
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_upgrade_is_idempotent(setup_engine, setup_db, monkeypatch) -> None:
    """Running upgrade() twice does not fail."""
    migration = _load_migration_module()

    engine = _sync_engine()
    try:
        with engine.connect() as sync_conn:
            ctx = MigrationContext.configure(sync_conn)
            real_op = Operations(ctx)
            monkeypatch.setattr(migration, "op", real_op)

            migration.upgrade()
            sync_conn.commit()

        existing_first = await _get_existing_indexes(_conftest.engine_test)

        with engine.connect() as sync_conn:
            ctx = MigrationContext.configure(sync_conn)
            real_op = Operations(ctx)
            monkeypatch.setattr(migration, "op", real_op)

            migration.upgrade()
            sync_conn.commit()

        existing_second = await _get_existing_indexes(_conftest.engine_test)

        expected_names = {name for _, name in EXPECTED_INDEXES}
        assert expected_names <= existing_first
        assert existing_first == existing_second
    finally:
        engine.dispose()
