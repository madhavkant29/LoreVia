"""Add book upload charge ledger.

Revision ID: 20260602_add_book_upload_charges
Revises: 20260601_add_character_identity_cleanup
Create Date: 2026-06-02 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260602_add_book_upload_charges"
down_revision: str | Sequence[str] | None = "20260601_add_character_identity_cleanup"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_names(inspector: sa.Inspector) -> set[str]:
    return set(inspector.get_table_names())


def _index_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    return {
        name
        for index in inspector.get_indexes(table_name)
        if isinstance(name := index.get("name"), str)
    }


def _constraint_names(inspector: sa.Inspector, table_name: str) -> set[str]:
    constraints = [
        *inspector.get_unique_constraints(table_name),
        *inspector.get_foreign_keys(table_name),
    ]
    return {
        name
        for constraint in constraints
        if isinstance(name := constraint.get("name"), str)
    }


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "book_upload_charges" not in tables:
        op.create_table(
            "book_upload_charges",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("charge_kind", sa.String(), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False, server_default=sa.text("1")),
            sa.Column("source_id", sa.String(), nullable=False),
            sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["book_id"], ["books.id"], name="fk_book_upload_charges_book_id", ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_book_upload_charges_user_id", ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id", "charge_kind", "source_id", name="uq_book_upload_charges_source"),
        )
        tables.add("book_upload_charges")

    if "book_upload_charges" in tables:
        indexes = _index_names(inspector, "book_upload_charges")
        constraints = _constraint_names(inspector, "book_upload_charges")
        for index_name, columns in (
            ("ix_book_upload_charges_user_id", ["user_id"]),
            ("ix_book_upload_charges_book_id", ["book_id"]),
            ("ix_book_upload_charges_charge_kind", ["charge_kind"]),
            ("ix_book_upload_charges_source_id", ["source_id"]),
            ("ix_book_upload_charges_created_at", ["created_at"]),
            ("ix_book_upload_charges_user_kind_created", ["user_id", "charge_kind", "created_at"]),
        ):
            if index_name not in indexes:
                op.create_index(index_name, "book_upload_charges", columns)
        if "uq_book_upload_charges_source" not in constraints:
            op.create_unique_constraint(
                "uq_book_upload_charges_source",
                "book_upload_charges",
                ["user_id", "charge_kind", "source_id"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)
    if "book_upload_charges" not in tables:
        return

    indexes = _index_names(inspector, "book_upload_charges")
    for index_name in (
        "ix_book_upload_charges_user_kind_created",
        "ix_book_upload_charges_created_at",
        "ix_book_upload_charges_source_id",
        "ix_book_upload_charges_charge_kind",
        "ix_book_upload_charges_book_id",
        "ix_book_upload_charges_user_id",
    ):
        if index_name in indexes:
            op.drop_index(index_name, table_name="book_upload_charges")
    op.drop_table("book_upload_charges")
