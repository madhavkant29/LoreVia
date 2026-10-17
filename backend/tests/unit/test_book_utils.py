"""Unit tests for book_utils functions."""

import io
import json
import uuid
from contextlib import nullcontext
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from PIL import Image

from app.models.book import Book, Chapter, ChapterMedia, ManuscriptAnnotation, NovelScene
from app.models.character import Character, CharacterState
from app.models.intelligence import (
    ChapterSummary,
    CharacterRelationship,
    ContinuityScan,
    PlotThread,
    WorldElement,
)
from app.models.user import User
from app.utils.advisor_scan_utils import build_advisor_suggestions_payload
from app.utils.books import manuscript
from app.utils.books import revision_analysis as revision_analysis_module
from app.utils.books import workspace_search as workspace_search_module
from app.utils.books.chapter_titles import (
    build_chapter_title_from_summary,
    chapter_title_is_placeholder,
    normalize_chapter_title,
)
from app.utils.books.character_cards import build_character_card_payload
from app.utils.books.consistency_reports import list_chapter_consistency_reports
from app.utils.books.continuity import (
    _detect_continuity_flags_from_rows,
    _latest_state_before_chapter,
    _map_chapter_consistency_state_history,
)
from app.utils.books.imports import (
    build_import_preview,
    normalize_imported_chapters,
    parse_book_upload_for_ingestion,
    require_extractable_manuscript_text,
    parse_import_upload,
    parse_screenplay_upload,
)
from app.utils.books.manuscript import (
    clean_manuscript_html,
    clean_markdown_asterisks_str,
    deserialize_manuscript_content,
    extract_inline_images_from_manuscript_html,
    load_novel_export_chapters,
    manuscript_html_to_text,
    markdown_to_html,
    serialize_manuscript_content,
    sync_chapter_media_from_images,
)
from app.utils.books.normalization import (
    normalize_chapter_kind,
    resolve_upload_format_and_work_type,
    story_unit_label,
    story_unit_name,
)
from app.utils.books.notes import (
    list_manuscript_annotations,
    save_manuscript_annotation,
)
from app.utils.books.planning import (
    build_emotional_arc_payload,
    build_prewriting_check,
)
from app.utils.books.processing import (
    normalize_public_processing_stage,
    processing_retry_available,
)
from app.utils.books.revision_analysis import (
    _build_knowledge_timeline,
    _build_narration_signature,
    _build_revision_change_summary,
    _describe_narration_shift,
    _genre_match_score,
    _scene_keyword_set,
    _select_genre_checks,
)
from app.utils.books.revision_decisions import (
    _finding_excerpt,
    _priority_revision_findings,
    apply_revision_finding_decision,
)
from app.utils.books.revision_service import (
    build_revision_intelligence_payload,
)
from app.utils.books.scene_metadata import (
    build_scene_chapter_import_text,
    build_workspace_chapter_text_from_scenes,
    chapter_body_needs_scene_workspace_fallback,
    extract_novel_scene_candidates,
    normalize_scene_metadata,
    strip_scene_metadata_from_manuscript_text,
)
from app.utils.books.scene_ordering import normalize_scene_reorder_ids
from app.utils.books.scene_sync import sync_chapter_content_from_novel_scenes
from app.utils.books.serialization import (
    build_blank_cover_image,
    chapter_word_count,
    compute_words_read_for_books,
    ensure_book_cover,
    preload_book_render_context,
)
from app.utils.books.story_health import estimate_readability
from app.utils.books.workspace_search import (
    build_manuscript_workspace_tree,
    search_author_workspace,
    search_author_workspace_page,
)
from app.utils.books.writer_workspace import (
    build_book_processing_payload,
    normalize_writer_workspace,
)


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def all(self):
        return self._value


class _ScalarList:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


def test_normalize_public_processing_stage_maps_internal_values():
    assert normalize_public_processing_stage("processing", "extraction") == "extracting"
    assert normalize_public_processing_stage("processing", "analysis") == "analyzing"
    assert normalize_public_processing_stage("ready", "complete", is_fully_ready=True) == "ready"
    assert normalize_public_processing_stage("failed", "extraction") == "failed"


def test_processing_retry_available_requires_actionable_state():
    assert processing_retry_available("failed", "failed", [], None) is True
    assert (
        processing_retry_available("processing", "extracting", ["retry_extraction"], None) is True
    )
    assert (
        processing_retry_available("processing", "analyzing", ["wait_for_analysis"], None) is False
    )
    assert processing_retry_available("ready", "ready", [], None) is False


class _FakeAnnotationDB:
    def __init__(self, *, execute_values=None, get_values=None):
        self._execute_values = list(execute_values or [])
        self._get_values = list(get_values or [])
        self.added: list[object] = []

    async def execute(self, *_args, **_kwargs):
        return self._execute_values.pop(0)

    async def get(self, *_args, **_kwargs):
        return self._get_values.pop(0) if self._get_values else None

    def add(self, value):
        self.added.append(value)
        if getattr(value, "id", None) is None:
            value.id = uuid.uuid4()
        if getattr(value, "created_at", None) is None:
            value.created_at = datetime.now(UTC)
        if getattr(value, "updated_at", None) is None:
            value.updated_at = datetime.now(UTC)

    async def commit(self):
        return None

    async def refresh(self, _value):
        return None


class _FakeExecuteDB:
    def __init__(self, execute_values=None):
        self._execute_values = list(execute_values or [])
        self.added: list[object] = []
        self.executed: list[object] = []

    async def execute(self, statement):
        self.executed.append(statement)
        return self._execute_values.pop(0) if self._execute_values else _AllResult([])

    @property
    def no_autoflush(self):
        return nullcontext()

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        return None


class _AllResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


class _ScalarsResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _ScalarList(self._rows)


class _RowResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


def test_scene_keyword_set_filters_common_revision_noise_but_keeps_story_terms():
    keywords = _scene_keyword_set(
        "Aide ailleurs apr auteurs said Nora crossed the silver gate with royal blood.",
        character_names={"Nora"},
        thread_terms={"Silver Gate"},
    )

    assert "aide" not in keywords
    assert "ailleurs" not in keywords
    assert "apr" not in keywords
    assert "auteurs" not in keywords
    assert {"nora", "silver gate", "royal", "blood"}.issubset(keywords)


@pytest.mark.asyncio
async def test_revision_analysis_chapter_text_loading_only_swallows_storage_io(monkeypatch):
    chapter = SimpleNamespace(number=3, s3_key="chapters/book/3.json")

    def _storage_missing(_key: str) -> bytes:
        raise OSError("object unavailable")

    monkeypatch.setattr(manuscript, "download_book", _storage_missing)

    assert await manuscript.load_chapter_texts([chapter]) == {3: ""}

    def _unexpected_bug(_key: str) -> bytes:
        raise RuntimeError("download wrapper bug")

    monkeypatch.setattr(manuscript, "download_book", _unexpected_bug)

    with pytest.raises(RuntimeError, match="download wrapper bug"):
        await manuscript.load_chapter_texts([chapter])


def test_build_revision_change_summary_falls_back_when_only_noise_terms_changed():
    summary, focus_terms = _build_revision_change_summary(
        before_text="Nora crossed the silver gate.",
        after_text="Aide ailleurs apr auteurs. Nora crossed the silver gate.",
        unit_label="Chapter 2",
        character_names={"Nora"},
        thread_terms={"Silver Gate"},
        world_terms=set(),
    )

    assert (
        summary
        == "You changed Chapter 2: the scene logic and wording shifted enough to re-check downstream assumptions."
    )
    assert focus_terms == []


def test_normalize_writer_workspace_preserves_reprocess_metadata():
    workspace = normalize_writer_workspace(
        {
            "reprocess": {
                "auto_reprocess_enabled": False,
                "pending_chapters": [3, 1, 3, 0, "bad"],
                "last_manual_chapter_number": 3,
                "last_manual_chapter_started_at": "2026-06-06T00:00:00+00:00",
            }
        }
    )

    assert workspace["reprocess"]["auto_reprocess_enabled"] is False
    assert workspace["reprocess"]["pending_chapters"] == [1, 3]
    assert workspace["reprocess"]["last_manual_chapter_number"] == 3


class TestCleanMarkdownAsterisks:
    """Tests for clean_markdown_asterisks_str function (word counting only)."""

    def test_removes_asterisks(self):
        """Test that asterisks for bold/italic are removed."""
        text = "**bold text** and *italic text*"
        result = clean_markdown_asterisks_str(text)
        assert "**" not in result
        assert "*" not in result
        assert "bold text" in result
        assert "italic text" in result

    def test_preserves_hashes(self):
        """Test that hashes are preserved (this is for word counting only)."""
        text = "# Header 1\n## Header 2"
        result = clean_markdown_asterisks_str(text)
        assert "#" in result

    def test_empty_string(self):
        """Test that empty string returns empty string."""
        assert clean_markdown_asterisks_str("") == ""

    def test_none_input(self):
        """Test that None input returns empty string."""
        assert clean_markdown_asterisks_str(None) == ""


