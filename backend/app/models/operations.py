import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    DateTime,
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
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class BookProcessingRun(Base):
    __tablename__ = "book_processing_runs"
    __table_args__ = (Index("ix_book_processing_runs_book_status", "book_id", "status"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    run_kind: Mapped[str] = mapped_column(String, nullable=False, default="initial_ingestion")
    status: Mapped[str] = mapped_column(String, nullable=False, default="queued", index=True)
    pause_reason: Mapped[str | None] = mapped_column(String)
    resume_blockers: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    next_chapter_number: Mapped[int | None] = mapped_column(Integer)
    chapters_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    chapters_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    rebuild_run_id: Mapped[str | None] = mapped_column(String, index=True)
    pipeline_version: Mapped[str] = mapped_column(String, nullable=False, default="2026-06")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class TaskExecution(Base):
    __tablename__ = "task_executions"
    __table_args__ = (
        UniqueConstraint("identity_key", name="uq_task_executions_identity_key"),
        Index("ix_task_executions_status_created", "status", "created_at"),
        Index("ix_task_executions_user_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    identity_key: Mapped[str] = mapped_column(String(64), nullable=False)
    task_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    feature: Mapped[str] = mapped_column(String, nullable=False, default="processing")
    processing_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("book_processing_runs.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    book_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), index=True)
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="SET NULL"), index=True)
    chapter_number: Mapped[int | None] = mapped_column(Integer)
    chapter_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("chapter_versions.id", ondelete="SET NULL"))
    rebuild_run_id: Mapped[str | None] = mapped_column(String)
    celery_task_id: Mapped[str | None] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending_dispatch", index=True)
    arguments_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    error_category: Mapped[str | None] = mapped_column(String, index=True)
    error_detail: Mapped[str | None] = mapped_column(Text)
    first_failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    dismissed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    dismissal_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class AiQualityEvent(Base):
    __tablename__ = "ai_quality_events"
    __table_args__ = (Index("ix_ai_quality_events_book_created", "book_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    task_execution_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("task_executions.id", ondelete="SET NULL"))
    entity_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    entity_id: Mapped[str | None] = mapped_column(String)
    outcome: Mapped[str] = mapped_column(String, nullable=False, index=True)
    model: Mapped[str | None] = mapped_column(String, index=True)
    extractor_version: Mapped[str | None] = mapped_column(String, index=True)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)


class SupportIncident(Base):
    __tablename__ = "support_incidents"
    __table_args__ = (Index("ix_support_incidents_status_created", "status", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True)
    book_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="SET NULL"), index=True)
    task_execution_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("task_executions.id", ondelete="SET NULL"))
    category: Mapped[str] = mapped_column(String, nullable=False, index=True)
    feature: Mapped[str | None] = mapped_column(String, index=True)
    severity: Mapped[str] = mapped_column(String, nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String, nullable=False, default="open", index=True)
    summary: Mapped[str] = mapped_column(String, nullable=False)
    resolution: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class RevenueLedgerEvent(Base):
    __tablename__ = "revenue_ledger_events"
    __table_args__ = (UniqueConstraint("source_event_id", name="uq_revenue_ledger_events_source"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source_event_id: Mapped[str] = mapped_column(String, nullable=False)
    transaction_id: Mapped[str | None] = mapped_column(String, index=True)
    plan: Mapped[str] = mapped_column(String, nullable=False, index=True)
    billing_interval: Mapped[str] = mapped_column(String, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    fee_amount: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    net_amount: Mapped[Decimal] = mapped_column(Numeric(14, 6), nullable=False)
    pricing_version: Mapped[str] = mapped_column(String, nullable=False)
    service_period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    service_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
