import re

import pytest

from app.parsers.heading_patterns import (
    ALL_LANGUAGES,
    HEADING_PATTERNS,
    NUMBER_WORDS,
    NUMBER_WORDS_BY_LANG,
    ORDINAL_WORDS,
    ORDINAL_WORDS_BY_LANG,
    build_heading_regex,
    classify_heading_type,
    get_number_words,
    get_ordinal_words,
    get_section_type_defaults,
    has_toc_signals,
    is_toc_indicator,
)

# ── Data integrity ─────────────────────────────────────────────────────────


def test_all_languages_have_required_section_types():
    required = {"chapter", "part", "prologue", "epilogue", "preface", "toc"}
    for lang in ALL_LANGUAGES:
        missing = required - set(HEADING_PATTERNS.get(lang, {}).keys())
        assert not missing, f"{lang} missing required types: {missing}"


def test_no_duplicate_keywords_within_language():
    for lang in ALL_LANGUAGES:
        patterns = HEADING_PATTERNS.get(lang, {})
        for stype, keywords in patterns.items():
            unique = set(kw.lower() for kw in keywords)
            assert len(unique) == len(keywords), (
                f"{lang}.{stype} has duplicate keywords: {keywords}"
            )


def test_all_keywords_are_non_empty():
    for lang in ALL_LANGUAGES:
        patterns = HEADING_PATTERNS.get(lang, {})
        for stype, keywords in patterns.items():
            for kw in keywords:
                assert kw.strip(), f"{lang}.{stype} has empty keyword"


def test_number_words_are_ints():
    for lang in ALL_LANGUAGES:
        nw = NUMBER_WORDS_BY_LANG.get(lang, {})
        for word, value in nw.items():
            assert isinstance(value, int), f"{lang} number word {word!r} value is not int"


def test_ordinal_words_are_ints():
    for lang in ALL_LANGUAGES:
        ow = ORDINAL_WORDS_BY_LANG.get(lang, {})
        for word, value in ow.items():
            assert isinstance(value, int), f"{lang} ordinal word {word!r} value is not int"


def test_backward_compat_number_words_exists():
    assert isinstance(NUMBER_WORDS, dict)
    assert NUMBER_WORDS["one"] == 1


def test_backward_compat_ordinal_words_exists():
    assert isinstance(ORDINAL_WORDS, dict)
    assert ORDINAL_WORDS["first"] == 1


# ── build_heading_regex ────────────────────────────────────────────────────


def test_regex_builds_with_all_languages():
    r = build_heading_regex()
    assert isinstance(r, re.Pattern)
    assert r.match("Chapter 1")
    assert r.match("Chapitre 10")
    assert r.match("Kapitel 3")


def test_regex_builds_with_single_language():
    r = build_heading_regex(languages=["en"])
    assert r.match("Chapter 1")
    assert not r.match("Chapitre 1")


def test_regex_builds_with_language_subset():
    r = build_heading_regex(languages=["en", "fr"])
    assert r.match("Chapter 1")
    assert r.match("Chapitre 10")
    assert not r.match("Kapitel 1")


def test_regex_filters_by_section_type():
    r = build_heading_regex(languages=["en"], section_types=["chapter"])
    assert r.match("Chapter 1")
    assert r.match("Chapter 10: The Beginning")
    assert not r.match("Prologue")
    assert not r.match("Epilogue")


def test_regex_matches_arabic_numeral_chapters():
    r = build_heading_regex()
    assert r.match("Chapter 1")
    assert r.match("Chapter 42")


def test_regex_matches_roman_numeral_chapters():
    r = build_heading_regex()
    assert r.match("Chapter IV")
    assert r.match("Chapter XIV")
    assert r.match("Chapter XXIII")


def test_regex_matches_letter_chapters():
    r = build_heading_regex()
    assert r.match("Chapter A")
    assert r.match("Chapter B")


def test_regex_matches_chapter_with_subtitle():
    r = build_heading_regex()
    assert r.match("Chapter 1: The Beginning")
    assert r.match("Chapter 10 - The End")
    assert r.match("Chapitre 1: SCYLLA")
    assert r.match("Chapitre 10. Le Change-Forme")


def test_regex_matches_written_number_chapters_en():
    r = build_heading_regex(languages=["en"])
    assert r.match("Chapter One")
    assert r.match("Chapter Twenty-One")


def test_regex_matches_ordinal_chapters_fr():
    r = build_heading_regex(languages=["fr"])
    assert r.match("Chapitre Premier")
    assert r.match("Chapitre Deuxieme")


def test_regex_matches_standalone_headings():
    r = build_heading_regex()
    assert r.match("Prologue")
    assert r.match("Epilogue")
    assert r.match("Epilogue")
    assert r.match("Prologo")
    assert r.match("Preface")
    assert r.match("Interlude")


