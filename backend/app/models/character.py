import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Character(Base):
    __tablename__ = "characters"
    __table_args__ = (
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

    # pgvector identity anchor
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_manual: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    book = relationship("Book", back_populates="characters")
    states = relationship("CharacterState", back_populates="character", cascade="all, delete-orphan")
    relationships_as_a = relationship("CharacterRelationship", foreign_keys="CharacterRelationship.character_a_id", back_populates="character_a", cascade="all, delete-orphan")
    relationships_as_b = relationship("CharacterRelationship", foreign_keys="CharacterRelationship.character_b_id", back_populates="character_b", cascade="all, delete-orphan")
    voice_profile = relationship("CharacterVoiceProfile", back_populates="character", uselist=False, cascade="all, delete-orphan")


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
