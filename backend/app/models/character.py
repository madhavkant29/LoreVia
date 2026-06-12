import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Character(Base):
    __tablename__ = "characters"
    __table_args__ = (
        Index(
            "uq_characters_book_normalized_active",
            "book_id",
            "normalized_name",
            unique=True,
            postgresql_where=text(
                "normalized_name is not null "
                "and merged_into_character_id is null "
                "and visibility_state in ('visible', 'quarantined') "
                "and approval_state not in ('rejected')"
            ),
        ),
        Index(
            "ix_characters_embedding_ivfflat",
            "embedding",
            postgresql_using="ivfflat",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_with={"lists": 100},
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String, nullable=False)
    normalized_name: Mapped[str | None] = mapped_column(String, index=True)
    aliases: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    role: Mapped[str | None] = mapped_column(String)       # mc | sc | background
    first_chapter: Mapped[int] = mapped_column(Integer, nullable=False)
    last_seen_chapter: Mapped[int | None] = mapped_column(Integer)      # updated during extraction
    mention_count: Mapped[int] = mapped_column(Integer, default=0)       # running count across all chunks

    # Confidence-weighted trait model
    # {"hair": {"value":"black","confidence":0.9,"type":"objective"}, ...}
    trait_state: Mapped[dict | None] = mapped_column(JSONB, default=dict)

    # Flat columns derived from trait_state above threshold 0.45
    hair: Mapped[str | None] = mapped_column(String)
    eyes: Mapped[str | None] = mapped_column(String)
    build: Mapped[str | None] = mapped_column(String)
    age_descriptor: Mapped[str | None] = mapped_column(String)
    distinguishing: Mapped[str | None] = mapped_column(String)
    personality_tags: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    # Intelligence fields
    motivations: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    fears: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    goal: Mapped[str | None] = mapped_column(String)
    lie_they_believe: Mapped[str | None] = mapped_column(String)
    backstory_wound: Mapped[str | None] = mapped_column(String)
    arc_type: Mapped[str | None] = mapped_column(String)
    arc_summary: Mapped[str | None] = mapped_column(String)
    archetype: Mapped[str | None] = mapped_column(String)
    growth_events: Mapped[list[dict] | None] = mapped_column(JSONB, default=list)

    # Character classification
    character_type: Mapped[str | None] = mapped_column(String)  # complex | normal | gag | meme
    character_type_score: Mapped[int | None] = mapped_column(Integer)  # 0-10 score for main type
    subtype_scores: Mapped[dict | None] = mapped_column(JSONB, default=dict)  # {"stoic": 7, "broken": 3, ...}
    analysis_metadata: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    visibility_state: Mapped[str] = mapped_column(String, nullable=False, default="visible", server_default="visible")
    approval_state: Mapped[str] = mapped_column(String, nullable=False, default="approved", server_default="approved")
    approval_source: Mapped[str | None] = mapped_column(String)
    approval_reason_codes: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    approval_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    merged_into_character_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("characters.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_auto_suppressed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    suppression_reason: Mapped[str | None] = mapped_column(String)

    # pgvector identity anchor
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    book = relationship("Book", back_populates="characters")
    states = relationship("CharacterState", back_populates="character", cascade="all, delete-orphan")
    relationships_as_a = relationship("CharacterRelationship", foreign_keys="CharacterRelationship.character_a_id", back_populates="character_a", cascade="all, delete-orphan")
    relationships_as_b = relationship("CharacterRelationship", foreign_keys="CharacterRelationship.character_b_id", back_populates="character_b", cascade="all, delete-orphan")
    voice_profile = relationship("CharacterVoiceProfile", back_populates="character", uselist=False, cascade="all, delete-orphan")
    matched_candidates = relationship(
        "CharacterCandidate",
        foreign_keys="CharacterCandidate.matched_character_id",
        back_populates="matched_character",
    )
    duplicate_suggestions_as_primary = relationship(
        "CharacterDuplicateSuggestion",
        foreign_keys="CharacterDuplicateSuggestion.primary_character_id",
        back_populates="primary_character",
        cascade="all, delete-orphan",
    )
    duplicate_suggestions_as_secondary = relationship(
        "CharacterDuplicateSuggestion",
        foreign_keys="CharacterDuplicateSuggestion.secondary_character_id",
        back_populates="secondary_character",
        cascade="all, delete-orphan",
    )
    relationship_candidates_as_a = relationship(
        "CharacterRelationshipCandidate",
        foreign_keys="CharacterRelationshipCandidate.matched_character_a_id",
        back_populates="matched_character_a",
    )
    relationship_candidates_as_b = relationship(
        "CharacterRelationshipCandidate",
        foreign_keys="CharacterRelationshipCandidate.matched_character_b_id",
        back_populates="matched_character_b",
    )
    mention_records = relationship(
        "CharacterMention",
        foreign_keys="CharacterMention.matched_character_id",
        back_populates="matched_character",
    )
    decision_events = relationship(
        "CharacterDecisionEvent",
        foreign_keys="CharacterDecisionEvent.character_id",
        back_populates="character",
        cascade="all, delete-orphan",
    )
    alias_records = relationship(
        "CharacterAlias",
        foreign_keys="CharacterAlias.character_id",
        back_populates="character",
        cascade="all, delete-orphan",
    )


class CharacterState(Base):
    """Spoiler-free snapshot at a given chapter."""
    __tablename__ = "character_states"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    character_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True)
    at_chapter: Mapped[int] = mapped_column(Integer, nullable=False)
    trait_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    motivations_snapshot: Mapped[list[str] | None] = mapped_column(JSONB, default=list)
    fears_snapshot: Mapped[list[str] | None] = mapped_column(JSONB, default=list)
    prompt_delta: Mapped[str | None] = mapped_column(String)
    arc_note: Mapped[str | None] = mapped_column(String)
    growth_event: Mapped[dict | None] = mapped_column(JSONB)

    character = relationship("Character", back_populates="states")


class CharacterVoiceProfile(Base):
    __tablename__ = "character_voice_profiles"
    __table_args__ = (
        UniqueConstraint("character_id", name="uq_character_voice_profiles_character_id"),
    )
    __mapper_args__ = {"confirm_deleted_rows": False}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    character_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    sample_dialogue_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    sample_word_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    avg_sentence_length: Mapped[int | None] = mapped_column(Integer)
    avg_word_length_x100: Mapped[int | None] = mapped_column(Integer)
    contraction_rate_x1000: Mapped[int | None] = mapped_column(Integer)
    question_rate_x1000: Mapped[int | None] = mapped_column(Integer)
    exclamation_rate_x1000: Mapped[int | None] = mapped_column(Integer)
    ellipsis_rate_x1000: Mapped[int | None] = mapped_column(Integer)
    dash_rate_x1000: Mapped[int | None] = mapped_column(Integer)
    uppercase_rate_x1000: Mapped[int | None] = mapped_column(Integer)
    formality_score_x1000: Mapped[int | None] = mapped_column(Integer)
    lexical_complexity_x1000: Mapped[int | None] = mapped_column(Integer)
    emotional_intensity_x1000: Mapped[int | None] = mapped_column(Integer)
    dominant_markers: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    signature_phrases: Mapped[list[str] | None] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)

    character = relationship("Character", back_populates="voice_profile")