def test_regex_matches_typo_variants():
    r = build_heading_regex(languages=["fr"])
    assert r.match("Chaptre 16")
    assert r.match("Chaptre XVI")


def test_regex_matches_case_insensitively():
    r = build_heading_regex()
    assert r.match("CHAPTER 1")
    assert r.match("chapitre 10: scylla")
    assert r.match("CHAPITRE XI")
    assert r.match("PROLOGUE")


def test_regex_matches_toc_headings():
    r = build_heading_regex()
    assert r.match("Table of Contents")
    assert r.match("Table des matieres")


def test_regex_matches_front_matter_types():
    r = build_heading_regex()
    assert r.match("Preface")
    assert r.match("Foreword")
    assert r.match("Dedication")
    assert r.match("Acknowledgements")
    assert r.match("Glossary")


def test_regex_does_not_match_regular_text():
    r = build_heading_regex()
    assert not r.match("It was a dark and stormy night")
    assert not r.match("The quick brown fox jumps over the lazy dog")
    assert not r.match("Once upon a time there lived a king")


def test_regex_does_not_match_partial_keywords():
    r = build_heading_regex()
    assert not r.match("part of the problem was")


def test_regex_does_not_match_preface_in_middle_of_sentence():
    r = build_heading_regex()
    assert not r.match("He wrote a preface to the book")


def test_regex_empty_languages_returns_no_match():
    r = build_heading_regex(languages=[])
    assert not r.match("Chapter 1")


# ── classify_heading_type ──────────────────────────────────────────────────


def test_classify_english_chapter():
    stype, conf = classify_heading_type("Chapter 1", "en")
    assert stype == "chapter"
    assert conf >= 0.9


def test_classify_french_chapter():
    stype, conf = classify_heading_type("Chapitre 1: SCYLLA", "fr")
    assert stype == "chapter"


def test_classify_english_prologue():
    stype, conf = classify_heading_type("Prologue", "en")
    assert stype == "prologue"
    assert conf == pytest.approx(1.0)


def test_classify_french_preface():
    stype, conf = classify_heading_type("Preface", "fr")
    assert stype == "preface"
    assert conf == pytest.approx(1.0)


def test_classify_french_avant_propos():
    stype, conf = classify_heading_type("Avant-propos", "fr")
    assert stype == "preface"


def test_classify_french_toc():
    stype, conf = classify_heading_type("Table des matieres", "fr")
    assert stype == "toc"


def test_classify_spanish_chapter():
    stype, conf = classify_heading_type("Capitulo 5", "es")
    assert stype == "chapter"


def test_classify_spanish_prologue():
    stype, conf = classify_heading_type("Prologo", "es")
    assert stype == "prologue"


def test_classify_german_chapter():
    stype, conf = classify_heading_type("Kapitel 3", "de")
    assert stype == "chapter"


def test_classify_german_toc():
    stype, conf = classify_heading_type("Inhaltsverzeichnis", "de")
    assert stype == "toc"


def test_classify_italian_chapter():
    stype, conf = classify_heading_type("Capitolo 2", "it")
    assert stype == "chapter"


def test_classify_portuguese_chapter():
    stype, conf = classify_heading_type("Capitulo 5", "pt")
    assert stype == "chapter"


def test_classify_portuguese_toc():
    stype, conf = classify_heading_type("Sumario", "pt")
    assert stype == "toc"


def test_classify_unknown_text():
    stype, conf = classify_heading_type("Just some random text", "en")
    assert stype == "unknown"
    assert conf == 0.0


def test_classify_empty_string():
    stype, conf = classify_heading_type("", "en")
    assert stype == "unknown"
    assert conf == 0.0


def test_classify_unknown_language_falls_back_to_en():
    stype, conf = classify_heading_type("Chapter 10", "xx")
    assert stype == "chapter"


def test_classify_french_glossary():
    stype, conf = classify_heading_type("Glossaire", "fr")
    assert stype == "glossary"


def test_classify_french_dedication():
    stype, conf = classify_heading_type("Dedicace", "fr")
    assert stype == "dedication"


# ── is_toc_indicator ───────────────────────────────────────────────────────


def test_toc_indicator_with_dotted_leaders():
    assert is_toc_indicator("Chapitre 1: SCYLLA.................. 1")
    assert is_toc_indicator("Chapter 2.......... 4")


def test_toc_indicator_with_multiple_dots():
    assert is_toc_indicator("Some heading...... 42")


