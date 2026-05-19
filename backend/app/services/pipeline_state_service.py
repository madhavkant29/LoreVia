from __future__ import annotations

from typing import Any

from app.models.book import Book
from app.schemas.books import WriterWorkspaceOut
from app.utils.book_utils import build_writer_workspace_payload, normalize_writer_workspace


def build_writer_workspace_response(book: Book) -> WriterWorkspaceOut:
    return WriterWorkspaceOut(**build_writer_workspace_payload(book))


def build_writer_workspace_update(book: Book, updates: dict[str, Any]) -> dict[str, Any]:
    return normalize_writer_workspace(
        {
            **build_writer_workspace_payload(book),
            **updates,
        }
    )
