from app.parsers.text_parser import MIN_BODY_WORDS_AFTER_HEADING, parse_text_chapters

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
