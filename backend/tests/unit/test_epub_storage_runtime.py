from __future__ import annotations

import io
from types import SimpleNamespace

import ebooklib
import pytest
from bs4 import BeautifulSoup
from ebooklib import epub

from app.core import storage
from app.parsers import epub_parser

REAL_UPLOAD_BOOK = storage.upload_book
REAL_UPLOAD_BOOK_BYTES = storage.upload_book_bytes
REAL_UPLOAD_BINARY = storage.upload_binary
REAL_UPLOAD_TEXT = storage.upload_text
REAL_DOWNLOAD_BOOK = storage.download_book
REAL_LIST_OBJECT_KEYS = storage.list_object_keys


def restore_storage_functions(monkeypatch):
    monkeypatch.setattr(storage, "upload_book", REAL_UPLOAD_BOOK)
    monkeypatch.setattr(storage, "upload_book_bytes", REAL_UPLOAD_BOOK_BYTES)
    monkeypatch.setattr(storage, "upload_binary", REAL_UPLOAD_BINARY)
    monkeypatch.setattr(storage, "upload_text", REAL_UPLOAD_TEXT)
    monkeypatch.setattr(storage, "download_book", REAL_DOWNLOAD_BOOK)
    monkeypatch.setattr(storage, "list_object_keys", REAL_LIST_OBJECT_KEYS)


class FakeEpubItem:
    def __init__(self, content: bytes, item_type: int = ebooklib.ITEM_DOCUMENT):
        self._content = content
        self._item_type = item_type

    def get_type(self):
        return self._item_type

    def get_content(self):
        return self._content


def test_parse_epub_extracts_documents_removes_assets_and_skips_short_items(monkeypatch):
    long_text = " ".join(["Mara opened the sealed gate."] * 25)
    fake_book = SimpleNamespace(
        get_items=lambda: [
            FakeEpubItem(b"cover", item_type=ebooklib.ITEM_COVER),
            FakeEpubItem(
                b"<html><h1>Chapter 12: The Gate</h1><script>bad()</script><style>.x{}</style><img src='x'>tiny</html>"
            ),
            FakeEpubItem(
                f"<html><h2>Chapter 12: The Gate</h2><p>{long_text}</p><p>\u2726 The key turned.</p></html>".encode()
            ),
            FakeEpubItem(f"<html><p>{long_text}</p></html>".encode()),
        ]
    )
    monkeypatch.setattr(epub_parser.epub, "read_epub", lambda path: fake_book)

    chapters = epub_parser.parse_epub(b"fake epub bytes", split_large_chapters=False)

    assert len(chapters) == 2
    assert chapters[0]["title"] == "Chapter 12: The Gate"
    assert chapters[0]["source_number"] == 12
    assert "bad()" not in chapters[0]["text"]
    assert "\u2726" not in chapters[0]["text"]
    assert chapters[1]["title"] == "Chapter 2"
    assert [chapter["number"] for chapter in chapters] == [1, 2]


def test_parse_epub_uses_spine_order_and_keeps_short_real_chapters_and_paragraphs(monkeypatch):
    first = FakeEpubItem(
        b"<html><h1>Chapter 1</h1><p>Mara <em>keeps</em> the key near the gate.</p>"
        b"<p>The guard notices the empty lock.</p></html>"
    )
    second = FakeEpubItem(b"<html><h1>Chapter 2</h1><p>The gate opens before sunrise.</p></html>")
    fake_book = SimpleNamespace(
        spine=[("first", "yes"), ("second", "yes")],
        get_item_with_id=lambda item_id: {"first": first, "second": second}[item_id],
        get_items=lambda: [second, first],
    )
    monkeypatch.setattr(epub_parser.epub, "read_epub", lambda path: fake_book)

    chapters = epub_parser.parse_epub(b"fake epub bytes", split_large_chapters=False)

    assert [chapter["title"] for chapter in chapters] == ["Chapter 1", "Chapter 2"]
    assert "Mara keeps the key" in chapters[0]["text"]
    assert "gate.\n\nThe guard" in chapters[0]["text"]
    assert "The gate opens before sunrise." in chapters[1]["text"]


