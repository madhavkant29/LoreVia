"""Focused book workspace search workflows."""

from __future__ import annotations

import asyncio
import re
import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.storage import download_book
from app.models.book import (
    Book,
    BookCollaborator,
    Chapter,
    NovelScene,
    VaultNoteSource,
)
from app.utils.books import (
    collaboration_access,
    manuscript,
    vault,
    vault_storage,
    writer_workspace,
)
from app.utils.books.scene_records import (
    list_novel_scenes,
)
from app.utils.books.scene_serialization import (
    _scene_out,
)
from app.utils.index_format import format_index
from app.utils.storage_utils import STORAGE_IO_EXCEPTIONS
from app.utils.tag_utils import (
    ENTITY_TYPE_CHAPTER,
    ENTITY_TYPE_SCENE,
    list_custom_tags_for_entity_ids,
)


async def build_manuscript_workspace_tree(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    collaborator: BookCollaborator | None = None,
) -> dict[str, Any]:
    workspace = writer_workspace.build_writer_workspace_payload(book)
    index_fmt: str = workspace.get("index_format") or "arabic"
    chapter_rows = list(
        (
            await db.execute(
                select(Chapter.id, Chapter.number, Chapter.title, Chapter.structure_version)
                .where(Chapter.book_id == book.id)
                .order_by(Chapter.number.asc())
            )
        ).all()
    )
    scenes = list(
        (
            await db.execute(
                select(NovelScene)
                .where(NovelScene.book_id == book.id)
                .order_by(
                    NovelScene.chapter_number.is_(None),
                    NovelScene.chapter_number.asc(),
                    NovelScene.sort_order.asc(),
                    NovelScene.created_at.asc(),
                )
            )
        )
        .scalars()
        .all()
    )
    if collaborator is not None:
        chapter_rows = [
            (chapter_id, number, chapter_title, structure_version)
            for chapter_id, number, chapter_title, structure_version in chapter_rows
            if collaboration_access.collaboration_allows_chapter(collaborator, int(number))
        ]
        scenes = [
            scene
            for scene in scenes
            if scene.chapter_number is not None
            and collaboration_access.collaboration_allows_chapter(
                collaborator, int(scene.chapter_number)
            )
        ]
    note_paths = [
        note["path"]
        for note in await vault_storage.list_vault_notes(
            db,
            book=book,
            user_id=user_id,
            source=VaultNoteSource.USER_NOTES.value,
        )
    ]
    tags_by_chapter = await list_custom_tags_for_entity_ids(
        db,
        entity_type=ENTITY_TYPE_CHAPTER,
        entity_ids=[
            chapter_id for chapter_id, _number, _chapter_title, _structure_version in chapter_rows
        ],
        book_id=book.id,
    )
    tags_by_scene = await list_custom_tags_for_entity_ids(
        db,
        entity_type=ENTITY_TYPE_SCENE,
        entity_ids=[scene.id for scene in scenes],
        book_id=book.id,
    )
    scene_counts: dict[int, int] = {}
    grouped_scenes: dict[int | None, list[dict[str, Any]]] = {}
    for scene in scenes:
        grouped_scenes.setdefault(scene.chapter_number, []).append(
            _scene_out(scene, tags=tags_by_scene.get(scene.id, []))
        )
        if scene.chapter_number:
            scene_counts[scene.chapter_number] = scene_counts.get(scene.chapter_number, 0) + 1

    scene_groups: list[dict[str, Any]] = []
    if grouped_scenes.get(None):
        scene_groups.append(
            {
                "id": "unassigned-scenes",
                "label": "Unassigned Scenes",
                "chapter_number": None,
                "collapsed_by_default": True,
                "scenes": grouped_scenes[None],
            }
        )
    for chapter_id, chapter_number, chapter_title, structure_version in chapter_rows:
        fmt_num = format_index(int(chapter_number), index_fmt)
        scene_groups.append(
            {
                "id": f"chapter-scenes-{chapter_number}",
                "label": f"Chapter {fmt_num}: {chapter_title or f'Chapter {fmt_num}'}",
                "chapter_number": int(chapter_number),
                "structure_version": int(structure_version or 0),
                "collapsed_by_default": False,
                "scenes": grouped_scenes.get(int(chapter_number), []),
            }
        )

    chapter_title_by_number = {
        int(number): chapter_title
        for _chapter_id, number, chapter_title, _structure_version in chapter_rows
    }
    scene_breadcrumbs = {
        str(scene.id): [
            {"id": f"book-{book.id}", "label": book.title, "kind": "book"},
            {
                "id": f"chapter-{scene.chapter_number}",
                "label": f"Chapter {format_index(int(scene.chapter_number or 0), index_fmt)}: {chapter_title_by_number.get(int(scene.chapter_number or 0)) or f'Chapter {format_index(int(scene.chapter_number or 0), index_fmt)}'}",
                "kind": "chapter",
            },
            {"id": str(scene.id), "label": scene.title, "kind": "scene"},
        ]
        for scene in scenes
        if scene.chapter_number
    }

    configured_structure = workspace.get("structure_tree")
    if isinstance(configured_structure, list) and configured_structure:
        structure_tree = (
            _filter_workspace_structure_tree_for_collaborator(configured_structure, collaborator)
            if collaborator is not None
            else configured_structure
        )
    else:
        structure_tree = [
            {
                "id": f"book-{book.id}",
                "label": book.title,
                "kind": "book",
                "children": [
                    {
                        "id": f"chapter-{int(number)}",
                        "label": chapter_title or f"Chapter {format_index(int(number), index_fmt)}",
                        "kind": "chapter",
                        "chapter_number": int(number),
                        "children": [
                            {
                                "id": str(scene.id),
                                "label": scene.title,
                                "kind": "scene",
                                "chapter_number": int(number),
                                "scene_id": str(scene.id),
                                "children": [],
                            }
                            for scene in scenes
                            if scene.chapter_number == int(number)
                        ],
                    }
                    for _chapter_id, number, chapter_title, _structure_version in chapter_rows
                ],
            }
        ]

    return {
        "chapters": [
            {
                "chapter_number": int(number),
                "title": chapter_title,
                "scene_count": scene_counts.get(int(number), 0),
                "structure_version": int(structure_version or 0),
                "tags": tags_by_chapter.get(chapter_id, []),
            }
            for chapter_id, number, chapter_title, structure_version in chapter_rows
        ],
        "scene_groups": scene_groups,
        "note_paths": note_paths,
        "structure_tree": structure_tree,
        "scene_breadcrumbs": scene_breadcrumbs,
    }


