"""
Test Unicode replacement character normalization to prevent black squares in exports.
"""
import pytest

from app.utils.book_utils import _normalize_unicode_replacements, clean_manuscript_html
from app.utils.export_utils import _normalize_unicode_for_export


def test_normalize_unicode_replacements_removes_replacement_character():
    """Test that Unicode replacement character (�) is removed."""
    text = "porridge of maize \uFFFDour which they said was \"mamaliga\""
    result = _normalize_unicode_replacements(text)
    assert "\uFFFD" not in result
    assert result == "porridge of maize our which they said was \"mamaliga\""


def test_normalize_unicode_replacements_removes_black_squares():
    """Test that black square characters are removed."""
    text = "text with \u25A0 and \u25AA squares"
    result = _normalize_unicode_replacements(text)
    assert "\u25A0" not in result
    assert "\u25AA" not in result
    assert result == "text with  and  squares"


def test_normalize_unicode_replacements_converts_smart_quotes():
    """Test that smart quotes are converted to straight quotes."""
    text = "\u201CHello\u201D and \u2018world\u2019"
    result = _normalize_unicode_replacements(text)
    assert result == '"Hello" and \'world\''


def test_normalize_unicode_replacements_converts_dashes():
    """Test that en-dash and em-dash are converted."""
    text = "Range: 1\u20135 and pause\u2014here"
    result = _normalize_unicode_replacements(text)
    assert result == "Range: 1-5 and pause--here"


def test_normalize_unicode_replacements_converts_ligatures():
    """Test that ligatures (fi, fl, ff, ffi, ffl) are converted to separate letters."""
    text = "\uFB01sh and \uFB02our with e\uFB00ect and a\uFB03rm and ba\uFB04e"
    result = _normalize_unicode_replacements(text)
    assert result == "fish and flour with effect and affirm and baffle"
    assert "\uFB01" not in result
    assert "\uFB02" not in result
    assert "\uFB00" not in result
    assert "\uFB03" not in result
    assert "\uFB04" not in result


def test_normalize_unicode_replacements_converts_ellipsis():
    """Test that ellipsis character is converted to three dots."""
    text = "Wait\u2026 what?"
    result = _normalize_unicode_replacements(text)
    assert result == "Wait... what?"


def test_normalize_unicode_replacements_converts_nbsp():
    """Test that non-breaking space is converted to regular space."""
    text = "word\u00A0word"
    result = _normalize_unicode_replacements(text)
    assert result == "word word"


def test_normalize_unicode_replacements_handles_empty_string():
    """Test that empty string is handled gracefully."""
    assert _normalize_unicode_replacements("") == ""
    assert _normalize_unicode_replacements(None) is None or _normalize_unicode_replacements(None) == ""


def test_normalize_unicode_replacements_handles_regular_text():
    """Test that regular text passes through unchanged."""
    text = "This is normal text with regular punctuation."
    result = _normalize_unicode_replacements(text)
    assert result == text


def test_clean_manuscript_html_normalizes_unicode():
    """Test that clean_manuscript_html applies Unicode normalization."""
    html = "<p>Text with \uFFFD replacement and \uFB01 ligature</p>"
    result = clean_manuscript_html(html)
    assert "\uFFFD" not in result
    assert "\uFB01" not in result
    assert "fi" in result


def test_export_utils_normalize_unicode_for_export():
    """Test that export utility has the same normalization function."""
    text = "Export text with \uFFFD and \u201Csmart quotes\u201D"
    result = _normalize_unicode_for_export(text)
    assert "\uFFFD" not in result
    assert result == 'Export text with  and "smart quotes"'


def test_combined_unicode_issues():
    """Test handling multiple Unicode issues in one string (real-world scenario)."""
    # This simulates the actual text from the user's screenshot
    text = (
        "I had for breakfast more paprika, and a sort of porridge of maize \uFFFDour which "
        "they said was \u201Cmamaliga\u201D, and egg-plant stu\uFFFDed with forcemeat, a very excellent dish"
    )
    result = _normalize_unicode_replacements(text)
    
    # Check no problematic characters remain
    assert "\uFFFD" not in result
    assert "\u201C" not in result
    assert "\u201D" not in result
    
    # Check proper conversions
    assert "flour" in result or "our" in result  # fl ligature or replacement removed
    assert "stuffed" in result or "stued" in result  # ff ligature or replacement removed
    assert '"mamaliga"' in result  # Smart quotes converted
