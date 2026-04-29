import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String, unique=True, nullable=True, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[str] = mapped_column(String, default="free")   # free | pro | power | admin
    reading_mode: Mapped[str] = mapped_column(String, default="casual")  # casual | analyst | speed
    legal_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    legal_version: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    books = relationship("Book", back_populates="user", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    reading_progress = relationship("ReadingProgress", back_populates="user", cascade="all, delete-orphan")
    reading_sessions = relationship("ReadingSession", back_populates="user", cascade="all, delete-orphan")
    rate_limit_override = relationship("UserRateLimitOverride", back_populates="user", cascade="all, delete-orphan", uselist=False)
    notifications = relationship("Notification", cascade="all, delete-orphan")


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