class TestMarkdownToHtml:
    """Tests for markdown_to_html function."""

    def test_headers_conversion(self):
        """Test that headers are converted to HTML h1-h6 tags."""
        text = "# Header 1\n## Header 2\n### Header 3"
        result = markdown_to_html(text)
        assert "<h1>Header 1</h1>" in result or "Header 1" in result
        assert "<h2>Header 2</h2>" in result or "Header 2" in result
        assert "<h3>Header 3</h3>" in result or "Header 3" in result

    def test_bold_conversion(self):
        """Test that bold markdown is converted to strong tags."""
        text = "**bold text**"
        result = markdown_to_html(text)
        assert "<strong>bold text</strong>" in result or "bold text" in result

    def test_italic_conversion(self):
        """Test that italic markdown is converted to em tags."""
        text = "*italic text*"
        result = markdown_to_html(text)
        assert "<em>italic text</em>" in result or "italic text" in result

    def test_paragraphs(self):
        """Test that paragraphs are preserved."""
        text = "First paragraph\n\nSecond paragraph"
        result = markdown_to_html(text)
        assert "First paragraph" in result
        assert "Second paragraph" in result

    def test_empty_string(self):
        """Test that empty string returns empty or minimal HTML."""
        result = markdown_to_html("")
        assert result == "" or "<p></p>" in result

    def test_none_input(self):
        """Test that None input returns empty string."""
        assert markdown_to_html(None) == ""

    def test_complex_markdown(self):
        """Test complex markdown with multiple elements."""
        text = "# Chapter 1\n\n**Bold** and *italic* text.\n\nRegular paragraph."
        result = markdown_to_html(text)
        assert "Chapter 1" in result
        assert "Bold" in result
        assert "italic" in result
        assert "Regular paragraph" in result

    def test_code_blocks(self):
        """Test that code blocks are handled."""
        text = "`inline code`"
        result = markdown_to_html(text)
        assert "inline code" in result

    def test_links(self):
        """Test that markdown links are converted."""
        text = "[link text](https://example.com)"
        result = markdown_to_html(text)
        assert "link text" in result

    def test_import_fallback_handles_headings_lists_paragraphs_and_large_heading(self, monkeypatch):
        """The dependency-free fallback should retain basic manuscript structure."""
        import builtins

        real_import = builtins.__import__

        def import_without_markdown_it(name, *args, **kwargs):
            if name == "markdown_it":
                raise ImportError("markdown-it unavailable")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", import_without_markdown_it)
        result = markdown_to_html(
            "Opening line\ncontinued\n\n# Chapter One\n####### Literal heading\n- First clue\n* Second clue\n\nFinal line"
        )

        assert "<p>Opening linecontinued</p>" in result
        assert "<h1>Chapter One</h1>" in result
        assert "####### Literal heading" in result
        assert "<li>First clue</li>" in result
        assert "<li>Second clue</li>" in result
        assert "<p>Final line</p>" in result


class TestManuscriptHtmlImages:
    """Tests for preserving inline chapter images in manuscript HTML."""

    def test_clean_manuscript_html_preserves_data_uri_images(self):
        """Data URI images should survive sanitization with safe attributes."""
        html = '<p>Intro</p><p><img src="data:image/png;base64,AAA" alt="Scene art" onerror="alert(1)"></p>'

        result = clean_manuscript_html(html)

        assert "<img" in result
        assert 'src="data:image/png;base64,AAA"' in result
        assert 'alt="Scene art"' in result
        assert "onerror" not in result

    def test_manuscript_html_to_text_ignores_images_but_keeps_copy(self):
        """Text extraction should ignore images without dropping surrounding prose."""
        html = (
            '<p>Intro</p><p><img src="data:image/png;base64,AAA" alt="Scene art"></p><p>Outro</p>'
        )

        result = manuscript_html_to_text(html)

        assert result == "Intro\n\nOutro"

    def test_serialize_and_deserialize_preserve_image_html(self):
        """Serializing chapter HTML should keep the image markup in stored payloads."""
        html = '<p>Intro</p><p><img src="data:image/png;base64,AAA" alt="Scene art"></p>'

        serialized = serialize_manuscript_content("Intro", html)
        payload = deserialize_manuscript_content(serialized)

        assert payload["format"] == "rich_text_v1"
        assert payload["html"] and "<img" in payload["html"]
        assert 'src="data:image/png;base64,AAA"' in payload["html"]
        assert payload["text"] == "Intro"

    def test_extract_inline_images_replaces_data_uri_with_marker(self):
        """Data URI images should become chapter media payloads and text markers."""
        html = (
            '<p>Intro</p><p><img src="data:image/png;base64,QUJD" alt="Scene art"></p><p>Outro</p>'
        )

        cleaned_html, images, retained = extract_inline_images_from_manuscript_html(html)

        assert retained == set()
        assert len(images) == 1
        assert images[0]["bytes"] == b"ABC"
        assert images[0]["content_type"] == "image/png"
        assert images[0]["marker"].startswith("[[IMAGE:")
        assert cleaned_html and images[0]["marker"] in cleaned_html
        assert "data:image/png" not in cleaned_html

    def test_extract_inline_images_retains_existing_marker_image(self):
        """Previously persisted editor images should keep their marker on save."""
        marker = "[[IMAGE:abc123]]"
        html = f'<p>Intro</p><p><img src="/api/v1/reader/media/1" alt="{marker}"></p>'

        cleaned_html, images, retained = extract_inline_images_from_manuscript_html(html)

        assert images == []
        assert retained == {marker}
        assert cleaned_html and marker in cleaned_html


@pytest.mark.asyncio
async def test_sync_chapter_media_from_images_copies_stored_media_references(monkeypatch):
    uploaded: list[tuple[str, bytes, str | None]] = []

    def _upload_binary(key: str, raw: bytes, content_type: str | None = None) -> str:
        uploaded.append((key, raw, content_type))
        return key

    monkeypatch.setattr("app.utils.books.manuscript.upload_binary", _upload_binary)
    db = _FakeExecuteDB()
    book = SimpleNamespace(id=uuid.uuid4())
    chapter = SimpleNamespace(id=uuid.uuid4(), number=3)

    await sync_chapter_media_from_images(
        db,
        book=book,
        chapter=chapter,
        images=[
            {
                "marker": "[[IMAGE:kept]]",
                "storage_key": "chapter-media/book/old-map.png",
                "content_type": "image/png",
                "caption": "Old map",
                "asset_type": "image",
            },
            {
                "marker": "[[IMAGE:fresh]]",
                "bytes": b"fresh-bytes",
                "content_type": "image/jpeg",
                "filename": "fresh.jpg",
            },
        ],
    )

    media = [item for item in db.added if isinstance(item, ChapterMedia)]
    assert [item.marker for item in media] == ["[[IMAGE:kept]]", "[[IMAGE:fresh]]"]
    assert media[0].storage_key == "chapter-media/book/old-map.png"
    assert media[0].caption == "Old map"
    assert media[1].storage_key.endswith("/1-fresh.jpg")
    assert uploaded == [(media[1].storage_key, b"fresh-bytes", "image/jpeg")]


@pytest.mark.asyncio
async def test_load_novel_export_chapters_includes_media_when_requested(monkeypatch):
    book = SimpleNamespace(id=uuid.uuid4())
    chapter_id = uuid.uuid4()
    media = SimpleNamespace(
        chapter_id=chapter_id,
        asset_type="image",
        content_type="image/png",
        storage_key="chapter-media/book/map.png",
        caption="Chapter map",
        marker="[[IMAGE:map]]",
    )
    db = _FakeExecuteDB(
        execute_values=[
            _AllResult([(chapter_id, 1, "Opening", "chapters/book/1.json")]),
            _ScalarsResult([media]),
        ]
    )

    def _download_book(key: str) -> bytes:
        if key == "chapters/book/1.json":
            return serialize_manuscript_content(
                "Intro\n\n[[IMAGE:map]]\n\nOutro",
                "<p>Intro</p><p>[[IMAGE:map]]</p><p>Outro</p>",
            ).encode("utf-8")
        return b"image-bytes"

    monkeypatch.setattr("app.utils.books.manuscript.download_book", _download_book)

    chapters = await load_novel_export_chapters(
        db,
        book=book,
        collaborator=None,
        include_images=True,
    )

    assert chapters == [
        {
            "number": 1,
            "title": "Opening",
            "text": "Intro\n\n[[IMAGE:map]]\n\nOutro",
            "media": [
                {
                    "raw": b"image-bytes",
                    "content_type": "image/png",
                    "caption": "Chapter map",
                    "marker": "[[IMAGE:map]]",
                }
            ],
        }
    ]


@pytest.mark.asyncio
async def test_load_novel_export_chapters_only_swallows_storage_io(monkeypatch):
    book = SimpleNamespace(id=uuid.uuid4())
    chapter_id = uuid.uuid4()

    db = _FakeExecuteDB(
        execute_values=[
            _AllResult([(chapter_id, 1, "Opening", "chapters/book/1.json")]),
        ]
    )

    def _storage_missing(_key: str) -> bytes:
        raise OSError("object unavailable")

    monkeypatch.setattr("app.utils.books.manuscript.download_book", _storage_missing)

    chapters = await load_novel_export_chapters(
        db,
        book=book,
        collaborator=None,
        include_images=False,
    )

    assert chapters[0]["text"] == ""

    db = _FakeExecuteDB(
        execute_values=[
            _AllResult([(chapter_id, 1, "Opening", "chapters/book/1.json")]),
        ]
    )
    monkeypatch.setattr("app.utils.books.manuscript.download_book", lambda _key: b"{}")

    def _deserialize_bug(_raw: bytes) -> dict:
        raise RuntimeError("deserializer bug")

    monkeypatch.setattr(
        "app.utils.books.manuscript.deserialize_manuscript_content",
        _deserialize_bug,
    )

    with pytest.raises(RuntimeError, match="deserializer bug"):
        await load_novel_export_chapters(
            db,
            book=book,
            collaborator=None,
            include_images=False,
        )


