import uuid
from types import SimpleNamespace

import pytest

from app.services import extraction_book_processing_service


@pytest.mark.asyncio
async def test_ensure_ingested_book_cover_generates_blank_cover_for_non_pdf(monkeypatch):
    uploaded: dict[str, object] = {}
    book = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="A New Draft",
        author="Mira Vale",
        format="txt",
        cover_s3_key=None,
    )

    monkeypatch.setattr(
        extraction_book_processing_service,
        "build_blank_cover_image",
        lambda title, author: (f"{title}:{author}".encode(), "image/png"),
    )

    def _upload_binary(key: str, raw: bytes, content_type: str) -> str:
        uploaded["payload"] = (key, raw, content_type)
        return key

    monkeypatch.setattr(extraction_book_processing_service, "upload_binary", _upload_binary)

    generated = await extraction_book_processing_service.ensure_ingested_book_cover(book, b"body")

    assert generated is True
    assert book.cover_s3_key == uploaded["payload"][0]
    assert uploaded["payload"][1] == b"A New Draft:Mira Vale"
    assert uploaded["payload"][2] == "image/png"


@pytest.mark.asyncio
async def test_ensure_ingested_book_cover_prefers_extracted_pdf_cover(monkeypatch):
    uploaded: dict[str, object] = {}
    book = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="PDF Draft",
        author="Mira Vale",
        format="pdf",
        cover_s3_key=None,
    )

    monkeypatch.setattr(
        "app.parsers.pdf_parser.extract_first_page_cover",
        lambda raw: (raw[:5], "image/png"),
    )
    monkeypatch.setattr(
        extraction_book_processing_service,
        "build_blank_cover_image",
        lambda *_args: (_ for _ in ()).throw(AssertionError("blank cover should not run")),
    )

    def _upload_binary(key: str, raw: bytes, content_type: str) -> str:
        uploaded["payload"] = (key, raw, content_type)
        return key

    monkeypatch.setattr(extraction_book_processing_service, "upload_binary", _upload_binary)

    generated = await extraction_book_processing_service.ensure_ingested_book_cover(
        book, b"pdf-cover-bytes"
    )

    assert generated is True
    assert book.cover_s3_key == uploaded["payload"][0]
    assert uploaded["payload"][1] == b"pdf-c"


@pytest.mark.asyncio
async def test_ensure_ingested_book_cover_does_not_replace_existing_cover(monkeypatch):
    book = SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        title="Existing",
        author="Mira Vale",
        format="txt",
        cover_s3_key="covers/existing.png",
    )

    monkeypatch.setattr(
        extraction_book_processing_service,
        "build_blank_cover_image",
        lambda *_args: (_ for _ in ()).throw(AssertionError("blank cover should not run")),
    )

    generated = await extraction_book_processing_service.ensure_ingested_book_cover(book, b"body")

    assert generated is False
    assert book.cover_s3_key == "covers/existing.png"
