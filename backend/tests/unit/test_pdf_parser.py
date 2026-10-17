import fitz

from app.parsers.heading_patterns import build_heading_regex
from app.parsers.pdf_parser import (
    _assemble_text_parts,
    _blank_chapter,
    _blocks_to_paragraphs,
    _build_chapters,
    _build_parser_diagnostics,
    _drop_front_matter_text_parts,
    _extract_heading,
    _extract_source_number_from_heading,
    _heading_remainder,
    _is_page_margin_noise,
    _is_pagination_noise,
    _is_probable_front_matter,
    _is_repeated_noise,
    _needs_forced_large_chapter_split,
    _normalize_chapters,
    _order_two_column_page_items,
    _page_blocks,
    _scrub_inline_page_artifacts,
    _should_merge_across_pages,
    _split_large_chapter_parts,
)


def test_clear_two_column_pages_read_down_each_column_before_crossing():
    title = {"type": "text", "text": "Chapter 1", "bbox": (40.0, 30.0, 550.0, 50.0)}
    left = [
        {"type": "text", "text": f"left-{index}", "bbox": (50.0, 80.0 + index * 24, 265.0, 95.0 + index * 24)}
        for index in range(6)
    ]
    right = [
        {"type": "text", "text": f"right-{index}", "bbox": (325.0, 80.0 + index * 24, 540.0, 95.0 + index * 24)}
        for index in range(6)
    ]

    ordered, detected = _order_two_column_page_items([*left, *right, title], 595.0)

    assert detected is True
    assert [item["text"] for item in ordered] == ["Chapter 1", *[item["text"] for item in left], *[item["text"] for item in right]]


def test_ambiguous_spanning_text_keeps_original_vertical_reading_order():
    left = [
        {"type": "text", "text": f"left-{index}", "bbox": (50.0, 80.0 + index * 24, 265.0, 95.0 + index * 24)}
        for index in range(6)
    ]
    right = [
        {"type": "text", "text": f"right-{index}", "bbox": (325.0, 80.0 + index * 24, 540.0, 95.0 + index * 24)}
        for index in range(6)
    ]
    middle = {"type": "text", "text": "ambiguous", "bbox": (40.0, 130.0, 550.0, 145.0)}

    ordered, detected = _order_two_column_page_items([*left, *right, middle], 595.0)

    assert detected is False
    assert ordered.index(middle) < ordered.index(left[-1])


def test_real_pdf_text_blocks_follow_detected_column_reading_order():
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    for index in range(6):
        y = 80 + index * 26
        page.insert_text((50, y), f"LEFT {index}: Mara guards the archive key.", fontsize=11)
        page.insert_text((325, y), f"RIGHT {index}: Jon watches the gate.", fontsize=11)
    diagnostics: dict = {}

    blocks = _page_blocks(page, diagnostics_state=diagnostics)
    document.close()

    texts = [block["text"] for block in blocks if block["type"] == "text"]
    assert diagnostics["multi_column_pages"] == 1
    assert max(index for index, value in enumerate(texts) if value.startswith("LEFT")) < min(
        index for index, value in enumerate(texts) if value.startswith("RIGHT")
    )


def test_extract_heading_handles_decorated_prologue():
    assert _extract_heading("\u2600 Prologue \U0001f312.") == "Prologue"


def test_extract_heading_handles_decorated_epilogue():
    assert _extract_heading("\u2600 Epilogue \U0001f312.") == "Epilogue"


def test_extract_heading_handles_decorated_chapter():
    assert _extract_heading("\u2600 Chapter 1 \U0001f312") == "Chapter 1"


def test_extract_heading_handles_roman_numeral_chapter():
    assert _extract_heading("Chapter XIV") == "Chapter XIV"


def test_extract_heading_handles_short_standalone_roman_numerals():
    assert _extract_heading("I") == "I"
    assert _extract_heading("II") == "II"
    assert _extract_heading("VI.") == "VI"


def test_extract_heading_rejects_page_number_only_lines():
    assert (
        _extract_heading(
            "100",
            next_text="This line begins the next page of prose with enough words to look substantial.",
        )
        is None
    )