@pytest.mark.asyncio
async def test_sync_chapter_content_from_novel_scenes_only_swallows_storage_io(monkeypatch):
    book = SimpleNamespace(id=uuid.uuid4(), title="Atlas")
    chapter = SimpleNamespace(
        id=uuid.uuid4(),
        s3_key="chapters/book/1.json",
        word_count=0,
        content_version=1,
        title="Opening",
    )

    def _upload_text(key: str, content: str) -> str:
        assert key == "chapters/book/1.json"
        assert isinstance(content, str)
        return key

    monkeypatch.setattr("app.utils.books.scene_sync.upload_text", _upload_text)

    def _storage_missing(_key: str) -> bytes:
        raise OSError("object unavailable")

    monkeypatch.setattr("app.utils.books.scene_sync.download_book", _storage_missing)
    db = _FakeExecuteDB(execute_values=[_ScalarResult(chapter), _ScalarsResult([])])

    synced = await sync_chapter_content_from_novel_scenes(
        db,
        book=book,
        chapter_number=1,
    )

    assert synced["chapter"] is chapter
    assert chapter.s3_key == "chapters/book/1.json"
    assert db.executed[0]._for_update_arg is not None

    monkeypatch.setattr("app.utils.books.scene_sync.download_book", lambda _key: b"{}")

    def _deserialize_bug(_raw: bytes) -> dict:
        raise RuntimeError("deserializer bug")

    monkeypatch.setattr(
        "app.utils.books.scene_sync.manuscript.deserialize_manuscript_content",
        _deserialize_bug,
    )
    db = _FakeExecuteDB(execute_values=[_ScalarResult(chapter), _ScalarsResult([])])

    with pytest.raises(RuntimeError, match="deserializer bug"):
        await sync_chapter_content_from_novel_scenes(
            db,
            book=book,
            chapter_number=1,
        )


def test_build_blank_cover_image_renders_title_and_author_placeholder():
    raw, content_type = build_blank_cover_image("The Silent Archive", "Mira Vale")

    assert content_type == "image/png"
    image = Image.open(io.BytesIO(raw))
    assert image.size == (1200, 1800)
    assert image.format == "PNG"


@pytest.mark.asyncio
async def test_compute_words_read_for_books_uses_preloaded_word_counts_without_content_fallback():
    book_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id)
    progress = SimpleNamespace(
        book_id=book_id, chapters_read=[1, 2], current_chapter=3, scroll_pct=0.5
    )
    db = _FakeAnnotationDB(
        execute_values=[
            _RowResult(
                [
                    (book_id, 1, 1000),
                    (book_id, 2, 1200),
                    (book_id, 3, None),
                ]
            )
        ]
    )

    totals = await compute_words_read_for_books(db, books=[book], progress_rows=[progress])

    assert totals[book_id] == 2200


@pytest.mark.asyncio
async def test_preload_book_render_context_does_not_generate_missing_covers(monkeypatch):
    calls: list[uuid.UUID] = []

    async def _generate_cover(_db, book):
        calls.append(book.id)

    monkeypatch.setattr("app.utils.books.serialization.ensure_book_cover", _generate_cover)

    book = Book(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="No Cover Yet",
        author="A. Writer",
        format="txt",
        work_type="novel",
        s3_key="books/user/story.txt",
        cover_s3_key=None,
        status="ready",
        is_public=False,
    )
    db = _FakeExecuteDB(execute_values=[_ScalarsResult([]), _RowResult([])])

    context = await preload_book_render_context(db, books=[book], user_id=book.user_id)

    assert calls == []
    assert context.cover_url_by_book_id[book.id] is None


@pytest.mark.asyncio
async def test_ensure_book_cover_generates_blank_cover_when_missing(monkeypatch):
    uploaded: dict[str, object] = {}

    class _FakeDB:
        async def flush(self):
            return None

    def _upload_binary(key: str, raw: bytes, content_type: str) -> str:
        uploaded["key"] = key
        uploaded["raw"] = raw
        uploaded["content_type"] = content_type
        return key

    monkeypatch.setattr("app.utils.books.serialization.upload_binary", _upload_binary)

    book = Book(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="No Cover Yet",
        author="A. Writer",
        format="txt",
        work_type="novel",
        s3_key="books/user/story.txt",
        cover_s3_key=None,
        status="pending",
        is_public=False,
    )

    await ensure_book_cover(_FakeDB(), book)

    assert book.cover_s3_key == uploaded["key"]
    assert uploaded["content_type"] == "image/png"
    image = Image.open(io.BytesIO(uploaded["raw"]))
    assert image.size == (1200, 1800)


@pytest.mark.asyncio
async def test_ensure_book_cover_only_swallows_expected_storage_failures(monkeypatch):
    class _FakeDB:
        async def flush(self):
            return None

    book = Book(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="No Cover Yet",
        author="A. Writer",
        format="txt",
        work_type="novel",
        s3_key="books/user/story.txt",
        cover_s3_key=None,
        status="pending",
        is_public=False,
    )

    def _storage_upload_failure(*_args, **_kwargs):
        raise OSError("storage unavailable")

    monkeypatch.setattr("app.utils.books.serialization.upload_binary", _storage_upload_failure)

    await ensure_book_cover(_FakeDB(), book)

    assert book.cover_s3_key is None

    def _unexpected_upload_bug(*_args, **_kwargs):
        raise RuntimeError("upload wrapper bug")

    monkeypatch.setattr("app.utils.books.serialization.upload_binary", _unexpected_upload_bug)

    with pytest.raises(RuntimeError, match="upload wrapper bug"):
        await ensure_book_cover(_FakeDB(), book)


@pytest.mark.asyncio
async def test_chapter_word_count_only_swallows_storage_io(monkeypatch):
    chapter = SimpleNamespace(word_count=None, s3_key="chapters/book/1.json")

    class _ScalarChapter:
        def scalar(self):
            return chapter

    class _FakeDB:
        async def execute(self, *_args, **_kwargs):
            return _ScalarChapter()

    def _storage_missing(_key: str) -> bytes:
        raise OSError("object unavailable")

    monkeypatch.setattr("app.utils.books.serialization.download_book", _storage_missing)

    assert await chapter_word_count(_FakeDB(), uuid.uuid4(), 1) == 0

    monkeypatch.setattr("app.utils.books.serialization.download_book", lambda _key: b"{}")

    def _deserialize_bug(_raw: bytes) -> dict:
        raise RuntimeError("deserializer bug")

    monkeypatch.setattr(
        "app.utils.books.serialization.manuscript.deserialize_manuscript_content",
        _deserialize_bug,
    )

    with pytest.raises(RuntimeError, match="deserializer bug"):
        await chapter_word_count(_FakeDB(), uuid.uuid4(), 1)


def test_normalize_writer_workspace_preserves_defaults_and_sanitizes_cards():
    workspace = normalize_writer_workspace(
        {
            "word_count_goals": {"chapter_target": 3200, "book_target": -5, "session_target": 900},
            "goal_calendar": [
                {
                    "title": " Draft chapter 4 ",
                    "due_date": "2026-05-08",
                    "quota_value": 2000,
                    "quota_unit": " words ",
                    "completed": True,
                },
                {"title": " ", "due_date": "not-a-date"},
            ],
            "corkboard_cards": [
                {"title": " Opening turn ", "lane": "drafting", "chapter_number": 3}
            ],
            "publishing": {"active_preset": "kdp_paperback", "trim_size": "6x9"},
            "processing": {
                "status": " processing ",
                "stage": "chapter_complete",
                "progress_pct": 33.3,
                "chapters_completed": 1,
                "chapters_total": 3,
                "eta_seconds": 120,
                "queue_wait_ms": 17,
                "last_chapter_number": 2,
                "last_chapter_title": " Chapter 2 ",
                "started_at": "2026-05-01T00:00:00+00:00",
                "updated_at": "2026-05-01T00:05:00+00:00",
            },
        }
    )

    assert workspace["word_count_goals"]["chapter_target"] == 3200
    assert workspace["word_count_goals"]["book_target"] is None
    assert workspace["word_count_goals"]["session_target"] == 900
    assert workspace["goal_calendar"][0]["title"] == "Draft chapter 4"
    assert workspace["goal_calendar"][0]["due_date"] == "2026-05-08"
    assert workspace["goal_calendar"][0]["quota_value"] == 2000
    assert workspace["goal_calendar"][0]["quota_unit"] == "words"
    assert workspace["goal_calendar"][0]["completed"] is True
    assert len(workspace["goal_calendar"]) == 1
    assert workspace["corkboard_cards"][0]["title"] == "Opening turn"
    assert workspace["corkboard_cards"][0]["lane"] == "drafting"
    assert workspace["publishing"]["active_preset"] == "kdp_paperback"
    assert workspace["editor_preferences"]["font_family"] == "Times New Roman"
    assert workspace["reading_themes"]["active_theme"] == "light"
    assert workspace["typewriter_mode"]["enabled"] is False
    assert workspace["manuscript_layout"]["page_size"] == "letter"
    assert workspace["revision_board"]["items"] == []
    assert workspace["processing"]["status"] == "processing"
    assert workspace["processing"]["last_chapter_title"] == "Chapter 2"
    assert (
        build_book_processing_payload(type("DummyBook", (), {"writer_workspace": workspace})())[
            "chapters_total"
        ]
        == 3
    )
    assert len(workspace["templates"]) >= 3


