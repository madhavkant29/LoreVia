from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps.auth import get_current_user
from app.api.deps.rate_limit import rate_limit_world_building_ai
from app.api.v1.routes import world_building_documents, world_building_notes
from app.core.database import get_db
from app.models.book import Book, Series
from app.models.intelligence import (
    WikiEntry,
    WorldCanonicalIdentity,
    WorldElement,
    WorldNote,
)
from app.schemas.world_building import (
    CanonOverrideBody,
    CanonOverrideOut,
    GapAnalysisRequest,
    GapAnalysisResponse,
    IntegrationAnalysisResponse,
    SuggestionAcceptance,
    WikiEntryOut,
    WikiGenerationResponse,
    WorldBuildingBootstrapOut,
    WorldElementOut,
    WorldQueryRequest,
    WorldQueryResponse,
)
from app.services.world_analysis_refresh_service import enqueue_world_analysis_refresh
from app.services.world_building_access_service import get_owned_world_building_book
from app.utils.billing_utils import require_author_access
from app.utils.tag_utils import (
    ENTITY_TYPE_WORLD_NOTE,
    list_custom_tags_for_entity_ids,
)
from app.utils.world_building_document_utils import (
    get_world_building_document,
    list_world_building_documents,
)
from app.utils.world_building_note_utils import save_canon_override, save_world_note
from app.utils.world_building_response_utils import (
    serialize_canon_override,
    serialize_world_document,
    serialize_world_note,
)
from app.utils.world_building_utils import (
    build_world_logic_response,
    classify_world_intent,
    detect_integration_analysis,
    detect_series_world_analysis,
    detect_world_gaps,
    list_extracted_world_elements,
    read_integration_analysis_snapshot,
    read_series_world_analysis_snapshot,
    read_world_gap_analysis_snapshot,
)
from app.utils.world_building_wiki_utils import generate_wiki_from_manuscript

router = APIRouter()
router.include_router(world_building_documents.router)
router.include_router(world_building_notes.router)


async def _queue_stale_world_snapshot(
    payload: dict,
    *,
    scope: str,
    target_id: uuid.UUID,
) -> dict:
    if not payload.get("is_stale") or payload.get("refresh_job_id"):
        return payload
    refresh_job_id = await enqueue_world_analysis_refresh(scope=scope, target_id=target_id)
    if refresh_job_id:
        return {**payload, "refresh_job_id": refresh_job_id}
    return payload


