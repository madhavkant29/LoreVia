"""
New models for intelligence features — no image generation models here.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class BookChunk(Base):
    """Full-book text chunks + embeddings. Core of semantic search."""

    __tablename__ = "book_chunks"
    __table_args__ = (
        Index(
            "ix_book_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_with={"m": 16, "ef_construction": 64},
        ),
        Index("ix_book_chunks_book_chunk", "book_id", "chunk_index"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    token_count: Mapped[int | None] = mapped_column(Integer)

    book = relationship("Book", back_populates="chunks")
    chapter = relationship("Chapter", back_populates="chunks")


class CharacterRelationship(Base):
    """Timeline-aware relationship pairs between characters."""

    __tablename__ = "character_relationships"
    __table_args__ = (
        Index("ix_character_relationships_book_from", "book_id", "from_chapter"),
        Index(
            "ix_character_relationships_book_a_from",
            "book_id",
            "character_a_id",
            "from_chapter",
        ),
        Index(
            "ix_character_relationships_book_b_from",
            "book_id",
            "character_b_id",
            "from_chapter",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    character_a_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    character_b_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False
    )
    rel_type: Mapped[str] = mapped_column(String, nullable=False)
    # Backward-compatible primary display label. Rich relationship facets live in the JSONB columns below.
    sentiment: Mapped[float | None] = mapped_column(Float)  # -1.0 hostile → 1.0 warm
    description: Mapped[str | None] = mapped_column(String)
    from_chapter: Mapped[int] = mapped_column(Integer, nullable=False)
    to_chapter: Mapped[int | None] = mapped_column(Integer)  # null = still active
    shared_labels: Mapped[list[str] | None] = mapped_column(JSONB, default=list)
    character_a_to_b_labels: Mapped[list[str] | None] = mapped_column(JSONB, default=list)
    character_b_to_a_labels: Mapped[list[str] | None] = mapped_column(JSONB, default=list)
    label_evidence: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    edited_by_author: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    book = relationship("Book", back_populates="relationships")
    character_a = relationship(
        "Character", foreign_keys=[character_a_id], back_populates="relationships_as_a"
    )
    character_b = relationship(
        "Character", foreign_keys=[character_b_id], back_populates="relationships_as_b"
    )


class PlotThread(Base):
    """Tracked arcs and subplots with status."""

    __tablename__ = "plot_threads"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
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
    edited_by_author: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    book = relationship("Book", back_populates="plot_threads")


class ChapterSummary(Base):
    """Cached LLM summaries — generated once, served forever."""

    __tablename__ = "chapter_summaries"
    __table_args__ = (Index("ix_chapter_summaries_chapter_mode", "chapter_id", "mode"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mode: Mapped[str] = mapped_column(String, nullable=False)  # short | detailed | key_points
    content: Mapped[str] = mapped_column(Text, nullable=False)
    key_events: Mapped[dict | None] = mapped_column(JSONB)
    char_changes: Mapped[dict | None] = mapped_column(JSONB)
    clues: Mapped[dict | None] = mapped_column(JSONB)
    themes: Mapped[list[dict] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    chapter = relationship("Chapter", back_populates="summaries")


class ContinuityScan(Base):
    """Version-aware full-book or targeted continuity analysis run."""

    __tablename__ = "continuity_scans"
    __table_args__ = (
        Index("ix_continuity_scans_book_created", "book_id", "created_at"),
        Index("ix_continuity_scans_book_status", "book_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    scope: Mapped[str] = mapped_column(String, nullable=False, default="full_book")
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="queued", server_default="queued", index=True
    )
    continuity_status: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="insufficient_evidence",
        server_default="insufficient_evidence",
        index=True,
    )
    detector_version: Mapped[str] = mapped_column(String, nullable=False)
    chapter_versions: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    coverage: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(14, 6))
    error_detail: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    observations = relationship(
        "ContinuityObservation", back_populates="scan", cascade="all, delete-orphan"
    )
    findings = relationship(
        "ContinuityFinding", back_populates="scan", cascade="all, delete-orphan"
    )


class ContinuityObservation(Base):
    """Immutable, cited story fact observed in one manuscript version."""

    __tablename__ = "continuity_observations"
    __table_args__ = (
        UniqueConstraint("identity_key", name="uq_continuity_observations_identity"),
        Index(
            "ix_continuity_observations_book_subject",
            "book_id",
            "subject_type",
            "subject_id",
        ),
        Index(
            "ix_continuity_observations_book_predicate_chapter",
            "book_id",
            "predicate",
            "chapter_number",
        ),
        Index("ix_continuity_observations_scan", "scan_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identity_key: Mapped[str] = mapped_column(String(64), nullable=False)
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("continuity_scans.id", ondelete="CASCADE"),
        nullable=False,
    )
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="SET NULL"), index=True
    )
    scene_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("novel_scenes.id", ondelete="SET NULL"), index=True
    )
    source_chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("book_chunks.id", ondelete="SET NULL"), index=True
    )
    subject_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    subject_id: Mapped[str | None] = mapped_column(String, index=True)
    subject_label: Mapped[str] = mapped_column(String, nullable=False)
    predicate: Mapped[str] = mapped_column(String, nullable=False, index=True)
    normalized_value: Mapped[str] = mapped_column(Text, nullable=False)
    display_value: Mapped[str] = mapped_column(Text, nullable=False)
    value_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    content_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    evidence_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    extractor_version: Mapped[str] = mapped_column(String, nullable=False)
    provenance: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    is_author_confirmed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    scan = relationship("ContinuityScan", back_populates="observations")
    evidence_links = relationship(
        "ContinuityFindingEvidence",
        back_populates="observation",
        cascade="all, delete-orphan",
    )


class ContinuityFinding(Base):
    """Actionable continuity result backed by ordered evidence."""

    __tablename__ = "continuity_findings"
    __table_args__ = (
        Index("ix_continuity_findings_book_status", "book_id", "status"),
        Index("ix_continuity_findings_book_category", "book_id", "category"),
        Index("ix_continuity_findings_scan", "scan_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("continuity_scans.id", ondelete="CASCADE"),
        nullable=False,
    )
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String, nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String, nullable=False, default="medium")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="pending", server_default="pending", index=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str | None] = mapped_column(Text)
    subject_type: Mapped[str] = mapped_column(String, nullable=False)
    subject_id: Mapped[str | None] = mapped_column(String, index=True)
    subject_label: Mapped[str] = mapped_column(String, nullable=False)
    detector_version: Mapped[str] = mapped_column(String, nullable=False)
    content_versions: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    coverage: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    is_stale: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false", index=True
    )
    decision: Mapped[str | None] = mapped_column(String)
    action: Mapped[str | None] = mapped_column(String)
    reason: Mapped[str | None] = mapped_column(String)
    decided_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    scan = relationship("ContinuityScan", back_populates="findings")
    evidence = relationship(
        "ContinuityFindingEvidence",
        back_populates="finding",
        cascade="all, delete-orphan",
        order_by="ContinuityFindingEvidence.evidence_order",
    )


class ContinuityFindingEvidence(Base):
    """Ordered evidence role connecting a finding to an immutable observation."""

    __tablename__ = "continuity_finding_evidence"
    __table_args__ = (
        UniqueConstraint(
            "finding_id",
            "evidence_order",
            name="uq_continuity_finding_evidence_order",
        ),
        UniqueConstraint(
            "finding_id",
            "observation_id",
            name="uq_continuity_finding_observation",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    finding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("continuity_findings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    observation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("continuity_observations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    evidence_order: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String, nullable=False, default="supporting")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    finding = relationship("ContinuityFinding", back_populates="evidence")
    observation = relationship("ContinuityObservation", back_populates="evidence_links")


class WikiEntry(Base):
    """Auto-generated wiki: locations, factions, items, events."""

    __tablename__ = "wiki_entries"
    __table_args__ = (Index("ix_wiki_entries_book_type_name", "book_id", "entry_type", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
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
    __table_args__ = (Index("ix_quote_entries_user_created", "user_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chapter_number: Mapped[int | None] = mapped_column(Integer)
    character_name: Mapped[str | None] = mapped_column(String)
    quote_text: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Notification(Base):
    """In-app notifications for author and reader workflows."""

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String, nullable=False, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String, unique=True, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict | None] = mapped_column(JSONB)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class AdvisorSuggestionJob(Base):
    """Persistent advisor suggestion scan job state for async polling."""

    __tablename__ = "advisor_suggestion_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="queued", server_default="queued", index=True
    )
    cache_key: Mapped[str | None] = mapped_column(String, index=True)
    result_json: Mapped[dict | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String, index=True)
    error_detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class AdvisorJob(Base):
    """Persistent advisor async job state used for polling without Celery results."""

    __tablename__ = "advisor_jobs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), index=True
    )
    series_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("series.id", ondelete="CASCADE"), index=True
    )
    scope: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="queued", server_default="queued", index=True
    )
    result_json: Mapped[dict | None] = mapped_column(JSONB)
    error_code: Mapped[str | None] = mapped_column(String, index=True)
    error_detail: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class WorldBuildingDocument(Base):
    """Book-scoped world-building reference document stored separately from story chapters."""

    __tablename__ = "world_building_documents"
    __table_args__ = (
        Index(
            "ix_world_building_documents_book_active_updated",
            "book_id",
            "is_active",
            "updated_at",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    source_name: Mapped[str | None] = mapped_column(String)
    s3_key: Mapped[str] = mapped_column(String, nullable=False)
    word_count: Mapped[int | None] = mapped_column(Integer)
    source_size_bytes: Mapped[int | None] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True
    )

    book = relationship("Book", back_populates="world_building_documents")


class WorldElement(Base):
    """Structured world-building element extracted from the manuscript."""

    __tablename__ = "world_elements"
    __table_args__ = (
        Index("ix_world_elements_book_usage_name", "book_id", "usage_count", "name"),
        Index("ix_world_elements_book_scope_name", "book_id", "source_scope", "name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    series_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("series.id", ondelete="SET NULL"), index=True
    )
    source_book_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="SET NULL"), index=True
    )
    world_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("world_building_documents.id", ondelete="CASCADE"),
        index=True,
    )
    source_scope: Mapped[str] = mapped_column(String, nullable=False, default="story", index=True)
    element_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    parent_element_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("world_elements.id", ondelete="SET NULL"), index=True
    )
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True
    )

    book = relationship("Book", foreign_keys=[book_id], back_populates="world_elements")
    series = relationship("Series")
    world_document = relationship("WorldBuildingDocument")
    parent = relationship("WorldElement", remote_side=[id])


class WorldCanonicalIdentity(Base):
    """Book-scoped canonical identity record for world-gap resolution."""

    __tablename__ = "world_canonical_identities"
    __table_args__ = (
        Index(
            "ix_world_canonical_identities_book_updated",
            "book_id",
            "updated_at",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    canonical_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String, index=True)
    aliases: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    source: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="author_override",
        server_default="author_override",
        index=True,
    )
    confidence: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True
    )

    book = relationship("Book", back_populates="world_canonical_identities")


class WorldGapAnalysis(Base):
    """Cached world gap detection and integration analysis output."""

    __tablename__ = "world_gap_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), index=True
    )
    series_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("series.id", ondelete="CASCADE"), index=True
    )
    analysis_mode: Mapped[str] = mapped_column(String, nullable=False, index=True)
    gap_categories: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    priority_gaps: Mapped[list[dict] | None] = mapped_column(JSONB, default=list)
    integration_opportunities: Mapped[list[dict] | None] = mapped_column(JSONB, default=list)
    consistency_flags: Mapped[list[dict] | None] = mapped_column(JSONB, default=list)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    book = relationship("Book", back_populates="world_gap_analyses")
    series = relationship("Series")


class WorldNote(Base):
    """Author-facing world-building note linked to a book and optional chapter."""

    __tablename__ = "world_notes"
    __table_args__ = (
        Index("ix_world_notes_book_type_created", "book_id", "note_type", "created_at"),
        Index(
            "ix_world_notes_book_chapter_type_created",
            "book_id",
            "chapter_number",
            "note_type",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    world_element_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("world_elements.id", ondelete="SET NULL"), index=True
    )
    world_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("world_building_documents.id", ondelete="SET NULL"),
        index=True,
    )
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True
    )

    book = relationship("Book", back_populates="world_notes")
    world_element = relationship("WorldElement")
    world_document = relationship("WorldBuildingDocument")
