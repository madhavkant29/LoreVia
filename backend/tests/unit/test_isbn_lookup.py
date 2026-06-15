from __future__ import annotations

import pytest

from app.utils.external import isbn_lookup


class _FakePage:
    def __init__(self, text: str):
        self._text = text

    def get_text(self):
        return self._text


class _FakeDoc:
    def __init__(self, pages: list[str]):
        self._pages = [_FakePage(text) for text in pages]
        self.closed = False

    def __len__(self):
        return len(self._pages)

    def __getitem__(self, index: int):
        return self._pages[index]

    def close(self):
        self.closed = True


def test_extract_isbn_from_pdf_normalizes_hyphenated_isbn(monkeypatch):
    doc = _FakeDoc(["copyright page\nISBN 978-1-4028-9462-6"])

    def _open(*_args, **_kwargs):
        return doc

    monkeypatch.setattr(isbn_lookup.fitz, "open", _open)

    assert isbn_lookup.extract_isbn_from_pdf(b"%PDF fake") == "9781402894626"
    assert doc.closed is True


def test_extract_isbn_from_pdf_checks_only_front_matter_pages(monkeypatch):
    doc = _FakeDoc([
        "title page",
        "copyright without identifier",
        "dedication",
        "chapter one ISBN 978-1-4028-9462-6",
    ])

    def _open(*_args, **_kwargs):
        return doc

    monkeypatch.setattr(isbn_lookup.fitz, "open", _open)

    assert isbn_lookup.extract_isbn_from_pdf(b"%PDF fake") is None
    assert doc.closed is True


def test_extract_isbn_from_pdf_returns_none_when_pdf_cannot_be_read(monkeypatch):
    def _open(*_args, **_kwargs):
        raise RuntimeError("not a pdf")

    monkeypatch.setattr(isbn_lookup.fitz, "open", _open)

    assert isbn_lookup.extract_isbn_from_pdf(b"not a pdf") is None
