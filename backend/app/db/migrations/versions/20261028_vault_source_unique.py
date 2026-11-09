"""Remove the obsolete path-only Vault Note uniqueness constraint.

Revision ID: 20261028_vault_source_unique
Revises: 20261018_voice_review_decisions

The source-aware constraint already protects (user_id, book_id, path, source).
Downgrade cannot restore the path-only constraint if notes with the same path
have since been created in different sources; remove those duplicates first.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261028_vault_source_unique"
down_revision: str | Sequence[str] | None = "20261018_voice_review_decisions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "book_vault_notes"
OLD_CONSTRAINT = "uq_book_vault_notes_user_book_path"
SOURCE_CONSTRAINT = "uq_book_vault_notes_user_book_path_source"


def _constraint_names() -> set[str] | None:
    inspector = sa.inspect(op.get_bind())
    if TABLE_NAME not in inspector.get_table_names():
        return None
    return {constraint.get("name") for constraint in inspector.get_unique_constraints(TABLE_NAME)}


def upgrade() -> None:
    constraints = _constraint_names()
    if constraints is None or OLD_CONSTRAINT not in constraints:
        return
    if SOURCE_CONSTRAINT not in constraints:
        raise RuntimeError(
            "Cannot remove path-only Vault Note uniqueness before the source-aware "
            "constraint exists. Repair the prior migration first."
        )
    op.drop_constraint(OLD_CONSTRAINT, TABLE_NAME, type_="unique")


def downgrade() -> None:
    constraints = _constraint_names()
    if constraints is None or OLD_CONSTRAINT in constraints:
        return
    duplicate = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT 1 FROM book_vault_notes "
                "GROUP BY user_id, book_id, path HAVING COUNT(*) > 1 LIMIT 1"
            )
        )
        .first()
    )
    if duplicate:
        raise RuntimeError(
            "Cannot restore path-only Vault Note uniqueness while different sources "
            "share a path. Resolve the duplicate paths before downgrading."
        )
    op.create_unique_constraint(OLD_CONSTRAINT, TABLE_NAME, ["user_id", "book_id", "path"])
