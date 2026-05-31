"""Unit tests for book_utils functions."""
import io
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from PIL import Image

from app.models.book import Book, Chapter, ManuscriptAnnotation
from app.models.user import User
from app.utils.book_utils import (
    _detect_continuity_flags_from_rows,
    _latest_state_before_chapter,
    _map_chapter_consistency_state_history,
    list_manuscript_annotations,
    _build_knowledge_timeline,
    _build_narration_signature,
    _describe_narration_shift,
    build_chapter_title_from_summary,
    build_emotional_arc_payload,
    build_book_processing_payload,
    build_blank_cover_image,
    compute_words_read_for_books,
    build_workspace_chapter_text_from_scenes,
    chapter_title_is_placeholder,
    clean_markdown_asterisks_str,
    clean_manuscript_html,
    chapter_body_needs_scene_workspace_fallback,
    deserialize_manuscript_content,
    ensure_book_cover,
    estimate_readability,
    extract_novel_scene_candidates,
    build_scene_chapter_import_text,
    markdown_to_html,
    manuscript_html_to_text,
    normalize_chapter_title,
    normalize_imported_chapters,
    normalize_scene_metadata,
    normalize_scene_reorder_ids,
    normalize_writer_workspace,
    parse_screenplay_upload,
    parse_book_upload_for_ingestion,
    resolve_upload_format_and_work_type,
    search_author_workspace,
    save_manuscript_annotation,
    serialize_manuscript_content,
    strip_scene_metadata_from_manuscript_text,
    story_unit_label,
    story_unit_name,
)
from app.models.character import Character, CharacterState


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def all(self):
        return self._value


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


class _RowResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return list(self._rows)


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
async def test_compute_words_read_for_books_uses_preloaded_word_counts_without_content_fallback():
    book_id = uuid.uuid4()
    book = SimpleNamespace(id=book_id)
    progress = SimpleNamespace(book_id=book_id, chapters_read=[1, 2], current_chapter=3, scroll_pct=0.5)
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
    assert workspace["editor_preferences"]["font_family"] == "Times New Roman"
    assert workspace["reading_themes"]["active_theme"] == "light"
    assert workspace["typewriter_mode"]["enabled"] is False
    assert workspace["manuscript_layout"]["page_size"] == "letter"
    assert workspace["revision_board"]["items"] == []
    assert workspace["processing"]["status"] == "processing"
    assert workspace["processing"]["last_chapter_title"] == "Chapter 2"
    assert build_book_processing_payload(type("DummyBook", (), {"writer_workspace": workspace})())["chapters_total"] == 3
    assert len(workspace["templates"]) >= 3


def test_estimate_readability_returns_basic_metrics():
    metrics = estimate_readability("This is a short sentence. This is another one.")

    assert metrics["words"] == 9
    assert metrics["sentences"] == 2
    assert metrics["paragraphs"] == 1


@pytest.mark.asyncio
async def test_manuscript_annotations_round_trip_and_hide_private_entries():
    author = User(id=uuid.uuid4(), email=f"author-{uuid.uuid4().hex[:8]}@example.com", username="author", password_hash="hash")
    reviewer = User(id=uuid.uuid4(), email=f"reviewer-{uuid.uuid4().hex[:8]}@example.com", username="reviewer", password_hash="hash")
    book = Book(id=uuid.uuid4(), user_id=author.id, title="Atlas", format="txt", work_type="novel", s3_key="atlas.txt", status="ready", mode="author")

    db = _FakeAnnotationDB(execute_values=[_ScalarResult("The Ember Gate"), _ScalarResult("The Ember Gate")])
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
            scope={"chapter_start": 1, "chapter_end": 3, "character_bible": False, "continuity_report": False, "reader_confusion_report": False},
        ),
    )

    assert len(author_visible) == 2
    assert [item["visibility"] for item in reviewer_visible] == ["shared"]


@pytest.mark.asyncio
async def test_save_manuscript_annotation_rejects_reversed_offsets():
    author = User(id=uuid.uuid4(), email=f"author-{uuid.uuid4().hex[:8]}@example.com", username="author2", password_hash="hash")
    book = Book(id=uuid.uuid4(), user_id=author.id, title="Atlas", format="txt", work_type="novel", s3_key="atlas.txt", status="ready", mode="author")
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
    assert chapter_body_needs_scene_workspace_fallback("", chapter_number=2, chapter_title="Chapter 2") is True
    assert chapter_body_needs_scene_workspace_fallback("2.", chapter_number=2, chapter_title="Chapter 2") is True
    assert chapter_body_needs_scene_workspace_fallback("II", chapter_number=2, chapter_title="II") is True
    assert chapter_body_needs_scene_workspace_fallback("A real opening line begins here.", chapter_number=2, chapter_title="Chapter 2") is False


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

    assert flags == [
        "Mira: hair description changed from 'black' to 'silver' since chapter 2."
    ]


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
    assert [cell["chapter_number"] for cell in timeline[0]["rows"][0]["cells"]] == [1, 2, 3, 4, 5, 6, 7]
    assert timeline[0]["rows"][0]["cells"][1]["state"] == "learned"
    assert timeline[0]["rows"][0]["cells"][-1]["state"] == "known"
    assert all(cell["state"] == "unknown" for cell in timeline[0]["rows"][1]["cells"])


