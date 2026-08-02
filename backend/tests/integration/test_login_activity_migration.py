"""Verify user_login_activity migration creates table, backfills, and is idempotent."""

from __future__ import annotations

from datetime import date
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text

import tests.conftest as _conftest

MIGRATION_FILE = "20260529_add_user_login_activity_table.py"


def _load_migration_module():
    module_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "db"
        / "migrations"
        / "versions"
        / MIGRATION_FILE
    )
    spec = spec_from_file_location("add_user_login_activity_table", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sync_engine():
    url = _conftest.TEST_DB
    return create_engine(url, echo=False)


async def _insert_test_user(engine) -> str:
    import uuid

    user_id = uuid.uuid4()
    async with engine.connect() as conn:
        await conn.execute(
            sa.text("ALTER TABLE users ADD COLUMN IF NOT EXISTS login_activity_dates DATE[]"),
        )
        await conn.execute(
            sa.text(
                "INSERT INTO users (id, email, password_hash, tier, reading_mode) VALUES (:id, :email, :hash, :tier, :reading_mode)"
            ),
            {
                "id": user_id,
                "email": f"test-{user_id}@lorevia.app",
                "hash": "$2b$12$LJ3m4ys3GZfnYMz8kVsKaOi6ELVNrfcA5KZpGJb5qM3VBQhY1Xf3u",
                "tier": "free",
                "reading_mode": "casual",
            },
        )
        await conn.commit()
    return str(user_id)


async def _get_table_rows(engine, user_id: str) -> list[date]:
    async with engine.connect() as conn:
        result = await conn.execute(
            sa.text(
                "SELECT DISTINCT login_date FROM user_login_activity WHERE user_id = :uid ORDER BY login_date"
            ),
            {"uid": user_id},
        )
        rows = []
        for row in result:
            val = row[0]
            if hasattr(val, "date"):
                val = val.date()
            rows.append(val)
        return rows


@pytest.mark.asyncio
async def test_upgrade_creates_table_and_index(setup_engine, setup_db, monkeypatch) -> None:
    migration = _load_migration_module()

    engine = _sync_engine()
    try:
        with engine.connect() as sync_conn:
            ctx = MigrationContext.configure(sync_conn)
            real_op = Operations(ctx)
            monkeypatch.setattr(migration, "op", real_op)

            migration.upgrade()
            sync_conn.commit()

        async with _conftest.engine_test.connect() as conn:
            tables = {
                row[0]
                for row in (
                    await conn.execute(
                        sa.text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
                    )
                ).fetchall()
            }
            assert "user_login_activity" in tables

            indexes = {
                row[0]
                for row in (
                    await conn.execute(
                        sa.text(
                            "SELECT indexname FROM pg_indexes WHERE schemaname = 'public' AND tablename = 'user_login_activity'"
                        )
                    )
                ).fetchall()
            }
            assert "ix_user_login_activity_user_date" in indexes
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_backfill_from_login_activity_dates(setup_engine, setup_db, monkeypatch) -> None:
    migration = _load_migration_module()

    user_id = await _insert_test_user(_conftest.engine_test)

    async with _conftest.engine_test.connect() as conn:
        await conn.execute(
            sa.text("UPDATE users SET login_activity_dates = :dates WHERE id = :uid"),
            {
                "dates": [date(2026, 5, 10), date(2026, 5, 11), date(2026, 5, 12)],
                "uid": user_id,
            },
        )
        await conn.commit()

    engine = _sync_engine()
    try:
        with engine.connect() as sync_conn:
            ctx = MigrationContext.configure(sync_conn)
            real_op = Operations(ctx)
            monkeypatch.setattr(migration, "op", real_op)

            migration.upgrade()
            sync_conn.commit()

        rows = await _get_table_rows(_conftest.engine_test, user_id)
        assert rows == [date(2026, 5, 10), date(2026, 5, 11), date(2026, 5, 12)]
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_backfill_handles_null_arrays(setup_engine, setup_db, monkeypatch) -> None:
    migration = _load_migration_module()

    user_id = await _insert_test_user(_conftest.engine_test)

    async with _conftest.engine_test.connect() as conn:
        await conn.execute(
            sa.text("UPDATE users SET login_activity_dates = NULL WHERE id = :uid"),
            {"uid": user_id},
        )
        await conn.commit()

    engine = _sync_engine()
    try:
        with engine.connect() as sync_conn:
            ctx = MigrationContext.configure(sync_conn)
            real_op = Operations(ctx)
            monkeypatch.setattr(migration, "op", real_op)

            migration.upgrade()
            sync_conn.commit()

        rows = await _get_table_rows(_conftest.engine_test, user_id)
        assert rows == []
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_backfill_handles_empty_arrays(setup_engine, setup_db, monkeypatch) -> None:
    migration = _load_migration_module()

    user_id = await _insert_test_user(_conftest.engine_test)

    async with _conftest.engine_test.connect() as conn:
        await conn.execute(
            sa.text("UPDATE users SET login_activity_dates = '{}' WHERE id = :uid"),
            {"uid": user_id},
        )
        await conn.commit()

    engine = _sync_engine()
    try:
        with engine.connect() as sync_conn:
            ctx = MigrationContext.configure(sync_conn)
            real_op = Operations(ctx)
            monkeypatch.setattr(migration, "op", real_op)

            migration.upgrade()
            sync_conn.commit()

        rows = await _get_table_rows(_conftest.engine_test, user_id)
        assert rows == []
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_upgrade_is_idempotent(setup_engine, setup_db, monkeypatch) -> None:
    migration = _load_migration_module()

    user_id = await _insert_test_user(_conftest.engine_test)

    async with _conftest.engine_test.connect() as conn:
        await conn.execute(
            sa.text("UPDATE users SET login_activity_dates = :dates WHERE id = :uid"),
            {
                "dates": [date(2026, 5, 14), date(2026, 5, 15)],
                "uid": user_id,
            },
        )
        await conn.commit()

    engine = _sync_engine()
    try:
        with engine.connect() as sync_conn:
            ctx = MigrationContext.configure(sync_conn)
            real_op = Operations(ctx)
            monkeypatch.setattr(migration, "op", real_op)

            migration.upgrade()
            sync_conn.commit()

        rows_first = await _get_table_rows(_conftest.engine_test, user_id)

        with engine.connect() as sync_conn:
            ctx = MigrationContext.configure(sync_conn)
            real_op = Operations(ctx)
            monkeypatch.setattr(migration, "op", real_op)

            migration.upgrade()
            sync_conn.commit()

        rows_second = await _get_table_rows(_conftest.engine_test, user_id)

        assert rows_first == rows_second == [date(2026, 5, 14), date(2026, 5, 15)]
    finally:
        engine.dispose()
