"""Unit tests for book_utils functions."""
import uuid
import pytest

from app.utils.book_utils import (
    build_emotional_arc_payload,
    clean_markdown_asterisks_str,
    clean_manuscript_html,
    deserialize_manuscript_content,
    estimate_readability,
    markdown_to_html,
    manuscript_html_to_text,
    normalize_writer_workspace,
    serialize_manuscript_content,
)
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


def test_normalize_writer_workspace_preserves_defaults_and_sanitizes_cards():
    workspace = normalize_writer_workspace(
        {
            "word_count_goals": {"chapter_target": 3200, "book_target": -5, "session_target": 900},
            "corkboard_cards": [{"title": " Opening turn ", "lane": "drafting", "chapter_number": 3}],
            "publishing": {"active_preset": "kdp_paperback", "trim_size": "6x9"},
        }
    )

    assert workspace["word_count_goals"]["chapter_target"] == 3200
    assert workspace["word_count_goals"]["book_target"] is None
    assert workspace["word_count_goals"]["session_target"] == 900
    assert workspace["corkboard_cards"][0]["title"] == "Opening turn"
    assert workspace["corkboard_cards"][0]["lane"] == "drafting"
    assert workspace["publishing"]["active_preset"] == "kdp_paperback"
    assert len(workspace["templates"]) >= 3


def test_estimate_readability_returns_basic_metrics():
    metrics = estimate_readability("This is a short sentence. This is another one.")

    assert metrics["words"] == 9
    assert metrics["sentences"] == 2
    assert metrics["paragraphs"] == 1
    assert metrics["average_sentence_length"] > 0
    assert metrics["label"] in {"Very easy", "Easy", "Balanced", "Demanding", "Dense"}


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
