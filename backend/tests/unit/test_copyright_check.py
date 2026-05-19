from __future__ import annotations

import io
import zipfile

import pytest

from app.utils.compliance.copyright_check import (
    evaluate_document_copyright,
    extract_document_text_for_copyright_checks,
    extract_isbn_from_text,
    normalize_isbn,
)


def test_normalize_isbn_rejects_invalid_values():
    assert normalize_isbn("978-0-306-40615-7") == "9780306406157"
    assert normalize_isbn("0-306-40615-2") == "0306406152"
    assert normalize_isbn("1234567890123") is None


def test_extract_isbn_from_text_finds_valid_candidate():
    text = "Front matter ISBN 978-0-306-40615-7 all rights reserved."
    assert extract_isbn_from_text(text) == "9780306406157"


def test_extract_document_text_for_docx_reads_zip_payload():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", "<w:p>ISBN 978-0-306-40615-7</w:p>")

    text = extract_document_text_for_copyright_checks("docx", buffer.getvalue())
    assert "978-0-306-40615-7" in text


@pytest.mark.asyncio
async def test_evaluate_document_copyright_flags_isbn_even_when_registry_misses(monkeypatch):
    async def _fake_check_isbn(_isbn: str) -> dict:
        return {"found": False}

    monkeypatch.setattr("app.utils.compliance.copyright_check.check_isbn", _fake_check_isbn)

    result = await evaluate_document_copyright(
        format_name="txt",
        raw=b"ISBN 978-0-306-40615-7\nSample title page",
    )

    assert result["isbn"] == "9780306406157"
    assert result["copyright_warning"] is True
    assert result["registry_hit"] is False


@pytest.mark.asyncio
async def test_evaluate_document_copyright_ignores_public_domain_marker(monkeypatch):
    async def _fake_check_isbn(_isbn: str) -> dict:
        return {"found": False}

    monkeypatch.setattr("app.utils.compliance.copyright_check.check_isbn", _fake_check_isbn)

    result = await evaluate_document_copyright(
        format_name="txt",
        raw=b"Project Gutenberg release. This ebook is in the public domain.",
    )

    assert result["isbn"] is None
    assert result["copyright_warning"] is False
