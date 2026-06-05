"""Rename obsidian-branded tables and constraints to vault.

Revision ID: 20260604_rename_obsidian_to_vault
Revises: 61eb02473fa9
Create Date: 2026-06-04 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260604_rename_obsidian_to_vault"
down_revision: str | None = "61eb02473fa9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE_RENAMES = [
    ("book_obsidian_notes", "book_vault_notes"),
    ("book_obsidian_note_links", "book_vault_note_links"),
    ("book_obsidian_note_backlinks", "book_vault_note_backlinks"),
    ("book_obsidian_note_tags", "book_vault_note_tags"),
    ("book_obsidian_note_series_links", "book_vault_note_series_links"),
]


def _rename_indexes(
    inspector: sa.Inspector, old_table: str, new_table: str
) -> None:
    for idx in inspector.get_indexes(old_table):
        old_name = idx["name"]
        if old_table in old_name:
            new_name = old_name.replace(old_table, new_table)
            if not any(
                existing["name"] == new_name
                for existing in inspector.get_indexes(old_table)
            ):
                op.execute(
                    f'ALTER INDEX "{old_name}" RENAME TO "{new_name}"'
                )


def _rename_fk_constraints(
    inspector: sa.Inspector, old_table: str, new_table: str
) -> None:
    for fk in inspector.get_foreign_keys(old_table):
        old_name = fk["name"]
        if old_name and old_table in old_name:
            new_name = old_name.replace(old_table, new_table)
            op.execute(
                f'ALTER TABLE "{old_table}" RENAME CONSTRAINT "{old_name}" TO "{new_name}"'
            )


def _rename_unique_constraints(
    inspector: sa.Inspector, old_table: str, new_table: str
) -> None:
    for uc in inspector.get_unique_constraints(old_table):
        old_name = uc.get("name")
        if old_name and old_table in old_name:
            new_name = old_name.replace(old_table, new_table)
            op.execute(
                f'ALTER TABLE "{old_table}" RENAME CONSTRAINT "{old_name}" TO "{new_name}"'
            )


def _rename_pk_constraint(inspector: sa.Inspector, old_table: str, new_table: str) -> None:
    pk_old = f"{old_table}_pkey"
    pk_new = f"{new_table}_pkey"
    pk_constraint = inspector.get_pk_constraint(old_table)
    existing_name = pk_constraint.get("name") if pk_constraint else None
    if existing_name and existing_name == pk_old:
        op.execute(
            f'ALTER INDEX "{pk_old}" RENAME TO "{pk_new}"'
        )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    for old_table, new_table in _TABLE_RENAMES:
        if old_table not in tables:
            continue

        op.execute(f'ALTER TABLE "{old_table}" RENAME TO "{new_table}"')
        inspector = sa.inspect(bind)

        _rename_pk_constraint(inspector, new_table, new_table)
        _rename_indexes(inspector, new_table, new_table)
        inspector = sa.inspect(bind)
        _rename_fk_constraints(inspector, new_table, new_table)
        inspector = sa.inspect(bind)
        _rename_unique_constraints(inspector, new_table, new_table)
        inspector = sa.inspect(bind)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    for old_table, new_table in reversed(_TABLE_RENAMES):
        if new_table not in tables:
            continue

        _rename_unique_constraints(inspector, new_table, old_table)
        inspector = sa.inspect(bind)
        _rename_fk_constraints(inspector, new_table, old_table)
        inspector = sa.inspect(bind)
        _rename_indexes(inspector, new_table, old_table)
        inspector = sa.inspect(bind)
        _rename_pk_constraint(inspector, new_table, old_table)
        inspector = sa.inspect(bind)

        op.execute(f'ALTER TABLE "{new_table}" RENAME TO "{old_table}"')
        inspector = sa.inspect(bind)
