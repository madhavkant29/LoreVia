"""Verify device_trials uniqueness migration deduplicates links and is idempotent."""

from __future__ import annotations

import uuid
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine

import tests.conftest as _conftest

MIGRATION_FILE = "20260602_enforce_device_trial_user_uniqueness.py"
CONSTRAINT_NAME = "uq_device_trials_user_device"


def _load_migration_module():
    module_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "db"
        / "migrations"
        / "versions"
        / MIGRATION_FILE
    )
    spec = spec_from_file_location("enforce_device_trial_user_uniqueness", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sync_engine():
    return create_engine(_conftest.TEST_DB, echo=False)


async def _seed_duplicate_device_links() -> tuple[str, str]:
    user_id = str(uuid.uuid4())
    device_hash = "device-hash-duplicate-001"

    async with _conftest.engine_test.connect() as conn:
        await conn.execute(
            sa.text(f"ALTER TABLE device_trials DROP CONSTRAINT IF EXISTS {CONSTRAINT_NAME}")
        )
        await conn.execute(
            sa.text(
                """
                INSERT INTO users (id, email, password_hash, tier, reading_mode)
                VALUES (:id, :email, :hash, :tier, :reading_mode)
                """
            ),
            {
                "id": user_id,
                "email": f"migration-{user_id}@lorevia.app",
                "hash": "$2b$12$LJ3m4ys3GZfnYMz8kVsKaOi6ELVNrfcA5KZpGJb5qM3VBQhY1Xf3u",
                "tier": "free",
                "reading_mode": "casual",
            },
        )
        for _ in range(2):
            await conn.execute(
                sa.text(
                    """
                    INSERT INTO device_trials (id, user_id, device_id_hash)
                    VALUES (:id, :user_id, :device_id_hash)
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "user_id": user_id,
                    "device_id_hash": device_hash,
                },
            )
        await conn.commit()

    return user_id, device_hash


async def _device_trial_count(user_id: str, device_hash: str) -> int:
    async with _conftest.engine_test.connect() as conn:
        result = await conn.execute(
            sa.text(
                """
                SELECT COUNT(*) FROM device_trials
                WHERE user_id = :user_id AND device_id_hash = :device_id_hash
                """
            ),
            {"user_id": user_id, "device_id_hash": device_hash},
        )
        return int(result.scalar_one())


async def _constraint_exists() -> bool:
    async with _conftest.engine_test.connect() as conn:
        result = await conn.execute(
            sa.text(
                """
                SELECT 1
                FROM pg_constraint
                WHERE conrelid = 'device_trials'::regclass
                  AND conname = :constraint_name
                """
            ),
            {"constraint_name": CONSTRAINT_NAME},
        )
        return result.scalar_one_or_none() == 1


@pytest.mark.asyncio
async def test_upgrade_deduplicates_device_trial_links_and_adds_constraint(
    setup_engine, setup_db, monkeypatch
) -> None:
    migration = _load_migration_module()
    user_id, device_hash = await _seed_duplicate_device_links()

    engine = _sync_engine()
    try:
        with engine.connect() as sync_conn:
            ctx = MigrationContext.configure(sync_conn)
            real_op = Operations(ctx)
            monkeypatch.setattr(migration, "op", real_op)

            migration.upgrade()
            sync_conn.commit()

        assert await _device_trial_count(user_id, device_hash) == 1
        assert await _constraint_exists() is True
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_upgrade_is_idempotent(setup_engine, setup_db, monkeypatch) -> None:
    migration = _load_migration_module()
    user_id, device_hash = await _seed_duplicate_device_links()

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

            migration.upgrade()
            sync_conn.commit()

        assert await _device_trial_count(user_id, device_hash) == 1
        assert await _constraint_exists() is True
    finally:
        engine.dispose()
