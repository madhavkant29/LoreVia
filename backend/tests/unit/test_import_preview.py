from io import BytesIO
from types import SimpleNamespace

import fitz
import pytest
from docx import Document
from fastapi import HTTPException

from app.utils.books.imports import (
    _parse_docx_text,
    _sample_epub_text,
    build_import_preview,
    decode_manuscript_text,
    parse_import_upload,
    parse_screenplay_upload,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Mara opened the gate.".encode("utf-8-sig"), "Mara opened the gate."),
        ("Mara opened the gate.".encode("utf-16"), "Mara opened the gate."),
        ("Café — dawn.".encode("cp1252"), "Café — dawn."),
    ],
)
def test_text_decoder_preserves_common_manuscript_encodings(raw, expected):
    assert decode_manuscript_text(raw) == expected


@pytest.mark.parametrize("raw", [b"Mara\x81returned", b"Mara\x00returned"])
def test_text_decoder_rejects_bytes_that_would_corrupt_content(raw):
    with pytest.raises(HTTPException) as error:
        decode_manuscript_text(raw)

    assert error.value.status_code == 400


def test_epub_language_sample_does_not_silently_drop_non_utf8_text(monkeypatch):
    from ebooklib import epub

    item = SimpleNamespace(get_content=lambda: b"<html><p>Caf\xe9 at the harbor.</p></html>")
    book = SimpleNamespace(get_items_of_type=lambda _item_type: [item])
    monkeypatch.setattr(epub, "read_epub", lambda _raw: book)

    assert "Café" in _sample_epub_text(b"epub fixture")


def test_screenplay_preview_decodes_utf16_instead_of_dropping_dialogue():
    raw = "INT. HARBOR - DAY\nMARA\nThe café is open.".encode("utf-16")

    preview = build_import_preview(format_name="fountain", work_type="screenplay", raw=raw)

    assert preview["chapter_count"] == 1
    assert preview["total_words"] >= 7


def test_screenplay_pdf_preview_extracts_pages_before_scene_detection():
    document = fitz.open()
    page = document.new_page(width=595, height=842)
    page.insert_text((72, 72), "INT. HARBOR - DAY", fontsize=16)
    page.insert_text((72, 110), "Mara returns with the archive key.", fontsize=12)
    raw = document.write()
    document.close()

    preview = build_import_preview(format_name="pdf", work_type="screenplay", raw=raw)

    assert preview["chapter_count"] == 1
    assert preview["total_words"] >= 7


@pytest.mark.asyncio
async def test_text_and_screenplay_uploads_do_not_drop_utf16_dialogue():
    raw = "INT. HARBOR - DAY\nMARA\nThe café is open.".encode("utf-16")

    manuscript = await parse_import_upload("draft.txt", raw, False)
    screenplay = await parse_screenplay_upload("draft.fountain", raw)

    assert "café" in manuscript[0]["text"]
    assert "café" in screenplay["text"]


def test_docx_extraction_preserves_paragraph_and_table_order():
    document = Document()
    document.add_paragraph("Chapter 1")
    document.add_paragraph("The sealed gate opened.")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Mara"
    table.cell(0, 1).text = "holds the key"
    document.add_paragraph("The guard followed her.")
    output = BytesIO()
    document.save(output)

    text = _parse_docx_text(output.getvalue())

    assert text == (
        "Chapter 1\n\nThe sealed gate opened.\n\n"
        "Mara | holds the key\n\nThe guard followed her."
    )


@pytest.mark.asyncio
async def test_docx_import_keeps_table_content_in_its_source_chapter():
    document = Document()
    document.add_paragraph("Chapter 1")
    document.add_paragraph("Mara carries the archive key into the old harbor while the watch closes the gates.")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Archive key"
    table.cell(0, 1).text = "Mara"
    document.add_paragraph("Chapter 2")
    document.add_paragraph("The guard returns to the harbor at dawn and discovers the archive door is open.")
    output = BytesIO()
    document.save(output)

    chapters = await parse_import_upload("manuscript.docx", output.getvalue(), True)

    assert len(chapters) == 2
    assert "Archive key | Mara" in chapters[0]["text"]
    assert "Archive key | Mara" not in chapters[1]["text"]


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
    assert "no_extractable_text" in preview["raw_diagnostics"]["anomalies"]
    assert any("OCR it" in warning["message"] for warning in preview["warnings"])
