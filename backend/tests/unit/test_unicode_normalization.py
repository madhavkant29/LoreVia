"""
Test Unicode replacement character normalization to prevent black squares in exports.
"""

import pytest

from app.utils.books.book_text import (
    _normalize_unicode_replacements,
)
from app.utils.books.manuscript import (
    clean_manuscript_html,
)
from app.utils.export_utils import _normalize_unicode_for_export


def test_normalize_unicode_replacements_removes_replacement_character():
    """Test that Unicode replacement character (ï¿½) is removed."""
    text = 'porridge of maize \ufffdour which they said was "mamaliga"'
    result = _normalize_unicode_replacements(text)
    assert "\ufffd" not in result
    assert result == 'porridge of maize our which they said was "mamaliga"'


def test_normalize_unicode_replacements_removes_black_squares():
    """Test that black square characters are removed."""
    text = "text with \u25a0 and \u25aa squares"
    result = _normalize_unicode_replacements(text)
    assert "\u25a0" not in result
    assert "\u25aa" not in result
    assert result == "text with  and  squares"


def test_normalize_unicode_replacements_converts_smart_quotes():
    """Test that smart quotes are converted to straight quotes."""
    text = "\u201cHello\u201d and \u2018world\u2019"
    result = _normalize_unicode_replacements(text)
    assert result == "\"Hello\" and 'world'"


def test_normalize_unicode_replacements_converts_dashes():
    """Test that en-dash and em-dash are converted."""
    text = "Range: 1\u20135 and pause\u2014here"
    result = _normalize_unicode_replacements(text)
    assert result == "Range: 1-5 and pause--here"


def test_normalize_unicode_replacements_converts_ligatures():
    """Test that ligatures (fi, fl, ff, ffi, ffl) are converted to separate letters."""
    text = "\ufb01sh and \ufb02our with e\ufb00ect and a\ufb03rm and ba\ufb04e"
    result = _normalize_unicode_replacements(text)
    assert result == "fish and flour with effect and affirm and baffle"
    assert "\ufb01" not in result
    assert "\ufb02" not in result
    assert "\ufb00" not in result
    assert "\ufb03" not in result
    assert "\ufb04" not in result


def test_normalize_unicode_replacements_converts_ellipsis():
    """Test that ellipsis character is converted to three dots."""
    text = "Wait\u2026 what?"
    result = _normalize_unicode_replacements(text)
    assert result == "Wait... what?"


def test_normalize_unicode_replacements_converts_nbsp():
    """Test that non-breaking space is converted to regular space."""
    text = "word\u00a0word"
    result = _normalize_unicode_replacements(text)
    assert result == "word word"


def test_normalize_unicode_replacements_handles_empty_string():
    """Test that empty string is handled gracefully."""
    assert _normalize_unicode_replacements("") == ""
    assert (
        _normalize_unicode_replacements(None) is None or _normalize_unicode_replacements(None) == ""
    )


def test_normalize_unicode_replacements_handles_regular_text():
    """Test that regular text passes through unchanged."""
    text = "This is normal text with regular punctuation."
    result = _normalize_unicode_replacements(text)
    assert result == text


def test_clean_manuscript_html_normalizes_unicode():
    """Test that clean_manuscript_html applies Unicode normalization."""
    html = "<p>Text with \ufffd replacement and \ufb01 ligature</p>"
    result = clean_manuscript_html(html)
    assert "\ufffd" not in result
    assert "\ufb01" not in result
    assert "fi" in result


def test_export_utils_normalize_unicode_for_export():
    """Test that export utility has the same normalization function."""
    text = "Export text with \ufffd and \u201csmart quotes\u201d"
    result = _normalize_unicode_for_export(text)
    assert "\ufffd" not in result
    assert result == 'Export text with  and "smart quotes"'


def test_combined_unicode_issues():
    """Test handling multiple Unicode issues in one string (real-world scenario)."""
    # This simulates the actual text from the user's screenshot
    text = (
        "I had for breakfast more paprika, and a sort of porridge of maize \ufffdour which "
        "they said was \u201cmamaliga\u201d, and egg-plant stu\ufffded with forcemeat, a very excellent dish"
    )
    result = _normalize_unicode_replacements(text)

    # Check no problematic characters remain
    assert "\ufffd" not in result
    assert "\u201c" not in result
    assert "\u201d" not in result

    # Check proper conversions
    assert "flour" in result or "our" in result  # fl ligature or replacement removed
    assert "stuffed" in result or "stued" in result  # ff ligature or replacement removed
    assert '"mamaliga"' in result  # Smart quotes converted
