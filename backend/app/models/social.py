from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class FriendRequest(Base):
    __tablename__ = "friend_requests"
    __table_args__ = (
        UniqueConstraint(
            "requester_user_id", "addressee_user_id", name="uq_friend_requests_direction"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    requester_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    addressee_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="pending", server_default="pending", index=True
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True
    )

    requester = relationship(
        "User", foreign_keys=[requester_user_id], back_populates="friend_requests_sent"
    )
    addressee = relationship(
        "User", foreign_keys=[addressee_user_id], back_populates="friend_requests_received"
    )


class DirectConversation(Base):
    __tablename__ = "direct_conversations"
    __table_args__ = (
        UniqueConstraint(
            "participant_a_user_id", "participant_b_user_id", name="uq_direct_conversations_pair"
        ),
        Index(
            "ix_direct_conversations_a_activity_id",
            "participant_a_user_id",
            text("COALESCE(last_message_at, created_at) DESC"),
            text("id DESC"),
        ),
        Index(
            "ix_direct_conversations_b_activity_id",
            "participant_b_user_id",
            text("COALESCE(last_message_at, created_at) DESC"),
            text("id DESC"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    participant_a_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    participant_b_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True
    )

    participant_a = relationship(
        "User", foreign_keys=[participant_a_user_id], back_populates="direct_conversations_as_a"
    )
    participant_b = relationship(
        "User", foreign_keys=[participant_b_user_id], back_populates="direct_conversations_as_b"
    )
    messages = relationship(
        "DirectMessage", back_populates="conversation", cascade="all, delete-orphan"
    )


class DirectMessage(Base):
    __tablename__ = "direct_messages"
    __table_args__ = (
        Index(
            "ix_direct_messages_conversation_created_id",
            "conversation_id",
            "created_at",
            "id",
        ),
        Index(
            "ix_direct_messages_recipient_unread_conversation",
            "recipient_user_id",
            "conversation_id",
            postgresql_where=text("recipient_read_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("direct_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recipient_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    recipient_read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    conversation = relationship("DirectConversation", back_populates="messages")
    sender = relationship(
        "User", foreign_keys=[sender_user_id], back_populates="direct_messages_sent"
    )
