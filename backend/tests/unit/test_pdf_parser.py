from app.parsers.pdf_parser import (
    _assemble_text_parts,
    _blocks_to_paragraphs,
    _extract_source_number_from_heading,
    _drop_front_matter_text_parts,
    _extract_heading,
    _heading_remainder,
    _is_probable_front_matter,
    _should_merge_across_pages,
    _split_large_chapter_parts,
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


def test_blocks_to_paragraphs_merges_soft_wrapped_lines():
    text = "This is a paragraph broken\nacross lines without ending punctuation\nand it should remain one paragraph."
    assert _blocks_to_paragraphs(text) == [
        "This is a paragraph broken across lines without ending punctuation and it should remain one paragraph."
    ]


def test_blocks_to_paragraphs_keeps_closed_sentence_starting_new_paragraph():
    text = "The scene ends here.\nThe next paragraph starts cleanly."
    assert _blocks_to_paragraphs(text) == [
        "The scene ends here.",
        "The next paragraph starts cleanly.",
    ]


def test_should_merge_across_pages_for_unfinished_paragraph():
    assert _should_merge_across_pages("The sentence carries over", "into the next page without punctuation")


def test_should_not_merge_across_pages_when_next_block_is_heading():
    assert not _should_merge_across_pages("The sentence carries over", "Chapter 3")


def test_extract_source_number_from_heading_supports_roman_numerals():
    assert _extract_source_number_from_heading("Chapter XIV") == 14


def test_extract_source_number_from_heading_supports_number_words():
    assert _extract_source_number_from_heading("Chapter Three") == 3


def test_extract_source_number_from_heading_supports_compound_number_words():
    assert _extract_source_number_from_heading("Chapter Twenty-One") == 21


def test_extract_source_number_from_heading_supports_compound_ordinal_words():
    assert _extract_source_number_from_heading("Chapter Thirty First") == 31


def test_extract_source_number_from_heading_supports_letter_labels():
    assert _extract_source_number_from_heading("Chapter C") == 3
    assert _extract_source_number_from_heading("Chapter AA") == 27


def test_extract_source_number_from_heading_supports_numeric_suffixes():
    assert _extract_source_number_from_heading("Chapter 14A") == 14