def test_build_book_processing_payload_normalizes_postgres_text_timestamps():
    payload = build_book_processing_payload(
        type(
            "DummyBook",
            (),
            {
                "writer_workspace": {
                    "processing": {
                        "status": "ready",
                        "stage": "complete",
                        "updated_at": "2026-06-06 05:11:51.272085+00",
                        "pipeline": {
                            "extraction": {
                                "status": "succeeded",
                                "updated_at": "2026-06-06 05:11:51.272085+00",
                            },
                            "analysis": {
                                "status": "succeeded",
                                "updated_at": "2026-06-06 05:11:51.272085+00",
                            },
                        },
                    }
                }
            },
        )()
    )

    assert payload["updated_at"] == "2026-06-06T05:11:51.272085Z"
    assert payload["pipeline"]["extraction"]["updated_at"] == "2026-06-06T05:11:51.272085Z"
    assert payload["pipeline"]["analysis"]["updated_at"] == "2026-06-06T05:11:51.272085Z"


def test_build_book_processing_payload_nulls_invalid_timestamps():
    payload = build_book_processing_payload(
        type(
            "DummyBook",
            (),
            {
                "writer_workspace": {
                    "processing": {
                        "status": "processing",
                        "stage": "analysis",
                        "updated_at": "not a timestamp",
                        "pipeline": {
                            "extraction": {
                                "status": "running",
                                "updated_at": "also not a timestamp",
                            },
                        },
                    }
                }
            },
        )()
    )

    assert payload["updated_at"] is None
    assert payload["pipeline"]["extraction"]["updated_at"] is None


def test_estimate_readability_returns_basic_metrics():
    metrics = estimate_readability("This is a short sentence. This is another one.")

    assert metrics["words"] == 9
    assert metrics["sentences"] == 2
    assert metrics["paragraphs"] == 1


@pytest.mark.asyncio
async def test_manuscript_annotations_round_trip_and_hide_private_entries():
    author = User(
        id=uuid.uuid4(),
        email=f"author-{uuid.uuid4().hex[:8]}@example.com",
        username="author",
        password_hash="hash",
    )
    reviewer = User(
        id=uuid.uuid4(),
        email=f"reviewer-{uuid.uuid4().hex[:8]}@example.com",
        username="reviewer",
        password_hash="hash",
    )
    book = Book(
        id=uuid.uuid4(),
        user_id=author.id,
        title="Atlas",
        format="txt",
        work_type="novel",
        s3_key="atlas.txt",
        status="ready",
        mode="author",
    )

    db = _FakeAnnotationDB(
        execute_values=[_ScalarResult("The Ember Gate"), _ScalarResult("The Ember Gate")]
    )
    shared = await save_manuscript_annotation(
        db,
        book=book,
        actor=author,
        annotation_id=None,
        chapter_number=2,
        category="continuity",
        status="open",
        visibility="shared",
        quote="The bell cracked at dawn.",
        comment="Keep the bell description aligned with chapter 1.",
        anchor_context_before="",
        anchor_context_after="",
        start_offset=12,
        end_offset=36,
    )
    private = await save_manuscript_annotation(
        db,
        book=book,
        actor=author,
        annotation_id=None,
        chapter_number=2,
        category="general",
        status="open",
        visibility="private",
        quote="Nora looked away.",
        comment="Private reminder to revisit the emotional turn.",
        anchor_context_before="",
        anchor_context_after="",
        start_offset=40,
        end_offset=57,
    )

    assert shared["visibility"] == "shared"
    assert private["visibility"] == "private"

    created_shared = db.added[0]
    created_private = db.added[1]
    list_db = _FakeAnnotationDB(
        execute_values=[
            _ScalarResult(
                [
                    (created_shared, "The Ember Gate", "author", author.email),
                    (created_private, "The Ember Gate", "author", author.email),
                ]
            )
        ]
    )
    author_visible = await list_manuscript_annotations(list_db, book=book, actor=author)
    reviewer_db = _FakeAnnotationDB(
        execute_values=[
            _ScalarResult(
                [
                    (created_shared, "The Ember Gate", "author", author.email),
                    (created_private, "The Ember Gate", "author", author.email),
                ]
            )
        ]
    )
    reviewer_visible = await list_manuscript_annotations(
        reviewer_db,
        book=book,
        actor=reviewer,
        collaborator=SimpleNamespace(
            role="commenter",
            permissions={"can_comment": True},
            scope={
                "chapter_start": 1,
                "chapter_end": 3,
                "character_bible": False,
                "continuity_report": False,
                "reader_confusion_report": False,
            },
        ),
    )

    assert len(author_visible) == 2
    assert [item["visibility"] for item in reviewer_visible] == ["shared"]


@pytest.mark.asyncio
async def test_save_manuscript_annotation_rejects_reversed_offsets():
    author = User(
        id=uuid.uuid4(),
        email=f"author-{uuid.uuid4().hex[:8]}@example.com",
        username="author2",
        password_hash="hash",
    )
    book = Book(
        id=uuid.uuid4(),
        user_id=author.id,
        title="Atlas",
        format="txt",
        work_type="novel",
        s3_key="atlas.txt",
        status="ready",
        mode="author",
    )
    db = _FakeAnnotationDB()

    with pytest.raises(HTTPException) as exc:
        await save_manuscript_annotation(
            db,
            book=book,
            actor=author,
            annotation_id=None,
            chapter_number=1,
            category="general",
            status="open",
            visibility="shared",
            quote="A short quote",
            comment="Invalid offsets",
            anchor_context_before="",
            anchor_context_after="",
            start_offset=20,
            end_offset=10,
        )

    assert exc.value.status_code == 400


def test_extract_novel_scene_candidates_splits_hash_breaks_and_assigns_paths():
    text = "Opening beat.\n\n#\n\nForest encounter.\n\n***\n\nAftermath.\n\n# Hidden cache\n\nReveal in the dark."

    scenes = extract_novel_scene_candidates(text=text, chapter_number=4, source="extracted")

    assert len(scenes) == 4
    assert scenes[0]["title"] == "Opening beat."
    assert scenes[0]["status"] == "assigned"
    assert scenes[0]["path"].startswith("scenes/chapter-04/")
    assert scenes[1]["title"] == "Forest encounter."
    assert scenes[2]["title"] == "Aftermath."
    assert scenes[3]["title"] == "Hidden cache"


def test_scene_import_text_can_include_or_strip_metadata():
    scene = {
        "title": "Rooftop Encounter",
        "description": "Recover the transmitter.",
        "body": (
            "POV: Arlen\n"
            "Location: Eastern Tower\n"
            "Time: Night\n\n"
            "Characters:\n"
            "- Arlen\n"
            "- Nyra\n\n"
            "The wind howled across the rooftop."
        ),
    }

    with_metadata = build_scene_chapter_import_text(scene, scene_number=1, include_metadata=True)
    without_metadata = build_scene_chapter_import_text(
        scene, scene_number=1, include_metadata=False
    )

    assert with_metadata.startswith("## Scene 1 - Rooftop Encounter")
    assert "POV: Arlen" in with_metadata
    assert "Characters:\n- Arlen\n- Nyra" in with_metadata
    assert with_metadata.endswith("The wind howled across the rooftop.")
    assert without_metadata == "The wind howled across the rooftop."


def test_strip_scene_metadata_from_manuscript_text_keeps_plain_scene_breaks():
    text = (
        "Opening paragraph.\n\n"
        "***\n\n"
        "## Scene 2 - Council Chamber\n\n"
        "POV: Nyra\n"
        "Location: Inner Citadel\n\n"
        "Characters:\n"
        "- Nyra\n\n"
        "---\n\n"
        "Nyra entered the chamber."
    )

    stripped = strip_scene_metadata_from_manuscript_text(text)

    assert "## Scene" not in stripped
    assert "POV:" not in stripped
    assert "Characters:" not in stripped
    assert stripped == "Opening paragraph.\n\n***\n\nNyra entered the chamber."


def test_build_workspace_chapter_text_from_scenes_joins_clean_scene_bodies():
    scenes = [
        {
            "title": "Arrival",
            "body": "POV: Mira\nLocation: Docks\n\nThe boat scraped against the pier.",
        },
        {
            "title": "Confrontation",
            "body": "## Confrontation\n\nConflict: Old debts\n\nThe captain blocked her path.",
        },
    ]

    compiled = build_workspace_chapter_text_from_scenes(scenes)

    assert compiled.startswith("## Scene 1 - Arrival")
    assert "POV: Mira" in compiled
    assert "Location: Docks" in compiled
    assert "The boat scraped against the pier." in compiled
    assert "\n\n***\n\n## Scene 2 - Confrontation" in compiled
    assert "Conflict:\n- Old debts" in compiled
    assert compiled.endswith("The captain blocked her path.")


def test_normalize_scene_reorder_ids_accepts_unique_uuid_strings():
    first_id = str(uuid.uuid4())
    second_id = str(uuid.uuid4())

    assert normalize_scene_reorder_ids([first_id, second_id]) == [
        uuid.UUID(first_id),
        uuid.UUID(second_id),
    ]


def test_normalize_scene_reorder_ids_rejects_duplicates_and_bad_values():
    scene_id = str(uuid.uuid4())

    with pytest.raises(HTTPException):
        normalize_scene_reorder_ids([scene_id, scene_id])

    with pytest.raises(HTTPException):
        normalize_scene_reorder_ids(["not-a-uuid"])


