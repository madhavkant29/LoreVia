"""Verify the Vault Note uniqueness repair against the local test schema."""

from __future__ import annotations

import uuid
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine

import tests.conftest as conftest
from app.models.book import Book, VaultNote
from app.models.user import User

MIGRATION_PATH = (
    Path(__file__).resolve().parents[2]
    / "app"
    / "db"
    / "migrations"
    / "versions"
    / "20261028_vault_source_unique.py"
)


def _load_migration():
    spec = spec_from_file_location("vault_source_unique_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.asyncio
async def test_vault_source_unique_migration_removes_old_constraint_and_downgrades(
    setup_engine, setup_db, monkeypatch
) -> None:
    migration = _load_migration()
    engine = create_engine(conftest.TEST_DB, echo=False)
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.execute(
                    sa.text(
                        "ALTER TABLE book_vault_notes ADD CONSTRAINT "
                        "uq_book_vault_notes_user_book_path UNIQUE (user_id, book_id, path)"
                    )
                )
                monkeypatch.setattr(
                    migration, "op", Operations(MigrationContext.configure(connection))
                )

                migration.upgrade()
                migration.upgrade()
                constraints = {
                    item["name"]
                    for item in sa.inspect(connection).get_unique_constraints("book_vault_notes")
                }
                assert migration.OLD_CONSTRAINT not in constraints
                assert migration.SOURCE_CONSTRAINT in constraints

                user_id, book_id = uuid.uuid4(), uuid.uuid4()
                connection.execute(
                    sa.insert(User).values(
                        id=user_id,
                        email=f"vault-{user_id}@lorevia.app",
                        username=f"vault-{user_id.hex[:12]}",
                        password_hash="hash",
                    )
                )
                connection.execute(
                    sa.insert(Book).values(
                        id=book_id,
                        user_id=user_id,
                        title="Vault migration",
                        format="manual",
                        s3_key="books/vault-migration.txt",
                    )
                )
                first_id, second_id = uuid.uuid4(), uuid.uuid4()
                for note_id, source in (
                    (first_id, "character_bible"),
                    (second_id, "user_notes"),
                ):
                    connection.execute(
                        sa.insert(VaultNote).values(
                            id=note_id,
                            user_id=user_id,
                            book_id=book_id,
                            path="Characters/Mara.md",
                            source=source,
                            content="Evidence-backed note",
                        )
                    )
                with pytest.raises(RuntimeError, match="different sources share a path"):
                    migration.downgrade()
                connection.execute(sa.delete(VaultNote).where(VaultNote.id == second_id))

                migration.downgrade()
                migration.downgrade()
                constraints = {
                    item["name"]
                    for item in sa.inspect(connection).get_unique_constraints("book_vault_notes")
                }
                assert migration.OLD_CONSTRAINT in constraints
                assert migration.SOURCE_CONSTRAINT in constraints

                connection.execute(
                    sa.text(
                        "ALTER TABLE book_vault_notes DROP CONSTRAINT "
                        "uq_book_vault_notes_user_book_path_source"
                    )
                )
                with pytest.raises(RuntimeError, match="source-aware constraint exists"):
                    migration.upgrade()
            finally:
                transaction.rollback()
    finally:
        engine.dispose()