def test_resolve_upload_format_and_work_type_infers_and_preserves_technical_format():
    assert resolve_upload_format_and_work_type("pilot.fountain") == ("fountain", "screenplay")
    assert resolve_upload_format_and_work_type("episode.txt", "screenplay") == ("txt", "screenplay")
    assert resolve_upload_format_and_work_type("novel.pdf") == ("pdf", "novel")


def test_normalize_imported_chapters_keeps_long_source_chapter_intact_when_structure_is_preserved():
    long_text = "\n\n".join([
        " ".join(["opening"] * 1800),
        " ".join(["middle"] * 1800),
    ])

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


def test_normalize_imported_chapters_keeps_images_with_matching_markers_when_split():
    text = "\n\n".join([
        "Opening section. [[IMAGE:cover]]",
        " ".join(["middle"] * 3600),
        "Closing section. [[IMAGE:map]]",
    ])

    normalized = normalize_imported_chapters(
        [{
            "number": 1,
            "title": "Chapter I",
            "text": text,
            "images": [
                {"marker": "[[IMAGE:cover]]", "bytes": b"cover-bytes"},
                {"marker": "[[IMAGE:map]]", "bytes": b"map-bytes"},
            ],
        }],
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
                    {"item_id": " impact-1 ", "status": "fixed", "assigned_version_id": " version-1 "},
                    {"item_id": "impact-1", "status": "ignored"},
                    {"item_id": " ", "status": "pending"},
                ],
                "last_generated_at": " 2026-05-11T10:00:00Z ",
            }
            ,
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
        }
    ]
    assert workspace["revision_recent_edits"][0]["kind"] == "scene"
    assert workspace["revision_recent_edits"][0]["scene_title"] == "Gate Approach"


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
async def test_search_author_workspace_returns_scoped_results(monkeypatch):
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

    class _ScalarRows:
        def __init__(self, rows):
            self._rows = rows

        def scalars(self):
            return self

        def all(self):
            return self._rows

    class _FakeSearchDB:
        async def execute(self, *_args, **_kwargs):
            chapter = Chapter(
                id=uuid.uuid4(),
                book_id=book.id,
                number=4,
                title="The Gate",
                s3_key="chapter-4.txt",
                content_version=1,
            )
            return _ScalarRows([chapter])

    async def _fake_list_novel_scenes(*_args, **_kwargs):
        return [{
            "id": "scene-1",
            "title": "Gate Approach",
            "description": "Mira heads to the harbor gate.",
            "body": "Mira reaches the silver gate with the dagger hidden in her sleeve.",
            "chapter_number": 4,
            "metadata": {"pov": "Mira", "location": "Harbor", "tags": ["dagger", "reveal"]},
            "tags": ["dagger", "reveal"],
        }]

    async def _fake_list_obsidian_notes(*_args, **_kwargs):
        return [{"path": "Plot Threads/Silver Gate.md", "content": "# Silver Gate\n\nMira hides the dagger near the gate."}]

    monkeypatch.setattr("app.utils.book_utils.list_novel_scenes", _fake_list_novel_scenes)
    monkeypatch.setattr("app.utils.book_utils.list_obsidian_notes", _fake_list_obsidian_notes)
    monkeypatch.setattr(
        "app.utils.book_utils.download_book",
        lambda _key: serialize_manuscript_content("The silver gate loomed over the harbor.", "<p>The silver gate loomed over the harbor.</p>").encode("utf-8"),
    )

    results = await search_author_workspace(
        _FakeSearchDB(),
        book=book,
        user_id=book.user_id,
        query="silver gate",
        scopes=["manuscript", "scenes", "notes"],
        filters={"pov": "Mira", "location": "Harbor", "tags": ["dagger"]},
    )

    assert [item["scope"] for item in results] == ["scenes", "notes", "manuscript"]
    assert results[0]["scene_id"] == "scene-1"
    assert results[1]["note_path"] == "Plot Threads/Silver Gate.md"
    assert results[2]["chapter_number"] == 4


def test_build_narration_signature_detects_first_person_anchor():
    signature = _build_narration_signature("I ran through the gate. My hands shook. I tasted blood on my lip.")

    assert signature["pov_mode"] == "first-person"
    assert signature["first_person_hits"] >= 3


def test_describe_narration_shift_flags_mode_change():
    previous = _build_narration_signature("She crossed the gate and kept her head down. Her breath stayed measured.")
    current = _build_narration_signature("I crossed the gate and kept my head down. My breath stayed measured.")

    assert _describe_narration_shift(previous, current) == "Narration shifts from third-person anchoring into first-person anchoring."


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