def test_chapter_body_needs_scene_workspace_fallback_detects_empty_and_placeholder_content():
    assert (
        chapter_body_needs_scene_workspace_fallback("", chapter_number=2, chapter_title="Chapter 2")
        is True
    )
    assert (
        chapter_body_needs_scene_workspace_fallback(
            "2.", chapter_number=2, chapter_title="Chapter 2"
        )
        is True
    )
    assert (
        chapter_body_needs_scene_workspace_fallback("II", chapter_number=2, chapter_title="II")
        is True
    )
    assert (
        chapter_body_needs_scene_workspace_fallback(
            "A real opening line begins here.", chapter_number=2, chapter_title="Chapter 2"
        )
        is False
    )


def test_build_emotional_arc_payload_uses_growth_events():
    character = Character(
        book_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        name="Mira",
        role="mc",
        first_chapter=2,
        arc_summary="Learns to trust her crew.",
        growth_events=[
            {
                "chapter_number": 2,
                "event_title": "Breaks rank",
                "impact_score": 7,
                "growth_direction": "negative",
            },
            {
                "chapter_number": 8,
                "event_title": "Chooses the crew",
                "impact_score": 9,
                "growth_direction": "positive",
            },
        ],
    )

    payload = build_emotional_arc_payload([character])

    assert payload["focus_character_count"] == 1
    assert payload["characters"][0]["character_name"] == "Mira"
    assert len(payload["characters"][0]["points"]) == 2
    assert payload["latest_turning_points"][0].startswith("Mira:")


def test_story_unit_helpers_switch_to_scene_language_for_screenplays():
    screenplay_book = Book(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="Pilot",
        format="fountain",
        work_type="screenplay",
        s3_key="books/pilot.fountain",
        status="ready",
    )

    assert story_unit_name("novel") == "Chapter"
    assert story_unit_name(screenplay_book, plural=True, lowercase=True) == "scenes"
    assert story_unit_label(screenplay_book, 3) == "Scene 3"
    assert story_unit_label(screenplay_book, 3, short=True) == "Sc. 3"


def test_latest_state_before_chapter_returns_closest_prior_snapshot():
    earlier = CharacterState(character_id=uuid.uuid4(), at_chapter=2, trait_snapshot={})
    later = CharacterState(character_id=earlier.character_id, at_chapter=5, trait_snapshot={})

    chapter_numbers, states = _map_chapter_consistency_state_history([earlier, later])

    assert _latest_state_before_chapter(chapter_numbers, states, 5) is earlier
    assert _latest_state_before_chapter(chapter_numbers, states, 6) is later
    assert _latest_state_before_chapter(chapter_numbers, states, 2) is None


def test_detect_continuity_flags_from_rows_uses_prefetched_prior_states():
    character_id = uuid.uuid4()
    previous = CharacterState(
        character_id=character_id,
        at_chapter=2,
        trait_snapshot={"hair": {"value": "black"}},
    )
    current = CharacterState(
        character_id=character_id,
        at_chapter=4,
        trait_snapshot={"hair": {"value": "silver"}},
    )

    flags = _detect_continuity_flags_from_rows(
        work_type="novel",
        chapter_number=4,
        rows=[(current, "Mira")],
        prior_states_by_character={
            character_id: _map_chapter_consistency_state_history([previous]),
        },
    )

    assert flags == ["Mira: hair description changed from 'black' to 'silver' since chapter 2."]


def test_detect_continuity_flags_from_rows_ignores_characters_without_prior_state():
    current = CharacterState(
        character_id=uuid.uuid4(),
        at_chapter=4,
        trait_snapshot={"hair": {"value": "silver"}},
    )

    flags = _detect_continuity_flags_from_rows(
        work_type="novel",
        chapter_number=4,
        rows=[(current, "Mira")],
        prior_states_by_character={},
    )

    assert flags == []


def test_normalize_chapter_title_accepts_one_to_four_words():
    assert normalize_chapter_title("  Ember Gate  ") == "Ember Gate"
    assert normalize_chapter_title("Ash") == "Ash"
    assert normalize_chapter_title("The Last Ember Gate") == "The Last Ember Gate"
    assert normalize_chapter_title("Winter's End") == "Winter's End"
    assert normalize_chapter_title("Winter’s End") == "Winter’s End"


def test_normalize_chapter_title_rejects_more_than_four_words():
    with pytest.raises(HTTPException) as exc_info:
        normalize_chapter_title("The Last Ember Gate Opens")

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Chapter title must be between 1 and 4 words."


def test_build_chapter_title_from_summary_prefers_key_event_titles_and_limits_words():
    derived = build_chapter_title_from_summary(
        "Mira reaches the shattered gate and realizes the city is already under watch.",
        key_events=[{"event_title": "The Shattered Gate Opens Wide"}],
    )

    assert derived == "Shattered Gate Opens Wide"


def test_chapter_title_is_placeholder_detects_generic_labels():
    assert chapter_title_is_placeholder("Chapter 7", chapter_number=7) is True
    assert chapter_title_is_placeholder("Part IV") is True
    assert chapter_title_is_placeholder("Ember Gate", chapter_number=7) is False


def test_build_knowledge_timeline_keeps_all_chapters_in_matrix():
    timeline = _build_knowledge_timeline(
        knowledge_matrix=[
            {
                "fact": "The king was poisoned",
                "entries": [
                    {
                        "character_name": "Mira",
                        "chapter_learned": 2,
                        "source": "Overheard guard",
                    },
                    {
                        "character_name": "Lina",
                        "chapter_learned": None,
                        "source": "No earlier evidence surfaced yet",
                    },
                ],
                "warning": "LoreVia has no clear evidence yet that Lina learned this.",
            }
        ],
        chapter_numbers=[1, 2, 3, 4, 5, 6, 7],
    )

    assert len(timeline) == 1
    assert [cell["chapter_number"] for cell in timeline[0]["rows"][0]["cells"]] == [
        1,
        2,
        3,
        4,
        5,
        6,
        7,
    ]
    assert timeline[0]["rows"][0]["cells"][1]["state"] == "learned"
    assert timeline[0]["rows"][0]["cells"][-1]["state"] == "known"
    assert all(cell["state"] == "unknown" for cell in timeline[0]["rows"][1]["cells"])


def test_resolve_upload_format_and_work_type_infers_and_preserves_technical_format():
    assert resolve_upload_format_and_work_type("pilot.fountain") == ("fountain", "screenplay")
    assert resolve_upload_format_and_work_type("episode.txt", "screenplay") == ("txt", "screenplay")
    assert resolve_upload_format_and_work_type("novel.pdf") == ("pdf", "novel")


def test_normalize_chapter_kind_accepts_supported_front_and_back_matter():
    assert normalize_chapter_kind("Preface") == "preface"
    assert normalize_chapter_kind("table of contents") == "toc"
    assert normalize_chapter_kind("acknowledgements") == "acknowledgments"
    assert normalize_chapter_kind("unknown-heading") == "chapter"
    assert normalize_chapter_kind(None) == "chapter"


def test_select_genre_checks_includes_ranked_findings():
    checks = _select_genre_checks(
        "Fantasy",
        [
            {
                "id": "finding-1",
                "category": "confusion",
                "title": "Lore term overload",
                "description": "Several world terms arrive in one scene.",
                "severity": "medium",
            },
            {
                "id": "finding-2",
                "category": "voice",
                "title": "Modern diction drift",
                "description": "The setting voice sounds too modern.",
                "severity": "medium",
            },
        ],
    )

    assert len(checks) == 1
    assert checks[0]["label"] == "Fantasy"
    assert [item["id"] for item in checks[0]["findings"]] == ["finding-1", "finding-2"]


def test_normalize_imported_chapters_preserves_section_type_as_chapter_kind():
    normalized = normalize_imported_chapters(
        [{"number": 1, "title": "Preface", "text": "Before the story.", "section_type": "preface"}],
        chapter_number=None,
        start_number=1,
        replace_existing=False,
        chunk_long_documents=False,
        preserve_exact_structure=False,
    )

    assert normalized[0]["chapter_kind"] == "preface"


def test_normalize_imported_chapters_keeps_long_source_chapter_intact_when_structure_is_preserved():
    long_text = "\n\n".join(
        [
            " ".join(["opening"] * 1800),
            " ".join(["middle"] * 1800),
        ]
    )

    normalized = normalize_imported_chapters(
        [{"number": 1, "title": "Chapter I", "text": long_text}],
        chapter_number=None,
        start_number=1,
        replace_existing=False,
        chunk_long_documents=True,
        preserve_exact_structure=True,
    )

    assert len(normalized) == 1
    assert normalized[0]["number"] == 1
    assert normalized[0]["title"] == "Chapter I"
    assert "(Part 1)" not in normalized[0]["title"]
    assert normalized[0]["text"] == long_text
    assert normalized[0]["chapter_kind"] == "chapter"


def test_normalize_imported_chapters_uses_chapter_kind_for_split_parts():
    long_text = "\n\n".join(
        [
            " ".join(["front"] * 1800),
            " ".join(["matter"] * 1800),
        ]
    )

    normalized = normalize_imported_chapters(
        [{"number": 1, "title": "Preface", "text": long_text, "section_type": "preface"}],
        chapter_number=None,
        start_number=1,
        replace_existing=False,
        chunk_long_documents=True,
        preserve_exact_structure=False,
    )

    assert len(normalized) == 2
    assert [chapter["chapter_kind"] for chapter in normalized] == ["chapter", "chapter"]


