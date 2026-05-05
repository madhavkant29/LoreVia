from app.parsers.pdf_parser import (
    _assemble_text_parts,
    _blocks_to_paragraphs,
    _extract_source_number_from_heading,
    _drop_front_matter_text_parts,
    _extract_heading,
    _heading_remainder,
    _build_parser_diagnostics,
    _is_page_margin_noise,
    _is_pagination_noise,
    _is_probable_front_matter,
    _is_repeated_noise,
    _needs_forced_large_chapter_split,
    _scrub_inline_page_artifacts,
    _should_merge_across_pages,
    _split_large_chapter_parts,
)


def test_extract_heading_handles_decorated_prologue():
    assert _extract_heading("\u2600 Prologue \U0001F312.") == "Prologue"


def test_extract_heading_handles_decorated_epilogue():
    assert _extract_heading("\u2600 Epilogue \U0001F312.") == "Epilogue"


def test_extract_heading_handles_decorated_chapter():
    assert _extract_heading("\u2600 Chapter 1 \U0001F312") == "Chapter 1"


def test_extract_heading_handles_roman_numeral_chapter():
    assert _extract_heading("Chapter XIV") == "Chapter XIV"


def test_extract_heading_handles_short_standalone_roman_numerals():
    assert _extract_heading("I") == "I"
    assert _extract_heading("II") == "II"
    assert _extract_heading("VI.") == "VI"


def test_extract_heading_handles_named_section():
    assert _extract_heading("Scene Second") == "Scene Second"


def test_extract_heading_does_not_promote_regular_sentence_with_part_keyword():
    assert _extract_heading("Er no not that part I was talking about um her given name") is None


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


def test_front_matter_cleanup_preserves_leading_image_markers():
    parts = _drop_front_matter_text_parts([
        "[[IMAGE:test]]",
        "Translated by TwilightsCall",
        "This is the real opening paragraph.",
    ])

    assert parts == ["[[IMAGE:test]]", "This is the real opening paragraph."]


def test_front_matter_detector_flags_credit_lines():
    assert _is_probable_front_matter("Translated by TwilightsCall")
    assert _is_probable_front_matter("Volume 2 - The Twin Towers at Iselma")


def test_pagination_noise_detector_flags_page_counter_artifacts():
    assert _is_pagination_noise("924 of 967")
    assert _is_pagination_noise("Page 12 of 400")
    assert _is_repeated_noise("923 / 967", set())


def test_page_margin_noise_detector_uses_geometry_and_page_context():
    assert _is_page_margin_noise(
        "967 of 967",
        bbox=(10.0, 940.0, 120.0, 960.0),
        page_height=1000.0,
        repeated_noise=set(),
        total_pages=967,
        page_number=967,
    )


def test_inline_page_artifact_scrubber_removes_embedded_footer_counter():
    raw = "that he would have to pay 966 of 967 dearly for it, that it would cost him great striving."
    cleaned, removed = _scrub_inline_page_artifacts(raw, total_pages=967, page_number=966)
    assert cleaned == "that he would have to pay dearly for it, that it would cost him great striving."
    assert removed == 1


def test_inline_page_artifact_scrubber_preserves_normal_numeric_prose():
    raw = "He counted 12 of 400 volunteers before the doors opened."
    cleaned, removed = _scrub_inline_page_artifacts(raw, total_pages=967, page_number=12)
    assert cleaned == raw
    assert removed == 0


def test_page_boundary_merge_does_not_merge_into_heading():
    assert not _should_merge_across_pages("The scene continues without punctuation", "Chapter 1")


def test_large_chapter_splits_only_on_closed_paragraph_boundary():
    first = ("word " * 4200).strip() + "."
    second = ("word " * 3200).strip() + "."
    third = ("word " * 300).strip()
    split = _split_large_chapter_parts([first, second, third])
    assert len(split) == 2
    assert split[0] == [first]
    assert split[1] == [second, third]


def test_assemble_text_parts_preserves_paragraph_breaks():
    text = _assemble_text_parts(["First paragraph.", "[[IMAGE:test]]", "Second paragraph."])
    assert text == "First paragraph.\n\n[[IMAGE:test]]\n\nSecond paragraph."


def test_forced_large_chapter_split_flags_suspicious_outlier():
    chapters = [
        {"text_parts": [("word " * 2000).strip() + "."], "images": []},
        {"text_parts": [("word " * 2200).strip() + "."], "images": []},
        {"text_parts": [("word " * 17000).strip() + "."], "images": []},
    ]

    assert _needs_forced_large_chapter_split(chapters, total_pages=967) is True


def test_build_parser_diagnostics_reports_anomalies_and_fallback():
    chapters = [
        {"title": "I", "text_parts": [("word " * 1800).strip() + "."], "images": []},
        {"title": "II", "text_parts": [("word " * 2100).strip() + "."], "images": []},
        {"title": "", "text_parts": [("word " * 17000).strip() + "."], "images": []},
    ]
    normalized = [
        {"number": 1, "title": "I", "text": ("word " * 1800).strip() + "."},
        {"number": 2, "title": "II", "text": ("word " * 2100).strip() + "."},
        {"number": 3, "title": "Chapter 3", "text": ("word " * 17000).strip() + "."},
    ]

    diagnostics = _build_parser_diagnostics(
        chapters,
        normalized_chapters=normalized,
        total_pages=967,
        repeated_noise={"crime and punishment"},
        fallback_strategy="permissive_heading_retry",
        forced_large_chapter_split=True,
        anomalies=["heading_style_dropout", "oversized_chapter_outlier"],
        diagnostics_state={
            "text_line_count": 100,
            "noise_lines_removed": 4,
            "noise_reason_counts": {"pagination_counter": 3, "repeated_margin_noise": 1},
            "inline_artifacts_removed": 2,
        },
    )

    assert diagnostics["fallback_strategy"] == "permissive_heading_retry"
    assert diagnostics["forced_large_chapter_split"] is True
    assert diagnostics["noise_reason_counts"]["pagination_counter"] == 3
    assert "heading_style_dropout" in diagnostics["anomalies"]


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