def test_extract_heading_handles_named_section():
    assert _extract_heading("Scene Second") == "Scene Second"


def test_extract_heading_does_not_promote_regular_sentence_with_part_keyword():
    assert _extract_heading("Er no not that part I was talking about um her given name") is None


def test_extract_heading_does_not_promote_prose_starting_with_part():
    assert (
        _extract_heading(
            "part of his body was in serious pain but he no longer gave any attention to it"
        )
        is None
    )


def test_extract_heading_does_not_promote_wrapped_prose_starting_with_part():
    assert (
        _extract_heading(
            "part of his body was in\nserious pain but he no longer gave any attention to it"
        )
        is None
    )


def test_heading_remainder_keeps_following_text():
    text = "\u2600 Prologue \U0001f312\nThis is the actual first paragraph."
    assert _extract_heading(text) == "Prologue"
    assert _heading_remainder(text, "Prologue") == "This is the actual first paragraph."


def test_front_matter_is_removed_from_leading_text():
    cleaned = _assemble_text_parts(
        _drop_front_matter_text_parts(
            [
                "Volume 2 - The Twin Towers at Iselma\n\nTranslated by TwilightsCall",
                "Compiled/formatted by Bonfire",
                "This is the real opening paragraph of the story, and it definitely belongs in the chapter.",
            ]
        )
    )
    assert "Translated by" not in cleaned
    assert "Compiled/formatted by" not in cleaned
    assert "real opening paragraph" in cleaned


def test_front_matter_cleanup_preserves_leading_image_markers():
    parts = _drop_front_matter_text_parts(
        [
            "[[IMAGE:test]]",
            "Translated by TwilightsCall",
            "This is the real opening paragraph.",
        ]
    )

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
    raw = (
        "that he would have to pay 966 of 967 dearly for it, that it would cost him great striving."
    )
    cleaned, removed = _scrub_inline_page_artifacts(raw, total_pages=967, page_number=966)
    assert (
        cleaned == "that he would have to pay dearly for it, that it would cost him great striving."
    )
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
    assert _should_merge_across_pages(
        "The sentence carries over", "into the next page without punctuation"
    )


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


def test_extract_source_number_from_heading_supports_french_chapters():
    assert _extract_source_number_from_heading("Chapitre 34: CHARON") == 34


# ── Phase 3: Multilingual heading + TOC + section_type ────────────────────


def test_extract_heading_accepts_multilingual_regex():
    fr_regex = build_heading_regex(languages=["fr"])
    assert _extract_heading("Chapitre 1: SCYLLA", heading_regex=fr_regex) == "Chapitre 1: SCYLLA"
    assert _extract_heading("Chapitre Premier", heading_regex=fr_regex) == "Chapitre Premier"


def test_extract_heading_falls_back_to_legacy_regex_when_none_given():
    assert _extract_heading("Chapter 1") == "Chapter 1"
    assert _extract_heading("Prologue") == "Prologue"


def test_extract_heading_requires_regex_for_multilingual():
    heading = _extract_heading("Kapitel 3")
    assert heading is None  # legacy CHAPTER_RE is English-only

    de_regex = build_heading_regex(languages=["de"])
    assert _extract_heading("Kapitel 3", heading_regex=de_regex) == "Kapitel 3"


def test_blank_chapter_includes_section_type():
    ch = _blank_chapter(1, "Chapter 1", "chapter")
    assert ch["section_type"] == "chapter"
    assert ch["number"] == 1


def test_blank_chapter_defaults_section_type_to_unknown():
    ch = _blank_chapter(1)
    assert ch["section_type"] == "unknown"


def test_build_chapters_assigns_section_type():
    en_regex = build_heading_regex(languages=["en"])
    stream = [
        {"type": "text", "text": "Prologue"},
        {"type": "text", "text": "Some body text here."},
    ]
    chapters = _build_chapters(stream, heading_regex=en_regex, language="en")
    prologue_ch = next((ch for ch in chapters if ch.get("title") == "Prologue"), None)
    assert prologue_ch is not None
    assert prologue_ch["section_type"] == "prologue"


