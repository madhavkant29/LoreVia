import uuid
from datetime import date, datetime

from sqlalchemy import ARRAY, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String, unique=True, nullable=True, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[str] = mapped_column(String, default="free")   # free | reader | author | architect | admin
    reading_mode: Mapped[str] = mapped_column(String, default="casual")  # casual | analyst | speed
    daily_word_goal: Mapped[int] = mapped_column(Integer, default=1000, server_default="1000")
    today_word_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    today_word_count_date: Mapped[date | None] = mapped_column(Date)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_date: Mapped[date | None] = mapped_column(Date)
    login_streak_days: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    longest_login_streak_days: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    login_activity_dates: Mapped[list[date] | None] = mapped_column(ARRAY(Date))
    legal_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    legal_version: Mapped[str | None] = mapped_column(String)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    referral_code: Mapped[str | None] = mapped_column(String, unique=True, nullable=True, index=True)
    consecutive_missed_beta_reads: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    beta_read_penalty_status: Mapped[str] = mapped_column(String, default="none", server_default="none")
    beta_read_penalty_required_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reputation_score: Mapped[int] = mapped_column(Integer, default=0, server_default="0", index=True)
    reputation_likes_received: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    reputation_dislikes_received: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    books = relationship("Book", back_populates="user", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    subscription_events = relationship("SubscriptionEvent", back_populates="user", cascade="all, delete-orphan")
    reading_progress = relationship("ReadingProgress", back_populates="user", cascade="all, delete-orphan")
    reading_sessions = relationship("ReadingSession", back_populates="user", cascade="all, delete-orphan")
    rate_limit_override = relationship("UserRateLimitOverride", back_populates="user", cascade="all, delete-orphan", uselist=False)
    notifications = relationship("Notification", cascade="all, delete-orphan")
    device_trials = relationship("DeviceTrial", back_populates="user", cascade="all, delete-orphan")
    point_entries = relationship("PointLedgerEntry", back_populates="user", cascade="all, delete-orphan")
    referrals_made = relationship(
        "Referral",
        foreign_keys="Referral.referrer_user_id",
        back_populates="referrer",
        cascade="all, delete-orphan",
    )
    referral_received = relationship(
        "Referral",
        foreign_keys="Referral.referred_user_id",
        back_populates="referred_user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    trial_email_events = relationship("TrialEmailEvent", back_populates="user", cascade="all, delete-orphan")
    rewarded_ad_sessions = relationship("RewardedAdSession", back_populates="user", cascade="all, delete-orphan")
    writing_activities = relationship("UserWritingActivity", back_populates="user", cascade="all, delete-orphan")
    llm_usage_events = relationship("LlmUsageEvent", cascade="all, delete-orphan")
    forum_comments = relationship("BookForumComment", back_populates="author", cascade="all, delete-orphan")
    forum_comment_reactions = relationship("BookForumCommentReaction", back_populates="user", cascade="all, delete-orphan")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), __import__("sqlalchemy").ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    paddle_customer_id: Mapped[str | None] = mapped_column(String)
    paddle_sub_id: Mapped[str | None] = mapped_column(String)
    paddle_transaction_id: Mapped[str | None] = mapped_column(String)
    stripe_customer_id: Mapped[str | None] = mapped_column(String)
    stripe_sub_id: Mapped[str | None] = mapped_column(String)
    plan: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="subscriptions")


class SubscriptionEvent(Base):
    __tablename__ = "subscription_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String, nullable=False, default="paddle", server_default="paddle", index=True)
    source_event_id: Mapped[str | None] = mapped_column(String, unique=True, index=True)
    plan: Mapped[str | None] = mapped_column(String, index=True)
    status: Mapped[str | None] = mapped_column(String, index=True)
    paddle_customer_id: Mapped[str | None] = mapped_column(String, index=True)
    paddle_sub_id: Mapped[str | None] = mapped_column(String, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    user = relationship("User", back_populates="subscription_events")


class UserRateLimitOverride(Base):
    __tablename__ = "user_rate_limit_overrides"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), __import__("sqlalchemy").ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    search_per_hour: Mapped[int | None] = mapped_column(__import__("sqlalchemy").Integer)
    summary_per_hour: Mapped[int | None] = mapped_column(__import__("sqlalchemy").Integer)
    chat_per_day: Mapped[int | None] = mapped_column(__import__("sqlalchemy").Integer)
    api_per_minute: Mapped[int | None] = mapped_column(__import__("sqlalchemy").Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="rate_limit_override")


class DeviceTrial(Base):
    __tablename__ = "device_trials"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), __import__("sqlalchemy").ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    device_id_hash: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="device_trials")


class PointLedgerEntry(Base):
    __tablename__ = "point_ledger_entries"
    __table_args__ = (
        UniqueConstraint("user_id", "entry_type", "source_type", "source_id", name="uq_point_ledger_entries_source"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    entry_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    source_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    points_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    user = relationship("User", back_populates="point_entries")


class Referral(Base):
    __tablename__ = "referrals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    referrer_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    referred_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    referral_code: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending", server_default="pending", index=True)
    qualified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rewarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    referrer = relationship("User", foreign_keys=[referrer_user_id], back_populates="referrals_made")
    referred_user = relationship("User", foreign_keys=[referred_user_id], back_populates="referral_received")


class TrialEmailEvent(Base):
    __tablename__ = "trial_email_events"
    __table_args__ = (UniqueConstraint("user_id", "email_type", name="uq_trial_email_events_user_type"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    email_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending", server_default="pending", index=True)
    resend_message_id: Mapped[str | None] = mapped_column(String)
    last_error: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="trial_email_events")


class RewardedAdSession(Base):
    __tablename__ = "rewarded_ad_sessions"
    __table_args__ = (UniqueConstraint("claim_token", name="uq_rewarded_ad_sessions_claim_token"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String, nullable=False, index=True)
    claim_token: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    ad_unit_path: Mapped[str] = mapped_column(String, nullable=False)
    placement: Mapped[str | None] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending", server_default="pending", index=True)
    reward_points: Mapped[int] = mapped_column(Integer, nullable=False)
    reward_granted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="rewarded_ad_sessions")


class UserWritingActivity(Base):
    __tablename__ = "user_writing_activities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="SET NULL"), index=True)
    chapter_number: Mapped[int | None] = mapped_column(Integer, index=True)
    entry_title: Mapped[str] = mapped_column(String, nullable=False)
    words_added: Mapped[int] = mapped_column(Integer, nullable=False)
    activity_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    user = relationship("User", back_populates="writing_activities")
    book = relationship("Book", back_populates="writing_activities")


class LlmUsageEvent(Base):
    __tablename__ = "llm_usage_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="SET NULL"), index=True)
    provider: Mapped[str] = mapped_column(String, nullable=False, default="openai", server_default="openai", index=True)
    model: Mapped[str] = mapped_column(String, nullable=False, index=True)
    operation: Mapped[str] = mapped_column(String, nullable=False, index=True)
    feature: Mapped[str] = mapped_column(String, nullable=False, index=True)
    request_id: Mapped[str | None] = mapped_column(String, index=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    cached: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    user = relationship("User")
