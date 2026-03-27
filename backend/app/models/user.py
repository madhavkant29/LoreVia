import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[str] = mapped_column(String, default="free")   # free | pro | power | admin
    reading_mode: Mapped[str] = mapped_column(String, default="casual")  # casual | analyst | speed
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    books = relationship("Book", back_populates="user", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    reading_progress = relationship("ReadingProgress", back_populates="user", cascade="all, delete-orphan")
    reading_sessions = relationship("ReadingSession", back_populates="user", cascade="all, delete-orphan")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), __import__("sqlalchemy").ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    stripe_customer_id: Mapped[str | None] = mapped_column(String)
    stripe_sub_id: Mapped[str | None] = mapped_column(String)
    plan: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="subscriptions")
