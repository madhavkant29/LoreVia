from app.parsers.text_parser import (
    MIN_BODY_WORDS_AFTER_HEADING,
    _extract_clean_heading,
    parse_text_chapters,
)

# ── Basic splitting ────────────────────────────────────────────────────────


def test_parse_english_chapters():
    body = "work " * 120
    text = f"Chapter 1\n{body}\n\nChapter 2\n{body}\n\nChapter 3\n{body}"
    chapters = parse_text_chapters(text, language="en")
    assert len(chapters) == 3
    assert chapters[0]["title"] == "Chapter 1"
    assert chapters[0]["section_type"] == "chapter"
    assert chapters[1]["title"] == "Chapter 2"
    assert chapters[2]["title"] == "Chapter 3"


def test_parse_french_chapters():
    body = "travail " * 120
    text = f"Chapitre 1: SCYLLA\n{body}\n\nChapitre 2: LE CHANGE-FORME\n{body}"
    chapters = parse_text_chapters(text, language="fr")
    assert len(chapters) == 2
    assert chapters[0]["title"] == "Chapitre 1: SCYLLA"
    assert chapters[0]["section_type"] == "chapter"
    assert chapters[1]["title"] == "Chapitre 2: LE CHANGE-FORME"


def test_parse_spanish_chapters():
    body = "trabajo " * 120
    text = f"Capitulo 1\n{body}\n\nCapitulo 2\n{body}"
    chapters = parse_text_chapters(text, language="es")
    assert len(chapters) == 2
    assert chapters[0]["title"] == "Capitulo 1"


def test_parse_german_chapters():
    body = "arbeit " * 120
    text = f"Kapitel 1\n{body}\n\nKapitel 2\n{body}"
    chapters = parse_text_chapters(text, language="de")
    assert len(chapters) == 2
    assert chapters[0]["title"] == "Kapitel 1"


def test_parse_italian_chapters():
    body = "lavoro " * 120
    text = f"Capitolo 1\n{body}\n\nCapitolo 2\n{body}"
    chapters = parse_text_chapters(text, language="it")
    assert len(chapters) == 2


def test_parse_portuguese_chapters():
    body = "trabalho " * 120
    text = f"Capitulo 1\n{body}\n\nCapitulo 2\n{body}"
    chapters = parse_text_chapters(text, language="pt")
    assert len(chapters) == 2


# ── Section type classification ────────────────────────────────────────────


def test_classifies_prologue():
    body = "content " * 120
    text = f"Prologue\n{body}\n\nChapter 1\n{body}"
    chapters = parse_text_chapters(text, language="en")
    assert len(chapters) == 2
    assert chapters[0]["section_type"] == "prologue"
    assert chapters[1]["section_type"] == "chapter"


def test_classifies_epilogue():
    body = "content " * 120
    text = f"Chapter 1\n{body}\n\nEpilogue\n{body}"
    chapters = parse_text_chapters(text, language="en")
    assert len(chapters) == 2
    assert chapters[1]["section_type"] == "epilogue"


def test_classifies_preface():
    body = "content " * 120
    text = f"Preface\n{body}\n\nChapter 1\n{body}"
    chapters = parse_text_chapters(text, language="en")
    assert len(chapters) == 2
    assert chapters[0]["section_type"] == "preface"


# ── Fallback behavior ──────────────────────────────────────────────────────


def test_single_chapter_fallback_no_headings():
    text = "This is just a regular document with no chapter headings at all." * 10
    chapters = parse_text_chapters(text, language="en")
    assert len(chapters) == 1
    assert chapters[0]["number"] == 1


def test_single_chapter_fallback_insufficient_body():
    body = "short text"
    text = f"Chapter 1\n{body}\n\nChapter 2\n{body}"
    chapters = parse_text_chapters(text, language="en")
    assert len(chapters) == 1


def test_single_chapter_fallback_one_heading_only():
    body = "content " * 120
    text = f"Chapter 1\n{body}"
    chapters = parse_text_chapters(text, language="en")
    assert len(chapters) == 1


