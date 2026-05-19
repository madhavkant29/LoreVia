from __future__ import annotations

import io
import zipfile

import pytest
from fastapi import HTTPException, UploadFile

from app.utils.upload_security_utils import (
    read_upload_bounded,
    validate_cover_magic,
    validate_document_upload_bytes,
    validate_zip_archive_safety,
)


def _upload(name: str, raw: bytes) -> UploadFile:
    return UploadFile(filename=name, file=io.BytesIO(raw))


def _minimal_docx_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", "<w:document><w:body><w:p><w:r><w:t>hello</w:t></w:r></w:p></w:body></w:document>")
    return buffer.getvalue()


def _minimal_epub_bytes() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("mimetype", b"application/epub+zip", compress_type=zipfile.ZIP_STORED)
        archive.writestr("META-INF/container.xml", "<container/>")
    return buffer.getvalue()


@pytest.mark.asyncio
async def test_read_upload_bounded_enforces_size_limit():
    upload = _upload("story.txt", b"hello world")
    assert await read_upload_bounded(upload, 32, "Book file") == b"hello world"

    oversized = _upload("big.txt", b"x" * 9)
    with pytest.raises(HTTPException) as exc_info:
        await read_upload_bounded(oversized, 4, "Book file")

    assert exc_info.value.status_code == 413


def test_validate_cover_magic_accepts_supported_images():
    assert validate_cover_magic(b"\xff\xd8\xffpayload")[0] == "jpg"
    assert validate_cover_magic(b"RIFF1234WEBPrest")[0] == "webp"

    with pytest.raises(HTTPException) as exc_info:
        validate_cover_magic(b"<svg></svg>")

    assert exc_info.value.status_code == 400


@pytest.mark.parametrize(
    ("filename", "raw", "format_name"),
    [
        ("story.pdf", b"%PDF-1.7\nbody\n%%EOF", "pdf"),
        ("story.docx", _minimal_docx_bytes(), "docx"),
        ("story.epub", _minimal_epub_bytes(), "epub"),
        ("story.doc", b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1payload", "doc"),
        ("story.txt", b"chapter one", "txt"),
    ],
)
def test_validate_document_upload_bytes_accepts_expected_content(filename: str, raw: bytes, format_name: str):
    validate_document_upload_bytes(filename, raw, format_name)


def test_validate_document_upload_bytes_rejects_disguised_pdf():
    with pytest.raises(HTTPException) as exc_info:
        validate_document_upload_bytes("story.pdf", b"<html>not pdf</html>", "pdf")

    assert exc_info.value.status_code == 400


def test_validate_document_upload_bytes_rejects_invalid_zip_based_document():
    with pytest.raises(HTTPException) as exc_info:
        validate_document_upload_bytes("story.docx", b"not-a-zip", "docx")

    assert exc_info.value.status_code == 400


def test_validate_zip_archive_safety_rejects_zip_bomb_characteristics():
    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("huge.md", b"A" * 5000)

    with pytest.raises(HTTPException) as exc_info:
        validate_zip_archive_safety(
            archive_buffer.getvalue(),
            max_entries=10,
            max_total_uncompressed_bytes=10000,
            max_compression_ratio=2,
            label="ZIP file",
        )

    assert exc_info.value.status_code == 400