def test_toc_indicator_with_very_short_prefix_is_not_toc():
    # A short prefix ending in a number is likely a chapter heading,
    # not a TOC entry (e.g. "Chapter 1").  TOC entries have longer titles.
    assert not is_toc_indicator("Chapter 1.. 1")


def test_toc_indicator_page_number_at_end():
    assert is_toc_indicator("Chapitre 1: SCYLLA              1")
    assert is_toc_indicator("Chapter The First               42")


def test_toc_indicator_regular_text_is_false():
    assert not is_toc_indicator("It was a dark and stormy night")
    assert not is_toc_indicator("The End")


def test_toc_indicator_empty_is_false():
    assert not is_toc_indicator("")
    assert not is_toc_indicator("   ")


# ── has_toc_signals ────────────────────────────────────────────────────────


def test_has_toc_signals_with_dotted_leaders():
    lines = [
        "Table des matieres",
        "Chapitre 1: SCYLLA.................. 1",
        "Chapitre 2: LE CHANGE-FORME......... 4",
        "Chapitre 3: LOUIS................... 7",
        "",
        "Regular text starts here...",
    ]
    assert has_toc_signals(lines)


def test_has_toc_signals_with_page_numbers():
    lines = [
        "Contents",
        "Chapter 1: The Beginning         1",
        "Chapter 2: The Middle           12",
        "Chapter 3: The End              34",
    ]
    assert has_toc_signals(lines)


def test_has_toc_signals_body_text_is_false():
    lines = [
        "It was a dark and stormy night. The rain fell in torrents",
        "except at occasional intervals, when it was checked by a",
        "violent gust of wind which swept up the streets of London.",
    ]
    assert not has_toc_signals(lines)


def test_has_toc_signals_empty_is_false():
    assert not has_toc_signals([])
    assert not has_toc_signals(["", "", ""])


def test_has_toc_signals_short_list_is_false():
    assert not has_toc_signals(["Chapter 1.......... 1", "Chapter 2.......... 2"])


def test_has_toc_signals_low_density_with_one_toc_line():
    lines = [
        "Chapter 1.......... 1",
        "A long body paragraph that goes on for a while with many words "
        "and sentences that make the average line length quite large.",
        "Another long paragraph that fills up the space substantially.",
        "Yet another lengthy paragraph with plenty of text content.",
    ]
    assert not has_toc_signals(lines)


# ── get_section_type_defaults ──────────────────────────────────────────────


def test_chapter_included_by_default():
    defaults = get_section_type_defaults("chapter")
    assert defaults["include_in_analysis"] is True


def test_toc_excluded_by_default():
    defaults = get_section_type_defaults("toc")
    assert defaults["include_in_analysis"] is False


def test_prologue_included_by_default():
    defaults = get_section_type_defaults("prologue")
    assert defaults["include_in_analysis"] is True


def test_epilogue_included_by_default():
    defaults = get_section_type_defaults("epilogue")
    assert defaults["include_in_analysis"] is True


def test_preface_included_by_default():
    defaults = get_section_type_defaults("preface")
    assert defaults["include_in_analysis"] is True


def test_acknowledgements_excluded_by_default():
    defaults = get_section_type_defaults("acknowledgements")
    assert defaults["include_in_analysis"] is False


def test_glossary_excluded_by_default():
    defaults = get_section_type_defaults("glossary")
    assert defaults["include_in_analysis"] is False


def test_unknown_included_by_default():
    defaults = get_section_type_defaults("unknown")
    assert defaults["include_in_analysis"] is True


def test_display_order_chapter_before_epilogue():
    chapter = get_section_type_defaults("chapter")
    epilogue = get_section_type_defaults("epilogue")
    assert chapter["display_order"] < epilogue["display_order"]


def test_display_order_toc_before_chapters():
    toc = get_section_type_defaults("toc")
    chapter = get_section_type_defaults("chapter")
    assert toc["display_order"] < chapter["display_order"]


# ── get_number_words / get_ordinal_words ───────────────────────────────────


def test_get_number_words_english():
    nw = get_number_words("en")
    assert nw["one"] == 1
    assert nw["twenty"] == 20


def test_get_number_words_french():
    nw = get_number_words("fr")
    assert nw["un"] == 1
    assert nw["vingt"] == 20


def test_get_number_words_unknown_language_falls_back():
    nw = get_number_words("xx")
    assert "one" in nw


def test_get_ordinal_words_english():
    ow = get_ordinal_words("en")
    assert ow["first"] == 1
    assert ow["twentieth"] == 20


def test_get_ordinal_words_french():
    ow = get_ordinal_words("fr")
    assert ow["premier"] == 1
    assert ow["vingtieme"] == 20


def test_get_ordinal_words_unknown_language_falls_back():
    ow = get_ordinal_words("xx")
    assert "first" in ow
