"""Verify the Voice Review decision migration creates and removes its schema."""

from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine

import tests.conftest as conftest

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "app"
    / "db"
    / "migrations"
    / "versions"
    / "20261018_add_voice_review_decisions.py"
)


def _load_migration():
    spec = spec_from_file_location("voice_review_decisions_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_voice_review_decisions_migration_creates_idempotent_schema_and_downgrades(
    setup_engine, setup_db, monkeypatch
) -> None:
    migration = _load_migration()
    engine = create_engine(conftest.TEST_DB, echo=False)
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                # The shared test fixture creates current ORM tables. Remove only
                # this table inside a transaction, then restore it by rollback.
                connection.execute(sa.text("DROP TABLE voice_review_decisions"))
                operations = Operations(MigrationContext.configure(connection))
                monkeypatch.setattr(migration, "op", operations)

                migration.upgrade()
                inspector = sa.inspect(connection)
                assert "voice_review_decisions" in inspector.get_table_names()
                assert {
                    "id",
                    "book_id",
                    "user_id",
                    "finding_key",
                    "decision",
                    "note",
                    "created_at",
                    "updated_at",
                } == {column["name"] for column in inspector.get_columns("voice_review_decisions")}
                assert {
                    "ix_voice_review_decisions_book_id",
                    "ix_voice_review_decisions_user_id",
                } <= {index["name"] for index in inspector.get_indexes("voice_review_decisions")}
                assert "uq_voice_review_decisions_user_finding" in {
                    constraint["name"]
                    for constraint in inspector.get_unique_constraints("voice_review_decisions")
                }
                assert {"books", "users"} == {
                    foreign_key["referred_table"]
                    for foreign_key in inspector.get_foreign_keys("voice_review_decisions")
                }

                migration.upgrade()
                migration.downgrade()
                assert "voice_review_decisions" not in sa.inspect(connection).get_table_names()
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