def test_normalize_imported_chapters_keeps_images_with_matching_markers_when_split():
    text = "\n\n".join(
        [
            "Opening section. [[IMAGE:cover]]",
            " ".join(["middle"] * 3600),
            "Closing section. [[IMAGE:map]]",
        ]
    )

    normalized = normalize_imported_chapters(
        [
            {
                "number": 1,
                "title": "Chapter I",
                "text": text,
                "images": [
                    {"marker": "[[IMAGE:cover]]", "bytes": b"cover-bytes"},
                    {"marker": "[[IMAGE:map]]", "bytes": b"map-bytes"},
                ],
            }
        ],
        chapter_number=None,
        start_number=1,
        replace_existing=False,
        chunk_long_documents=True,
        preserve_exact_structure=False,
    )

    assert len(normalized) == 2
    assert [image["marker"] for image in normalized[0]["images"]] == ["[[IMAGE:cover]]"]
    assert [image["marker"] for image in normalized[1]["images"]] == ["[[IMAGE:map]]"]


def test_normalize_writer_workspace_includes_front_matter_defaults():
    workspace = normalize_writer_workspace({})

    front_matter = workspace["manuscript_front_matter"]

    assert workspace["goal_calendar"] == []
    assert workspace["revision_board"]["items"] == []
    assert workspace["editor_preferences"]["font_size"] == 12
    assert workspace["reading_themes"]["allow_dark_mode"] is True
    assert workspace["typewriter_mode"]["center_offset_px"] == 160
    assert workspace["manuscript_layout"]["different_first_page"] is True
    assert workspace["structure_tree"] == []
    assert front_matter["author_name"] == ""
    assert front_matter["title"] == ""
    assert front_matter["include_dedication"] is False
    assert front_matter["include_acknowledgments"] is False


def test_normalize_writer_workspace_sanitizes_revision_board_items():
    workspace = normalize_writer_workspace(
        {
            "revision_board": {
                "items": [
                    {
                        "item_id": " impact-1 ",
                        "status": "fixed",
                        "assigned_version_id": " version-1 ",
                    },
                    {"item_id": "impact-1", "status": "ignored"},
                    {"item_id": " ", "status": "pending"},
                ],
                "last_generated_at": " 2026-05-11T10:00:00Z ",
            },
            "revision_recent_edits": [
                {
                    "id": " edit-1 ",
                    "kind": "scene",
                    "chapter_number": 2,
                    "scene_title": " Gate Approach ",
                    "before_text": "Before",
                    "after_text": "After",
                    "updated_at": " 2026-05-13T10:00:00Z ",
                }
            ],
        }
    )

    assert workspace["revision_board"]["last_generated_at"] == "2026-05-11T10:00:00Z"
    assert workspace["revision_board"]["items"] == [
        {
            "item_id": "impact-1",
            "status": "fixed",
            "assigned_version_id": "version-1",
            "task_id": None,
            "updated_at": None,
            "decision": None,
            "action": None,
            "reason": None,
            "source_content_versions": {},
            "finding_snapshot": None,
        }
    ]
    assert workspace["revision_recent_edits"][0]["kind"] == "scene"
    assert workspace["revision_recent_edits"][0]["scene_title"] == "Gate Approach"


def test_priority_revision_findings_prefers_severity_and_category_diversity():
    findings = [
        {
            "id": "low",
            "category": "impact",
            "severity": "low",
            "chapter_ref": 1,
            "status": "pending",
        },
        {
            "id": "high-2",
            "category": "impact",
            "severity": "high",
            "chapter_ref": 5,
            "status": "pending",
        },
        {
            "id": "medium",
            "category": "voice",
            "severity": "medium",
            "chapter_ref": 3,
            "status": "pending",
        },
        {
            "id": "high-1",
            "category": "confusion",
            "severity": "high",
            "chapter_ref": 2,
            "status": "pending",
        },
    ]

    selected = _priority_revision_findings(findings)

    assert [item["id"] for item in selected] == ["high-1", "high-2", "medium"]


def test_finding_excerpt_returns_only_real_source_text_and_match_strength():
    excerpt, matched = _finding_excerpt(
        "Mira entered the harbor. The silver key was missing from her coat. She called for Rowan.",
        {"title": "Missing silver key", "description": "The silver key disappears."},
    )

    assert "silver key was missing" in excerpt
    assert matched is True
    assert _finding_excerpt("", {"title": "Anything"}) == ("", False)

    clipped, clipped_matched = _finding_excerpt(
        f"{'Opening context. ' * 12}The silver key was missing. {'Closing context. ' * 12}",
        {"title": "Missing silver key", "description": "The silver key disappears."},
        max_chars=80,
    )
    assert clipped.startswith("...")
    assert clipped.endswith("...")
    assert clipped_matched is True


def test_apply_revision_finding_decision_persists_snapshot_and_activation():
    book = Book(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="Atlas",
        format="txt",
        work_type="novel",
        s3_key="atlas.txt",
        status="ready",
        mode="author",
        writer_workspace={},
    )
    finding = {
        "id": "rev-1",
        "title": "Missing key",
        "evidence": [
            {"chapter_ref": 2, "source_content_version": 4, "excerpt": "The key was gone."}
        ],
    }

    apply_revision_finding_decision(
        book,
        finding=finding,
        decision="accepted",
        action="added_to_revision_plan",
        reason=None,
    )

    workspace = normalize_writer_workspace(book.writer_workspace)
    state = workspace["revision_board"]["items"][0]
    assert state["status"] == "task_created"
    assert state["decision"] == "accepted"
    assert state["source_content_versions"] == {"2": 4}
    assert state["finding_snapshot"]["id"] == "rev-1"
    assert workspace["activation"]["completion_action"] == "added_to_revision_plan"


def test_normalize_scene_metadata_preserves_structured_fields_and_cleans_lists():
    metadata = normalize_scene_metadata(
        {
            "pov": " Mira ",
            "timeline": " Day 3 ",
            "location": " Harbor ",
            "tags": [" reveal ", "dagger", "dagger"],
            "mood": [" tense ", "", "foreboding"],
            "status_note": " revised ",
            "anchors": ["^dock", " ^dock ", ""],
            "bookmarks": ["scene-1"],
        },
        description="A turning-point scene.",
    )

    assert metadata["pov"] == "Mira"
    assert metadata["timeline"] == "Day 3"
    assert metadata["location"] == "Harbor"
    assert metadata["tags"] == ["reveal", "dagger"]
    assert metadata["mood"] == ["tense", "foreboding"]
    assert metadata["status_note"] == "revised"
    assert metadata["anchors"] == ["^dock"]
    assert metadata["bookmarks"] == ["scene-1"]
    assert metadata["summary"] == "A turning-point scene."


@pytest.mark.asyncio
async def test_search_author_workspace_uses_bounded_persisted_search_results():
    book = Book(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="Atlas",
        format="txt",
        work_type="novel",
        s3_key="atlas.txt",
        status="ready",
        mode="author",
    )

    scene_id = uuid.uuid4()
    note_id = uuid.uuid4()
    chapter_id = uuid.uuid4()

    class _Rows:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

    class _FakeSearchDB:
        def __init__(self):
            self.statements = []

        async def execute(self, *_args, **_kwargs):
            self.statements.append(_args[0])
            rows = [
                [
                    (
                        scene_id,
                        "Gate Approach",
                        "Mira heads to the harbor gate.",
                        "Mira reaches the silver gate with the dagger hidden in her sleeve.",
                        4,
                        0.7,
                    )
                ],
                [
                    (
                        note_id,
                        "Plot Threads/Silver Gate.md",
                        "# Silver Gate\n\nMira hides the dagger near the gate.",
                        0.5,
                    )
                ],
                [
                    (
                        chapter_id,
                        4,
                        "The Gate",
                        "The silver gate loomed over the harbor.",
                        0.3,
                    )
                ],
            ]
            return _Rows(rows[len(self.statements) - 1])

    db = _FakeSearchDB()
    results = await search_author_workspace(
        db,
        book=book,
        user_id=book.user_id,
        query="silver gate",
        scopes=["manuscript", "scenes", "notes"],
    )

    assert [item["scope"] for item in results] == ["scenes", "notes", "manuscript"]
    assert results[0]["scene_id"] == str(scene_id)
    assert results[1]["note_path"] == "Plot Threads/Silver Gate.md"
    assert results[2]["chapter_number"] == 4
    assert len(db.statements) == 3
    assert all("LIMIT" in str(statement) for statement in db.statements)


@pytest.mark.asyncio
async def test_search_author_workspace_does_not_download_manuscript_objects():
    book = Book(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="Atlas",
        format="txt",
        work_type="novel",
        s3_key="atlas.txt",
        status="ready",
        mode="author",
    )

    class _Rows:
        def all(self):
            return []

    class _FakeSearchDB:
        async def execute(self, *_args, **_kwargs):
            return _Rows()

    assert (
        await search_author_workspace(
            _FakeSearchDB(),
            book=book,
            user_id=book.user_id,
            query="silver gate",
            scopes=["manuscript"],
        )
        == []
    )
    assert "download_book" not in workspace_search_module.__dict__
    assert "deserialize_manuscript_content" not in workspace_search_module.__dict__