@router.get("/{book_id}/world-building/bootstrap", response_model=WorldBuildingBootstrapOut)
async def get_world_building_bootstrap(
    book_id: uuid.UUID,
    document_id: uuid.UUID | None = Query(None),
    focus: str = Query("editor", pattern="^(editor|gap)$"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_world_building_book(db, book_id, current_user.id)
    require_author_access(current_user)
    documents = await list_world_building_documents(db, book)
    selected_document = None
    if document_id is not None:
        document = await get_world_building_document(db, book, document_id)
        # Bootstrap is a dashboard read: the editor fetches source content from
        # its dedicated document endpoint after the user selects a document.
        selected_document = serialize_world_document(document, payload={})

    notes = (
        (
            await db.execute(
                select(WorldNote)
                .where(WorldNote.book_id == book.id, WorldNote.note_type != "canon_override")
                .order_by(WorldNote.created_at.desc())
            )
        )
        .scalars()
        .all()
    )
    tags_by_note = await list_custom_tags_for_entity_ids(
        db,
        entity_type=ENTITY_TYPE_WORLD_NOTE,
        entity_ids=[note.id for note in notes],
        book_id=book.id,
    )
    canon_overrides = (
        (
            await db.execute(
                select(WorldCanonicalIdentity)
                .where(WorldCanonicalIdentity.book_id == book.id)
                .order_by(
                    WorldCanonicalIdentity.updated_at.desc(),
                    WorldCanonicalIdentity.created_at.desc(),
                )
            )
        )
        .scalars()
        .all()
    )
    wiki_rows = (
        (
            await db.execute(
                select(WikiEntry)
                .where(WikiEntry.book_id == book.id)
                .order_by(WikiEntry.entry_type.asc(), WikiEntry.name.asc())
            )
        )
        .scalars()
        .all()
    )
    gap_analysis = None
    if focus == "gap" and documents:
        gap_payload = await read_world_gap_analysis_snapshot(db, book)
        gap_analysis = GapAnalysisResponse(
            **(
                await _queue_stale_world_snapshot(
                    gap_payload,
                    scope="book",
                    target_id=book.id,
                )
            )
        )
    return WorldBuildingBootstrapOut(
        documents=[serialize_world_document(document) for document in documents],
        selected_document=selected_document,
        notes=[serialize_world_note(note, tags=tags_by_note.get(note.id, [])) for note in notes],
        canon_overrides=[serialize_canon_override(identity) for identity in canon_overrides],
        elements=await list_extracted_world_elements(db, book),
        wiki=[
            WikiEntryOut(
                id=str(item.id),
                book_id=str(item.book_id),
                entry_type=item.entry_type,
                name=item.name,
                description=item.description,
                first_mention=item.first_mention,
                related_char_ids=item.related_char_ids,
                created_at=item.created_at,
            )
            for item in wiki_rows
        ],
        stats=None,
        gap_analysis=gap_analysis,
    )


@router.post("/{book_id}/world-building/analyze")
async def analyze_world_building(
    book_id: uuid.UUID,
    body: GapAnalysisRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_world_building_ai),
):
    book = await get_owned_world_building_book(db, book_id, current_user.id)
    require_author_access(current_user)
    mode = body.mode or classify_world_intent(body.query)
    if mode == "story_integration":
        payload = await detect_integration_analysis(db, book)
        if body.auto_create_notes:
            for item in payload["integration_opportunities"][:5]:
                world_document_id = item.get("world_document_id")
                note = await save_world_note(
                    db,
                    user_id=current_user.id,
                    book_id=book.id,
                    world_element_id=None,
                    world_document_id=uuid.UUID(world_document_id) if world_document_id else None,
                    note_type="integration",
                    chapter_number=item.get("target_chapter"),
                    title=item.get("element_name"),
                    body=item.get("description") or "",
                    priority="high" if int(item.get("priority") or 0) >= 6 else "medium",
                    status="open",
                    linked_integration_id=item.get("id"),
                    context_label=item.get("world_document_title"),
                    suggested_fix="\n".join(
                        str(suggestion) for suggestion in (item.get("suggestions") or [])[:2]
                    ),
                )
                await db.refresh(note)
        await db.commit()
        return payload

    payload = await detect_world_gaps(db, book)
    if body.auto_create_notes:
        for item in payload["priority_gaps"][:5]:
            priority_value = int(item.get("priority") or 0)
            note = await save_world_note(
                db,
                user_id=current_user.id,
                book_id=book.id,
                world_element_id=None,
                world_document_id=uuid.UUID(item["world_document_id"])
                if item.get("world_document_id")
                else None,
                note_type="world_gap",
                chapter_number=item.get("story_chapter_number"),
                title=item.get("title"),
                body=item.get("description") or "",
                priority="critical"
                if priority_value >= 8
                else ("high" if priority_value >= 6 else "medium"),
                status="open",
                linked_gap_id=item.get("id"),
                context_label=item.get("world_document_title"),
                suggested_fix=item.get("suggested_fix"),
            )
            await db.refresh(note)
    await db.commit()
    return payload


@router.get("/{book_id}/world-building/gaps", response_model=GapAnalysisResponse)
async def get_world_gaps(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_world_building_ai),
):
    book = await get_owned_world_building_book(db, book_id, current_user.id)
    require_author_access(current_user)
    payload = await read_world_gap_analysis_snapshot(db, book)
    payload = await _queue_stale_world_snapshot(payload, scope="book", target_id=book.id)
    return GapAnalysisResponse(**payload)


