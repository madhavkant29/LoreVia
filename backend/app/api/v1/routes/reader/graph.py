import uuid
from typing import Any, cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps.auth import get_current_user
from app.core.config import settings
from app.core.database import get_db
from app.core.redis import (
    cache_get,
    cache_set,
    get_book_cache_version,
    get_reader_progress_cache_version,
    get_relationship_evolution_cache,
    key_relationship_graph,
    set_relationship_evolution_cache,
)
from app.models.book import Book
from app.models.character import Character, CharacterState
from app.models.intelligence import CharacterRelationship
from app.utils.billing_utils import require_author_access
from app.utils.book_utils import (
    collaboration_allows_chapter,
    get_book_with_collaboration_access,
)
from app.utils.reader_utils import (
    collapse_graph_characters,
    graph_character_visibility_analysis,
    is_graph_character_visible,
    relationship_node_description,
)
from app.utils.relationship_utils import (
    canonicalize_relationship_book_rows,
    normalize_relationship_labels,
    relationship_label_display,
    relationship_effective_status,
)
from app.utils.sparse_utils import apply_sparse_includes, include_requested, parse_csv_param

router = APIRouter()


@router.get("/{book_id}/relationships")
async def get_relationships(
    book_id: uuid.UUID,
    chapter: int = Query(...),
    include_inactive: bool = Query(False),
    include: str | None = Query(None, description="Comma-separated sub-objects: nodes, edges, hidden_nodes"),
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if limit < 1 or limit > 100:
        raise HTTPException(400, "limit must be between 1 and 100")
    if offset < 0:
        raise HTTPException(400, "offset must be >= 0")
    book = await db.get(Book, book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404)
    require_author_access(current_user)
    use_cache = parse_csv_param(include) is None
    cache_scope = "all" if include_inactive else "active"
    cache_key = f"{key_relationship_graph(str(book_id), chapter)}:v5:{cache_scope}"
    if use_cache:
        cached = await cache_get(cache_key)
        if cached:
            graph = cast(dict[str, Any], cached)
            graph = apply_sparse_includes(graph, include)
            all_edges = graph.get("edges", [])
            total_edges = len(all_edges)
            graph["edges"] = all_edges[offset : offset + limit]
            graph["total_edges"] = total_edges
            graph["limit"] = limit
            graph["offset"] = offset
            graph["has_more"] = (offset + limit) < total_edges
            return graph

    want_nodes = include_requested(include, "nodes")
    want_edges = include_requested(include, "edges")
    want_hidden_nodes = include_requested(include, "hidden_nodes")

    chars_result = await db.execute(
        select(Character).where(Character.book_id == book_id, Character.first_chapter <= chapter)
    )
    chars = list(chars_result.scalars().all())

    rels_result = await db.execute(
        select(CharacterRelationship)
        .where(
            CharacterRelationship.book_id == book_id,
            CharacterRelationship.from_chapter <= chapter,
        )
        .options(
            selectinload(CharacterRelationship.character_a),
            selectinload(CharacterRelationship.character_b),
        )
    )
    historical_rels, _ = canonicalize_relationship_book_rows(list(rels_result.scalars().all()))
    relationship_counts: dict[str, int] = {}
    for rel in historical_rels:
        relationship_counts[str(rel.character_a_id)] = relationship_counts.get(str(rel.character_a_id), 0) + 1
        relationship_counts[str(rel.character_b_id)] = relationship_counts.get(str(rel.character_b_id), 0) + 1

    for char in chars:
        setattr(char, "_graph_relationship_count", relationship_counts.get(str(char.id), 0))

    analyses = {
        str(char.id): graph_character_visibility_analysis(char, relationship_counts.get(str(char.id), 0))
        for char in chars
    }

    visible_chars = [char for char in chars if is_graph_character_visible(char)]
    visible_ids = {str(char.id) for char in visible_chars}
    hidden_chars = [char for char in chars if str(char.id) not in visible_ids]
    chars, id_map = collapse_graph_characters(visible_chars)
    canonical_ids = {str(char.id) for char in chars}
    char_names = {str(char.id): char.name for char in chars}
    rels = historical_rels if include_inactive else [
        rel for rel in historical_rels if relationship_effective_status(rel, chapter) == "ongoing"
    ]
    rels = [
        rel for rel in rels
        if str(rel.character_a_id) in visible_ids and str(rel.character_b_id) in visible_ids
    ]

    rel_summaries: dict[str, list[str]] = {}
    edge_map: dict[tuple[str, ...], dict[str, Any]] = {}
    if want_edges:
        for rel in rels:
            source = id_map.get(str(rel.character_a_id), str(rel.character_a_id))
            target = id_map.get(str(rel.character_b_id), str(rel.character_b_id))
            if source == target or source not in canonical_ids or target not in canonical_ids:
                continue
            left_key, right_key = sorted((source, target))
            shared_labels = normalize_relationship_labels(getattr(rel, "shared_labels", None))
            source_to_target_labels = normalize_relationship_labels(getattr(rel, "character_a_to_b_labels", None))
            target_to_source_labels = normalize_relationship_labels(getattr(rel, "character_b_to_a_labels", None))
            if source != left_key:
                source_to_target_labels, target_to_source_labels = target_to_source_labels, source_to_target_labels
            label_key = (
                ",".join(shared_labels),
                ",".join(source_to_target_labels),
                ",".join(target_to_source_labels),
            )
            if include_inactive:
                key = (
                    left_key,
                    right_key,
                    rel.rel_type or "neutral",
                    *label_key,
                    str(rel.from_chapter or 0),
                    str(rel.to_chapter or "open"),
                )
            else:
                key = (left_key, right_key, rel.rel_type or "neutral", *label_key)
            bucket = edge_map.setdefault(key, {
                "relationship_ids": [], "source": key[0], "target": key[1],
                "type": rel.rel_type or "neutral", "sentiment_values": [],
                "descriptions": [], "chapters": [], "end_chapters": [],
                "shared_labels": [], "source_to_target_labels": [], "target_to_source_labels": [],
                "label_evidence": {},
            })
            bucket["relationship_ids"].append(str(rel.id))
            bucket["shared_labels"].extend(label for label in shared_labels if label not in bucket["shared_labels"])
            bucket["source_to_target_labels"].extend(label for label in source_to_target_labels if label not in bucket["source_to_target_labels"])
            bucket["target_to_source_labels"].extend(label for label in target_to_source_labels if label not in bucket["target_to_source_labels"])
            if getattr(rel, "label_evidence", None):
                bucket["label_evidence"].update(dict(getattr(rel, "label_evidence") or {}))
            if rel.sentiment is not None:
                bucket["sentiment_values"].append(rel.sentiment)
            if rel.description:
                bucket["descriptions"].append(rel.description.strip())
            if rel.from_chapter is not None:
                bucket["chapters"].append(rel.from_chapter)
            if rel.to_chapter is not None:
                bucket["end_chapters"].append(rel.to_chapter)

        for item in edge_map.values():
            for char_id, other_id in ((item["source"], item["target"]), (item["target"], item["source"])):
                directional = item["source_to_target_labels"] if char_id == item["source"] else item["target_to_source_labels"]
                labels = directional + [label for label in item["shared_labels"] if label not in directional]
                label_text = ", ".join(relationship_label_display(label) for label in labels[:4]) or item["type"].replace("_", " ")
                rel_summaries.setdefault(char_id, []).append(
                    f"{label_text.capitalize()} with {char_names.get(other_id, other_id)}."
                )

    chars_with_details = []
    if want_nodes:
        latest_states: dict[str, CharacterState] = {}
        if chars:
            state_rows_result = await db.execute(
                select(CharacterState)
                .where(CharacterState.character_id.in_([char.id for char in chars]), CharacterState.at_chapter <= chapter)
                .order_by(CharacterState.character_id, desc(CharacterState.at_chapter))
            )
            state_rows = state_rows_result.scalars().all()
            for state in state_rows:
                latest_states.setdefault(str(state.character_id), state)

        for c in chars:
            latest_state = latest_states.get(str(c.id))
            trait_snapshot_raw = cast(dict[str, Any], latest_state.trait_snapshot) if latest_state else cast(dict[str, Any], c.trait_state or {})
            trait_snapshot = dict(trait_snapshot_raw)
            chars_with_details.append({
                "id": str(c.id), "name": c.name, "role": c.role, "first_chapter": c.first_chapter,
                "description": relationship_node_description(c, trait_snapshot, rel_summaries.get(str(c.id), [])),
                "trait_state": trait_snapshot, "personality_tags": c.personality_tags or [],
                "aliases": c.aliases or [], "motivations": c.motivations or [],
                "fears": c.fears or [], "archetype": c.archetype, "arc_summary": c.arc_summary,
                "mention_count": c.mention_count or 0, "is_manual": getattr(c, "is_manual", False),
                "graph_visibility_override": analyses[str(c.id)]["override"],
                "visibility_score": analyses[str(c.id)]["score"],
                "visibility_reasons": analyses[str(c.id)]["reasons"],
            })

    hidden_node_list = []
    if want_hidden_nodes:
        hidden_node_list = [
            {
                "id": str(char.id),
                "name": char.name,
                "role": char.role,
                "first_chapter": char.first_chapter,
                "mention_count": char.mention_count or 0,
                "is_manual": getattr(char, "is_manual", False),
                "graph_visibility_override": analyses[str(char.id)]["override"],
                "visibility_score": analyses[str(char.id)]["score"],
                "visibility_reasons": analyses[str(char.id)]["reasons"],
                "connected_relationship_count": relationship_counts.get(str(char.id), 0),
            }
            for char in sorted(hidden_chars, key=lambda item: (item.first_chapter, item.name))
        ]

    graph = {
        "nodes": chars_with_details,
        "edges": [
            {
                "id": item["relationship_ids"][0] if item["relationship_ids"] else None,
                "source": item["source"], "target": item["target"], "type": item["type"],
                "sentiment": round(sum(item["sentiment_values"]) / len(item["sentiment_values"]), 3) if item["sentiment_values"] else None,
                "description": " ".join(dict.fromkeys(item["descriptions"])) or None,
                "from_chapter": min(item["chapters"]) if item["chapters"] else None,
                "to_chapter": max(item["end_chapters"]) if item["end_chapters"] else None,
                "status": "ended" if item["end_chapters"] and max(item["end_chapters"]) < chapter else "ongoing",
                "shared_labels": item["shared_labels"],
                "character_a_to_b_labels": item["source_to_target_labels"],
                "character_b_to_a_labels": item["target_to_source_labels"],
                "label_evidence": item["label_evidence"],
            }
            for item in edge_map.values()
        ],
        "hidden_nodes": hidden_node_list,
    }
    if use_cache and (graph["nodes"] or graph["edges"] or graph["hidden_nodes"]):
        await cache_set(cache_key, graph, settings.REDIS_TTL_GRAPH)

    graph = apply_sparse_includes(graph, include)
    all_edges = graph.get("edges", [])
    total_edges = len(all_edges)
    graph["edges"] = all_edges[offset : offset + limit]
    graph["total_edges"] = total_edges
    graph["limit"] = limit
    graph["offset"] = offset
    graph["has_more"] = (offset + limit) < total_edges
    return graph


@router.get("/{book_id}/relationship-evolution")
async def get_relationship_evolution(
    book_id: uuid.UUID,
    chapter: int = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book, collaborator = await get_book_with_collaboration_access(db, book_id, current_user)
    if collaborator is not None and not collaboration_allows_chapter(collaborator, chapter):
        raise HTTPException(403, "This share does not include that chapter.")
    if collaborator is None:
        require_author_access(current_user)
    book_version = await get_book_cache_version(str(book_id))
    progress_version = await get_reader_progress_cache_version(str(book_id), str(current_user.id))
    cached = await get_relationship_evolution_cache(
        str(book_id),
        str(current_user.id),
        chapter,
        book_version,
        progress_version,
    )
    if cached is not None:
        return cached

    rels_result = await db.execute(
        select(CharacterRelationship).where(
            CharacterRelationship.book_id == book_id,
            CharacterRelationship.from_chapter <= chapter,
        ).order_by(CharacterRelationship.from_chapter, CharacterRelationship.character_a_id, CharacterRelationship.character_b_id)
    )
    rels, _ = canonicalize_relationship_book_rows(rels_result.scalars().all())

    chars_result = await db.execute(select(Character).where(Character.book_id == book_id))
    chars = chars_result.scalars().all()
    name_by_id = {char.id: char.name for char in chars}

    grouped: dict[tuple[str, str], list[dict]] = {}
    for rel in rels:
        a_name = name_by_id.get(rel.character_a_id)
        b_name = name_by_id.get(rel.character_b_id)
        if not a_name or not b_name:
            continue
        key = (a_name, b_name) if a_name <= b_name else (b_name, a_name)
        grouped.setdefault(key, []).append({
            "chapter": rel.from_chapter, "type": rel.rel_type,
            "description": rel.description, "sentiment": rel.sentiment,
            "to_chapter": rel.to_chapter,
            "status": relationship_effective_status(rel, chapter),
            "shared_labels": list(getattr(rel, "shared_labels", None) or []),
            "character_a_to_b_labels": list(getattr(rel, "character_a_to_b_labels", None) or []),
            "character_b_to_a_labels": list(getattr(rel, "character_b_to_a_labels", None) or []),
            "label_evidence": dict(getattr(rel, "label_evidence", None) or {}),
        })

    payload = {"pairs": [{"characters": list(key), "events": value} for key, value in grouped.items()]}
    await set_relationship_evolution_cache(
        str(book_id),
        str(current_user.id),
        chapter,
        book_version,
        progress_version,
        payload,
    )
    return payload