@pytest.mark.asyncio
async def test_workspace_search_page_uses_stable_cursor_and_reports_partial_index():
    book = Book(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="Atlas",
        format="txt",
        work_type="novel",
        s3_key="atlas.txt",
        status="processing",
        mode="author",
    )
    first_chapter_id = uuid.uuid4()
    second_chapter_id = uuid.uuid4()

    class _Rows:
        def __init__(self, rows):
            self._rows = rows

        def all(self):
            return self._rows

    class _FakeSearchDB:
        def __init__(self):
            self.statements = []
            self.scalar_statements = []
            self.scalar_values = [2, 1, 2, 1]

        async def execute(self, statement):
            self.statements.append(statement)
            return _Rows(
                [
                    (first_chapter_id, 1, "One", "The silver gate opens.", 0.8),
                    (second_chapter_id, 2, "Two", "The silver gate closes.", 0.6),
                ]
            )

        async def scalar(self, statement):
            self.scalar_statements.append(statement)
            return self.scalar_values.pop(0)

    db = _FakeSearchDB()
    first_page = await search_author_workspace_page(
        db,
        book=book,
        user_id=book.user_id,
        query="silver gate",
        scopes=["manuscript"],
        limit=1,
    )
    second_page = await search_author_workspace_page(
        db,
        book=book,
        user_id=book.user_id,
        query="silver gate",
        scopes=["manuscript"],
        limit=1,
        cursor=first_page["next_cursor"],
    )

    assert first_page["items"][0]["chapter_number"] == 1
    assert first_page["has_more"] is True
    assert first_page["index_status"] == "building"
    assert second_page["items"][0]["chapter_number"] == 2
    assert second_page["has_more"] is False
    assert len(db.scalar_statements) == 4


@pytest.mark.asyncio
async def test_search_author_workspace_rejects_nested_regex_repetition():
    with pytest.raises(HTTPException) as exc_info:
        await search_author_workspace(
            None,
            book=SimpleNamespace(id=uuid.uuid4()),
            user_id=uuid.uuid4(),
            query="(a+)+$",
            scopes=["manuscript"],
            regex=True,
        )

    assert exc_info.value.status_code == 400


def test_build_narration_signature_detects_first_person_anchor():
    signature = _build_narration_signature(
        "I ran through the gate. My hands shook. I tasted blood on my lip."
    )

    assert signature["pov_mode"] == "first-person"
    assert signature["first_person_hits"] >= 3


def test_describe_narration_shift_flags_mode_change():
    previous = _build_narration_signature(
        "She crossed the gate and kept her head down. Her breath stayed measured."
    )
    current = _build_narration_signature(
        "I crossed the gate and kept my head down. My breath stayed measured."
    )

    assert (
        _describe_narration_shift(previous, current)
        == "Narration shifts from third-person anchoring into first-person anchoring."
    )


@pytest.mark.asyncio
async def test_parse_screenplay_upload_builds_scene_chapters_and_dialogue_counts():
    raw = b"""INT. WRITERS ROOM - DAY

MAYA (V.O.)
(whispering)
This is the opening line.

EXT. STREET - NIGHT

MAYA
We have to go now.
"""

    payload = await parse_screenplay_upload("episode.fountain", raw)

    assert payload["title"] == "episode"
    assert len(payload["chapters"]) == 2
    assert len(payload["scenes"]) == 2
    assert payload["stats"]["total_scenes"] == 2
    assert payload["stats"]["total_dialogue_lines"] == 2
    assert payload["chapters"][0]["scene_heading"] == "INT. WRITERS ROOM - DAY"
    assert payload["chapters"][0]["dialogue_count"] == 1
    assert "Maya (V.O.)" in payload["chapters"][0]["text"]
    assert "This is the opening line." in payload["chapters"][0]["text"]


@pytest.mark.asyncio
async def test_parse_book_upload_for_ingestion_returns_pdf_parser_diagnostics(monkeypatch):
    chapters = [{"number": 1, "title": "Chapter 1", "text": "Opening text."}]
    diagnostics = {"source": "pdf", "chapter_count": 1, "fallback_strategy": None}
    parse_calls: list[str] = []

    def _fake_parse_pdf(raw, *, language=None):
        parse_calls.append("structured")
        return chapters, diagnostics

    monkeypatch.setattr(
        "app.parsers.pdf_parser.parse_pdf_structure",
        _fake_parse_pdf,
    )

    payload = await parse_book_upload_for_ingestion(
        format_name="pdf",
        work_type="novel",
        raw=b"%PDF-1.4 mock",
        preserve_chapter_numbers=False,
        preserve_source_chapters=False,
    )

    assert [(chapter["title"], chapter["text"]) for chapter in payload["chapters"]] == [
        ("Chapter 1", "Opening text.")
    ]
    assert payload["structure_plan"]["parser_version"]
    assert payload["parser_diagnostics"] == diagnostics
    assert parse_calls == ["structured"]


@pytest.mark.asyncio
async def test_parse_book_upload_for_ingestion_disables_large_split_for_exact_source_preservation(
    monkeypatch,
):
    parse_calls: list[str] = []

    def _fake_parse_pdf(raw, *, language=None):
        parse_calls.append("structured")
        return (
            [{"number": 1, "title": "Chapter 7", "text": "Original full chapter"}],
            {"source": "pdf"},
        )

    monkeypatch.setattr("app.parsers.pdf_parser.parse_pdf_structure", _fake_parse_pdf)

    payload = await parse_book_upload_for_ingestion(
        format_name="pdf",
        work_type="novel",
        raw=b"%PDF-1.4 mock",
        preserve_chapter_numbers=False,
        preserve_source_chapters=True,
    )

    assert parse_calls == ["structured"]
    assert payload["chapters"][0]["title"] == "Chapter 7"


def test_require_extractable_manuscript_text_rejects_image_only_documents():
    with pytest.raises(HTTPException, match="No extractable text") as error:
        require_extractable_manuscript_text([{"text": "[[IMAGE:cover]]"}], "pdf")
    assert error.value.status_code == 400
    require_extractable_manuscript_text([{"text": "[[IMAGE:cover]]\nMara opens the gate."}], "pdf")


@pytest.mark.asyncio
async def test_pdf_ingestion_rejects_a_parser_result_without_manuscript_text(monkeypatch):
    monkeypatch.setattr(
        "app.parsers.pdf_parser.parse_pdf_structure",
        lambda *_args, **_kwargs: ([{"title": "Full Text", "text": ""}], {"source": "pdf"}),
    )
    with pytest.raises(HTTPException, match="No extractable text") as error:
        await parse_book_upload_for_ingestion(
            format_name="pdf",
            work_type="novel",
            raw=b"%PDF-1.4 mock",
            preserve_chapter_numbers=False,
            preserve_source_chapters=True,
        )
    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_chapter_consistency_reports_load_full_context(db):
    user = User(
        email=f"consistency-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"consistency{uuid.uuid4().hex[:8]}",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="The Context Book",
        format="txt",
        s3_key="books/context.txt",
        status="ready",
        total_chapters=2,
        mode="author",
        work_type="novel",
    )
    db.add(book)
    await db.flush()
    chapters = [
        Chapter(book_id=book.id, number=1, title="Arrival", s3_key="chapters/context/1.txt"),
        Chapter(book_id=book.id, number=2, title="Reckoning", s3_key="chapters/context/2.txt"),
    ]
    db.add_all(chapters)
    await db.flush()
    mara = Character(
        book_id=book.id,
        name="Mara",
        normalized_name="mara",
        role="protagonist",
        first_chapter=1,
        last_seen_chapter=2,
        mention_count=4,
    )
    jon = Character(
        book_id=book.id,
        name="Jon",
        normalized_name="jon",
        role="supporting",
        first_chapter=2,
        last_seen_chapter=2,
        mention_count=2,
    )
    db.add_all([mara, jon])
    await db.flush()
    db.add_all(
        [
            ChapterSummary(
                chapter_id=chapters[1].id, mode="short", content="Mara confronts Jon at the gate."
            ),
            ChapterSummary(
                chapter_id=chapters[1].id,
                mode="editorial_note",
                content=json.dumps([{"issue": "The reconciliation is abrupt.", "evidence": "Mara confronts Jon.", "suggestion": "Show what changes Mara's mind."}]),
            ),
            CharacterRelationship(
                book_id=book.id,
                character_a_id=mara.id,
                character_b_id=jon.id,
                rel_type="uneasy_allies",
                description="They agree to cooperate.",
                from_chapter=2,
            ),
            PlotThread(
                book_id=book.id,
                title="The sealed gate",
                status="resolved",
                introduced_at=1,
                resolved_at=2,
                importance=8,
                character_ids=[str(mara.id)],
            ),
            CharacterState(
                character_id=mara.id,
                at_chapter=1,
                trait_snapshot={"location": "harbor", "eyes": "blue"},
            ),
            CharacterState(
                character_id=mara.id,
                at_chapter=2,
                trait_snapshot={"location": "citadel", "eyes": "green"},
            ),
            WorldElement(
                book_id=book.id,
                source_scope="story",
                element_type="location",
                name="Northreach",
                description="A frozen capital.",
                usage_count=4,
            ),
            NovelScene(
                book_id=book.id,
                chapter_id=chapters[1].id,
                chapter_number=2,
                title="Gate confrontation",
                body="Mara confronts Jon.",
                path="scenes/chapter-02/gate-confrontation.md",
                status="assigned",
                sort_order=1,
            ),
            NovelScene(
                book_id=book.id,
                chapter_number=None,
                title="Unused fragment",
                body="A possible later scene.",
                path="scenes/unassigned/unused-fragment.md",
                status="unassigned",
                sort_order=1,
            ),
            ContinuityScan(
                book_id=book.id,
                user_id=user.id,
                scope="full_book",
                status="ready",
                continuity_status="clean",
                detector_version="continuity-rules-v2",
                chapter_versions={"1": 1, "2": 1},
                coverage={"chapters_analyzed": 2},
                duration_ms=420,
                completed_at=datetime(2026, 7, 24, 9, 0, tzinfo=UTC),
            ),
        ]
    )
    await db.commit()

    reports = await list_chapter_consistency_reports(db, book, limit=12)

    assert [report.chapter_number for report in reports] == [2, 1]
    latest = reports[0]
    assert latest.chapter_title == "Reckoning"
    assert latest.new_characters[0].name == "Jon"
    assert len(latest.relationship_changes) == 1
    assert (
        latest.relationship_changes[0] == "Mara and Jon: uneasy allies - They agree to cooperate."
    )
    assert latest.plot_threads_resolved == ["The sealed gate"]
    assert "Mara confronts Jon" in latest.summary
    assert latest.editorial_concerns is not None
    assert latest.editorial_concerns[0].issue == "The reconciliation is abrupt."
    assert reports[1].editorial_concerns is None

    prewriting = await build_prewriting_check(db, book, upcoming_chapter=3)
    assert prewriting["upcoming_chapter"] == 3
    assert prewriting["active_characters"][0]["name"] in {"Mara", "Jon"}
    assert prewriting["recent_events"] == []

    tree = await build_manuscript_workspace_tree(db, book=book, user_id=user.id)
    assert [chapter["chapter_number"] for chapter in tree["chapters"]] == [1, 2]
    assert tree["scene_groups"][0]["label"] == "Unassigned Scenes"
    assert tree["scene_groups"][2]["scenes"][0]["title"] == "Gate confrontation"
    assert "body" not in tree["scene_groups"][2]["scenes"][0]
    assert tree["scene_breadcrumbs"]

    full_tree = await build_manuscript_workspace_tree(
        db,
        book=book,
        user_id=user.id,
        include_scene_bodies=True,
    )
    assert full_tree["scene_groups"][2]["scenes"][0]["body"] == "Mara confronts Jon."

    book.total_chapters = 50
    revision = await build_revision_intelligence_payload(db, book)
    assert revision["summary"]["active_item_count"] >= 0
    assert revision["revision_plan"]
    assert isinstance(revision["knowledge_timeline"], list)
    assert revision["continuity_status"] == "clean"
    assert revision["continuity_scan_id"] is not None
    assert revision["continuity_completed_at"] == datetime(2026, 7, 24, 9, 0, tzinfo=UTC)
    assert revision["continuity_duration_ms"] == 420

    advisor_scan = await build_advisor_suggestions_payload(
        db=db,
        book=book,
        user_id=user.id,
        skip_llm=True,
    )
    assert advisor_scan["suggestions"]
    assert "characters" in advisor_scan["meta"]["scan_basis"]
    assert any(item["type"] == "trait_contradiction" for item in advisor_scan["suggestions"])


