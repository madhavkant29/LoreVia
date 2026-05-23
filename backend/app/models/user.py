import uuid
from datetime import date, datetime

from sqlalchemy import ARRAY, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        UniqueConstraint("username", name="uq_users_username"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, nullable=False)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[str] = mapped_column(String, default="free")   # subscription tier only: free | author | architect | admin (legacy reader/collaborator aliases normalize to free)
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
    consecutive_missed_beta_reads: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    beta_read_penalty_status: Mapped[str] = mapped_column(String, default="none", server_default="none")
    beta_read_penalty_required_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reputation_score: Mapped[int] = mapped_column(Integer, default=0, server_default="0", index=True)
    reputation_likes_received: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    reputation_dislikes_received: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    messaging_permission: Mapped[str] = mapped_column(String, default="anyone", server_default="anyone")
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    books = relationship("Book", foreign_keys="Book.user_id", back_populates="user", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    subscription_events = relationship("SubscriptionEvent", back_populates="user", cascade="all, delete-orphan")
    reading_progress = relationship("ReadingProgress", back_populates="user", cascade="all, delete-orphan")
    reading_sessions = relationship("ReadingSession", back_populates="user", cascade="all, delete-orphan")
    rate_limit_override = relationship("UserRateLimitOverride", back_populates="user", cascade="all, delete-orphan", uselist=False)
    notifications = relationship("Notification", cascade="all, delete-orphan")
    device_trials = relationship("DeviceTrial", back_populates="user", cascade="all, delete-orphan")
    trial_email_events = relationship("TrialEmailEvent", back_populates="user", cascade="all, delete-orphan")
    writing_activities = relationship("UserWritingActivity", back_populates="user", cascade="all, delete-orphan")
    llm_usage_events = relationship("LlmUsageEvent", back_populates="user", cascade="all, delete-orphan")
    forum_comments = relationship("BookForumComment", back_populates="author", cascade="all, delete-orphan")
    forum_post_reactions = relationship("BookForumPostReaction", back_populates="user", cascade="all, delete-orphan")
    forum_comment_reactions = relationship("BookForumCommentReaction", back_populates="user", cascade="all, delete-orphan")
    friend_requests_sent = relationship("FriendRequest", foreign_keys="FriendRequest.requester_user_id", back_populates="requester", cascade="all, delete-orphan")
    friend_requests_received = relationship("FriendRequest", foreign_keys="FriendRequest.addressee_user_id", back_populates="addressee", cascade="all, delete-orphan")
    direct_conversations_as_a = relationship("DirectConversation", foreign_keys="DirectConversation.participant_a_user_id", back_populates="participant_a", cascade="all, delete-orphan")
    direct_conversations_as_b = relationship("DirectConversation", foreign_keys="DirectConversation.participant_b_user_id", back_populates="participant_b", cascade="all, delete-orphan")
    direct_messages_sent = relationship("DirectMessage", foreign_keys="DirectMessage.sender_user_id", back_populates="sender", cascade="all, delete-orphan")
    email_preferences = relationship("EmailPreference", back_populates="user", cascade="all, delete-orphan", uselist=False)


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
    __table_args__ = (
        UniqueConstraint("source_event_id", name="uq_subscription_events_source_event_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String, nullable=False, default="paddle", server_default="paddle", index=True)
    source_event_id: Mapped[str | None] = mapped_column(String)
    plan: Mapped[str | None] = mapped_column(String, index=True)
    status: Mapped[str | None] = mapped_column(String, index=True)
    paddle_customer_id: Mapped[str | None] = mapped_column(String, index=True)
    paddle_sub_id: Mapped[str | None] = mapped_column(String, index=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    user = relationship("User", back_populates="subscription_events")


class PaddleWebhookEvent(Base):
    __tablename__ = "paddle_webhook_events"
    __table_args__ = (
        UniqueConstraint("event_id", name="uq_paddle_webhook_events_event_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    notification_id: Mapped[str | None] = mapped_column(String)
    processing_status: Mapped[str] = mapped_column(String, nullable=False, default="processing", server_default="processing", index=True)
    payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    first_received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    last_error: Mapped[str | None] = mapped_column(Text)
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class UserRateLimitOverride(Base):
    __tablename__ = "user_rate_limit_overrides"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_rate_limit_overrides_user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), __import__("sqlalchemy").ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
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


class EmailPreference(Base):
    __tablename__ = "email_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_email_preferences_user_id"),
        UniqueConstraint("email", name="uq_email_preferences_email"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String, nullable=False, index=True)
    product_updates: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    marketing: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    unsubscribed_all: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)

    user = relationship("User", back_populates="email_preferences")


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

    user = relationship("User", back_populates="llm_usage_events")