# ── TOC exclusion ──────────────────────────────────────────────────────────


def test_skips_toc_entries():
    body = "content " * 120
    text = (
        "Table of Contents\n"
        "Chapitre 1: A Long Chapter Title Here    1\n"
        "Chapitre 2: Another Long Chapter Title   5\n"
        "Chapitre 3: A Third Chapter Title Here  12\n"
        "\n"
        f"Chapitre 1: A Long Chapter Title Here\n{body}\n\n"
        f"Chapitre 2: Another Long Chapter Title\n{body}\n\n"
        f"Chapitre 3: A Third Chapter Title Here\n{body}"
    )
    chapters = parse_text_chapters(text, language="fr")
    assert len(chapters) == 3
    for ch in chapters:
        assert ch["section_type"] == "chapter"


def test_toc_with_dotted_leaders_is_skipped():
    body = "content " * 120
    text = (
        "Chapter 1: SCYLLA.................. 1\n"
        "Chapter 2: LE CHANGE-FORME......... 4\n"
        "\n"
        f"Chapter 1: SCYLLA\n{body}\n\n"
        f"Chapter 2: LE CHANGE-FORME\n{body}"
    )
    chapters = parse_text_chapters(text, language="en")
    assert len(chapters) == 2


# ── Auto language detection ────────────────────────────────────────────────


def test_auto_detects_language():
    body = "travail " * 120
    text = f"Chapitre 1: Introduction\n{body}\n\nChapitre 2: Suite\n{body}"
    chapters = parse_text_chapters(text)
    assert len(chapters) == 2
    assert chapters[0]["title"] == "Chapitre 1: Introduction"


def test_auto_detects_english():
    body = "work " * 120
    text = f"Chapter 1\n{body}\n\nChapter 2\n{body}"
    chapters = parse_text_chapters(text)
    assert len(chapters) == 2


# ── Edge cases ─────────────────────────────────────────────────────────────


def test_empty_text():
    chapters = parse_text_chapters("")
    assert len(chapters) == 1
    assert chapters[0]["text"] == ""


def test_whitespace_only_text():
    chapters = parse_text_chapters("   \n\n   ")
    assert len(chapters) == 1


def test_chapter_text_preserved():
    body = "This is the body of the first chapter."
    text = f"Chapter 1\n{body}\n\nChapter 2\n"
    chapters = parse_text_chapters(text, language="en")
    assert len(chapters) == 1  # Chapter 2 has no body → fallback
    assert chapters[0]["text"] == text.rstrip()


def test_custom_title():
    text = "Just text without any headings at all."
    chapters = parse_text_chapters(text, title="My Manuscript")
    assert chapters[0]["title"] == "My Manuscript"
    assert chapters[0]["number"] == 1


def test_typo_tolerant_french():
    body = "travail " * 120
    text = f"Chaptre 1\n{body}\n\nChaptre 2\n{body}"
    chapters = parse_text_chapters(text, language="fr")
    assert len(chapters) == 2
    assert chapters[0]["title"] == "Chaptre 1"


def test_numbering_is_sequential():
    body = "content " * 120
    text = f"Part 1\n{body}\n\nChapter 2\n{body}\n\nChapter 3\n{body}"
    chapters = parse_text_chapters(text, language="en")
    for i, ch in enumerate(chapters):
        assert ch["number"] == i + 1


# ── Chapter text integrity ─────────────────────────────────────────────────


def test_chapter_text_excludes_heading():
    body = "The body text starts here."
    text = f"Chapter 1: The Beginning\n{body}"
    chapters = parse_text_chapters(text, language="en")
    assert len(chapters) == 1  # only one heading with body → fallback
    # The full text should be returned
    assert body in chapters[0]["text"]


