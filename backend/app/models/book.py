import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class VaultNoteSource(enum.StrEnum):
    CHARACTER_BIBLE = "character_bible"
    USER_NOTES = "user_notes"


class Book(Base):
    __tablename__ = "books"
    __table_args__ = (
        UniqueConstraint("public_slug", name="uq_books_public_slug"),
        Index("ix_books_user_hidden_created", "user_id", "hidden_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    author: Mapped[str | None] = mapped_column(String)
    genre: Mapped[str | None] = mapped_column(String)
    format: Mapped[str] = mapped_column(
        String, nullable=False
    )  # pdf | epub | docx | fountain | txt | md | manual
    work_type: Mapped[str] = mapped_column(
        String, nullable=False, default="novel", server_default="novel"
    )
    s3_key: Mapped[str] = mapped_column(String, nullable=False)
    source_size_bytes: Mapped[int | None] = mapped_column(Integer)
    cover_s3_key: Mapped[str | None] = mapped_column(String)
    isbn: Mapped[str | None] = mapped_column(String)
    language: Mapped[str] = mapped_column(String, default="en")
    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    mode: Mapped[str] = mapped_column(String, default="reader")
    source_kind: Mapped[str] = mapped_column(String, default="single_upload")
    preserve_chapter_numbers: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    preserve_source_chapters: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    total_chapters: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    total_chunks: Mapped[int | None] = mapped_column(Integer)
    is_truncated: Mapped[bool] = mapped_column(Boolean, default=False)
    primary_series_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("series.id", ondelete="SET NULL")
    )
    series_name: Mapped[str | None] = mapped_column(String)
    series_order: Mapped[int | None] = mapped_column(Integer)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    public_description: Mapped[str | None] = mapped_column(String)
    public_status: Mapped[str] = mapped_column(
        String, nullable=False, default="draft", server_default="draft", index=True
    )
    public_slug: Mapped[str | None] = mapped_column(String, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    public_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    public_visibility: Mapped[str] = mapped_column(
        String, nullable=False, default="private", server_default="private", index=True
    )
    rights_confirmation: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    rights_confirmation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rights_confirmation_ip_hash: Mapped[str | None] = mapped_column(String)
    rights_confirmation_user_agent: Mapped[str | None] = mapped_column(Text)
    content_source_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
        default="user_original",
        server_default="user_original",
        index=True,
    )
    moderation_status: Mapped[str] = mapped_column(
        String, nullable=False, default="clean", server_default="clean", index=True
    )
    moderation_reason: Mapped[str | None] = mapped_column(Text)
    takedown_reason: Mapped[str | None] = mapped_column(Text)
    takedown_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    takedown_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    public_upload_counted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    source_title: Mapped[str | None] = mapped_column(String)
    source_author: Mapped[str | None] = mapped_column(String)
    source_public_domain_note: Mapped[str | None] = mapped_column(Text)
    source_url: Mapped[str | None] = mapped_column(Text)
    public_share_status: Mapped[str] = mapped_column(
        String, default="not_requested", server_default="not_requested", index=True
    )
    public_share_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    public_share_approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    public_share_approved_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    copyright_warning: Mapped[bool] = mapped_column(Boolean, default=False)
    is_editor_project: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    writer_workspace: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    import_structure: Mapped[dict | None] = mapped_column(JSONB, default=None)
    force_single_manuscript: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", foreign_keys=[user_id], back_populates="books")
    public_share_approved_by_user = relationship(
        "User", foreign_keys=[public_share_approved_by_user_id]
    )
    takedown_by_user = relationship("User", foreign_keys=[takedown_by_user_id])
    chapters = relationship("Chapter", back_populates="book", cascade="all, delete-orphan")
    characters = relationship("Character", back_populates="book", cascade="all, delete-orphan")
    chunks = relationship("BookChunk", back_populates="book", cascade="all, delete-orphan")
    relationships = relationship(
        "CharacterRelationship", back_populates="book", cascade="all, delete-orphan"
    )
    plot_threads = relationship("PlotThread", back_populates="book", cascade="all, delete-orphan")
    wiki_entries = relationship("WikiEntry", back_populates="book", cascade="all, delete-orphan")
    world_building_documents = relationship(
        "WorldBuildingDocument", back_populates="book", cascade="all, delete-orphan"
    )
    world_canonical_identities = relationship(
        "WorldCanonicalIdentity", back_populates="book", cascade="all, delete-orphan"
    )
    world_elements = relationship(
        "WorldElement",
        foreign_keys="WorldElement.book_id",
        back_populates="book",
        cascade="all, delete-orphan",
    )
    world_gap_analyses = relationship(
        "WorldGapAnalysis", back_populates="book", cascade="all, delete-orphan"
    )
    world_notes = relationship("WorldNote", back_populates="book", cascade="all, delete-orphan")
    reading_progress = relationship(
        "ReadingProgress", back_populates="book", cascade="all, delete-orphan"
    )
    reading_sessions = relationship(
        "ReadingSession", back_populates="book", cascade="all, delete-orphan"
    )
    notes = relationship("BookNote", back_populates="book", cascade="all, delete-orphan")
    manuscript_annotations = relationship(
        "ManuscriptAnnotation", back_populates="book", cascade="all, delete-orphan"
    )
    vault_notes = relationship("VaultNote", back_populates="book", cascade="all, delete-orphan")
    vault_note_links = relationship("NoteLink", back_populates="book", cascade="all, delete-orphan")
    vault_note_backlinks = relationship(
        "NoteBacklink", back_populates="book", cascade="all, delete-orphan"
    )
    vault_note_tags = relationship("NoteTag", back_populates="book", cascade="all, delete-orphan")
    vault_note_series_links = relationship(
        "NoteSeriesLink",
        foreign_keys="NoteSeriesLink.source_book_id",
        back_populates="source_book",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    primary_series = relationship(
        "Series", foreign_keys=[primary_series_id], back_populates="primary_books"
    )
    series_memberships = relationship(
        "SeriesBook", back_populates="book", cascade="all, delete-orphan"
    )
    scenes = relationship("Scene", back_populates="book", cascade="all, delete-orphan")
    novel_scenes = relationship("NovelScene", back_populates="book", cascade="all, delete-orphan")
    collaborators = relationship(
        "BookCollaborator", back_populates="book", cascade="all, delete-orphan"
    )
    beta_read_assignments = relationship(
        "BetaReadAssignment", back_populates="book", cascade="all, delete-orphan"
    )
    forum_posts = relationship("BookForumPost", back_populates="book", cascade="all, delete-orphan")
    forum_interests = relationship(
        "BookForumInterest", back_populates="book", cascade="all, delete-orphan"
    )
    forum_comments = relationship(
        "BookForumComment", back_populates="book", cascade="all, delete-orphan"
    )
    custom_tags = relationship("CustomTag", back_populates="book", cascade="all, delete-orphan")
    writing_activities = relationship("UserWritingActivity", back_populates="book")
    public_analytics_events = relationship(
        "PublicBookAnalyticsEvent", back_populates="book", cascade="all, delete-orphan"
    )
    public_rankings = relationship(
        "PublicBookRanking", back_populates="book", cascade="all, delete-orphan"
    )


class BookUploadCharge(Base):
    __tablename__ = "book_upload_charges"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "charge_kind", "source_id", name="uq_book_upload_charges_source"
        ),
        Index("ix_book_upload_charges_user_kind_created", "user_id", "charge_kind", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    charge_kind: Mapped[str] = mapped_column(String, nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    source_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    metadata_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )


class PublicBookAnalyticsEvent(Base):
    __tablename__ = "public_book_analytics_events"
    __table_args__ = (
        UniqueConstraint(
            "book_id",
            "chapter_number",
            "event_type",
            "visitor_fingerprint_hash",
            "event_date",
            name="uq_public_book_analytics_events_daily_fingerprint",
        ),
        Index("ix_public_book_analytics_events_book_created_at", "book_id", "created_at"),
        Index("ix_public_book_analytics_events_book_event_type", "book_id", "event_type"),
        Index("ix_public_book_analytics_events_book_event_date", "book_id", "event_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False
    )
    chapter_number: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    visitor_fingerprint_hash: Mapped[str] = mapped_column(String, nullable=False)
    event_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    book = relationship("Book", back_populates="public_analytics_events")


class PublicBookRanking(Base):
    __tablename__ = "public_book_rankings"
    __table_args__ = (
        UniqueConstraint(
            "book_id",
            "surface",
            "ranking_key",
            "time_window",
            "snapshot_date",
            name="uq_public_book_rankings_snapshot",
        ),
        Index(
            "ix_public_book_rankings_surface_key_window_snapshot_rank",
            "surface",
            "ranking_key",
            "time_window",
            "snapshot_date",
            "rank_position",
        ),
        Index("ix_public_book_rankings_book_surface", "book_id", "surface"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False
    )
    surface: Mapped[str] = mapped_column(String, nullable=False)
    ranking_key: Mapped[str] = mapped_column(String, nullable=False)
    time_window: Mapped[str] = mapped_column(String, nullable=False)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    rank_position: Mapped[int] = mapped_column(Integer, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0, server_default="0")
    primary_timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    book = relationship("Book", back_populates="public_rankings")


class BookCollaborator(Base):
    __tablename__ = "book_collaborators"
    __table_args__ = (
        UniqueConstraint("book_id", "email", name="uq_book_collaborators_book_email"),
        Index(
            "ix_book_collaborators_email_status_invited",
            "email",
            "invite_status",
            "invited_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    invited_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    email: Mapped[str] = mapped_column(String, nullable=False, index=True)
    display_name: Mapped[str | None] = mapped_column(String)
    role: Mapped[str] = mapped_column(
        String, nullable=False, default="viewer", server_default="viewer", index=True
    )
    scope: Mapped[dict | None] = mapped_column(JSONB, default=dict, server_default="{}")
    permissions: Mapped[dict | None] = mapped_column(JSONB, default=dict, server_default="{}")
    scope_chapter_start: Mapped[int | None] = mapped_column(Integer)
    scope_chapter_end: Mapped[int | None] = mapped_column(Integer)
    scope_character_bible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    scope_continuity_report: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    scope_reader_confusion_report: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    permission_can_edit_manuscript: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    permission_can_view_story_bible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    permission_can_run_ai_scans: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    permission_can_export: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    permission_can_comment: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    permission_can_view_selected_chapters_only: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    invite_status: Mapped[str] = mapped_column(
        String, nullable=False, default="active", server_default="active", index=True
    )
    invited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True
    )

    book = relationship("Book", back_populates="collaborators")


class BookForumPost(Base):
    __tablename__ = "book_forum_posts"
    __table_args__ = (
        Index("ix_book_forum_posts_book_status", "book_id", "status"),
        Index("ix_book_forum_posts_status_created_at", "status", "created_at"),
        Index(
            "ix_book_forum_posts_thread_type_status_created_at",
            "thread_type",
            "status",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), index=True
    )
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    thread_type: Mapped[str] = mapped_column(
        String, nullable=False, default="novel", server_default="novel", index=True
    )
    headline: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    image_s3_key: Mapped[str | None] = mapped_column(String)
    image_content_type: Mapped[str | None] = mapped_column(String)
    image_filename: Mapped[str | None] = mapped_column(String)
    desired_beta_reader_count: Mapped[int | None] = mapped_column(Integer)
    allow_contact_requests: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="open", server_default="open", index=True
    )
    like_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    dislike_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True
    )

    book = relationship("Book", back_populates="forum_posts")
    interests = relationship(
        "BookForumInterest", back_populates="post", cascade="all, delete-orphan"
    )
    comments = relationship("BookForumComment", back_populates="post", cascade="all, delete-orphan")
    reactions = relationship(
        "BookForumPostReaction", back_populates="post", cascade="all, delete-orphan"
    )


class BookForumInterest(Base):
    __tablename__ = "book_forum_interests"
    __table_args__ = (
        UniqueConstraint("post_id", "interested_user_id", name="uq_book_forum_interests_post_user"),
        Index("ix_book_forum_interests_post_status_created_at", "post_id", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("book_forum_posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    interested_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
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

    post = relationship("BookForumPost", back_populates="interests")
    book = relationship("Book", back_populates="forum_interests")
    interested_user = relationship("User", foreign_keys=[interested_user_id])


class BookForumComment(Base):
    __tablename__ = "book_forum_comments"
    __table_args__ = (
        Index("ix_book_forum_comments_post_created_at", "post_id", "created_at"),
        Index("ix_book_forum_comments_parent_created_at", "parent_comment_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("book_forum_posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    book_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), index=True
    )
    parent_comment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("book_forum_comments.id", ondelete="CASCADE"), index=True
    )
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    image_s3_key: Mapped[str | None] = mapped_column(String)
    image_content_type: Mapped[str | None] = mapped_column(String)
    image_filename: Mapped[str | None] = mapped_column(String)
    like_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    dislike_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True
    )

    post = relationship("BookForumPost", back_populates="comments")
    book = relationship("Book", back_populates="forum_comments")
    author = relationship("User", foreign_keys=[author_user_id], back_populates="forum_comments")
    parent_comment = relationship("BookForumComment", remote_side=[id], back_populates="replies")
    replies = relationship(
        "BookForumComment", back_populates="parent_comment", cascade="all, delete-orphan"
    )
    reactions = relationship(
        "BookForumCommentReaction", back_populates="comment", cascade="all, delete-orphan"
    )


class BookForumCommentReaction(Base):
    __tablename__ = "book_forum_comment_reactions"
    __table_args__ = (
        UniqueConstraint(
            "comment_id", "user_id", name="uq_book_forum_comment_reactions_comment_user"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    comment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("book_forum_comments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("book_forum_posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reaction: Mapped[str] = mapped_column(
        String, nullable=False, default="like", server_default="like"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True
    )

    comment = relationship("BookForumComment", back_populates="reactions")
    user = relationship("User", back_populates="forum_comment_reactions")


class BookForumPostReaction(Base):
    __tablename__ = "book_forum_post_reactions"
    __table_args__ = (
        UniqueConstraint("post_id", "user_id", name="uq_book_forum_post_reactions_post_user"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("book_forum_posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reaction: Mapped[str] = mapped_column(
        String, nullable=False, default="like", server_default="like"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True
    )

    post = relationship("BookForumPost", back_populates="reactions")
    user = relationship("User", back_populates="forum_post_reactions")


class Chapter(Base):
    __tablename__ = "chapters"
    __table_args__ = (Index("ix_chapters_book_id_number", "book_id", "number"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    structure_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    title: Mapped[str | None] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(String)
    chapter_kind: Mapped[str] = mapped_column(
        String, nullable=False, default="chapter", server_default="chapter", index=True
    )
    s3_key: Mapped[str] = mapped_column(String, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    word_count: Mapped[int | None] = mapped_column(Integer)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)
    analysis_state: Mapped[dict | None] = mapped_column(JSONB, default=dict)

    book = relationship("Book", back_populates="chapters")
    chunks = relationship("BookChunk", back_populates="chapter", cascade="all, delete-orphan")
    summaries = relationship(
        "ChapterSummary", back_populates="chapter", cascade="all, delete-orphan"
    )
    media = relationship("ChapterMedia", back_populates="chapter", cascade="all, delete-orphan")
    versions = relationship(
        "ChapterVersion", back_populates="chapter", cascade="all, delete-orphan"
    )
    novel_scenes = relationship(
        "NovelScene", back_populates="chapter", cascade="all, delete-orphan"
    )


class ChapterVersion(Base):
    __tablename__ = "chapter_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="SET NULL"), index=True
    )
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String)
    s3_key: Mapped[str] = mapped_column(String, nullable=False)
    word_count: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String)
    snapshot_kind: Mapped[str] = mapped_column(
        String, nullable=False, default="manual", server_default="manual"
    )
    restored_from_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chapter_versions.id", ondelete="SET NULL")
    )
    restore_status: Mapped[str | None] = mapped_column(String, index=True)
    restore_error: Mapped[str | None] = mapped_column(Text)
    restore_task_id: Mapped[str | None] = mapped_column(String)
    restore_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    restore_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    chapter = relationship("Chapter", back_populates="versions")
    restored_from = relationship("ChapterVersion", remote_side=[id])


class BookNote(Base):
    __tablename__ = "book_notes"
    __table_args__ = (
        Index("ix_book_notes_book_chapter_updated", "book_id", "chapter_number", "updated_at"),
        Index("ix_book_notes_user_updated", "user_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chapter_number: Mapped[int | None] = mapped_column(Integer, index=True)
    title: Mapped[str | None] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True
    )

    book = relationship("Book", back_populates="notes")


class ManuscriptAnnotation(Base):
    __tablename__ = "manuscript_annotations"
    __table_args__ = (
        Index(
            "ix_manuscript_annotations_book_chapter_created",
            "book_id",
            "chapter_number",
            "created_at",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    category: Mapped[str] = mapped_column(
        String, nullable=False, default="general", server_default="general", index=True
    )
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="open", server_default="open", index=True
    )
    visibility: Mapped[str] = mapped_column(
        String, nullable=False, default="shared", server_default="shared", index=True
    )
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)
    anchor_context_before: Mapped[str | None] = mapped_column(Text)
    anchor_context_after: Mapped[str | None] = mapped_column(Text)
    start_offset: Mapped[int | None] = mapped_column(Integer)
    end_offset: Mapped[int | None] = mapped_column(Integer)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True
    )

    book = relationship("Book", back_populates="manuscript_annotations")
    user = relationship("User")


class VaultNote(Base):
    __tablename__ = "book_vault_notes"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "book_id", "path", "source", name="uq_book_vault_notes_user_book_path_source"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    path: Mapped[str] = mapped_column(String, nullable=False, index=True)
    source: Mapped[VaultNoteSource] = mapped_column(
        String,
        nullable=False,
        default=VaultNoteSource.CHARACTER_BIBLE.value,
        server_default=VaultNoteSource.CHARACTER_BIBLE.value,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True
    )

    book = relationship("Book", back_populates="vault_notes")
    outgoing_links = relationship(
        "NoteLink",
        foreign_keys="NoteLink.source_note_id",
        back_populates="source_note",
        cascade="all, delete-orphan",
    )
    incoming_links = relationship(
        "NoteLink",
        foreign_keys="NoteLink.target_note_id",
        back_populates="target_note",
        cascade="all, delete-orphan",
    )
    backlinks = relationship(
        "NoteBacklink",
        foreign_keys="NoteBacklink.target_note_id",
        back_populates="target_note",
        cascade="all, delete-orphan",
    )
    tags = relationship("NoteTag", back_populates="note", cascade="all, delete-orphan")


class NoteLink(Base):
    __tablename__ = "book_vault_note_links"
    __table_args__ = (
        UniqueConstraint(
            "source_note_id",
            "target_note_id",
            "link_type",
            name="uq_book_vault_note_links_source_target_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("book_vault_notes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("book_vault_notes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    link_type: Mapped[str] = mapped_column(
        String, nullable=False, default="reference", server_default="reference", index=True
    )
    target_label: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    book = relationship("Book", back_populates="vault_note_links")
    source_note = relationship(
        "VaultNote", foreign_keys=[source_note_id], back_populates="outgoing_links"
    )
    target_note = relationship(
        "VaultNote", foreign_keys=[target_note_id], back_populates="incoming_links"
    )


class NoteBacklink(Base):
    __tablename__ = "book_vault_note_backlinks"
    __table_args__ = (
        UniqueConstraint(
            "source_note_id",
            "target_note_id",
            "link_type",
            name="uq_book_vault_note_backlinks_source_target_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("book_vault_notes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("book_vault_notes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    link_type: Mapped[str] = mapped_column(
        String, nullable=False, default="reference", server_default="reference", index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    book = relationship("Book", back_populates="vault_note_backlinks")
    source_note = relationship("VaultNote", foreign_keys=[source_note_id])
    target_note = relationship(
        "VaultNote", foreign_keys=[target_note_id], back_populates="backlinks"
    )


class NoteTag(Base):
    __tablename__ = "book_vault_note_tags"
    __table_args__ = (
        UniqueConstraint("note_id", "tag_name", name="uq_book_vault_note_tags_note_tag"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("book_vault_notes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tag_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    book = relationship("Book", back_populates="vault_note_tags")
    note = relationship("VaultNote", back_populates="tags")


class NoteSeriesLink(Base):
    __tablename__ = "book_vault_note_series_links"
    __table_args__ = (
        UniqueConstraint(
            "source_note_id",
            "target_note_id",
            "link_type",
            name="uq_book_vault_note_series_links_source_target_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("series.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("book_vault_notes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_note_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("book_vault_notes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    link_type: Mapped[str] = mapped_column(
        String, nullable=False, default="reference", server_default="reference", index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    source_book = relationship(
        "Book", foreign_keys=[source_book_id], back_populates="vault_note_series_links"
    )
    target_book = relationship("Book", foreign_keys=[target_book_id])
    source_note = relationship("VaultNote", foreign_keys=[source_note_id])
    target_note = relationship("VaultNote", foreign_keys=[target_note_id])


class ChapterMedia(Base):
    __tablename__ = "chapter_media"
    __table_args__ = (UniqueConstraint("chapter_id", "marker", name="uq_chapter_media_marker"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    marker: Mapped[str] = mapped_column(String, nullable=False)
    asset_type: Mapped[str] = mapped_column(String, default="image")
    content_type: Mapped[str | None] = mapped_column(String)
    storage_key: Mapped[str] = mapped_column(String, nullable=False)
    caption: Mapped[str | None] = mapped_column(String)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    chapter = relationship("Chapter", back_populates="media")


class Series(Base):
    __tablename__ = "series"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    primary_books = relationship(
        "Book", foreign_keys=[Book.primary_series_id], back_populates="primary_series"
    )
    memberships = relationship("SeriesBook", back_populates="series", cascade="all, delete-orphan")


class SeriesBook(Base):
    __tablename__ = "series_books"
    __table_args__ = (
        UniqueConstraint("series_id", "book_id", name="uq_series_books_series_book"),
        Index("ix_series_books_series_position_book", "series_id", "position", "book_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    series_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("series.id", ondelete="CASCADE"), nullable=False, index=True
    )
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    position: Mapped[int | None] = mapped_column(Integer)
    marked_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    series = relationship("Series", back_populates="memberships")
    book = relationship("Book", back_populates="series_memberships")


class Scene(Base):
    __tablename__ = "scenes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="SET NULL"), index=True
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    heading: Mapped[str] = mapped_column(String, nullable=False)  # INT. LOCATION - DAY
    location: Mapped[str | None] = mapped_column(String)  # LOCATION
    time_of_day: Mapped[str | None] = mapped_column(String)  # DAY/NIGHT/DAWN/ETC
    interior: Mapped[bool] = mapped_column(Boolean, default=False)
    exterior: Mapped[bool] = mapped_column(Boolean, default=False)
    scene_number: Mapped[str | None] = mapped_column(String)  # Optional scene numbering
    description: Mapped[str | None] = mapped_column(Text)  # Action/description text
    word_count: Mapped[int | None] = mapped_column(Integer)
    page_number: Mapped[int | None] = mapped_column(Integer)  # Page number in script
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    book = relationship("Book")
    chapter = relationship("Chapter")
    dialogue = relationship("Dialogue", back_populates="scene", cascade="all, delete-orphan")


class Dialogue(Base):
    __tablename__ = "dialogue"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scene_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    character_name: Mapped[str] = mapped_column(String, nullable=False)
    character_extension: Mapped[str | None] = mapped_column(String)  # (O.S.), (V.O.), (CONT'D)
    dialogue_text: Mapped[str] = mapped_column(Text, nullable=False)
    parenthetical: Mapped[str | None] = mapped_column(String)  # (wrylies)
    line_number: Mapped[int] = mapped_column(Integer, nullable=False)  # Order within scene
    word_count: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    scene = relationship("Scene", back_populates="dialogue")


class NovelScene(Base):
    __tablename__ = "novel_scenes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="SET NULL"), index=True
    )
    chapter_number: Mapped[int | None] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    html_body: Mapped[str | None] = mapped_column(Text)
    scene_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict)
    path: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String, nullable=False, default="unassigned", server_default="unassigned", index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    source: Mapped[str] = mapped_column(
        String, nullable=False, default="manual", server_default="manual"
    )
    origin_chapter_number: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True
    )

    book = relationship("Book", back_populates="novel_scenes")
    chapter = relationship("Chapter", back_populates="novel_scenes")
    versions = relationship("SceneVersion", back_populates="scene", cascade="all, delete-orphan")


class SceneVersion(Base):
    __tablename__ = "scene_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True
    )
    scene_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("novel_scenes.id", ondelete="SET NULL"), index=True
    )
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="SET NULL"), index=True
    )
    chapter_number: Mapped[int | None] = mapped_column(Integer, index=True)
    scene_title: Mapped[str] = mapped_column(String, nullable=False)
    scene_description: Mapped[str | None] = mapped_column(String)
    scene_path: Mapped[str | None] = mapped_column(String, index=True)
    s3_key: Mapped[str] = mapped_column(String, nullable=False)
    word_count: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String)
    snapshot_kind: Mapped[str] = mapped_column(
        String, nullable=False, default="manual", server_default="manual", index=True
    )
    restored_from_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scene_versions.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    scene = relationship("NovelScene", back_populates="versions")
    chapter = relationship("Chapter")
    restored_from = relationship("SceneVersion", remote_side=[id])
