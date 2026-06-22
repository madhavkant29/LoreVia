"""Focused book scene serialization workflows."""

from __future__ import annotations

from typing import Any, cast

from app.models.book import (
    NovelScene,
    SceneVersion,
)
from app.utils.books.scene_metadata import (
    normalize_scene_metadata,
)


def _scene_out(scene: NovelScene, *, tags: list[str] | None = None) -> dict[str, Any]:
    metadata = normalize_scene_metadata(
        cast(dict[str, Any] | None, scene.scene_metadata), description=scene.description
    )
    if tags:
        existing_tags = metadata.get("tags")
        if isinstance(existing_tags, list):
            metadata["tags"] = [*existing_tags, *[tag for tag in tags if tag not in existing_tags]]
        else:
            metadata["tags"] = tags
    return {
        "id": str(scene.id),
        "book_id": str(scene.book_id),
        "chapter_id": str(scene.chapter_id) if scene.chapter_id else None,
        "chapter_number": scene.chapter_number,
        "title": scene.title,
        "description": scene.description,
        "body": scene.body,
        "html_body": scene.html_body,
        "metadata": metadata,
        "path": scene.path,
        "status": scene.status,
        "sort_order": scene.sort_order,
        "source": scene.source,
        "origin_chapter_number": scene.origin_chapter_number,
        "tags": tags or [],
        "created_at": scene.created_at,
        "updated_at": scene.updated_at,
    }


def _scene_version_out(version: SceneVersion) -> dict[str, Any]:
    return {
        "id": str(version.id),
        "scene_id": str(version.scene_id) if version.scene_id else None,
        "chapter_number": version.chapter_number,
        "scene_title": version.scene_title,
        "scene_path": version.scene_path,
        "word_count": version.word_count,
        "note": version.note,
        "snapshot_kind": version.snapshot_kind,
        "created_at": version.created_at,
    }