def test_parse_epub_splits_multiple_chapters_in_one_spine_document(monkeypatch):
    first = "Mara keeps the archive key while the watchman circles the gate. " * 4
    second = "The watchman returns and sees that the key is missing. " * 4
    fake_book = SimpleNamespace(
        get_items=lambda: [
            FakeEpubItem(
                f"<html><h1>Chapter 1</h1><p>{first}</p><h1>Chapter 2</h1><p>{second}</p></html>".encode()
            )
        ]
    )
    monkeypatch.setattr(epub_parser.epub, "read_epub", lambda path: fake_book)

    chapters = epub_parser.parse_epub(b"fake epub bytes", split_large_chapters=False)

    assert [chapter["title"] for chapter in chapters] == ["Chapter 1", "Chapter 2"]
    assert first.strip() in chapters[0]["text"]
    assert second.strip() in chapters[1]["text"]
    assert second.strip() not in chapters[0]["text"]


def test_epub_block_extraction_keeps_div_and_section_prose_in_order(monkeypatch):
    html = (
        "<html><body><h2>Chapter 1</h2>"
        "<div>Mara <em>keeps</em> the key near the gate.</div>"
        "<section><p>The guard sees the empty lock.</p>"
        "<div>The alarm rings before dawn.</div></section></body></html>"
    )
    assert epub_parser._extract_epub_blocks(BeautifulSoup(html, "html.parser")) == [
        "Chapter 1",
        "Mara keeps the key near the gate.",
        "The guard sees the empty lock.",
        "The alarm rings before dawn.",
    ]
    monkeypatch.setattr(
        epub_parser.epub,
        "read_epub",
        lambda path: SimpleNamespace(get_items=lambda: [FakeEpubItem(html.encode())]),
    )

    chapters = epub_parser.parse_epub(b"fake epub bytes", split_large_chapters=False)

    assert len(chapters) == 1
    assert chapters[0]["title"] == "Chapter 1"
    assert "The alarm rings before dawn." in chapters[0]["text"]


def test_epub_block_extraction_preserves_inline_word_boundaries():
    html = "<body><p>Un<em>break</em>able words and <strong>emphasis</strong>.</p></body>"

    assert epub_parser._extract_epub_blocks(BeautifulSoup(html, "html.parser")) == [
        "Unbreakable words and emphasis."
    ]


def test_parse_real_epub_obeys_spine_order_and_preserves_inline_text(tmp_path):
    book = epub.EpubBook()
    book.set_identifier("lorevia-spine-order-test")
    book.set_title("Spine Order Test")
    book.set_language("en")
    first = epub.EpubHtml(title="Chapter 1", file_name="first.xhtml", lang="en")
    first.content = (
        "<html><body><h1>Chapter 1</h1><p>Un<em>break</em>able proof appears.</p></body></html>"
    )
    second = epub.EpubHtml(title="Chapter 2", file_name="second.xhtml", lang="en")
    second.content = "<html><body><h1>Chapter 2</h1><p>The answer follows.</p></body></html>"
    book.add_item(second)
    book.add_item(first)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.toc = (first, second)
    book.spine = [first, second]
    path = tmp_path / "spine-order.epub"
    epub.write_epub(str(path), book)

    chapters = epub_parser.parse_epub(path.read_bytes(), split_large_chapters=False)

    assert [chapter["title"] for chapter in chapters] == ["Chapter 1", "Chapter 2"]
    assert "Unbreakable proof appears." in chapters[0]["text"]
    assert "The answer follows." in chapters[1]["text"]


def test_epub_keeps_a_very_short_chapter_with_an_explicit_chapter_heading(monkeypatch):
    fake_book = SimpleNamespace(
        get_items=lambda: [FakeEpubItem(b"<html><h1>Chapter 3</h1><p>She vanished.</p></html>")]
    )
    monkeypatch.setattr(epub_parser.epub, "read_epub", lambda path: fake_book)

    chapters = epub_parser.parse_epub(b"fake epub bytes", split_large_chapters=False)

    assert len(chapters) == 1
    assert chapters[0]["source_number"] == 3
    assert "She vanished." in chapters[0]["text"]


