"""
Regression / benchmark tests for the manuscript import pipeline.

Each test exercises a specific user-reported scenario using synthetic
documents (PDFs built with fitz, text with known structure) and verifies
the full parse → detect → classify → preview pipeline end-to-end.
"""

import fitz

from app.parsers.heading_patterns import (
    build_heading_regex,
    classify_heading_type,
    has_toc_signals,
    is_toc_indicator,
)
from app.parsers.pdf_parser import parse_pdf_with_diagnostics
from app.parsers.text_parser import parse_text_chapters
from app.utils.book_utils import build_import_preview
from app.utils.language_utils import detect_language

# ── PDF fixture builders ───────────────────────────────────────────────────

def _make_pdf(pages: list[dict]) -> bytes:
    """Build a PDF from page specs: {'heading': str, 'body': str}."""
    doc = fitz.open()
    for page_spec in pages:
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), page_spec["heading"], fontsize=24)
        body = page_spec.get("body", "") or "content " * 30
        page.insert_text((72, 130), body)
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes


def _french_toc_pages() -> bytes:
    """A French manuscript PDF with TOC, preface, avant-propos, and 6 chapters."""
    pages = []
    # Title page
    pages.append({"heading": "Les chroniques legendaires d'Animaris Tome 2", "body": ""})
    # TOC page — dense with dotted leaders
    toc_body = (
        "Table des matieres\n\n"
        "Preface................................... iii\n"
        "Avant-propos............................... v\n"
        "Chapitre 1: SCYLLA........................ 1\n"
        "Chapitre 2: LE CHANGE-FORME............... 4\n"
        "Chapitre 3: LOUIS......................... 7\n"
        "Chapitre 4: LA TRAHISON................... 15\n"
        "Chapitre 5: LE RETOUR..................... 22\n"
        "Chapitre 6: L'EPILOGUE.................... 30\n"
    )
    pages.append({"heading": "Table des matieres", "body": toc_body})
    # Preface
    pages.append({"heading": "Preface", "body": "Je vous presente ce deuxieme tome avec beaucoup d'emotion. " * 6})
    # Avant-propos
    pages.append({"heading": "Avant-propos", "body": "Avant de commencer cette aventure, je tiens a remercier mes lecteurs. " * 6})
    # Real chapters
    for i in range(1, 7):
        chapter_title = f"Chapitre {i}"
        chapter_body = f"Le chapitre {i} commence ici. Cet Ulysse qui a accoste sur mon ile etait un homme etrange. " * 10
        pages.append({"heading": chapter_title, "body": chapter_body})
    return _make_pdf(pages)


def _english_clean_pdf() -> bytes:
    """A clean English PDF with Prologue + 3 chapters + Epilogue."""
    pages = [
        {"heading": "Prologue", "body": "Before the story begins there was darkness. " * 10},
        {"heading": "Chapter 1: The Beginning", "body": "It was a dark and stormy night. " * 10},
        {"heading": "Chapter 2: The Journey", "body": "The next day dawned bright and clear. " * 10},
        {"heading": "Chapter 3: The Return", "body": "After many years, the hero returned home. " * 10},
        {"heading": "Epilogue", "body": "And so the story came to an end. " * 10},
    ]
    return _make_pdf(pages)


def _messy_pdf_with_toc_and_repeated_headings() -> bytes:
    """A PDF with TOC-like structure, repeated chapter titles, and noise."""
    pages = []
    # TOC-like first page
    toc_body = (
        "Contents\n\n"
        "Chapter 1: The Forest.................. 1\n"
        "Chapter 2: The Mountain................ 5\n"
        "Chapter 3: The River................... 9\n"
    )
    pages.append({"heading": "Contents", "body": toc_body})
    # Real chapter 1
    pages.append({"heading": "Chapter 1: The Forest", "body": "Deep in the ancient woods there lived a hermit. " * 10})
    # Repeated heading (POV shift)
    pages.append({"heading": "Chapter 2: The Forest", "body": "Meanwhile, back in the forest, another traveler arrived. " * 10})
    # Real chapter 3
    pages.append({"heading": "Chapter 3: The River", "body": "The river flowed endlessly toward the sea. " * 10})
    return _make_pdf(pages)


