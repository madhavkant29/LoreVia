import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ObsidianVaultNoteSource(str, enum.Enum):
    CHARACTER_BIBLE = "character_bible"
    USER_NOTES = "user_notes"


class Book(Base):
    __tablename__ = "books"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    author: Mapped[str | None] = mapped_column(String)
    genre: Mapped[str | None] = mapped_column(String)
    format: Mapped[str] = mapped_column(String, nullable=False)   # pdf | epub | docx | fountain | txt | md | manual
    work_type: Mapped[str] = mapped_column(String, nullable=False, default="novel", server_default="novel")
    s3_key: Mapped[str] = mapped_column(String, nullable=False)
    cover_s3_key: Mapped[str | None] = mapped_column(String)
    isbn: Mapped[str | None] = mapped_column(String)
    language: Mapped[str] = mapped_column(String, default="en")
    status: Mapped[str] = mapped_column(String, default="pending", index=True)
    mode: Mapped[str] = mapped_column(String, default="reader")
    source_kind: Mapped[str] = mapped_column(String, default="single_upload")
    preserve_chapter_numbers: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    total_chapters: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    total_chunks: Mapped[int | None] = mapped_column(Integer)
    is_truncated: Mapped[bool] = mapped_column(Boolean, default=False)
    primary_series_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("series.id", ondelete="SET NULL"))
    series_name: Mapped[str | None] = mapped_column(String)
    series_order: Mapped[int | None] = mapped_column(Integer)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    public_description: Mapped[str | None] = mapped_column(String)
    copyright_warning: Mapped[bool] = mapped_column(Boolean, default=False)
    writer_workspace: Mapped[dict | None] = mapped_column(JSONB, default=dict)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="books")
    chapters = relationship("Chapter", back_populates="book", cascade="all, delete-orphan")
    characters = relationship("Character", back_populates="book", cascade="all, delete-orphan")
    chunks = relationship("BookChunk", back_populates="book", cascade="all, delete-orphan")
    relationships = relationship("CharacterRelationship", back_populates="book", cascade="all, delete-orphan")
    plot_threads = relationship("PlotThread", back_populates="book", cascade="all, delete-orphan")
    wiki_entries = relationship("WikiEntry", back_populates="book", cascade="all, delete-orphan")
    world_building_documents = relationship("WorldBuildingDocument", back_populates="book", cascade="all, delete-orphan")
    world_canonical_identities = relationship("WorldCanonicalIdentity", back_populates="book", cascade="all, delete-orphan")
    world_elements = relationship("WorldElement", foreign_keys="WorldElement.book_id", back_populates="book", cascade="all, delete-orphan")
    world_gap_analyses = relationship("WorldGapAnalysis", back_populates="book", cascade="all, delete-orphan")
    world_notes = relationship("WorldNote", back_populates="book", cascade="all, delete-orphan")
    reading_progress = relationship("ReadingProgress", back_populates="book", cascade="all, delete-orphan")
    reading_sessions = relationship("ReadingSession", back_populates="book", cascade="all, delete-orphan")
    notes = relationship("BookNote", back_populates="book", cascade="all, delete-orphan")
    obsidian_notes = relationship("ObsidianVaultNote", back_populates="book", cascade="all, delete-orphan")
    obsidian_note_links = relationship("NoteLink", back_populates="book", cascade="all, delete-orphan")
    obsidian_note_backlinks = relationship("NoteBacklink", back_populates="book", cascade="all, delete-orphan")
    obsidian_note_tags = relationship("NoteTag", back_populates="book", cascade="all, delete-orphan")
    obsidian_note_series_links = relationship(
        "NoteSeriesLink",
        foreign_keys="NoteSeriesLink.source_book_id",
        back_populates="source_book",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    primary_series = relationship("Series", foreign_keys=[primary_series_id], back_populates="primary_books")
    series_memberships = relationship("SeriesBook", back_populates="book", cascade="all, delete-orphan")
    scenes = relationship("Scene", back_populates="book", cascade="all, delete-orphan")
    novel_scenes = relationship("NovelScene", back_populates="book", cascade="all, delete-orphan")


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(String)
    s3_key: Mapped[str] = mapped_column(String, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    word_count: Mapped[int | None] = mapped_column(Integer)
    processed: Mapped[bool] = mapped_column(Boolean, default=False)

    book = relationship("Book", back_populates="chapters")
    chunks = relationship("BookChunk", back_populates="chapter", cascade="all, delete-orphan")
    summaries = relationship("ChapterSummary", back_populates="chapter", cascade="all, delete-orphan")
    media = relationship("ChapterMedia", back_populates="chapter", cascade="all, delete-orphan")
    versions = relationship("ChapterVersion", back_populates="chapter", cascade="all, delete-orphan")
    novel_scenes = relationship("NovelScene", back_populates="chapter", cascade="all, delete-orphan")


class ChapterVersion(Base):
    __tablename__ = "chapter_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="SET NULL"), index=True)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String)
    s3_key: Mapped[str] = mapped_column(String, nullable=False)
    word_count: Mapped[int | None] = mapped_column(Integer)
    note: Mapped[str | None] = mapped_column(String)
    snapshot_kind: Mapped[str] = mapped_column(String, nullable=False, default="manual", server_default="manual")
    restored_from_version_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("chapter_versions.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    chapter = relationship("Chapter", back_populates="versions")
    restored_from = relationship("ChapterVersion", remote_side=[id])


class BookNote(Base):
    __tablename__ = "book_notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_number: Mapped[int | None] = mapped_column(Integer, index=True)
    title: Mapped[str | None] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)

    book = relationship("Book", back_populates="notes")


class ObsidianVaultNote(Base):
    __tablename__ = "book_obsidian_notes"
    __table_args__ = (
        UniqueConstraint("user_id", "book_id", "path", "source", name="uq_book_obsidian_notes_user_book_path_source"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    path: Mapped[str] = mapped_column(String, nullable=False, index=True)
    source: Mapped[ObsidianVaultNoteSource] = mapped_column(
        String,
        nullable=False,
        default=ObsidianVaultNoteSource.CHARACTER_BIBLE.value,
        server_default=ObsidianVaultNoteSource.CHARACTER_BIBLE.value,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)

    book = relationship("Book", back_populates="obsidian_notes")
    outgoing_links = relationship("NoteLink", foreign_keys="NoteLink.source_note_id", back_populates="source_note", cascade="all, delete-orphan")
    incoming_links = relationship("NoteLink", foreign_keys="NoteLink.target_note_id", back_populates="target_note", cascade="all, delete-orphan")
    backlinks = relationship("NoteBacklink", foreign_keys="NoteBacklink.target_note_id", back_populates="target_note", cascade="all, delete-orphan")
    tags = relationship("NoteTag", back_populates="note", cascade="all, delete-orphan")


class NoteLink(Base):
    __tablename__ = "book_obsidian_note_links"
    __table_args__ = (
        UniqueConstraint("source_note_id", "target_note_id", "link_type", name="uq_book_obsidian_note_links_source_target_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    source_note_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("book_obsidian_notes.id", ondelete="CASCADE"), nullable=False, index=True)
    target_note_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("book_obsidian_notes.id", ondelete="CASCADE"), nullable=False, index=True)
    link_type: Mapped[str] = mapped_column(String, nullable=False, default="reference", server_default="reference", index=True)
    target_label: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    book = relationship("Book", back_populates="obsidian_note_links")
    source_note = relationship("ObsidianVaultNote", foreign_keys=[source_note_id], back_populates="outgoing_links")
    target_note = relationship("ObsidianVaultNote", foreign_keys=[target_note_id], back_populates="incoming_links")


class NoteBacklink(Base):
    __tablename__ = "book_obsidian_note_backlinks"
    __table_args__ = (
        UniqueConstraint("source_note_id", "target_note_id", "link_type", name="uq_book_obsidian_note_backlinks_source_target_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    source_note_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("book_obsidian_notes.id", ondelete="CASCADE"), nullable=False, index=True)
    target_note_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("book_obsidian_notes.id", ondelete="CASCADE"), nullable=False, index=True)
    link_type: Mapped[str] = mapped_column(String, nullable=False, default="reference", server_default="reference", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    book = relationship("Book", back_populates="obsidian_note_backlinks")
    source_note = relationship("ObsidianVaultNote", foreign_keys=[source_note_id])
    target_note = relationship("ObsidianVaultNote", foreign_keys=[target_note_id], back_populates="backlinks")


class NoteTag(Base):
    __tablename__ = "book_obsidian_note_tags"
    __table_args__ = (
        UniqueConstraint("note_id", "tag_name", name="uq_book_obsidian_note_tags_note_tag"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    note_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("book_obsidian_notes.id", ondelete="CASCADE"), nullable=False, index=True)
    tag_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    book = relationship("Book", back_populates="obsidian_note_tags")
    note = relationship("ObsidianVaultNote", back_populates="tags")


class NoteSeriesLink(Base):
    __tablename__ = "book_obsidian_note_series_links"
    __table_args__ = (
        UniqueConstraint("source_note_id", "target_note_id", "link_type", name="uq_book_obsidian_note_series_links_source_target_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    series_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("series.id", ondelete="CASCADE"), nullable=False, index=True)
    source_book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    target_book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    source_note_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("book_obsidian_notes.id", ondelete="CASCADE"), nullable=False, index=True)
    target_note_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("book_obsidian_notes.id", ondelete="CASCADE"), nullable=False, index=True)
    link_type: Mapped[str] = mapped_column(String, nullable=False, default="reference", server_default="reference", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    source_book = relationship("Book", foreign_keys=[source_book_id], back_populates="obsidian_note_series_links")
    target_book = relationship("Book", foreign_keys=[target_book_id])
    source_note = relationship("ObsidianVaultNote", foreign_keys=[source_note_id])
    target_note = relationship("ObsidianVaultNote", foreign_keys=[target_note_id])


class ChapterMedia(Base):
    __tablename__ = "chapter_media"
    __table_args__ = (
        UniqueConstraint("chapter_id", "marker", name="uq_chapter_media_marker"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False, index=True)
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
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    primary_books = relationship("Book", foreign_keys=[Book.primary_series_id], back_populates="primary_series")
    memberships = relationship("SeriesBook", back_populates="series", cascade="all, delete-orphan")


class SeriesBook(Base):
    __tablename__ = "series_books"
    __table_args__ = (
        UniqueConstraint("series_id", "book_id", name="uq_series_books_series_book"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    series_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("series.id", ondelete="CASCADE"), nullable=False, index=True)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    position: Mapped[int | None] = mapped_column(Integer)
    marked_complete: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    series = relationship("Series", back_populates="memberships")
    book = relationship("Book", back_populates="series_memberships")


class Scene(Base):
    __tablename__ = "scenes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="SET NULL"), index=True)
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
    scene_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False, index=True)
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
    book_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("books.id", ondelete="CASCADE"), nullable=False, index=True)
    chapter_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("chapters.id", ondelete="SET NULL"), index=True)
    chapter_number: Mapped[int | None] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    html_body: Mapped[str | None] = mapped_column(Text)
    scene_metadata: Mapped[dict | None] = mapped_column("metadata", JSONB, default=dict)
    path: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, default="unassigned", server_default="unassigned", index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    source: Mapped[str] = mapped_column(String, nullable=False, default="manual", server_default="manual")
    origin_chapter_number: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), index=True)

    book = relationship("Book", back_populates="novel_scenes")
    chapter = relationship("Chapter", back_populates="novel_scenes")