def test_build_chapters_detects_and_skips_toc():
    fr_regex = build_heading_regex(languages=["fr"])
    stream = [
        {"type": "text", "text": "Table des matieres"},
        {"type": "text", "text": "Chapitre 1: SCYLLA.................. 1"},
        {"type": "text", "text": "Chapitre 2: LE CHANGE-FORME......... 4"},
        {"type": "text", "text": "Chapitre 3: LOUIS................... 7"},
        {"type": "text", "text": ""},
        {"type": "text", "text": "Chapitre 1: SCYLLA"},
        {"type": "text", "text": "Cet Ulysse qui a accoste sur mon ile..."},
        {"type": "text", "text": "Chapitre 2: LE CHANGE-FORME"},
        {"type": "text", "text": "Le matin se leva sur une brume epaisse..."},
    ]
    chapters = _build_chapters(stream, heading_regex=fr_regex, language="fr")
    titles = [ch.get("title") for ch in chapters]
    assert "Chapitre 1: SCYLLA" in titles
    assert "Chapitre 2: LE CHANGE-FORME" in titles
    for ch in chapters:
        assert "........." not in str(ch.get("title", ""))


def test_normalize_chapters_skips_toc_sections():
    chapters = [
        {"title": "TOC", "text_parts": ["toc"], "images": [], "section_type": "toc"},
        {"title": "Chapter 1", "text_parts": ["body"], "images": [], "section_type": "chapter"},
    ]
    normalized = _normalize_chapters(chapters, split_large_chapters=False, total_pages=10)
    assert len(normalized) == 1
    assert normalized[0]["section_type"] == "chapter"


def test_normalize_chapters_splits_embedded_french_headings_and_drops_toc_entries():
    chapters = [
        {
            "title": "Opening",
            "text_parts": [
                "Description de l'auteur. Table des matières "
                "Chapitre 1: SCYLLA...................... 1 "
                "Chapitre 2: LE CHANGE-FORME.............. 4 "
                "Préface Texte de la préface. "
                "Chapitre 1: SCYLLA Cet Ulysse qui a accosté sur mon île. "
                "Chapitre 2: LE CHANGE-FORME Le matin se leva sur une brume épaisse."
            ],
            "images": [],
            "section_type": "unknown",
        }
    ]

    normalized = _normalize_chapters(chapters, split_large_chapters=False, total_pages=130)

    assert [chapter["title"] for chapter in normalized] == [
        "Chapitre 1: SCYLLA",
        "Chapitre 2: LE CHANGE-FORME",
    ]
    assert normalized[0]["source_number"] == 1
    assert normalized[1]["source_number"] == 2
    assert "Table des matières" not in normalized[0]["text"]
    assert "Cet Ulysse" in normalized[0]["text"]


def test_normalize_chapters_passes_section_type_through():
    chapters = [
        {"title": "Prologue", "text_parts": ["content"], "images": [], "section_type": "prologue"},
    ]
    normalized = _normalize_chapters(chapters, split_large_chapters=False, total_pages=5)
    assert normalized[0]["section_type"] == "prologue"


def test_normalize_chapters_drops_title_page_and_numeric_page_sections():
    chapters = [
        {
            "title": "TOME 2: LES ABYSSES",
            "text_parts": [
                "Les chroniques legendaires d'Animaris TOME 2: LES ABYSSES Du meme auteur"
            ],
            "images": [],
            "section_type": "part",
        },
        {
            "title": "100",
            "text_parts": ["A short page fragment that should not become a chapter."],
            "images": [],
            "section_type": "unknown",
        },
        {
            "title": "Chapitre 1: SCYLLA",
            "text_parts": ["Cet Ulysse qui a accoste sur mon ile."],
            "images": [],
            "section_type": "chapter",
        },
    ]

    normalized = _normalize_chapters(chapters, split_large_chapters=False, total_pages=130)

    assert [chapter["title"] for chapter in normalized] == ["Chapitre 1: SCYLLA"]