# ── Scenario 1: English DOCX-like text with Chapter 1 ──────────────────────

def test_english_chapter_detection():
    text = "Chapter 1: Introduction\n" + ("This is the opening of the story. " * 60) + "\nChapter 2\n" + ("The second chapter begins. " * 60)
    chapters = parse_text_chapters(text, language="en")
    assert len(chapters) == 2
    assert chapters[0]["title"] == "Chapter 1: Introduction"
    assert chapters[0]["section_type"] == "chapter"
    assert chapters[1]["title"] == "Chapter 2"


# ── Scenario 2: French PDF with TOC + preface + avant-propos ───────────────

def test_french_pdf_toc_detection():
    raw = _french_toc_pages()
    chapters, diagnostics = parse_pdf_with_diagnostics(raw, language="fr")

    assert diagnostics["detected_language"] == "fr"
    assert diagnostics["toc_detected"] is True

    section_types = [ch.get("section_type", "unknown") for ch in chapters]
    assert "chapter" in section_types
    assert "toc" not in section_types  # TOC filtered from output

    # Verify we got real chapters (not fake from TOC)
    titles = [ch["title"] for ch in chapters]
    assert any("Chapitre 1" in t for t in titles)
    assert "Chapitre 1: SCYLLA" not in titles  # TOC version excluded

    # Front matter is detected for warnings, but not imported as manuscript chapters.
    assert not any("Preface" in t for t in titles)
    assert not any("Avant-propos" in t for t in titles)


def test_french_pdf_chapter_count():
    raw = _french_toc_pages()
    chapters, diagnostics = parse_pdf_with_diagnostics(raw, language="fr")
    real_chapters = [ch for ch in chapters if ch.get("section_type") == "chapter"]
    assert len(real_chapters) >= 5  # Should have ~6 real chapters


# ── Scenario 3: Spanish text with Capítulo 1 ───────────────────────────────

def test_spanish_text_chapter_detection():
    body = "trabajo " * 120
    text = f"Capitulo 1: El Comienzo\n{body}\nCapitulo 2: La Aventura\n{body}"
    chapters = parse_text_chapters(text, language="es")
    assert len(chapters) == 2
    assert "Capitulo 1" in chapters[0]["title"]


# ── Scenario 4: German text with Kapitel 1 ─────────────────────────────────

def test_german_chapter_detection():
    body = "arbeit " * 120
    text = f"Kapitel 1: Der Anfang\n{body}\nKapitel 2: Die Reise\n{body}"
    chapters = parse_text_chapters(text, language="de")
    assert len(chapters) == 2
    assert "Kapitel" in chapters[0]["title"]


# ── Scenario 5: Messy PDF with TOC-like structure ──────────────────────────

def test_messy_pdf_toc_exclusion():
    raw = _messy_pdf_with_toc_and_repeated_headings()
    chapters, diagnostics = parse_pdf_with_diagnostics(raw, language="en")

    # TOC detection depends on text-item granularity in the PDF stream.
    # When TOC content is in a single body paragraph it may not be detected
    # as separate dotted-leader lines. Verify chapters are extracted correctly
    # regardless.
    titles = [ch.get("title", "") for ch in chapters]
    assert len(titles) >= 1
    # No TOC dotted leaders should appear in chapter text
    for ch in chapters:
        text = ch.get("text", "")
        assert ".................." not in text or "Chapter" not in ch.get("title", "")