@router.get("/{book_id}/world-building/integration", response_model=IntegrationAnalysisResponse)
async def get_world_integration(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_world_building_book(db, book_id, current_user.id)
    require_author_access(current_user)
    payload = await read_integration_analysis_snapshot(db, book)
    payload = await _queue_stale_world_snapshot(payload, scope="book", target_id=book.id)
    return IntegrationAnalysisResponse(**payload)


@router.get("/{book_id}/world-building/elements", response_model=list[WorldElementOut])
async def list_world_elements(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_world_building_book(db, book_id, current_user.id)
    require_author_access(current_user)
    snapshot = await read_world_gap_analysis_snapshot(db, book)
    await _queue_stale_world_snapshot(snapshot, scope="book", target_id=book.id)
    return await list_extracted_world_elements(db, book)


@router.get("/{book_id}/world-building/wiki", response_model=list[WikiEntryOut])
async def list_auto_wiki(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_world_building_book(db, book_id, current_user.id)
    require_author_access(current_user)
    rows = (
        (
            await db.execute(
                select(WikiEntry)
                .where(WikiEntry.book_id == book.id)
                .order_by(WikiEntry.entry_type.asc(), WikiEntry.name.asc())
            )
        )
        .scalars()
        .all()
    )
    return [
        WikiEntryOut(
            id=str(item.id),
            book_id=str(item.book_id),
            entry_type=item.entry_type,
            name=item.name,
            description=item.description,
            first_mention=item.first_mention,
            related_char_ids=item.related_char_ids,
            created_at=item.created_at,
        )
        for item in rows
    ]


@router.post("/{book_id}/world-building/wiki/generate", response_model=WikiGenerationResponse)
async def generate_auto_wiki(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_world_building_book(db, book_id, current_user.id)
    require_author_access(current_user)
    generated = await generate_wiki_from_manuscript(db, book)
    await db.commit()
    return WikiGenerationResponse(
        generated_count=len(generated),
        updated_names=[item.name for item in generated[:20]],
        entries=[
            WikiEntryOut(
                id=str(item.id),
                book_id=str(item.book_id),
                entry_type=item.entry_type,
                name=item.name,
                description=item.description,
                first_mention=item.first_mention,
                related_char_ids=item.related_char_ids,
                created_at=item.created_at,
            )
            for item in generated[:40]
        ],
    )


@router.post("/{book_id}/world-building/query", response_model=WorldQueryResponse)
async def query_world_building(
    book_id: uuid.UUID,
    body: WorldQueryRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    _=Depends(rate_limit_world_building_ai),
):
    book = await get_owned_world_building_book(db, book_id, current_user.id)
    require_author_access(current_user)
    mode = body.mode or classify_world_intent(body.query)
    snapshot = (
        await read_integration_analysis_snapshot(db, book)
        if mode == "story_integration"
        else await read_world_gap_analysis_snapshot(db, book)
    )
    await _queue_stale_world_snapshot(snapshot, scope="book", target_id=book.id)
    payload = await build_world_logic_response(db, book, body.query, mode)
    return WorldQueryResponse(**payload)


@router.get("/series/{series_id}/world-building/series-analysis")
async def get_series_world_analysis(
    series_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    series = await db.get(Series, series_id)
    if not series or series.user_id != current_user.id:
        raise HTTPException(404, "Series not found")
    require_author_access(current_user)
    payload = await read_series_world_analysis_snapshot(db, series_id)
    gap_payload = payload.get("gap_analysis") if isinstance(payload, dict) else None
    if isinstance(gap_payload, dict):
        queued = await _queue_stale_world_snapshot(
            gap_payload,
            scope="series",
            target_id=series_id,
        )
        if queued is not gap_payload:
            payload = {**payload, "gap_analysis": queued}
            integration_payload = payload.get("integration_analysis")
            if isinstance(integration_payload, dict):
                payload["integration_analysis"] = {
                    **integration_payload,
                    "refresh_job_id": queued.get("refresh_job_id"),
                }
    return {**payload, "series_name": series.name}


@router.post("/series/{series_id}/world-building/series-analysis/refresh")
async def refresh_series_world_analysis(
    series_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Explicitly refresh a series snapshot; reads remain storage-free."""

    series = await db.get(Series, series_id)
    if not series or series.user_id != current_user.id:
        raise HTTPException(404, "Series not found")
    require_author_access(current_user)
    payload = await detect_series_world_analysis(db, series_id)
    await db.commit()
    return {**payload, "series_name": series.name}


@router.post("/{world_element_id}/world-building/accept-suggestion")
async def accept_world_suggestion(
    world_element_id: uuid.UUID,
    body: SuggestionAcceptance,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    element = await db.get(WorldElement, world_element_id)
    if not element:
        raise HTTPException(404, "World element not found")
    book = await db.get(Book, element.book_id)
    if not book or book.user_id != current_user.id:
        raise HTTPException(404, "World element not found")
    require_author_access(current_user)
    suggestions = list(element.suggestions or [])
    remaining = []
    for item in suggestions:
        if isinstance(item, dict):
            if str(item.get("id") or "") == body.suggestion_id:
                continue
        elif str(item) == body.suggestion_id:
            continue
        remaining.append(item)
    element.suggestions = remaining
    if body.mark_implemented:
        element.edited_by_author = True
        element.edited_at = datetime.now(UTC)
    await db.commit()
    return {"accepted": body.suggestion_id, "remaining": len(remaining)}


@router.get("/{book_id}/world-building/canon-overrides", response_model=list[CanonOverrideOut])
async def list_canon_overrides(
    book_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_world_building_book(db, book_id, current_user.id)
    require_author_access(current_user)
    overrides = (
        (
            await db.execute(
                select(WorldCanonicalIdentity)
                .where(WorldCanonicalIdentity.book_id == book.id)
                .order_by(
                    WorldCanonicalIdentity.updated_at.desc(),
                    WorldCanonicalIdentity.created_at.desc(),
                )
            )
        )
        .scalars()
        .all()
    )
    return [serialize_canon_override(identity) for identity in overrides]


@router.post("/{book_id}/world-building/canon-overrides", response_model=CanonOverrideOut)
async def create_canon_override(
    book_id: uuid.UUID,
    body: CanonOverrideBody,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    book = await get_owned_world_building_book(db, book_id, current_user.id)
    require_author_access(current_user)
    identity = await save_canon_override(
        db,
        user_id=current_user.id,
        book=book,
        canonical_name=body.canonical_name,
        aliases=body.aliases,
        entity_type=body.entity_type,
        notes=body.notes,
    )
    await db.commit()
    await enqueue_world_analysis_refresh(scope="book", target_id=book.id)
    await db.refresh(identity)
    return serialize_canon_override(identity)