class CharacterCandidate(Base):
    __tablename__ = "character_candidates"
    __table_args__ = (
        Index("ix_character_candidates_book_status", "book_id", "status"),
        Index("ix_character_candidates_book_normalized_name", "book_id", "normalized_name"),
        Index("ix_character_candidates_matched_character_id", "matched_character_id"),
        Index("ix_character_candidates_book_adjudication", "book_id", "adjudication_status"),
        Index("ix_character_candidates_book_entity_type", "book_id", "entity_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="SET NULL"), nullable=True, index=True)
    scene_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("novel_scenes.id", ondelete="SET NULL"), nullable=True, index=True)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_name: Mapped[str] = mapped_column(String, nullable=False)
    proposed_name: Mapped[str] = mapped_column(String, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String)
    normalized_name: Mapped[str] = mapped_column(String, nullable=False)
    aliases: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    matched_character_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("characters.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending", server_default="pending")
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    reason_codes: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    evidence: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    mention_count: Mapped[int | None] = mapped_column(Integer)
    chapter_count: Mapped[int | None] = mapped_column(Integer)
    evidence_windows: Mapped[list[dict] | None] = mapped_column(JSONB, default=list)
    entity_type: Mapped[str | None] = mapped_column(String)
    adjudication_status: Mapped[str | None] = mapped_column(String)
    character_score: Mapped[int | None] = mapped_column(Integer)
    rejection_reason: Mapped[str | None] = mapped_column(String)
    source_batch_key: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    matched_character = relationship("Character", back_populates="matched_candidates")


class CharacterMention(Base):
    __tablename__ = "character_mentions"
    __table_args__ = (
        Index("ix_character_mentions_book_chapter", "book_id", "chapter_number"),
        Index("ix_character_mentions_book_normalized_name", "book_id", "normalized_name"),
        Index("ix_character_mentions_book_cluster_key", "book_id", "cluster_key"),
        Index("ix_character_mentions_matched_character_id", "matched_character_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_name: Mapped[str] = mapped_column(String, nullable=False)
    normalized_name: Mapped[str] = mapped_column(String, nullable=False)
    source_batch_key: Mapped[str | None] = mapped_column(String)
    cluster_key: Mapped[str | None] = mapped_column(String)
    mention_text: Mapped[str | None] = mapped_column(String)
    matched_character_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("characters.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolver_status: Mapped[str] = mapped_column(String, nullable=False, default="unresolved", server_default="unresolved")
    resolver_reasons: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    evidence: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    matched_character = relationship("Character", back_populates="mention_records")


class CharacterAlias(Base):
    __tablename__ = "character_aliases"
    __table_args__ = (
        UniqueConstraint(
            "book_id",
            "character_id",
            "normalized_alias",
            name="uq_character_aliases_book_char_alias",
        ),
        Index("ix_character_aliases_book_norm_alias", "book_id", "normalized_alias"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    character_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True)
    alias_text: Mapped[str] = mapped_column(String, nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String, nullable=False, index=True)
    alias_kind: Mapped[str] = mapped_column(String, nullable=False, default="unspecified", server_default="unspecified")
    source: Mapped[str] = mapped_column(String, nullable=False, default="extraction", server_default="extraction")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5, server_default="0.5")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    character = relationship("Character", back_populates="alias_records")


class CharacterSuppression(Base):
    __tablename__ = "character_suppressions"
    __table_args__ = (
        Index("ix_character_suppressions_book_normalized_text", "book_id", "normalized_text"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    character_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="SET NULL"), nullable=True, index=True)
    chapter_number: Mapped[int | None] = mapped_column(Integer)
    surface_text: Mapped[str] = mapped_column(String, nullable=False)
    normalized_text: Mapped[str] = mapped_column(String, nullable=False)
    candidate_kind: Mapped[str | None] = mapped_column(String)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")
    evidence_quote: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CharacterIdentityConstraint(Base):
    __tablename__ = "character_identity_constraints"
    __table_args__ = (
        UniqueConstraint(
            "book_id",
            "left_character_id",
            "right_character_id",
            "constraint_type",
            name="uq_character_identity_constraints",
        ),
        Index("ix_character_identity_constraints_book_type", "book_id", "constraint_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    left_character_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    right_character_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    left_text: Mapped[str] = mapped_column(String, nullable=False)
    right_text: Mapped[str] = mapped_column(String, nullable=False)
    constraint_type: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str | None] = mapped_column(String)
    source: Mapped[str] = mapped_column(String, nullable=False, default="system", server_default="system")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CharacterIdentityAction(Base):
    __tablename__ = "character_identity_actions"
    __table_args__ = (
        Index("ix_character_identity_actions_book_created_at", "book_id", "created_at"),
        Index("ix_character_identity_actions_source_character", "source_character_id"),
        Index("ix_character_identity_actions_target_character", "target_character_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    action_type: Mapped[str] = mapped_column(String, nullable=False)
    source_character_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="SET NULL"), nullable=True)
    target_character_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="SET NULL"), nullable=True)
    surface_text: Mapped[str | None] = mapped_column(String)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")
    reason: Mapped[str | None] = mapped_column(String)
    reversible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    reversible_data: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    repair_run_id: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CharacterDecisionEvent(Base):
    __tablename__ = "character_decision_events"
    __table_args__ = (
        Index("ix_character_decision_events_book_created_at", "book_id", "created_at"),
        Index("ix_character_decision_events_character_id", "character_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    character_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    visibility_state: Mapped[str | None] = mapped_column(String)
    approval_state: Mapped[str | None] = mapped_column(String)
    approval_source: Mapped[str | None] = mapped_column(String)
    reason_codes: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    evidence: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    character = relationship("Character", back_populates="decision_events")


class CharacterDuplicateSuggestion(Base):
    __tablename__ = "character_duplicate_suggestions"
    __table_args__ = (
        UniqueConstraint(
            "book_id",
            "primary_character_id",
            "secondary_character_id",
            name="uq_character_duplicate_suggestions_pair",
        ),
        Index("ix_character_duplicate_suggestions_book_status", "book_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    primary_character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("characters.id", ondelete="CASCADE"),
        nullable=False,
    )
    secondary_character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("characters.id", ondelete="CASCADE"),
        nullable=False,
    )
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    reasons: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    shared_evidence: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending", server_default="pending")
    dismissal_reason: Mapped[str | None] = mapped_column(String)
    auto_dismissed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    primary_character = relationship(
        "Character",
        foreign_keys=[primary_character_id],
        back_populates="duplicate_suggestions_as_primary",
    )
    secondary_character = relationship(
        "Character",
        foreign_keys=[secondary_character_id],
        back_populates="duplicate_suggestions_as_secondary",
    )


class CharacterRelationshipCandidate(Base):
    __tablename__ = "character_relationship_candidates"
    __table_args__ = (
        Index("ix_character_relationship_candidates_book_status", "book_id", "status"),
        Index("ix_character_relationship_candidates_book_chapter", "book_id", "chapter_number"),
        Index("ix_character_relationship_candidates_match_a", "matched_character_a_id"),
        Index("ix_character_relationship_candidates_match_b", "matched_character_b_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    raw_character_a: Mapped[str] = mapped_column(String, nullable=False)
    raw_character_b: Mapped[str] = mapped_column(String, nullable=False)
    matched_character_a_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("characters.id", ondelete="SET NULL"),
        nullable=True,
    )
    matched_character_b_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("characters.id", ondelete="SET NULL"),
        nullable=True,
    )
    rel_type: Mapped[str | None] = mapped_column(String)
    sentiment: Mapped[float | None] = mapped_column(Float)
    description: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending", server_default="pending")
    reason_codes: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    evidence: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    source_batch_key: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    matched_character_a = relationship(
        "Character",
        foreign_keys=[matched_character_a_id],
        back_populates="relationship_candidates_as_a",
    )
    matched_character_b = relationship(
        "Character",
        foreign_keys=[matched_character_b_id],
        back_populates="relationship_candidates_as_b",
    )
