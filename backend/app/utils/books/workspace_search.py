"""Focused book workspace search workflows."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import math
import re
import uuid
from collections.abc import Mapping
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.book import (
    Book,
    BookCollaborator,
    Chapter,
    NovelScene,
    VaultNote,
    VaultNoteSource,
)
from app.models.intelligence import BookChunk
from app.models.tag import CustomTag
from app.utils.books import (
    collaboration_access,
    vault,
    vault_storage,
    writer_workspace,
)
from app.utils.books.collaboration import collaboration_scope_payload
from app.utils.books.scene_metadata import normalize_scene_metadata
from app.utils.index_format import format_index
from app.utils.tag_utils import (
    ENTITY_TYPE_CHAPTER,
    ENTITY_TYPE_SCENE,
    list_custom_tags_for_entity_ids,
)

WORKSPACE_SEARCH_CANDIDATE_LIMIT = 100
WORKSPACE_SEARCH_RETURN_LIMIT = 50
WORKSPACE_SEARCH_CURSOR_VERSION = 1


async def build_manuscript_workspace_tree(
    db: AsyncSession,
    *,
    book: Book,
    user_id: uuid.UUID,
    collaborator: BookCollaborator | None = None,
    include_scene_bodies: bool = False,
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
    scene_columns = [
        NovelScene.id,
        NovelScene.book_id,
        NovelScene.chapter_id,
        NovelScene.chapter_number,
        NovelScene.title,
        NovelScene.description,
        NovelScene.scene_metadata,
        NovelScene.path,
        NovelScene.status,
        NovelScene.sort_order,
        NovelScene.source,
        NovelScene.origin_chapter_number,
        NovelScene.created_at,
        NovelScene.updated_at,
    ]
    if include_scene_bodies:
        scene_columns.extend([NovelScene.body, NovelScene.html_body])
    scenes = list(
        (
            await db.execute(
                select(*scene_columns)
                .where(NovelScene.book_id == book.id)
                .order_by(
                    NovelScene.chapter_number.is_(None),
                    NovelScene.chapter_number.asc(),
                    NovelScene.sort_order.asc(),
                    NovelScene.created_at.asc(),
                )
            )
        )
        .mappings()
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
            if _scene_value(scene, "chapter_number") is not None
            and collaboration_access.collaboration_allows_chapter(
                collaborator, int(_scene_value(scene, "chapter_number"))
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
        entity_ids=[_scene_value(scene, "id") for scene in scenes],
        book_id=book.id,
    )
    scene_counts: dict[int, int] = {}
    grouped_scenes: dict[int | None, list[dict[str, Any]]] = {}
    for scene in scenes:
        chapter_number = _scene_value(scene, "chapter_number")
        scene_id = _scene_value(scene, "id")
        grouped_scenes.setdefault(chapter_number, []).append(
            _workspace_scene_out(
                scene,
                tags=tags_by_scene.get(scene_id, []),
                include_body=include_scene_bodies,
            )
        )
        if chapter_number:
            scene_counts[chapter_number] = scene_counts.get(chapter_number, 0) + 1

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
    scene_breadcrumbs: dict[str, list[dict[str, Any]]] = {}
    for scene in scenes:
        scene_chapter_number = _scene_value(scene, "chapter_number")
        if not scene_chapter_number:
            continue
        formatted_chapter_number = format_index(int(scene_chapter_number), index_fmt)
        scene_breadcrumbs[str(_scene_value(scene, "id"))] = [
            {"id": f"book-{book.id}", "label": book.title, "kind": "book"},
            {
                "id": f"chapter-{scene_chapter_number}",
                "label": (
                    f"Chapter {formatted_chapter_number}: "
                    f"{chapter_title_by_number.get(int(scene_chapter_number)) or f'Chapter {formatted_chapter_number}'}"
                ),
                "kind": "chapter",
            },
            {
                "id": str(_scene_value(scene, "id")),
                "label": _scene_value(scene, "title"),
                "kind": "scene",
            },
        ]

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
                                "id": str(_scene_value(scene, "id")),
                                "label": _scene_value(scene, "title"),
                                "kind": "scene",
                                "chapter_number": int(number),
                                "scene_id": str(_scene_value(scene, "id")),
                                "children": [],
                            }
                            for scene in scenes
                            if _scene_value(scene, "chapter_number") == int(number)
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


def _scene_value(scene: Mapping[str, Any] | Any, key: str) -> Any:
    if isinstance(scene, Mapping):
        return scene[key]
    return getattr(scene, key)


def _workspace_scene_out(
    scene: Mapping[str, Any] | Any,
    *,
    tags: list[str] | None = None,
    include_body: bool = False,
) -> dict[str, Any]:
    metadata = normalize_scene_metadata(
        _scene_value(scene, "scene_metadata"),
        description=_scene_value(scene, "description"),
    )
    if tags:
        existing_tags = metadata.get("tags")
        if isinstance(existing_tags, list):
            metadata["tags"] = [*existing_tags, *[tag for tag in tags if tag not in existing_tags]]
        else:
            metadata["tags"] = tags

    payload = {
        "id": str(_scene_value(scene, "id")),
        "book_id": str(_scene_value(scene, "book_id")),
        "chapter_id": str(_scene_value(scene, "chapter_id"))
        if _scene_value(scene, "chapter_id")
        else None,
        "chapter_number": _scene_value(scene, "chapter_number"),
        "title": _scene_value(scene, "title"),
        "description": _scene_value(scene, "description"),
        "metadata": metadata,
        "path": _scene_value(scene, "path"),
        "status": _scene_value(scene, "status"),
        "sort_order": _scene_value(scene, "sort_order"),
        "source": _scene_value(scene, "source"),
        "origin_chapter_number": _scene_value(scene, "origin_chapter_number"),
        "tags": tags or [],
        "created_at": _scene_value(scene, "created_at"),
        "updated_at": _scene_value(scene, "updated_at"),
    }
    if include_body:
        payload["body"] = _scene_value(scene, "body")
        payload["html_body"] = _scene_value(scene, "html_body")
    return payload


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
    limit: int = WORKSPACE_SEARCH_RETURN_LIMIT,
) -> list[dict[str, Any]]:
    """Legacy bounded list response retained while clients move to cursor pages."""
    results, _normalized_scopes, _chapter_filter = await _collect_workspace_search_results(
        db,
        book=book,
        user_id=user_id,
        query=query,
        scopes=scopes,
        case_sensitive=case_sensitive,
        whole_word=whole_word,
        regex=regex,
        filters=filters,
        collaborator=collaborator,
    )
    return results[:_workspace_result_limit(limit)]


async def search_author_workspace_page(
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
    limit: int = WORKSPACE_SEARCH_RETURN_LIMIT,
    cursor: str | None = None,
) -> dict[str, Any]:
    """Return one stable cursor page from the bounded persisted search projection."""
    results, normalized_scopes, chapter_filter = await _collect_workspace_search_results(
        db,
        book=book,
        user_id=user_id,
        query=query,
        scopes=scopes,
        case_sensitive=case_sensitive,
        whole_word=whole_word,
        regex=regex,
        filters=filters,
        collaborator=collaborator,
    )
    fingerprint = _workspace_search_fingerprint(
        book_id=book.id,
        user_id=user_id,
        query=query,
        normalized_scopes=normalized_scopes,
        case_sensitive=case_sensitive,
        whole_word=whole_word,
        regex=regex,
        filters=filters,
    )
    after_key = _decode_workspace_search_cursor(cursor, fingerprint=fingerprint)
    remaining = (
        [item for item in results if _workspace_result_sort_key(item) > after_key]
        if after_key is not None
        else results
    )
    result_limit = _workspace_result_limit(limit)
    items = remaining[:result_limit]
    has_more = len(remaining) > len(items)
    next_cursor = (
        _encode_workspace_search_cursor(
            fingerprint=fingerprint,
            sort_key=_workspace_result_sort_key(items[-1]),
        )
        if has_more and items
        else None
    )
    return {
        "items": items,
        "next_cursor": next_cursor,
        "has_more": has_more,
        "index_status": await _workspace_manuscript_index_status(
            db,
            book=book,
            normalized_scopes=normalized_scopes,
            chapter_filter=chapter_filter,
            collaborator=collaborator,
        ),
    }


async def _collect_workspace_search_results(
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
) -> tuple[list[dict[str, Any]], set[str], object]:
    """Search persisted workspace records without reading manuscript objects from storage.

    Manuscript chunks are indexed while a book is processed, so a workspace search
    must use that local projection rather than downloading and deserializing every
    chapter during the request. Scene and vault searches are likewise constrained
    in SQL before text bodies are selected.
    """
    normalized_scopes = {
        scope for scope in scopes if scope in {"manuscript", "scenes", "notes"}
    } or {"manuscript", "scenes", "notes"}
    search_query = " ".join((query or "").split()).strip()
    if not search_query:
        return [], normalized_scopes, None

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
    if regex:
        _compile_workspace_search_pattern(search_query, flags=flags)
        _validate_workspace_regex_scope(
            normalized_scopes=normalized_scopes,
            chapter_filter=chapter_filter,
        )

    results: list[dict[str, Any]] = []

    if "scenes" in normalized_scopes:
        scene_document = _workspace_search_document(
            NovelScene.title,
            NovelScene.description,
            NovelScene.body,
        )
        scene_rank = _workspace_search_rank(
            scene_document,
            search_query=search_query,
            case_sensitive=case_sensitive,
            whole_word=whole_word,
            regex=regex,
        )
        scene_stmt = select(
            NovelScene.id,
            NovelScene.title,
            NovelScene.description,
            NovelScene.body,
            NovelScene.chapter_number,
            scene_rank.label("search_rank"),
        ).where(
            NovelScene.book_id == book.id,
            _workspace_search_predicate(
                scene_document,
                search_query=search_query,
                case_sensitive=case_sensitive,
                whole_word=whole_word,
                regex=regex,
            )
        )
        scene_stmt = _apply_workspace_chapter_filter(
            scene_stmt,
            chapter_column=NovelScene.chapter_number,
            chapter_filter=chapter_filter,
            collaborator=collaborator,
        )
        if scene_id_filter:
            scene_stmt = scene_stmt.where(NovelScene.id == scene_id_filter)
        if pov_filter:
            scene_stmt = scene_stmt.where(
                func.lower(NovelScene.scene_metadata["pov"].astext) == pov_filter
            )
        if location_filter:
            scene_stmt = scene_stmt.where(
                func.lower(NovelScene.scene_metadata["location"].astext) == location_filter
            )
        for tag_filter in tag_filters:
            scene_stmt = scene_stmt.where(
                or_(
                    NovelScene.scene_metadata["tags"].contains([tag_filter]),
                    select(CustomTag.id)
                    .where(
                        CustomTag.book_id == book.id,
                        CustomTag.entity_type == ENTITY_TYPE_SCENE,
                        CustomTag.entity_id == NovelScene.id,
                        func.lower(CustomTag.tag_name) == tag_filter,
                    )
                    .exists(),
                )
            )
        scene_rows = (
            await db.execute(
                scene_stmt.order_by(scene_rank.desc(), NovelScene.id.asc()).limit(
                    WORKSPACE_SEARCH_CANDIDATE_LIMIT
                )
            )
        ).all()
        for scene_id, title, description, body, scene_chapter_number, search_rank in scene_rows:
            results.append(
                {
                    "scope": "scenes",
                    "id": str(scene_id),
                    "title": str(title or "Scene"),
                    "excerpt": _workspace_excerpt(
                        str(body or description or ""), search_query
                    ),
                    "chapter_number": scene_chapter_number,
                    "scene_id": str(scene_id),
                    "note_path": None,
                    "rank": 300 + float(search_rank or 0),
                }
            )

    if "notes" in normalized_scopes and collaborator is None:
        note_document = _workspace_search_document(VaultNote.path, VaultNote.content)
        note_rank = _workspace_search_rank(
            note_document,
            search_query=search_query,
            case_sensitive=case_sensitive,
            whole_word=whole_word,
            regex=regex,
        )
        note_stmt = select(
            VaultNote.id,
            VaultNote.path,
            VaultNote.content,
            note_rank.label("search_rank"),
        ).where(
            VaultNote.book_id == book.id,
            VaultNote.user_id == user_id,
            VaultNote.source == VaultNoteSource.USER_NOTES.value,
        )
        if regex:
            # PostgreSQL applies a regex predicate before LIMIT. Resolve a stable,
            # bounded candidate ID set first so a broad user pattern cannot scan an
            # author's entire vault.
            regex_candidate_ids = list(
                (
                    await db.execute(
                        select(VaultNote.id)
                        .where(
                            VaultNote.book_id == book.id,
                            VaultNote.user_id == user_id,
                            VaultNote.source == VaultNoteSource.USER_NOTES.value,
                        )
                        .order_by(VaultNote.updated_at.desc(), VaultNote.id.asc())
                        .limit(WORKSPACE_SEARCH_CANDIDATE_LIMIT)
                    )
                )
                .scalars()
                .all()
            )
            if not regex_candidate_ids:
                note_rows: list[tuple[Any, ...]] = []
            else:
                note_rows = (
                    await db.execute(
                        note_stmt.where(
                            VaultNote.id.in_(regex_candidate_ids),
                            _workspace_search_predicate(
                                note_document,
                                search_query=search_query,
                                case_sensitive=case_sensitive,
                                whole_word=whole_word,
                                regex=True,
                            ),
                        )
                        .order_by(note_rank.desc(), VaultNote.id.asc())
                    )
                ).all()
        else:
            note_rows = (
                await db.execute(
                    note_stmt.where(
                        _workspace_search_predicate(
                            note_document,
                            search_query=search_query,
                            case_sensitive=case_sensitive,
                            whole_word=whole_word,
                            regex=False,
                        ),
                    )
                    .order_by(note_rank.desc(), VaultNote.id.asc())
                    .limit(WORKSPACE_SEARCH_CANDIDATE_LIMIT)
                )
            ).all()
        for _note_id, path, content, search_rank in note_rows:
            results.append(
                {
                    "scope": "notes",
                    "id": str(path),
                    "title": vault.vault_note_title(str(path)),
                    "excerpt": _workspace_excerpt(content, search_query),
                    "chapter_number": None,
                    "scene_id": None,
                    "note_path": str(path),
                    "rank": 200 + float(search_rank or 0),
                }
            )

    if "manuscript" in normalized_scopes:
        chunk_rank = _workspace_search_rank(
            BookChunk.text,
            search_query=search_query,
            case_sensitive=case_sensitive,
            whole_word=whole_word,
            regex=regex,
        )
        chapter_match_order = func.row_number().over(
            partition_by=Chapter.id,
            order_by=(chunk_rank.desc(), BookChunk.chunk_index.asc()),
        )
        chunk_match_stmt = select(
            Chapter.id.label("chapter_id"),
            Chapter.number.label("chapter_number"),
            Chapter.title.label("chapter_title"),
            BookChunk.text.label("chunk_text"),
            BookChunk.chunk_index.label("chunk_index"),
            chunk_rank.label("search_rank"),
            chapter_match_order.label("chapter_match_order"),
        ).join(BookChunk, BookChunk.chapter_id == Chapter.id).where(
            Chapter.book_id == book.id,
            BookChunk.book_id == book.id,
            _workspace_search_predicate(
                BookChunk.text,
                search_query=search_query,
                case_sensitive=case_sensitive,
                whole_word=whole_word,
                regex=regex,
            ),
        )
        chunk_match_stmt = _apply_workspace_chapter_filter(
            chunk_match_stmt,
            chapter_column=Chapter.number,
            chapter_filter=chapter_filter,
            collaborator=collaborator,
        )
        chunk_matches = chunk_match_stmt.subquery()
        chunk_rows = (
            await db.execute(
                select(
                    chunk_matches.c.chapter_id,
                    chunk_matches.c.chapter_number,
                    chunk_matches.c.chapter_title,
                    chunk_matches.c.chunk_text,
                    chunk_matches.c.search_rank,
                )
                .where(chunk_matches.c.chapter_match_order == 1)
                .order_by(
                    chunk_matches.c.search_rank.desc(),
                    chunk_matches.c.chapter_number.asc(),
                    chunk_matches.c.chunk_index.asc(),
                )
                .limit(WORKSPACE_SEARCH_CANDIDATE_LIMIT)
            )
        ).all()
        for chapter_id, chapter_number, chapter_title, chunk_text, search_rank in chunk_rows:
            title = chapter_title or f"Chapter {chapter_number}"
            results.append(
                {
                    "scope": "manuscript",
                    "id": f"chapter-{chapter_number}",
                    "title": title,
                    "excerpt": _workspace_excerpt(chunk_text, search_query),
                    "chapter_number": chapter_number,
                    "scene_id": None,
                    "note_path": None,
                    "rank": 100 + float(search_rank or 0),
                }
            )

    results.sort(key=_workspace_result_sort_key)
    return results, normalized_scopes, chapter_filter


def _workspace_result_limit(limit: int) -> int:
    try:
        requested_limit = int(limit)
    except (TypeError, ValueError):
        requested_limit = WORKSPACE_SEARCH_RETURN_LIMIT
    return max(1, min(requested_limit, WORKSPACE_SEARCH_RETURN_LIMIT))


def _workspace_result_sort_key(result: Mapping[str, Any]) -> tuple[float, str, str]:
    """Return a stable, cursor-safe ordering key for mixed workspace scopes."""
    try:
        rank = float(result.get("rank") or 0)
    except (TypeError, ValueError):
        rank = 0.0
    if not math.isfinite(rank):
        rank = 0.0
    return (-rank, str(result.get("scope") or ""), str(result.get("id") or ""))


def _workspace_search_fingerprint(
    *,
    book_id: uuid.UUID,
    user_id: uuid.UUID,
    query: str,
    normalized_scopes: set[str],
    case_sensitive: bool,
    whole_word: bool,
    regex: bool,
    filters: dict[str, Any] | None,
) -> str:
    """Bind cursors to a single user, book, and normalized search request."""
    payload = {
        "book_id": str(book_id),
        "user_id": str(user_id),
        "query": " ".join((query or "").split()),
        "scopes": sorted(normalized_scopes),
        "case_sensitive": case_sensitive,
        "whole_word": whole_word,
        "regex": regex,
        "filters": filters if isinstance(filters, dict) else {},
    }
    encoded = json.dumps(
        payload,
        default=str,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _encode_workspace_search_cursor(
    *,
    fingerprint: str,
    sort_key: tuple[float, str, str],
) -> str:
    payload = {
        "v": WORKSPACE_SEARCH_CURSOR_VERSION,
        "f": fingerprint,
        "k": [sort_key[0], sort_key[1], sort_key[2]],
    }
    return base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).decode().rstrip("=")


def _decode_workspace_search_cursor(
    cursor: str | None,
    *,
    fingerprint: str,
) -> tuple[float, str, str] | None:
    if cursor is None:
        return None
    try:
        padded_cursor = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded_cursor.encode()))
        if not isinstance(payload, dict):
            raise ValueError("Cursor payload must be an object")
        if (
            payload.get("v") != WORKSPACE_SEARCH_CURSOR_VERSION
            or payload.get("f") != fingerprint
        ):
            raise ValueError("Cursor does not match this search")
        raw_key = payload.get("k")
        if not isinstance(raw_key, list) or len(raw_key) != 3:
            raise ValueError("Cursor sort key is invalid")
        rank, scope, item_id = raw_key
        if isinstance(rank, bool) or not isinstance(rank, (int, float)):
            raise ValueError("Cursor rank is invalid")
        rank_value = float(rank)
        if not math.isfinite(rank_value) or not isinstance(scope, str) or not isinstance(item_id, str):
            raise ValueError("Cursor sort key is invalid")
        return rank_value, scope, item_id
    except (binascii.Error, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise HTTPException(400, "Invalid workspace search cursor") from exc


async def _workspace_manuscript_index_status(
    db: AsyncSession,
    *,
    book: Book,
    normalized_scopes: set[str],
    chapter_filter: object,
    collaborator: BookCollaborator | None,
) -> str:
    """Report whether every searchable chapter has a persisted chunk projection."""
    if "manuscript" not in normalized_scopes:
        return "not_requested"

    chapter_count_stmt = select(func.count(Chapter.id)).where(Chapter.book_id == book.id)
    chapter_count_stmt = _apply_workspace_chapter_filter(
        chapter_count_stmt,
        chapter_column=Chapter.number,
        chapter_filter=chapter_filter,
        collaborator=collaborator,
    )
    chapter_count = int(await db.scalar(chapter_count_stmt) or 0)
    if chapter_count == 0:
        return "ready"

    indexed_chapter_count_stmt = (
        select(func.count(func.distinct(BookChunk.chapter_id)))
        .select_from(BookChunk)
        .join(Chapter, Chapter.id == BookChunk.chapter_id)
        .where(BookChunk.book_id == book.id, Chapter.book_id == book.id)
    )
    indexed_chapter_count_stmt = _apply_workspace_chapter_filter(
        indexed_chapter_count_stmt,
        chapter_column=Chapter.number,
        chapter_filter=chapter_filter,
        collaborator=collaborator,
    )
    indexed_chapter_count = int(await db.scalar(indexed_chapter_count_stmt) or 0)
    return "ready" if indexed_chapter_count >= chapter_count else "building"


def _workspace_search_document(*columns: Any) -> Any:
    document = func.coalesce(columns[0], "")
    for column in columns[1:]:
        document = document + literal(" ") + func.coalesce(column, "")
    return document


def _workspace_search_uses_fts(*, case_sensitive: bool, whole_word: bool, regex: bool) -> bool:
    return not case_sensitive and not whole_word and not regex


def _workspace_search_predicate(
    document: Any,
    *,
    search_query: str,
    case_sensitive: bool,
    whole_word: bool,
    regex: bool,
) -> Any:
    if _workspace_search_uses_fts(
        case_sensitive=case_sensitive,
        whole_word=whole_word,
        regex=regex,
    ):
        return func.to_tsvector("simple", document).op("@@")(
            func.websearch_to_tsquery("simple", search_query)
        )
    if regex:
        return document.op("~" if case_sensitive else "~*")(search_query)
    if whole_word:
        return document.op("~" if case_sensitive else "~*")(
            rf"\m{re.escape(search_query)}\M"
        )
    escaped_query = search_query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    pattern = f"%{escaped_query}%"
    if case_sensitive:
        return document.like(pattern, escape="\\")
    return document.ilike(pattern, escape="\\")


def _workspace_search_rank(
    document: Any,
    *,
    search_query: str,
    case_sensitive: bool,
    whole_word: bool,
    regex: bool,
) -> Any:
    if not _workspace_search_uses_fts(
        case_sensitive=case_sensitive,
        whole_word=whole_word,
        regex=regex,
    ):
        return literal(1.0)
    return func.ts_rank_cd(
        func.to_tsvector("simple", document),
        func.websearch_to_tsquery("simple", search_query),
    )


def _apply_workspace_chapter_filter(
    stmt: Any,
    *,
    chapter_column: Any,
    chapter_filter: object,
    collaborator: BookCollaborator | None,
) -> Any:
    if isinstance(chapter_filter, int) and chapter_filter > 0:
        stmt = stmt.where(chapter_column == chapter_filter)
    if collaborator is None or not collaboration_access.collaboration_is_chapter_restricted(
        collaborator
    ):
        return stmt
    scope = collaboration_scope_payload(collaborator)
    chapter_start = scope.get("chapter_start")
    chapter_end = scope.get("chapter_end")
    stmt = stmt.where(chapter_column.is_not(None))
    if isinstance(chapter_start, int):
        stmt = stmt.where(chapter_column >= chapter_start)
    if isinstance(chapter_end, int):
        stmt = stmt.where(chapter_column <= chapter_end)
    return stmt


def _validate_workspace_regex_scope(
    *,
    normalized_scopes: set[str],
    chapter_filter: object,
) -> None:
    if len(normalized_scopes) != 1:
        raise HTTPException(400, "Regex search requires exactly one workspace scope.")
    scope = next(iter(normalized_scopes))
    if scope != "notes" and not (isinstance(chapter_filter, int) and chapter_filter > 0):
        raise HTTPException(400, "Regex search in manuscript or scenes requires a chapter filter.")
