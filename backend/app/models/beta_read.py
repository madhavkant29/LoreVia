import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class BetaReadAssignmentState(str, enum.Enum):
    ACTIVE = "active"
    IN_PROGRESS = "in_progress"
    READY_TO_SUBMIT = "ready_to_submit"
    SUBMITTED = "submitted"
    COMPLETED = "completed"
    EXPIRED = "expired"
    MISSED = "missed"
    REVOKED = "revoked"
    DISQUALIFIED = "disqualified"


class BetaReadScopeKind(str, enum.Enum):
    FULL_BOOK = "full_book"
    CHAPTER_RANGE = "chapter_range"
    SECTION = "section"


class BetaReadFeedbackKind(str, enum.Enum):
    CHAPTER_COMMENT = "chapter_comment"
    SCENE_REACTION = "scene_reaction"
    ANSWER = "answer"
    CONFUSING = "confusing"
    BORING = "boring"
    FAVORITE = "favorite"


class BetaReadAssignment(Base):
    __tablename__ = "beta_read_assignments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    author_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    reader_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True)
    collaborator_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("book_collaborators.id", ondelete="SET NULL"), index=True)
    reader_email: Mapped[str] = mapped_column(String, nullable=False, index=True)
    state: Mapped[str] = mapped_column(String, nullable=False, default=BetaReadAssignmentState.ACTIVE.value, server_default=BetaReadAssignmentState.ACTIVE.value, index=True)
    scope_kind: Mapped[str] = mapped_column(String, nullable=False, default=BetaReadScopeKind.FULL_BOOK.value, server_default=BetaReadScopeKind.FULL_BOOK.value)
    task_label: Mapped[str] = mapped_column(String, nullable=False)
    section_label: Mapped[str | None] = mapped_column(String)
    chapter_start: Mapped[int | None] = mapped_column(Integer)
    chapter_end: Mapped[int | None] = mapped_column(Integer)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_points: Mapped[int] = mapped_column(Integer, nullable=False)
    required_progress_pct: Mapped[int] = mapped_column(Integer, nullable=False, default=100, server_default="100")
    required_comment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    required_feedback_item_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    require_final_feedback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    author_questions_json: Mapped[list | None] = mapped_column(JSONB, default=list, server_default="[]")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    access_granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    first_opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    awarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    awarded_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    final_feedback: Mapped[str | None] = mapped_column(Text)
    final_rating: Mapped[float | None] = mapped_column(Float, index=True)
    feedback_payload: Mapped[dict | None] = mapped_column(JSONB, default=dict, server_default="{}")
    submission_metadata: Mapped[dict | None] = mapped_column(JSONB, default=dict, server_default="{}")
    submitted_progress_pct: Mapped[float | None] = mapped_column(Float)
    submitted_chapters_total: Mapped[int | None] = mapped_column(Integer)
    submitted_chapters_read_count: Mapped[int | None] = mapped_column(Integer)
    submitted_comment_count: Mapped[int | None] = mapped_column(Integer)
    submitted_feedback_item_count: Mapped[int | None] = mapped_column(Integer)
    submitted_answer_count: Mapped[int | None] = mapped_column(Integer)
    submitted_rating_sentiment: Mapped[str | None] = mapped_column(String, index=True)
    submitted_before_deadline: Mapped[bool | None] = mapped_column(Boolean)
    late_feedback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    reminder_24h_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    reminder_6h_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    missed_reason: Mapped[str | None] = mapped_column(String, index=True)
    counted_toward_missed_streak: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    revoked_reason: Mapped[str | None] = mapped_column(String)
    disqualified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    disqualified_reason: Mapped[str | None] = mapped_column(String)
    state_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)

    book = relationship("Book", back_populates="beta_read_assignments")
    questions = relationship("BetaReadQuestion", back_populates="assignment", cascade="all, delete-orphan")
    feedback_items = relationship("BetaReadFeedbackItem", back_populates="assignment", cascade="all, delete-orphan")


class BetaReadQuestion(Base):
    __tablename__ = "beta_read_questions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("beta_read_assignments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("books.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)

    assignment = relationship("BetaReadAssignment", back_populates="questions")
    feedback_items = relationship("BetaReadFeedbackItem", back_populates="question")


class BetaReadFeedbackItem(Base):
    __tablename__ = "beta_read_feedback_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("beta_read_assignments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("books.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reader_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    question_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("beta_read_questions.id", ondelete="SET NULL"),
        index=True,
    )
    scene_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("novel_scenes.id", ondelete="SET NULL"),
        index=True,
    )
    kind: Mapped[str] = mapped_column(String, nullable=False, index=True)
    chapter_number: Mapped[int | None] = mapped_column(Integer, index=True)
    reaction: Mapped[str | None] = mapped_column(String)
    anchor_text: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)

    assignment = relationship("BetaReadAssignment", back_populates="feedback_items")
    question = relationship("BetaReadQuestion", back_populates="feedback_items")
