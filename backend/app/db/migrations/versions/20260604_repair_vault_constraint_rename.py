"""Repair incomplete rename of obsidian-branded indexes and constraints to vault.

Revision ID: 20260604_repair_vault_constraint_rename
Revises: 20260604_rename_obsidian_to_vault
Create Date: 2026-06-04 00:01:00.000000

The 20260604_rename_obsidian_to_vault migration renamed the tables from
book_obsidian_* to book_vault_* but its upgrade() passed the wrong
arguments to the constraint/index rename helpers (new_table in both
positions), so those renames silently did nothing. This follow-up
repairs the leftover naming by renaming any remaining book_obsidian_*
indexes, PK constraints, FK constraints, and unique constraints on the
already-renamed book_vault_* tables.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260604_repair_vault_constraint_rename"
down_revision: str | None = "20260604_rename_obsidian_to_vault"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE_REPAIRS = [
    ("book_vault_notes", "book_obsidian_notes"),
    ("book_vault_note_links", "book_obsidian_note_links"),
    ("book_vault_note_backlinks", "book_obsidian_note_backlinks"),
    ("book_vault_note_tags", "book_obsidian_note_tags"),
    ("book_vault_note_series_links", "book_obsidian_note_series_links"),
]


def _repair_indexes(
    inspector: sa.Inspector, table_name: str, search: str, replace: str
) -> None:
    for idx in inspector.get_indexes(table_name):
        old_name = idx["name"]
        if search in old_name:
            new_name = old_name.replace(search, replace)
            existing = {e["name"] for e in inspector.get_indexes(table_name)}
            if new_name not in existing:
                op.execute(
                    f'ALTER INDEX "{old_name}" RENAME TO "{new_name}"'
                )


def _repair_fk_constraints(
    inspector: sa.Inspector, table_name: str, search: str, replace: str
) -> None:
    for fk in inspector.get_foreign_keys(table_name):
        old_name = fk["name"]
        if old_name and search in old_name:
            new_name = old_name.replace(search, replace)
            op.execute(
                f'ALTER TABLE "{table_name}" RENAME CONSTRAINT "{old_name}" TO "{new_name}"'
            )


def _repair_unique_constraints(
    inspector: sa.Inspector, table_name: str, search: str, replace: str
) -> None:
    for uc in inspector.get_unique_constraints(table_name):
        old_name = uc.get("name")
        if old_name and search in old_name:
            new_name = old_name.replace(search, replace)
            op.execute(
                f'ALTER TABLE "{table_name}" RENAME CONSTRAINT "{old_name}" TO "{new_name}"'
            )


def _repair_pk_constraint(
    inspector: sa.Inspector, table_name: str, search: str, replace: str
) -> None:
    pk_old = f"{search}_pkey"
    pk_new = f"{replace}_pkey"
    pk_constraint = inspector.get_pk_constraint(table_name)
    existing_name = pk_constraint.get("name") if pk_constraint else None
    if existing_name and existing_name == pk_old:
        op.execute(
            f'ALTER INDEX "{pk_old}" RENAME TO "{pk_new}"'
        )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    for table_name, old_prefix in _TABLE_REPAIRS:
        if table_name not in tables:
            continue

        _repair_pk_constraint(inspector, table_name, old_prefix, table_name)
        _repair_indexes(inspector, table_name, old_prefix, table_name)
        inspector = sa.inspect(bind)
        _repair_fk_constraints(inspector, table_name, old_prefix, table_name)
        inspector = sa.inspect(bind)
        _repair_unique_constraints(inspector, table_name, old_prefix, table_name)
        inspector = sa.inspect(bind)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    for table_name, old_prefix in _TABLE_REPAIRS:
        if table_name not in tables:
            continue

        _repair_unique_constraints(inspector, table_name, table_name, old_prefix)
        inspector = sa.inspect(bind)
        _repair_fk_constraints(inspector, table_name, table_name, old_prefix)
        inspector = sa.inspect(bind)
        _repair_indexes(inspector, table_name, table_name, old_prefix)
        inspector = sa.inspect(bind)
        _repair_pk_constraint(inspector, table_name, table_name, old_prefix)
        inspector = sa.inspect(bind)