def test_chapter_boundary_preserves_blank_lines():
    body = "word " * 120
    text = f"Chapter 1\n\n{body}\n\n\nChapter 2\n\n{body}"
    chapters = parse_text_chapters(text, language="en")
    assert len(chapters) == 2
    assert chapters[0]["text"].startswith("word")
    assert chapters[1]["text"].startswith("word")


# ── MIN_BODY_WORDS_AFTER_HEADING constant ──────────────────────────────────


def test_min_body_words_constant():
    assert MIN_BODY_WORDS_AFTER_HEADING > 0
    assert MIN_BODY_WORDS_AFTER_HEADING < 1000


# ── Title truncation (body text merged onto heading line) ──────────────────


def test_clean_title_unchanged():
    """A clean heading line with no body text remains intact."""
    title, extra = _extract_clean_heading("Chapter 1")
    assert title == "Chapter 1"
    assert extra == ""


def test_clean_title_with_separator_unchanged():
    """A heading with a separator and short title stays as-is."""
    title, extra = _extract_clean_heading("Chapter 1: The Beginning")
    assert title == "Chapter 1: The Beginning"
    assert extra == ""


def test_clean_title_with_period_separator_unchanged():
    title, extra = _extract_clean_heading("Chapter 1. The Beginning")
    assert title == "Chapter 1. The Beginning"
    assert extra == ""


def test_clean_dash_separator_unchanged():
    title, extra = _extract_clean_heading("Chapter 1 - The Beginning")
    assert title == "Chapter 1 - The Beginning"
    assert extra == ""


def test_truncates_body_text_at_date_pattern():
    """Body text starting with a date ('5 May') after the title is stripped."""
    title, extra = _extract_clean_heading(
        "CHAPTER II.—JONATHAN HARKERS JOURNAL continued 5 May.—I must have "
        "been asleep for certainly if I had been fully awake"
    )
    assert "5 May" not in title
    assert title == "CHAPTER II.—JONATHAN HARKERS JOURNAL continued"
    assert extra.startswith("5 May")


def test_truncates_body_text_with_day_first_date():
    title, extra = _extract_clean_heading(
        "CHAPTER 3.—MINA HARKER'S JOURNAL continued 3 June.—It was a dark and stormy night"
    )
    assert "3 June" not in title
    assert "June" in extra
    assert title == "CHAPTER 3.—MINA HARKER'S JOURNAL continued"


def test_short_title_within_word_limit_stays():
    """A multi-word title within MAX_TITLE_WORDS is kept whole."""
    title, extra = _extract_clean_heading("Chapter 5: A Very Long Descriptive Title About Dragons")
    assert title == "Chapter 5: A Very Long Descriptive Title About Dragons"
    assert extra == ""


def test_body_text_recovered_in_chapter():
    """Body text on the heading line is prepended to the chapter body."""
    body = "had been awake I must have noticed." + " work " * 120
    heading = "CHAPTER II.—JONATHAN HARKERS JOURNAL continued 5 May.—I must have been asleep for certainly if I"
    text = f"{heading}\n{body}\n\nCHAPTER III\n{'text ' * 120}"
    chapters = parse_text_chapters(text, language="en")
    assert len(chapters) == 2
    # The body text that was on the heading line should be in the chapter body
    assert chapters[0]["text"].startswith("5 May")
    assert "I must have been asleep" in chapters[0]["text"]


def test_no_date_truncates_at_word_limit():
    """Without a date pattern, over-long titles are truncated at word limit."""
    long_title = " ".join(f"word{i}" for i in range(20))
    title, extra = _extract_clean_heading(f"Chapter 10: {long_title}")
    # Should truncate to MAX_TITLE_WORDS (12) words after the separator
    words_after_sep = title.split(": ", 1)[1].split()
    assert len(words_after_sep) <= 12
    assert extra  # has leftover body text


def test_no_separator_returns_base_heading():
    """When no separator follows the heading number, rest is treated as body."""
    title, extra = _extract_clean_heading("CHAPTER II JONATHAN HARKER'S JOURNAL continued 5 May")
    assert title == "CHAPTER II"
    assert "JONATHAN" in extra
