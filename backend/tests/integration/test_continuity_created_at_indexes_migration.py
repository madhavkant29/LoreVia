"""Verify the continuity created-at index repair migration."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine

from tests import conftest

MIGRATION_FILE = "20260802_add_continuity_created_at_indexes.py"

EXPECTED_INDEXES: dict[str, str] = {
    "continuity_scans": "ix_continuity_scans_created_at",
    "continuity_observations": "ix_continuity_observations_created_at",
    "continuity_findings": "ix_continuity_findings_created_at",
}


def _load_migration_module():
    module_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "db"
        / "migrations"
        / "versions"
        / MIGRATION_FILE
    )
    spec = spec_from_file_location("add_continuity_created_at_indexes", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sync_engine():
    return create_engine(conftest.TEST_DB, echo=False)


async def _existing_indexes() -> set[str]:
    async with conftest.engine_test.connect() as connection:
        result = await connection.execute(
            sa.text(
                """SELECT indexname FROM pg_indexes
                   WHERE schemaname = 'public'
                     AND tablename = ANY(:tables)"""
            ),
            {"tables": sorted(EXPECTED_INDEXES)},
        )
        return {row[0] for row in result}


@pytest.mark.asyncio
async def test_upgrade_creates_missing_indexes_and_is_idempotent(
    setup_engine, setup_db, monkeypatch
) -> None:
    migration = _load_migration_module()
    expected_names = set(EXPECTED_INDEXES.values())
    engine = _sync_engine()
    try:
        with engine.connect() as connection:
            operations = Operations(MigrationContext.configure(connection))
            monkeypatch.setattr(migration, "op", operations)
            migration.downgrade()
            connection.commit()

        assert expected_names.isdisjoint(await _existing_indexes())

        with engine.connect() as connection:
            operations = Operations(MigrationContext.configure(connection))
            monkeypatch.setattr(migration, "op", operations)
            migration.upgrade()
            migration.upgrade()
            connection.commit()

        assert expected_names <= await _existing_indexes()
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_downgrade_removes_created_indexes(setup_engine, setup_db, monkeypatch) -> None:
    migration = _load_migration_module()
    expected_names = set(EXPECTED_INDEXES.values())
    engine = _sync_engine()
    try:
        with engine.connect() as connection:
            operations = Operations(MigrationContext.configure(connection))
            monkeypatch.setattr(migration, "op", operations)
            migration.upgrade()
            connection.commit()

        with engine.connect() as connection:
            operations = Operations(MigrationContext.configure(connection))
            monkeypatch.setattr(migration, "op", operations)
            migration.downgrade()
            connection.commit()

        assert expected_names.isdisjoint(await _existing_indexes())
    finally:
        engine.dispose()
