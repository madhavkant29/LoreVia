"""
New models for intelligence features — no image generation models here.
"""
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, func, ARRAY, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
from app.core.database import Base


class BookChunk(Base):
    """Full-book text chunks + embeddings. Core of semantic search."""
    __tablename__ = "book_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    token_count: Mapped[int | None] = mapped_column(Integer)

    book = relationship("Book", back_populates="chunks")
    chapter = relationship("Chapter", back_populates="chunks")


class CharacterRelationship(Base):
    """Timeline-aware relationship pairs between characters."""
    __tablename__ = "character_relationships"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    character_a_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    character_b_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    rel_type: Mapped[str] = mapped_column(String, nullable=False)
    # ally | enemy | romantic | family | political | mentor | rival | neutral
    sentiment: Mapped[float | None] = mapped_column(Float)   # -1.0 hostile → 1.0 warm
    description: Mapped[str | None] = mapped_column(String)
    from_chapter: Mapped[int] = mapped_column(Integer, nullable=False)
    to_chapter: Mapped[int | None] = mapped_column(Integer)  # null = still active

    book = relationship("Book", back_populates="relationships")
    character_a = relationship("Character", foreign_keys=[character_a_id], back_populates="relationships_as_a")
    character_b = relationship("Character", foreign_keys=[character_b_id], back_populates="relationships_as_b")


class PlotThread(Base):
    """Tracked arcs and subplots with status."""
    __tablename__ = "plot_threads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String)
    thread_type: Mapped[str | None] = mapped_column(String)
    # main | sub | mystery | romance | political
    status: Mapped[str] = mapped_column(String, default="introduced")
    # introduced | ongoing | resolved | abandoned | unknown
    introduced_at: Mapped[int | None] = mapped_column(Integer)
    resolved_at: Mapped[int | None] = mapped_column(Integer)
    character_ids: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    importance: Mapped[int] = mapped_column(Integer, default=5)  # 1–10
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    book = relationship("Book", back_populates="plot_threads")


class ChapterSummary(Base):
    """Cached LLM summaries — generated once, served forever."""
    __tablename__ = "chapter_summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chapter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True)
    mode: Mapped[str] = mapped_column(String, nullable=False)  # short | detailed | key_points
    content: Mapped[str] = mapped_column(Text, nullable=False)
    key_events: Mapped[dict | None] = mapped_column(JSONB)
    char_changes: Mapped[dict | None] = mapped_column(JSONB)
    clues: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    chapter = relationship("Chapter", back_populates="summaries")


class WikiEntry(Base):
    """Auto-generated wiki: locations, factions, items, events."""
    __tablename__ = "wiki_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    entry_type: Mapped[str] = mapped_column(String, nullable=False)
    # location | faction | item | event | concept
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String)
    first_mention: Mapped[int | None] = mapped_column(Integer)
    related_char_ids: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    book = relationship("Book", back_populates="wiki_entries")