def _filter_workspace_structure_tree_for_collaborator(
    nodes: list[dict[str, Any]],
    collaborator: BookCollaborator,
) -> list[dict[str, Any]]:
    filtered_nodes: list[dict[str, Any]] = []
    for raw_node in nodes:
        if not isinstance(raw_node, dict):
            continue
        node = dict(raw_node)
        chapter_number = node.get("chapter_number")
        if (
            isinstance(chapter_number, int)
            and chapter_number > 0
            and not collaboration_access.collaboration_allows_chapter(collaborator, chapter_number)
        ):
            continue
        children = node.get("children")
        if isinstance(children, list):
            node["children"] = _filter_workspace_structure_tree_for_collaborator(
                children, collaborator
            )
        filtered_nodes.append(node)
    return filtered_nodes


def _compile_workspace_search_pattern(search_query: str, *, flags: int) -> re.Pattern[str]:
    if len(search_query) > settings.WORKSPACE_REGEX_MAX_PATTERN_LENGTH:
        raise HTTPException(400, "Search pattern is too long.")
    if re.search(r"\([^)]*[+*][^)]*\)[+*{]", search_query):
        raise HTTPException(400, "Search pattern contains unsafe nested repetition.")
    try:
        return re.compile(search_query, flags)
    except re.error as exc:
        raise HTTPException(400, f"Invalid search pattern: {exc}") from exc


def _workspace_excerpt(text: str, query: str, *, radius: int = 90) -> str:
    normalized_text = " ".join((text or "").split()).strip()
    if not normalized_text:
        return ""
    if not query:
        return normalized_text[: radius * 2]
    index = normalized_text.lower().find(query.lower())
    if index < 0:
        return normalized_text[: radius * 2]
    start = max(0, index - radius)
    end = min(len(normalized_text), index + len(query) + radius)
    excerpt = normalized_text[start:end]
    if start > 0:
        excerpt = f"...{excerpt}"
    if end < len(normalized_text):
        excerpt = f"{excerpt}..."
    return excerpt


