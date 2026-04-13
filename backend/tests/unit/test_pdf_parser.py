from app.parsers.pdf_parser import (
    _assemble_text_parts,
    _drop_front_matter_text_parts,
    _extract_heading,
    _heading_remainder,
    _is_probable_front_matter,
    _split_large_chapter_parts,
    _should_merge_across_pages,
)


def test_extract_heading_handles_decorated_prologue():
    assert _extract_heading("\u2600 Prologue \U0001F312.") == "Prologue"


def test_extract_heading_handles_decorated_chapter():
    assert _extract_heading("\u2600 Chapter 1 \U0001F312") == "Chapter 1"


def test_extract_heading_handles_roman_numeral_chapter():
    assert _extract_heading("Chapter XIV") == "Chapter XIV"


def test_extract_heading_handles_named_section():
    assert _extract_heading("Scene Second") == "Scene Second"


def test_heading_remainder_keeps_following_text():
    text = "\u2600 Prologue \U0001F312\nThis is the actual first paragraph."
    assert _extract_heading(text) == "Prologue"
    assert _heading_remainder(text, "Prologue") == "This is the actual first paragraph."


def test_front_matter_is_removed_from_leading_text():
    cleaned = _assemble_text_parts(
        _drop_front_matter_text_parts([
            "Volume 2 - The Twin Towers at Iselma\n\nTranslated by TwilightsCall",
            "Compiled/formatted by Bonfire",
            "This is the real opening paragraph of the story, and it definitely belongs in the chapter.",
        ])
    )
    assert "Translated by" not in cleaned
    assert "Compiled/formatted by" not in cleaned
    assert "real opening paragraph" in cleaned


def test_front_matter_detector_flags_credit_lines():
    assert _is_probable_front_matter("Translated by TwilightsCall")
    assert _is_probable_front_matter("Volume 2 - The Twin Towers at Iselma")


def test_page_boundary_merge_does_not_merge_into_heading():
    assert not _should_merge_across_pages("The scene continues without punctuation", "Chapter 1")


def test_large_chapter_splits_only_on_closed_paragraph_boundary():
    first = ("word " * 2500).strip() + "."
    second = ("word " * 1800).strip() + "."
    third = ("word " * 300).strip()
    split = _split_large_chapter_parts([first, second, third])
    assert len(split) == 2
    assert split[0] == [first]
    assert split[1] == [second, third]


def test_assemble_text_parts_preserves_paragraph_breaks():
    text = _assemble_text_parts(["First paragraph.", "[[IMAGE:test]]", "Second paragraph."])
    assert text == "First paragraph.\n\n[[IMAGE:test]]\n\nSecond paragraph."
