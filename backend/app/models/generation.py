"""Atomic generations for replaceable, machine-derived book intelligence."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from app.core.database import Base


class GenerationScopedMixin:
    """Marks a row as derived from one replaceable processing generation.

    A NULL generation is deliberately reserved for author-curated data and
    legacy rows that have not yet been adopted by ``prepare_rebuild``.
    """

    @declared_attr
    def generation_id(cls) -> Mapped[uuid.UUID | None]:
        return mapped_column(
            UUID(as_uuid=True),
            ForeignKey("book_data_generations.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        )


class BookDataGeneration(Base):
    __tablename__ = "book_data_generations"
    __table_args__ = (
        Index(
            "uq_book_data_generations_active_book",
            "book_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
        Index("ix_book_data_generations_status_updated", "status", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rebuild_run_id: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="staging", server_default="staging", index=True
    )
    reason: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    promoted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    chapter_state_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    book = relationship("Book")