def test_epub_keeps_a_one_word_chapter_with_an_explicit_heading(monkeypatch):
    fake_book = SimpleNamespace(
        get_items=lambda: [FakeEpubItem(b"<html><h1>Chapter 4</h1><p>No.</p></html>")]
    )
    monkeypatch.setattr(epub_parser.epub, "read_epub", lambda path: fake_book)

    chapters = epub_parser.parse_epub(b"fake epub bytes", split_large_chapters=False)

    assert len(chapters) == 1
    assert chapters[0]["source_number"] == 4
    assert "No." in chapters[0]["text"]


def test_epub_split_helpers_split_only_at_sentence_boundaries(monkeypatch):
    monkeypatch.setattr(epub_parser, "PARAGRAPH_SPLIT_TARGET_WORDS", 5)
    chapters = [
        {
            "number": 8,
            "title": "Long chapter",
            "text": "One two three.\n\nFour five six.\n\nSeven eight nine.",
            "source_number": 8,
        }
    ]

    split = epub_parser._split_large_chapters(chapters, split_large_chapters=True)
    unsplit = epub_parser._split_large_chapters(chapters, split_large_chapters=False)

    assert [part["title"] for part in split] == [
        "Long chapter - Part 1",
        "Long chapter - Part 2",
        "Long chapter - Part 3",
    ]
    assert all(part["source_number"] is None for part in split)
    assert unsplit == [
        {
            "number": 1,
            "title": "Long chapter",
            "text": "One two three.\n\nFour five six.\n\nSeven eight nine.",
            "source_number": 8,
        }
    ]
    assert epub_parser._split_parts([]) == []
    assert epub_parser._can_close_section(["unfinished clause"]) is False
    assert epub_parser._can_close_section(['Finished sentence!"']) is True


def test_local_storage_round_trip_move_delete_and_permissions(monkeypatch, tmp_path):
    restore_storage_functions(monkeypatch)
    monkeypatch.setattr(storage.settings, "S3_ENDPOINT_URL", tmp_path.as_uri())
    monkeypatch.setattr(storage.settings, "S3_BUCKET", "bucket")

    book_key = storage.upload_book(io.BytesIO(b"book"), "user-1", "../novel.epub")
    bytes_key = storage.upload_book_bytes(b"bytes", "user-1", "draft.txt")
    assert book_key.endswith("/novel.epub")
    assert bytes_key.endswith("/draft.txt")
    assert storage.download_book(book_key) == b"book"
    assert storage.download_book(bytes_key) == b"bytes"

    assert (
        storage.upload_binary("assets/image.bin", b"binary", "application/octet-stream")
        == "assets/image.bin"
    )
    assert storage.upload_text("notes/note.txt", "hello") == "notes/note.txt"
    assert storage.download_book("assets/image.bin") == b"binary"
    assert storage.download_book("notes/note.txt") == b"hello"
    assert storage.get_presigned_url("assets/image.bin") is None
    assert storage.list_object_keys("assets") == ["assets/image.bin"]
    assert storage.list_object_keys("notes", limit=1) == ["notes/note.txt"]
    assert storage.list_object_keys("missing") == []

    assert storage.move_object("assets/image.bin", "archive/image.bin") == "archive/image.bin"
    assert storage.download_book("archive/image.bin") == b"binary"
    assert storage.move_object("archive/image.bin", "archive/image.bin") == "archive/image.bin"
    storage.delete_object("archive/image.bin")
    storage.delete_object("archive/missing.bin")
    assert not storage._local_path("archive/image.bin").exists()

    touched = []
    monkeypatch.setattr(storage.os, "geteuid", lambda: 0)
    monkeypatch.setattr(storage, "_storage_owner_ids", lambda: (10001, 10001))
    monkeypatch.setattr(
        storage,
        "_apply_local_storage_permissions",
        lambda path, uid, gid: touched.append((path, uid, gid)),
    )
    storage.ensure_local_storage_permissions()
    assert any(path.name == "note.txt" for path, _, _ in touched)


