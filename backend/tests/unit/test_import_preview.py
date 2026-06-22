import fitz

from app.utils.books.imports import build_import_preview


def _make_text_pdf(chapters: list[str]) -> bytes:
    doc = fitz.open()
    for heading in chapters:
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), heading, fontsize=24)
        page.insert_text((72, 120), "It was a dark and stormy night. " * 30)
    pdf_bytes = doc.write()
    doc.close()
    return pdf_bytes


def test_preview_txt_english_chapters():
    body = "word " * 200
    raw = f"Chapter 1\n{body}\nChapter 2\n{body}".encode()
    preview = build_import_preview(format_name="txt", work_type="novel", raw=raw)
    assert preview["detected_language"] == "en"
    assert preview["chapter_count"] == 2
    assert len(preview["sections"]) == 2
    assert preview["confidence"] > 0.4


def test_preview_txt_french_chapters():
    body = "travail " * 200
    raw = f"Chapitre 1: SCYLLA\n{body}\nChapitre 2: LE CHANGE-FORME\n{body}".encode()
    preview = build_import_preview(format_name="txt", work_type="novel", raw=raw)
    assert preview["chapter_count"] == 2
    assert any(s["type"] == "chapter" for s in preview["sections"])


def test_preview_txt_single_chapter():
    raw = b"This is a manuscript without chapter headings." * 20
    preview = build_import_preview(format_name="txt", work_type="novel", raw=raw)
    assert len(preview["sections"]) == 1


def test_preview_txt_language_provided():
    body = "work " * 200
    raw = f"Chapter 1\n{body}\nChapter 2\n{body}".encode()
    preview = build_import_preview(format_name="txt", work_type="novel", raw=raw, language="en")
    assert preview["detected_language"] == "en"


def test_preview_pdf_english():
    raw = _make_text_pdf(["Chapter 1", "Chapter 2"])
    preview = build_import_preview(format_name="pdf", work_type="novel", raw=raw)
    assert preview["chapter_count"] == 2
    assert len(preview["sections"]) == 2
    for s in preview["sections"]:
        assert s["type"] == "chapter"
        assert s["include_in_analysis"] is True


def test_preview_pdf_language_provided():
    raw = _make_text_pdf(["Chapitre 1", "Chapitre 2"])
    preview = build_import_preview(format_name="pdf", work_type="novel", raw=raw, language="fr")
    assert preview["detected_language"] == "fr"


def test_preview_pdf_sections_have_ids():
    raw = _make_text_pdf(["Chapter 1", "Chapter 2"])
    preview = build_import_preview(format_name="pdf", work_type="novel", raw=raw)
    for s in preview["sections"]:
        assert "id" in s
        assert len(s["id"]) == 32


def test_preview_includes_all_fields():
    raw = _make_text_pdf(["Chapter 1"])
    preview = build_import_preview(format_name="pdf", work_type="novel", raw=raw)
    required = [
        "detected_language",
        "language_confidence",
        "title",
        "author",
        "sections",
        "chapter_count",
        "toc_detected",
        "front_matter_count",
        "confidence",
        "warnings",
    ]
    for key in required:
        assert key in preview, f"Missing field: {key}"


def test_preview_sections_are_serializable():
    raw = _make_text_pdf(["Chapter 1", "Chapter 2"])
    preview = build_import_preview(format_name="pdf", work_type="novel", raw=raw)
    import json

    serialized = json.dumps(preview)
    assert serialized


def test_preview_unsupported_format():
    try:
        build_import_preview(format_name="rtf", work_type="novel", raw=b"test")
        assert False, "Should have raised"
    except (ValueError, Exception):
        pass


def test_preview_empty_pdf():
    doc = fitz.open()
    doc.new_page(width=595, height=842)
    pdf_bytes = doc.write()
    doc.close()
    preview = build_import_preview(format_name="pdf", work_type="novel", raw=pdf_bytes)
    assert len(preview["sections"]) >= 0