def test_normalize_chapters_removes_front_matter_before_embedded_story_heading():
    chapters = [
        {
            "title": "123",
            "text_parts": [
                "Chapitre 34: CHARON..................... 127 "
                "Preface Texte de la preface. "
                "Avantpropos Texte de l'avant-propos. "
                "Chapitre 1: SCYLLA Cet Ulysse qui a accoste sur mon ile. "
                "Chapitre 2: LE CHANGEFORME Je chutais dans une eau glaciale."
            ],
            "images": [],
            "section_type": "unknown",
        },
    ]

    normalized = _normalize_chapters(chapters, split_large_chapters=False, total_pages=130)

    assert [chapter["title"] for chapter in normalized] == [
        "Chapitre 1: SCYLLA",
        "Chapitre 2: LE CHANGEFORME",
    ]
    assert "Preface" not in normalized[0]["text"]
    assert "Avantpropos" not in normalized[0]["text"]
    assert "Cet Ulysse" in normalized[0]["text"]


def test_build_parser_diagnostics_includes_language_info():
    chapters = [{"title": "Ch 1", "text_parts": ["c"], "images": [], "section_type": "chapter"}]
    normalized = [{"number": 1, "title": "Ch 1", "text": "c"}]

    diagnostics = _build_parser_diagnostics(
        chapters,
        normalized_chapters=normalized,
        total_pages=10,
        repeated_noise=set(),
        fallback_strategy=None,
        forced_large_chapter_split=False,
        anomalies=[],
        diagnostics_state={
            "text_line_count": 50,
            "noise_lines_removed": 0,
            "noise_reason_counts": {},
            "inline_artifacts_removed": 0,
        },
        detected_language="fr",
        detected_language_confidence=0.92,
    )

    assert diagnostics["detected_language"] == "fr"
    assert diagnostics["detected_language_confidence"] == 0.92
    assert diagnostics["section_type_counts"] == {"chapter": 1}
    assert diagnostics["toc_detected"] is False
    assert diagnostics["front_matter_count"] == 0
    assert diagnostics["parser_version"] == "pdf_linewise_v4"


def test_build_parser_diagnostics_reports_toc_and_front_matter():
    chapters = [
        {"title": "Preface", "text_parts": ["p"], "images": [], "section_type": "preface"},
        {"title": "TOC", "text_parts": ["t"], "images": [], "section_type": "toc"},
        {"title": "Chapitre 1", "text_parts": ["1"], "images": [], "section_type": "chapter"},
    ]
    normalized = [{"number": 1, "title": "Chapitre 1", "text": "1"}]

    diagnostics = _build_parser_diagnostics(
        chapters,
        normalized_chapters=normalized,
        total_pages=20,
        repeated_noise=set(),
        fallback_strategy=None,
        forced_large_chapter_split=False,
        anomalies=[],
        diagnostics_state={
            "text_line_count": 100,
            "noise_lines_removed": 0,
            "noise_reason_counts": {},
            "inline_artifacts_removed": 0,
        },
        detected_language="fr",
    )

    assert diagnostics["toc_detected"] is True
    assert diagnostics["front_matter_count"] == 1
    assert diagnostics["section_type_counts"]["toc"] == 1
    assert diagnostics["section_type_counts"]["preface"] == 1


def test_build_parser_diagnostics_backward_compat_without_language():
    chapters = [{"title": "I", "text_parts": ["c"], "images": [], "section_type": "unknown"}]
    normalized = [{"number": 1, "title": "I", "text": "c"}]

    diagnostics = _build_parser_diagnostics(
        chapters,
        normalized_chapters=normalized,
        total_pages=5,
        repeated_noise=set(),
        fallback_strategy=None,
        forced_large_chapter_split=False,
        anomalies=[],
        diagnostics_state={
            "text_line_count": 10,
            "noise_lines_removed": 0,
            "noise_reason_counts": {},
            "inline_artifacts_removed": 0,
        },
    )

    assert diagnostics["detected_language"] == "en"