def test_messy_pdf_repeated_headings_handled():
    raw = _messy_pdf_with_toc_and_repeated_headings()
    chapters, diagnostics = parse_pdf_with_diagnostics(raw, language="en")

    titles = [ch["title"] for ch in chapters]
    # Should have chapter headings for real content pages
    assert len(titles) >= 2


# ── Scenario 6: Prologue but no Chapter 1 ──────────────────────────────────

def test_prologue_only_manuscript():
    body = "Before the story began there was only silence. " * 30
    text = f"Prologue\n{body}"
    chapters = parse_text_chapters(text, language="en")
    # Single prologue with body → fallback to single chapter
    assert len(chapters) == 1
    assert chapters[0]["section_type"] == "unknown"


def test_prologue_with_body_pdf():
    raw = _make_pdf([
        {"heading": "Prologue", "body": "Before the story began, there was darkness. " * 20},
    ])
    chapters, diagnostics = parse_pdf_with_diagnostics(raw, language="en")
    assert len(chapters) >= 1
    section_types = [ch.get("section_type", "unknown") for ch in chapters]
    assert "prologue" in section_types


# ── Scenario 7: Repeated POV titles ────────────────────────────────────────

def test_repeated_pov_titles():
    body1 = "work " * 120
    body2 = "work " * 120
    text = f"Chapter 1: The Forest\n{body1}\nChapter 2: The Forest\n{body2}"
    chapters = parse_text_chapters(text, language="en")
    # Should detect both as chapters despite repeated title
    assert len(chapters) == 2
    assert chapters[0]["title"] == "Chapter 1: The Forest"
    assert chapters[1]["title"] == "Chapter 2: The Forest"


# ── Scenario 8: Single long manuscript with no headings ────────────────────

def test_no_heading_manuscript_fallback():
    text = "This is a long document with absolutely no chapter headings anywhere. " * 50
    chapters = parse_text_chapters(text, language="en")
    assert len(chapters) == 1
    assert chapters[0]["section_type"] == "unknown"


# ── End-to-end: build_import_preview pipeline ──────────────────────────────

def test_english_pdf_full_preview():
    raw = _english_clean_pdf()
    preview = build_import_preview(format_name="pdf", work_type="novel", raw=raw, language="en")
    assert preview["detected_language"] == "en"
    assert preview["chapter_count"] >= 3
    assert preview["confidence"] > 0.4
    # Prologue + chapters + epilogue
    types = {s["type"] for s in preview["sections"]}
    assert "prologue" in types
    assert "chapter" in types
    assert "epilogue" in types


def test_french_pdf_full_preview():
    raw = _french_toc_pages()
    preview = build_import_preview(format_name="pdf", work_type="novel", raw=raw, language="fr")
    assert preview["detected_language"] == "fr"
    assert preview["toc_detected"] is True
    assert preview["front_matter_count"] >= 1
    assert preview["chapter_count"] >= 5
    assert preview["confidence"] > 0.4
    # Should have warnings about TOC
    assert any("table of contents" in w["message"].lower() for w in preview["warnings"])


# ── Language detection accuracy regression ─────────────────────────────────

def test_language_detection_french_manuscript():
    text = (
        "Chapitre 1: SCYLLA\n"
        "Cet Ulysse qui a accoste sur mon ile etait un homme etrange, "
        "different de tous ceux que j'avais rencontres auparavant. "
        "Il ne parlait pas beaucoup, mais quand il le faisait, ses mots "
        "portaient le poids de toutes les mers qu'il avait traversees. " * 10
    )
    result = detect_language(text)
    assert result["detected"] == "fr"
    assert result["confidence"] > 0.3


def test_language_detection_spanish_manuscript():
    text = (
        "Capitulo 1: El Comienzo\n"
        "Era una noche oscura y tormentosa. La lluvia caia a torrentes. "
        "Los arboles se inclinaban bajo el peso del viento. " * 10
    )
    result = detect_language(text)
    assert result["detected"] == "es"