@pytest.mark.parametrize(
    "key",
    (
        "",
        "/absolute/path.txt",
        "../escape.txt",
        "safe/../escape.txt",
        "safe\\.\\escape.txt",
        "safe//empty.txt",
        "safe/\x00/nul.txt",
    ),
)
def test_storage_key_validation_rejects_unsafe_paths(monkeypatch, tmp_path, key):
    restore_storage_functions(monkeypatch)
    monkeypatch.setattr(storage.settings, "S3_ENDPOINT_URL", tmp_path.as_uri())
    monkeypatch.setattr(storage.settings, "S3_BUCKET", "bucket")

    with pytest.raises(ValueError):
        storage.upload_binary(key, b"unsafe")


def test_storage_owner_and_permission_fallbacks(monkeypatch, tmp_path):
    monkeypatch.setattr(storage.settings, "S3_ENDPOINT_URL", tmp_path.as_uri())
    monkeypatch.setattr(storage.os, "chown", lambda *args: (_ for _ in ()).throw(PermissionError()))
    monkeypatch.setattr(storage.os, "chmod", lambda *args: (_ for _ in ()).throw(OSError()))
    storage._apply_local_storage_permissions(tmp_path / "missing", 1, 1)

    import pwd

    monkeypatch.setattr(pwd, "getpwnam", lambda name: (_ for _ in ()).throw(KeyError(name)))
    assert storage._storage_owner_ids() == (10001, 10001)

    monkeypatch.setattr(storage.os, "geteuid", lambda: 1000)
    storage.ensure_local_storage_permissions()


class FakeS3Client:
    def __init__(self):
        self.calls = []

    def upload_fileobj(self, file, bucket, key):
        self.calls.append(("upload_fileobj", file.read(), bucket, key))

    def put_object(self, **kwargs):
        self.calls.append(("put_object", kwargs))

    def get_object(self, **kwargs):
        self.calls.append(("get_object", kwargs))
        return {"Body": io.BytesIO(b"remote")}

    def delete_object(self, **kwargs):
        self.calls.append(("delete_object", kwargs))

    def copy_object(self, **kwargs):
        self.calls.append(("copy_object", kwargs))

    def generate_presigned_url(self, operation, **kwargs):
        self.calls.append(("presign", operation, kwargs))
        return "https://storage.example/signed"

    def list_objects_v2(self, **kwargs):
        self.calls.append(("list_objects_v2", kwargs))
        if "ContinuationToken" not in kwargs:
            return {
                "Contents": [{"Key": "system/upload-intents/first.json"}],
                "IsTruncated": True,
                "NextContinuationToken": "next-page",
            }
        return {
            "Contents": [{"Key": "system/upload-intents/second.json"}],
            "IsTruncated": False,
        }


def test_remote_storage_exercises_s3_operations(monkeypatch):
    restore_storage_functions(monkeypatch)
    client = FakeS3Client()
    monkeypatch.setattr(storage, "is_local_storage", lambda: False)
    monkeypatch.setattr(storage, "_get_s3_client", lambda: client)
    monkeypatch.setattr(storage.settings, "S3_BUCKET", "remote-bucket")

    assert storage.upload_book(io.BytesIO(b"book"), "user-2", "novel.pdf").endswith("/novel.pdf")
    assert storage.upload_book_bytes(b"bytes", "user-2", "draft.txt").endswith("/draft.txt")
    assert storage.upload_binary("asset.bin", b"data", "application/octet-stream") == "asset.bin"
    assert storage.upload_binary("plain.bin", b"plain") == "plain.bin"
    assert storage.upload_text("note.txt", "hello") == "note.txt"
    assert storage.download_book("note.txt") == b"remote"
    storage.delete_object("note.txt")
    assert storage.move_object("source", "destination") == "destination"
    assert storage.move_object("same", "same") == "same"
    assert storage.get_presigned_url("destination", expires=120) == "https://storage.example/signed"
    assert storage.list_object_keys("system/upload-intents", limit=2) == [
        "system/upload-intents/first.json",
        "system/upload-intents/second.json",
    ]

    call_names = [call[0] for call in client.calls]
    assert "upload_fileobj" in call_names
    assert call_names.count("put_object") == 4
    assert "get_object" in call_names
    assert "copy_object" in call_names
    assert call_names.count("delete_object") == 2
    assert "presign" in call_names
    assert call_names.count("list_objects_v2") == 2
