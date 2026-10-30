"""Store author decisions on source-backed voice findings.

Revision ID: 20261018_voice_review_decisions
Revises: 20261018_reconcile_reported_indexes
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "20261018_voice_review_decisions"
down_revision: str | Sequence[str] | None = "20261018_reconcile_reported_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "voice_review_decisions" not in inspector.get_table_names():
        op.create_table(
            "voice_review_decisions",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
            sa.Column(
                "book_id",
                UUID(as_uuid=True),
                sa.ForeignKey("books.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "user_id",
                UUID(as_uuid=True),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("finding_key", sa.String(length=64), nullable=False),
            sa.Column("decision", sa.String(length=20), nullable=False),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column(
                "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
            ),
            sa.Column(
                "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
            ),
            sa.UniqueConstraint(
                "book_id", "user_id", "finding_key", name="uq_voice_review_decisions_user_finding"
            ),
        )
    indexes = {
        index["name"]
        for index in sa.inspect(op.get_bind()).get_indexes("voice_review_decisions")
    }
    if "ix_voice_review_decisions_book_id" not in indexes:
        op.create_index(
            "ix_voice_review_decisions_book_id", "voice_review_decisions", ["book_id"]
        )
    if "ix_voice_review_decisions_user_id" not in indexes:
        op.create_index(
            "ix_voice_review_decisions_user_id", "voice_review_decisions", ["user_id"]
        )


def downgrade() -> None:
    if "voice_review_decisions" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("voice_review_decisions")
