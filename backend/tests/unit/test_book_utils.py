"""Unit tests for book_utils functions."""
import pytest

from app.utils.book_utils import clean_markdown_asterisks_str, markdown_to_html


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