async def search_author_workspace(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    query: str,
    scopes: list[str],
    case_sensitive: bool = False,
    whole_word: bool = False,
    regex: bool = False,
    filters: dict[str, Any] | None = None,
    collaborator: BookCollaborator | None = None,
) -> list[dict[str, Any]]:
    search_query = " ".join((query or "").split()).strip()
    normalized_scopes = {
        scope for scope in scopes if scope in {"manuscript", "scenes", "notes"}
    } or {"manuscript", "scenes", "notes"}
    filter_payload = filters if isinstance(filters, dict) else {}
    chapter_filter = filter_payload.get("chapter_number")
    scene_id_filter = " ".join(str(filter_payload.get("scene_id") or "").split()).strip() or None
    pov_filter = " ".join(str(filter_payload.get("pov") or "").split()).strip().lower() or None
    location_filter = (
        " ".join(str(filter_payload.get("location") or "").split()).strip().lower() or None
    )
    tag_filters = {
        " ".join(str(tag or "").split()).strip().lower()
        for tag in (filter_payload.get("tags") or [])
        if " ".join(str(tag or "").split()).strip()
    }

    flags = 0 if case_sensitive else re.IGNORECASE
    pattern: re.Pattern[str] | None = None
    if regex and search_query:
        pattern = _compile_workspace_search_pattern(search_query, flags=flags)
    elif search_query and whole_word:
        pattern = re.compile(rf"\b{re.escape(search_query)}\b", flags)

    def _matches(value: str) -> bool:
        haystack = value or ""
        if not search_query:
            return True
        if pattern is not None:
            return bool(pattern.search(haystack))
        if case_sensitive:
            return search_query in haystack
        return search_query.lower() in haystack.lower()

    results: list[dict[str, Any]] = []

    if "scenes" in normalized_scopes:
        scene_rows = await list_novel_scenes(
            db,
            book=book,
            collaborator=collaborator,
            chapter_number=int(chapter_filter)
            if isinstance(chapter_filter, int) and chapter_filter > 0
            else None,
            query=None,
        )
        for scene in scene_rows:
            metadata = scene.get("metadata") if isinstance(scene.get("metadata"), dict) else {}
            if scene_id_filter and str(scene.get("id")) != scene_id_filter:
                continue
            if pov_filter and str(metadata.get("pov") or "").strip().lower() != pov_filter:
                continue
            if (
                location_filter
                and str(metadata.get("location") or "").strip().lower() != location_filter
            ):
                continue
            scene_tags = {
                " ".join(str(tag or "").split()).strip().lower()
                for tag in (metadata.get("tags") or scene.get("tags") or [])
                if " ".join(str(tag or "").split()).strip()
            }
            if tag_filters and not tag_filters.issubset(scene_tags):
                continue
            searchable = "\n".join(
                [
                    str(scene.get("title") or ""),
                    str(scene.get("description") or ""),
                    str(scene.get("body") or ""),
                ]
            )
            if not _matches(searchable):
                continue
            results.append(
                {
                    "scope": "scenes",
                    "id": str(scene["id"]),
                    "title": str(scene.get("title") or "Scene"),
                    "excerpt": _workspace_excerpt(
                        str(scene.get("body") or scene.get("description") or ""), search_query
                    ),
                    "chapter_number": scene.get("chapter_number"),
                    "scene_id": str(scene["id"]),
                    "note_path": None,
                    "rank": 3,
                }
            )

    if "notes" in normalized_scopes and collaborator is None:
        notes = await vault_storage.list_vault_notes(
            db,
            book=book,
            user_id=user_id,
            source=VaultNoteSource.USER_NOTES.value,
        )
        for note in notes:
            path = str(note.get("path") or "")
            content = str(note.get("content") or "")
            if not _matches(f"{path}\n{content}"):
                continue
            results.append(
                {
                    "scope": "notes",
                    "id": path,
                    "title": vault.vault_note_title(path),
                    "excerpt": _workspace_excerpt(content, search_query),
                    "chapter_number": None,
                    "scene_id": None,
                    "note_path": path,
                    "rank": 2,
                }
            )

    if "manuscript" in normalized_scopes:
        chapter_stmt = (
            select(Chapter).where(Chapter.book_id == book.id).order_by(Chapter.number.asc())
        )
        if isinstance(chapter_filter, int) and chapter_filter > 0:
            chapter_stmt = chapter_stmt.where(Chapter.number == int(chapter_filter))
        chapter_rows = list((await db.execute(chapter_stmt)).scalars().all())
        for chapter in chapter_rows:
            if collaborator is not None and not collaboration_access.collaboration_allows_chapter(
                collaborator, int(chapter.number)
            ):
                continue
            if not chapter.s3_key:
                continue
            try:
                raw = await asyncio.to_thread(download_book, chapter.s3_key)
            except STORAGE_IO_EXCEPTIONS:
                continue
            stored = manuscript.deserialize_manuscript_content(raw)
            text = str(stored.get("text") or "")
            title = chapter.title or f"Chapter {chapter.number}"
            if not _matches(f"{title}\n{text}"):
                continue
            results.append(
                {
                    "scope": "manuscript",
                    "id": f"chapter-{chapter.number}",
                    "title": title,
                    "excerpt": _workspace_excerpt(text, search_query),
                    "chapter_number": chapter.number,
                    "scene_id": None,
                    "note_path": None,
                    "rank": 1,
                }
            )

    results.sort(
        key=lambda item: (
            -float(item.get("rank") or 0),
            int(item.get("chapter_number") or 0),
            str(item.get("title") or "").lower(),
        )
    )
    return results
