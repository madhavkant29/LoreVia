import uuid
from datetime import datetime
from sqlalchemy import Integer, Float, Boolean, DateTime, ForeignKey, func, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class ReadingProgress(Base):
    __tablename__ = "reading_progress"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    current_chapter: Mapped[int] = mapped_column(Integer, default=1)
    scroll_pct: Mapped[float] = mapped_column(Float, default=0.0)
    session_seconds: Mapped[int] = mapped_column(Integer, default=0)
    chapters_read: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    last_read: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="reading_progress")
    book = relationship("Book", back_populates="reading_progress")


class ReadingSession(Base):
    """Tracks individual sessions for memory recall."""
    __tablename__ = "reading_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    chapters_read: Mapped[list[int] | None] = mapped_column(ARRAY(Integer))
    duration_secs: Mapped[int | None] = mapped_column(Integer)
    recall_shown: Mapped[bool] = mapped_column(Boolean, default=False)

    user = relationship("User", back_populates="reading_sessions")
    book = relationship("Book", back_populates="reading_sessions")
