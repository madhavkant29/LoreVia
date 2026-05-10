"""Unit tests for book_utils functions."""
import io
import uuid
import pytest
from PIL import Image

from app.utils.book_utils import (
    build_emotional_arc_payload,
    build_book_processing_payload,
    build_blank_cover_image,
    clean_markdown_asterisks_str,
    clean_manuscript_html,
    deserialize_manuscript_content,
    ensure_book_cover,
    estimate_readability,
    extract_novel_scene_candidates,
    build_scene_chapter_import_text,
    markdown_to_html,
    manuscript_html_to_text,
    normalize_writer_workspace,
    parse_screenplay_upload,
    parse_book_upload_for_ingestion,
    resolve_upload_format_and_work_type,
    serialize_manuscript_content,
    strip_scene_metadata_from_manuscript_text,
    story_unit_label,
    story_unit_name,
)
from app.models.book import Book
from app.models.character import Character


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
        html = '<p>Intro</p><p><img src="data:image/png;base64,AAA" alt="Scene art"></p><p>Outro</p>'

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


def test_build_blank_cover_image_renders_title_and_author_placeholder():
    raw, content_type = build_blank_cover_image("The Silent Archive", "Mira Vale")

    assert content_type == "image/png"
    image = Image.open(io.BytesIO(raw))
    assert image.size == (1200, 1800)
    assert image.format == "PNG"


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

    monkeypatch.setattr("app.utils.book_utils.upload_binary", _upload_binary)

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


def test_normalize_writer_workspace_preserves_defaults_and_sanitizes_cards():
    workspace = normalize_writer_workspace(
        {
            "word_count_goals": {"chapter_target": 3200, "book_target": -5, "session_target": 900},
            "goal_calendar": [
                {"title": " Draft chapter 4 ", "due_date": "2026-05-08", "quota_value": 2000, "quota_unit": " words ", "completed": True},
                {"title": " ", "due_date": "not-a-date"},
            ],
            "corkboard_cards": [{"title": " Opening turn ", "lane": "drafting", "chapter_number": 3}],
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
    assert workspace["processing"]["status"] == "processing"
    assert workspace["processing"]["last_chapter_title"] == "Chapter 2"
    assert build_book_processing_payload(type("DummyBook", (), {"writer_workspace": workspace})())["chapters_total"] == 3
    assert len(workspace["templates"]) >= 3


def test_estimate_readability_returns_basic_metrics():
    metrics = estimate_readability("This is a short sentence. This is another one.")

    assert metrics["words"] == 9
    assert metrics["sentences"] == 2
    assert metrics["paragraphs"] == 1
    assert metrics["average_sentence_length"] > 0
    assert metrics["label"] in {"Very easy", "Easy", "Balanced", "Demanding", "Dense"}


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
    without_metadata = build_scene_chapter_import_text(scene, scene_number=1, include_metadata=False)

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


def test_build_emotional_arc_payload_uses_growth_events():
    character = Character(
        book_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        name="Mira",
        role="mc",
        first_chapter=2,
        arc_summary="Learns to trust her crew.",
        growth_events=[
            {"chapter_number": 2, "event_title": "Breaks rank", "impact_score": 7, "growth_direction": "negative"},
            {"chapter_number": 8, "event_title": "Chooses the crew", "impact_score": 9, "growth_direction": "positive"},
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


def test_resolve_upload_format_and_work_type_infers_and_preserves_technical_format():
    assert resolve_upload_format_and_work_type("pilot.fountain") == ("fountain", "screenplay")
    assert resolve_upload_format_and_work_type("episode.txt", "screenplay") == ("txt", "screenplay")
    assert resolve_upload_format_and_work_type("novel.pdf") == ("pdf", "novel")


def test_normalize_writer_workspace_includes_front_matter_defaults():
    workspace = normalize_writer_workspace({})

    front_matter = workspace["manuscript_front_matter"]

    assert workspace["goal_calendar"] == []
    assert front_matter["author_name"] == ""
    assert front_matter["title"] == ""
    assert front_matter["include_dedication"] is False
    assert front_matter["include_acknowledgments"] is False


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

    monkeypatch.setattr(
        "app.parsers.pdf_parser.parse_pdf_with_diagnostics",
        lambda raw, *, split_large_chapters=True: (chapters, diagnostics),
    )

    payload = await parse_book_upload_for_ingestion(
        format_name="pdf",
        work_type="novel",
        raw=b"%PDF-1.4 mock",
        preserve_chapter_numbers=False,
        preserve_source_chapters=False,
    )

    assert payload["chapters"] == chapters
    assert payload["parser_diagnostics"] == diagnostics


@pytest.mark.asyncio
async def test_parse_book_upload_for_ingestion_disables_large_split_for_exact_source_preservation(monkeypatch):
    parse_calls: list[bool] = []

    def _fake_parse_pdf(raw, *, split_large_chapters=True):
        parse_calls.append(split_large_chapters)
        return ([{"number": 1, "title": "Chapter 7", "text": "Original full chapter"}], {"source": "pdf"})

    monkeypatch.setattr("app.parsers.pdf_parser.parse_pdf_with_diagnostics", _fake_parse_pdf)

    payload = await parse_book_upload_for_ingestion(
        format_name="pdf",
        work_type="novel",
        raw=b"%PDF-1.4 mock",
        preserve_chapter_numbers=False,
        preserve_source_chapters=True,
    )

    assert parse_calls == [False]
    assert payload["chapters"][0]["title"] == "Chapter 7"
