import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, func, BigInteger, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from pgvector.sqlalchemy import Vector
from app.core.database import Base


class Character(Base):
    __tablename__ = "characters"

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
    arc_summary: Mapped[str | None] = mapped_column(String)
    archetype: Mapped[str | None] = mapped_column(String)
    growth_events: Mapped[list[dict] | None] = mapped_column(JSONB, default=list)

    # pgvector identity anchor
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    book = relationship("Book", back_populates="characters")
    states = relationship("CharacterState", back_populates="character", cascade="all, delete-orphan")
    relationships_as_a = relationship("CharacterRelationship", foreign_keys="CharacterRelationship.character_a_id", back_populates="character_a", cascade="all, delete-orphan")
    relationships_as_b = relationship("CharacterRelationship", foreign_keys="CharacterRelationship.character_b_id", back_populates="character_b", cascade="all, delete-orphan")


class CharacterState(Base):
    """Spoiler-free snapshot at a given chapter."""
    __tablename__ = "character_states"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    character_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("characters.id", ondelete="CASCADE"), nullable=False, index=True)
    at_chapter: Mapped[int] = mapped_column(Integer, nullable=False)
    trait_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    prompt_delta: Mapped[str | None] = mapped_column(String)
    arc_note: Mapped[str | None] = mapped_column(String)
    growth_event: Mapped[dict | None] = mapped_column(JSONB)

    character = relationship("Character", back_populates="states")