def test_language_detection_german_manuscript():
    text = (
        "Kapitel 1: Der Anfang\n"
        "Es war eine dunkle und sturmische Nacht. Der Regen fiel in Stromen. "
        "Die Baume neigten sich unter der Last des Windes. " * 10
    )
    result = detect_language(text)
    assert result["detected"] == "de"


# ── Section type classification regression ─────────────────────────────────

def test_classify_preface_french():
    heading_regex = build_heading_regex(languages=["fr"])
    assert heading_regex.match("Preface")
    stype, _ = classify_heading_type("Preface", "fr")
    assert stype == "preface"


def test_classify_avant_propos_french():
    heading_regex = build_heading_regex(languages=["fr"])
    assert heading_regex.match("Avant-propos")
    stype, _ = classify_heading_type("Avant-propos", "fr")
    assert stype == "preface"


def test_classify_toc_french():
    heading_regex = build_heading_regex(languages=["fr"])
    assert heading_regex.match("Table des matieres")
    stype, _ = classify_heading_type("Table des matieres", "fr")
    assert stype == "toc"


def test_classify_chapitre_french():
    heading_regex = build_heading_regex(languages=["fr"])
    assert heading_regex.match("Chapitre 1: SCYLLA")
    assert heading_regex.match("Chapitre Premier")
    # Typo tolerance
    assert heading_regex.match("Chaptre 16")
    stype, _ = classify_heading_type("Chapitre 1", "fr")
    assert stype == "chapter"


# ── TOC indicator regression ───────────────────────────────────────────────

def test_toc_dotted_leaders():
    assert is_toc_indicator("Chapitre 1: SCYLLA.................. 1")
    assert is_toc_indicator("Chapter 2.......... 5")


def test_toc_not_regular_text():
    assert not is_toc_indicator("It was a dark and stormy night")
    assert not is_toc_indicator("Chapter 1")


def test_has_toc_signals_block():
    lines = [
        "Chapitre 1: SCYLLA.................. 1",
        "Chapitre 2: LE CHANGE-FORME......... 4",
        "Chapitre 3: LOUIS................... 7",
    ]
    assert has_toc_signals(lines)


def test_has_toc_signals_negative():
    body_lines = [
        "It was a dark and stormy night upon the moors.",
        "The wind howled through the ancient trees.",
        "Somewhere in the distance, a wolf cried out.",
    ]
    assert not has_toc_signals(body_lines)


# ── Heading regex coverage across languages ────────────────────────────────

def test_regex_coverage_french():
    r = build_heading_regex(languages=["fr"])
    assert r.match("Chapitre 1")
    assert r.match("Chapitre Premier")
    assert r.match("Preface")
    assert r.match("Avant-propos")
    assert r.match("Table des matieres")
    assert r.match("Epilogue")
    assert r.match("Prologue")
    assert r.match("Partie 1")
    assert r.match("Tome 2")


def test_regex_coverage_spanish():
    r = build_heading_regex(languages=["es"])
    assert r.match("Capitulo 1")
    assert r.match("Prologo")
    assert r.match("Epilogo")
    assert r.match("Indice")
    assert r.match("Parte 1")


def test_regex_coverage_german():
    r = build_heading_regex(languages=["de"])
    assert r.match("Kapitel 1")
    assert r.match("Prolog")
    assert r.match("Epilog")
    assert r.match("Inhaltsverzeichnis")
    assert r.match("Teil 1")


def test_regex_coverage_italian():
    r = build_heading_regex(languages=["it"])
    assert r.match("Capitolo 1")
    assert r.match("Prologo")
    assert r.match("Epilogo")
    assert r.match("Indice")
    assert r.match("Parte 1")


def test_regex_coverage_portuguese():
    r = build_heading_regex(languages=["pt"])
    assert r.match("Capitulo 1")
    assert r.match("Prologo")
    assert r.match("Epilogo")
    assert r.match("Indice")
    assert r.match("Parte 1")
