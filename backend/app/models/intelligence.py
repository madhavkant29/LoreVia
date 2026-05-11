"""
New models for intelligence features — no image generation models here.
"""
import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class BookChunk(Base):
    """Full-book text chunks + embeddings. Core of semantic search."""
    __tablename__ = "book_chunks"
    __table_args__ = (
        Index(
            "ix_book_chunks_embedding_ivfflat",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_with={"lists": 100},
        ),
    )

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
    # promise | mystery | conflict | prophecy | goal | object | clue |
    # relationship_tension | open_question | subplot | political | romance | main
    status: Mapped[str] = mapped_column(String, default="introduced")
    # introduced | developing | paused | resolved | contradicted | abandoned | unknown
    introduced_at: Mapped[int | None] = mapped_column(Integer)
    last_mentioned_at: Mapped[int | None] = mapped_column(Integer)
    resolved_at: Mapped[int | None] = mapped_column(Integer)
    mention_count: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    note: Mapped[str | None] = mapped_column(Text)
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
    themes: Mapped[list[dict] | None] = mapped_column(JSONB)
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


class QuoteEntry(Base):
    """Saved reader quotes with lightweight provenance metadata."""
    __tablename__ = "quote_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_number: Mapped[int | None] = mapped_column(Integer)
    character_name: Mapped[str | None] = mapped_column(String)
    quote_text: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Notification(Base):
    """In-app notifications for author and reader workflows."""
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict | None] = mapped_column(JSONB)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class WorldBuildingDocument(Base):
    """Book-scoped world-building reference document stored separately from story chapters."""
    __tablename__ = "world_building_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    source_name: Mapped[str | None] = mapped_column(String)
    s3_key: Mapped[str] = mapped_column(String, nullable=False)
    word_count: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)

    book = relationship("Book", back_populates="world_building_documents")


class WorldElement(Base):
    """Structured world-building element extracted from the manuscript."""
    __tablename__ = "world_elements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    series_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("series.id", ondelete="SET NULL"), index=True)
    source_book_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="SET NULL"), index=True)
    world_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("world_building_documents.id", ondelete="CASCADE"), index=True)
    source_scope: Mapped[str] = mapped_column(String, nullable=False, default="story", index=True)
    element_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    parent_element_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("world_elements.id", ondelete="SET NULL"), index=True)
    dependencies: Mapped[list[dict] | list[str] | None] = mapped_column(JSONB, default=list)
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    gap_score: Mapped[float | None] = mapped_column(Float)
    integration_score: Mapped[float | None] = mapped_column(Float)
    suggestions: Mapped[list[dict] | None] = mapped_column(JSONB, default=list)
    analysis_metadata: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    edited_by_author: Mapped[bool] = mapped_column(default=False)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_series_canonical: Mapped[bool] = mapped_column(default=False)
    last_gap_analysis: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_integration_analysis: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)

    book = relationship("Book", foreign_keys=[book_id], back_populates="world_elements")
    series = relationship("Series")
    world_document = relationship("WorldBuildingDocument")
    parent = relationship("WorldElement", remote_side=[id])


class WorldCanonicalIdentity(Base):
    """Book-scoped canonical identity record for world-gap resolution."""
    __tablename__ = "world_canonical_identities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    canonical_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String, index=True)
    aliases: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    source: Mapped[str] = mapped_column(String, nullable=False, default="author_override", server_default="author_override", index=True)
    confidence: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)

    book = relationship("Book", back_populates="world_canonical_identities")


class WorldGapAnalysis(Base):
    """Cached world gap detection and integration analysis output."""
    __tablename__ = "world_gap_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), index=True)
    series_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("series.id", ondelete="CASCADE"), index=True)
    analysis_mode: Mapped[str] = mapped_column(String, nullable=False, index=True)
    gap_categories: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    priority_gaps: Mapped[list[dict] | None] = mapped_column(JSONB, default=list)
    integration_opportunities: Mapped[list[dict] | None] = mapped_column(JSONB, default=list)
    consistency_flags: Mapped[list[dict] | None] = mapped_column(JSONB, default=list)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    book = relationship("Book", back_populates="world_gap_analyses")
    series = relationship("Series")


class WorldNote(Base):
    """Author-facing world-building note linked to a book and optional chapter."""
    __tablename__ = "world_notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    world_element_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("world_elements.id", ondelete="SET NULL"), index=True)
    world_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("world_building_documents.id", ondelete="SET NULL"), index=True)
    note_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    chapter_number: Mapped[int | None] = mapped_column(Integer, index=True)
    title: Mapped[str | None] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String, default="medium", index=True)
    status: Mapped[str] = mapped_column(String, default="open", index=True)
    linked_gap_id: Mapped[str | None] = mapped_column(String)
    linked_integration_id: Mapped[str | None] = mapped_column(String)
    context_label: Mapped[str | None] = mapped_column(String)
    suggested_fix: Mapped[str | None] = mapped_column(Text)
    addressed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)

    book = relationship("Book", back_populates="world_notes")
    world_element = relationship("WorldElement")
    world_document = relationship("WorldBuildingDocument")