@pytest.mark.asyncio
async def test_character_card_payload_includes_relationships_threads_and_watchlist(db):
    user = User(
        email=f"card-{uuid.uuid4().hex[:8]}@lorevia.app",
        username=f"card{uuid.uuid4().hex[:8]}",
        password_hash="hash",
    )
    db.add(user)
    await db.flush()
    book = Book(
        user_id=user.id,
        title="Long Road",
        format="txt",
        s3_key="books/long-road.txt",
        status="ready",
        total_chapters=40,
        mode="author",
        work_type="novel",
    )
    db.add(book)
    await db.flush()
    hero = Character(
        book_id=book.id,
        name="Ari Vale",
        normalized_name="ari vale",
        aliases=["Ari"],
        role="protagonist",
        first_chapter=1,
        last_seen_chapter=10,
        mention_count=12,
        personality_tags=["wary"],
        motivations=["protect the city"],
        fears=["failure"],
    )
    ally = Character(
        book_id=book.id,
        name="Mina",
        normalized_name="mina",
        role="supporting",
        first_chapter=2,
        last_seen_chapter=12,
        mention_count=5,
    )
    db.add_all([hero, ally])
    await db.flush()
    db.add_all(
        [
            CharacterRelationship(
                book_id=book.id,
                character_a_id=hero.id,
                character_b_id=ally.id,
                rel_type="trusted_ally",
                sentiment=0.8,
                description="Mina guards Ari's secret.",
                from_chapter=3,
            ),
            PlotThread(
                book_id=book.id,
                title="Ari's missing map",
                status="developing",
                introduced_at=4,
                importance=9,
                character_ids=["Ari"],
            ),
            CharacterState(character_id=hero.id, at_chapter=3, trait_snapshot={"mood": "hopeful"}),
        ]
    )
    await db.commit()

    payload = await build_character_card_payload(db, book, hero)

    assert payload["name"] == "Ari Vale"
    assert payload["relationships"][0]["name"] == "Mina"
    assert payload["plot_threads"][0]["title"] == "Ari's missing map"
    assert any("has not appeared for 30 chapters" in item for item in payload["continuity_watch"])
    assert any("unresolved threads" in item for item in payload["continuity_watch"])
    assert payload["filename_base"] == "Long-Road-Ari-Vale"


@pytest.mark.asyncio
async def test_parse_import_upload_covers_text_markdown_pdf_epub_and_unsupported(monkeypatch):
    markdown = await parse_import_upload("draft.md", b"# Chapter One\n\nOpening.", False)
    assert markdown[0]["title"] == "draft"
    assert "<h1>Chapter One</h1>" in markdown[0]["html"]

    split_text = await parse_import_upload(
        "draft.txt",
        b"Chapter One\nOpening.\n\nChapter Two\nEnding.",
        True,
    )
    assert split_text

    monkeypatch.setattr(
        "app.parsers.pdf_parser.parse_pdf",
        lambda _raw, **_kwargs: [
            {"number": 1, "title": "One", "text": "First"},
            {"number": 2, "title": "Two", "text": "Second"},
        ],
    )
    monkeypatch.setattr(
        "app.parsers.epub_parser.parse_epub",
        lambda _raw, **_kwargs: [{"number": 1, "title": "EPUB", "text": "Book text"}],
    )
    merged_pdf = await parse_import_upload("book.pdf", b"pdf", False)
    split_pdf = await parse_import_upload("book.pdf", b"pdf", True)
    merged_epub = await parse_import_upload("book.epub", b"epub", False)
    assert merged_pdf[0]["text"] == "First\n\nSecond"
    assert len(split_pdf) == 2
    assert merged_epub[0]["text"] == "Book text"

    with pytest.raises(HTTPException, match="Unsupported manuscript import"):
        await parse_import_upload("book.xyz", b"unknown", False)


@pytest.mark.asyncio
async def test_parse_import_upload_legacy_doc_only_maps_expected_parse_failures(monkeypatch):
    from docx.opc.exceptions import PackageNotFoundError

    def _expected_doc_parse_failure(*_args, **_kwargs):
        raise PackageNotFoundError("legacy doc")

    monkeypatch.setattr("docx.Document", _expected_doc_parse_failure)

    with pytest.raises(HTTPException, match="Legacy \\.doc files"):
        await parse_import_upload("legacy.doc", b"not-a-docx", False)

    def _unexpected_doc_bug(*_args, **_kwargs):
        raise RuntimeError("doc parser bug")

    monkeypatch.setattr("docx.Document", _unexpected_doc_bug)

    with pytest.raises(RuntimeError, match="doc parser bug"):
        await parse_import_upload("legacy.doc", b"not-a-docx", False)


def test_build_import_preview_covers_text_screenplay_and_invalid_format(monkeypatch):
    monkeypatch.setattr(
        "app.utils.language_utils.detect_language",
        lambda *_args, **_kwargs: {"detected": "en", "confidence": 0.99},
    )
    text_preview = build_import_preview(
        format_name="txt",
        work_type="novel",
        raw=b"Chapter One\nOpening.\n\nChapter Two\nEnding.",
    )
    assert text_preview["detected_language"] == "en"
    assert text_preview["chapter_count"] >= 1

    screenplay = build_import_preview(
        format_name="fountain",
        work_type="screenplay",
        raw=b"INT. ROOM - DAY\n\nMARA\nWe begin.",
    )
    assert screenplay["chapter_count"] == 1

    with pytest.raises(ValueError, match="Unsupported format"):
        build_import_preview(format_name="xyz", work_type="novel", raw=b"text", language="en")


@pytest.mark.parametrize(
    ("genre", "item"),
    [
        ("epic fantasy", {"category": "confusion", "title": "Magic kingdom lore conflict"}),
        ("science fiction", {"category": "impact", "title": "Technology system rule"}),
        ("romance", {"category": "voice", "title": "Relationship chemistry payoff"}),
        ("mystery thriller", {"category": "impact", "title": "Clue timeline reveal"}),
        ("horror", {"category": "scene", "title": "Ominous creature threat"}),
        ("young adult", {"category": "voice", "title": "Coming-of-age peer conflict"}),
    ],
)
def test_genre_match_score_covers_genre_specific_revision_signals(genre, item):
    assert _genre_match_score(genre, item) > 0
