from __future__ import annotations

import json
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.llm import get_openai_client
from app.models.book import Book, BookCollaborator, Chapter
from app.models.character import Character, CharacterVoiceProfile
from app.models.intelligence import WorldElement
from app.schemas.advisor import BetaReaderAnalysisRequest, BetaReaderReportOut
from app.utils.advisor_beta_reader_analysis_utils import (
    analyze_character_voice_distinctness,
    analyze_overused_language,
    build_beta_reader_request_hash,
    build_chapter_source_fingerprint,
    build_passage_source_fingerprint,
    build_scoped_voice_profiles,
    normalize_beta_reader_synthesis,
    split_beta_reader_batches,
)
from app.utils.advisor_beta_reader_report_utils import (
    beta_reader_report_timestamp,
    bound_beta_reader_report,
    build_beta_reader_revision_candidates,
    find_cached_beta_reader_report,
    merge_beta_reader_report,
    normalize_ai_beta_reader_state,
)
from app.utils.advisor_route_errors import ADVISOR_STREAM_ERRORS
from app.utils.books import manuscript, writer_workspace
from app.utils.books.collaboration_access import (
    collaboration_allows_chapter,
    collaboration_is_chapter_restricted,
)
from app.utils.llm_usage_utils import create_tracked_chat_completion

ProgressCallback = Callable[[dict[str, Any]], Awaitable[None]]

_BATCH_SYSTEM = """You are an attentive fiction beta reader. Read the supplied manuscript section and return JSON only:
{
  "overall_impression": "specific reader reaction",
  "reader_vibe": "short description of the manuscript's emotional and genre feel",
  "story_understanding": "concise account of the premise, emotional core, central relationships, and themes",
  "strengths": ["specific, manuscript-grounded craft strength with a chapter or scene reference when available"],
  "reader_questions": ["questions raised while reading"],
  "prioritized_revisions": ["highest-value revision"],
  "findings": [{
    "category": "engagement|pacing|clarity|character|voice|continuity",
    "severity": "high|medium|low",
    "title": "short label",
    "description": "reader-centered explanation",
    "chapter_number": 1,
    "evidence": "brief exact or closely grounded excerpt",
    "recommendation": "concrete revision direction",
    "reader_question": "optional question"
  }]
}
Do not invent events or quotes. Only name strengths supported by the supplied manuscript. Strengths may include character work, scene construction, theme, pacing, dialogue, emotional impact, or voice, but do not force every category and return an empty list when no strength can be grounded. Focus on reader experience, not copyediting.
"""

_SYNTHESIS_SYSTEM = """You are the lead beta reader synthesizing section reports and deterministic craft metrics. Return JSON only in the same schema you received. Consolidate duplicates, preserve chapter numbers, prioritize no more than eight revisions, and never change supplied repetition counts or voice scores."""


def beta_reader_request_payload(body: BetaReaderAnalysisRequest) -> dict[str, Any]:
    return {
        "scope": body.scope,
        "text_hash": build_passage_source_fingerprint(body.text or "") if body.text else None,
        "chapter_number": body.chapter_number,
        "chapter_start": body.chapter_start,
        "chapter_end": body.chapter_end,
        "character_ids": sorted(str(value) for value in body.character_ids),
        "checks": sorted(body.checks),
    }


async def _book_chapters(db: AsyncSession, book_id: uuid.UUID) -> list[Chapter]:
    return list(
        (
            await db.execute(
                select(Chapter).where(Chapter.book_id == book_id).order_by(Chapter.number.asc())
            )
        )
        .scalars()
        .all()
    )


def select_beta_reader_chapters(
    chapters: list[Chapter],
    *,
    body: BetaReaderAnalysisRequest,
    collaborator: BookCollaborator | None,
) -> list[Chapter]:
    if body.scope == "passage":
        if body.chapter_number is None and collaboration_is_chapter_restricted(collaborator):
            raise HTTPException(
                403,
                "Select an allowed chapter when analyzing a passage with restricted access.",
            )
        if body.chapter_number is not None and not collaboration_allows_chapter(
            collaborator, body.chapter_number
        ):
            raise HTTPException(403, "This collaboration does not include that chapter.")
        return []
    if body.scope == "chapter":
        requested = {int(body.chapter_number or 0)}
    elif body.scope == "chapter_range":
        requested = set(range(int(body.chapter_start or 0), int(body.chapter_end or 0) + 1))
    else:
        requested = {chapter.number for chapter in chapters}
    selected = [chapter for chapter in chapters if chapter.number in requested]
    if {chapter.number for chapter in selected} != requested:
        raise HTTPException(404, "One or more requested chapters were not found.")
    denied = [
        chapter.number
        for chapter in selected
        if not collaboration_allows_chapter(collaborator, chapter.number)
    ]
    if denied:
        raise HTTPException(403, "This collaboration does not include every requested chapter.")
    return selected


async def prepare_beta_reader_run(
    db: AsyncSession,
    *,
    book: Book,
    collaborator: BookCollaborator | None,
    body: BetaReaderAnalysisRequest,
) -> dict[str, Any]:
    chapters = await _book_chapters(db, book.id)
    selected_chapters = select_beta_reader_chapters(chapters, body=body, collaborator=collaborator)
    if body.character_ids:
        found_ids = set(
            (
                await db.execute(
                    select(Character.id).where(
                        Character.book_id == book.id, Character.id.in_(body.character_ids)
                    )
                )
            )
            .scalars()
            .all()
        )
        if found_ids != set(body.character_ids):
            raise HTTPException(400, "One or more selected characters do not belong to this book.")
    request_hash = build_beta_reader_request_hash(beta_reader_request_payload(body))
    source_fingerprint = (
        build_passage_source_fingerprint(body.text or "")
        if body.scope == "passage"
        else build_chapter_source_fingerprint(selected_chapters)
    )
    cached = find_cached_beta_reader_report(
        (book.writer_workspace or {}).get("ai_beta_reader")
        if isinstance(book.writer_workspace, dict)
        else None,
        request_hash=request_hash,
        source_fingerprint=source_fingerprint,
    )
    return {
        "chapters": selected_chapters,
        "request_hash": request_hash,
        "source_fingerprint": source_fingerprint,
        "cached": cached,
    }


async def _character_context(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    selected_ids: list[uuid.UUID],
) -> tuple[list[Character], list[CharacterVoiceProfile], list[str]]:
    character_query = select(Character).where(Character.book_id == book_id)
    if selected_ids:
        character_query = character_query.where(Character.id.in_(selected_ids))
    characters = list(
        (await db.execute(character_query.order_by(Character.mention_count.desc(), Character.name)))
        .scalars()
        .all()
    )
    character_ids = [character.id for character in characters]
    profiles = (
        list(
            (
                await db.execute(
                    select(CharacterVoiceProfile).where(
                        CharacterVoiceProfile.book_id == book_id,
                        CharacterVoiceProfile.character_id.in_(character_ids),
                    )
                )
            )
            .scalars()
            .all()
        )
        if character_ids
        else []
    )
    world_names = list(
        (
            await db.execute(
                select(WorldElement.name)
                .where(WorldElement.book_id == book_id)
                .order_by(WorldElement.usage_count.desc())
                .limit(100)
            )
        )
        .scalars()
        .all()
    )
    aliases = [
        value
        for character in characters
        for value in [character.name, *(character.aliases or [])]
        if value
    ]
    return characters, profiles, [*aliases, *world_names]


def _batch_text(batch: list[tuple[int, str]]) -> str:
    return "\n\n".join(f"--- Chapter {number} ---\n{text}" for number, text in batch)


async def _reader_feedback_synthesis(
    *,
    db: AsyncSession,
    book: Book,
    user_id: uuid.UUID,
    chapter_texts: dict[int, str],
    overused_terms: list[dict[str, Any]],
    voices: list[dict[str, Any]],
    progress: ProgressCallback | None,
) -> dict[str, Any]:
    batches = split_beta_reader_batches(chapter_texts)
    if not batches:
        return normalize_beta_reader_synthesis("{}")
    client = get_openai_client()
    batch_results: list[dict[str, Any]] = []
    try:
        for index, batch in enumerate(batches, start=1):
            if progress:
                await progress(
                    {
                        "stage": "reader_feedback",
                        "completed": index - 1,
                        "total": len(batches),
                        "message": f"Reading manuscript batch {index} of {len(batches)}...",
                    }
                )
            response = await create_tracked_chat_completion(
                client=client,
                feature="advisor_beta_reader",
                model=settings.OPENAI_INTEL_MODEL,
                db=db,
                user_id=user_id,
                book_id=book.id,
                temperature=0.2,
                max_tokens=1800,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": _BATCH_SYSTEM},
                    {
                        "role": "user",
                        "content": f"Book: {book.title}\n\n{_batch_text(batch)}",
                    },
                ],
            )
            batch_results.append(
                normalize_beta_reader_synthesis(response.choices[0].message.content or "{}")
            )
        if len(batch_results) == 1:
            return batch_results[0]
        deterministic = {
            "top_repetitions": [
                {"term": item["term"], "count": item["count"], "rate": item["rate_per_1000"]}
                for item in overused_terms[:12]
            ],
            "voice_distinctness": [
                {
                    "character": item["character_name"],
                    "distinctness": item["distinctness_score"],
                    "closest": item["closest_character_name"],
                    "confidence": item["confidence"],
                }
                for item in voices
            ],
        }
        response = await create_tracked_chat_completion(
            client=client,
            feature="advisor_beta_reader",
            model=settings.OPENAI_INTEL_MODEL,
            db=db,
            user_id=user_id,
            book_id=book.id,
            temperature=0.1,
            max_tokens=2200,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SYNTHESIS_SYSTEM},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"section_reports": batch_results, "deterministic_metrics": deterministic}
                    ),
                },
            ],
        )
        return normalize_beta_reader_synthesis(response.choices[0].message.content or "{}")
    finally:
        # The client is owned by the process/loop registry and is closed only
        # during application or worker shutdown.
        pass


async def build_beta_reader_report(
    db: AsyncSession,
    *,
    book: Book,
    collaborator: BookCollaborator | None,
    user_id: uuid.UUID,
    body: BetaReaderAnalysisRequest,
    progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    prepared = await prepare_beta_reader_run(db, book=book, collaborator=collaborator, body=body)
    selected_chapters: list[Chapter] = prepared["chapters"]
    if body.scope == "passage":
        passage_key = body.chapter_number or 0
        chapter_texts = {passage_key: body.text or ""}
        requested_chapters = [body.chapter_number] if body.chapter_number else []
    else:
        chapter_texts = await manuscript.load_chapter_texts(selected_chapters)
        requested_chapters = [chapter.number for chapter in selected_chapters]
    usable_texts = {number: text for number, text in chapter_texts.items() if text.strip()}
    if not usable_texts:
        raise ValueError("No manuscript text was available for this AI beta read.")
    missing_chapters = [
        chapter.number
        for chapter in selected_chapters
        if not chapter_texts.get(chapter.number, "").strip()
    ]
    warnings = [
        f"Chapter {number} could not be loaded and was excluded from this report."
        for number in missing_chapters
    ]
    characters, profiles, excluded_names = await _character_context(
        db, book_id=book.id, selected_ids=body.character_ids
    )
    if progress:
        await progress(
            {
                "stage": "analysis",
                "completed": 0,
                "total": 1,
                "message": "Counting repeated language and comparing voices...",
            }
        )
    overused_terms = (
        analyze_overused_language(usable_texts, excluded_names=excluded_names)
        if "repetition" in body.checks
        else []
    )
    if "voice" in body.checks:
        scoped_profiles = build_scoped_voice_profiles(
            usable_texts,
            characters,
            profiles,
            include_stored_signatures=not collaboration_is_chapter_restricted(collaborator),
        )
        voice_characters = characters
        if collaboration_is_chapter_restricted(collaborator):
            scoped_character_ids = {
                str(profile["character_id"])
                for profile in scoped_profiles
                if int(profile.get("sample_dialogue_count") or 0) > 0
            }
            voice_characters = [
                character for character in characters if str(character.id) in scoped_character_ids
            ]
            scoped_profiles = [
                profile
                for profile in scoped_profiles
                if str(profile["character_id"]) in scoped_character_ids
            ]
        voices, voice_warnings = analyze_character_voice_distinctness(
            voice_characters, scoped_profiles
        )
    else:
        voice_characters, voices, voice_warnings = characters, [], []
    warnings.extend(voice_warnings)
    synthesis = normalize_beta_reader_synthesis("{}")
    if "reader_feedback" in body.checks:
        try:
            synthesis = await _reader_feedback_synthesis(
                db=db,
                book=book,
                user_id=user_id,
                chapter_texts=usable_texts,
                overused_terms=overused_terms,
                voices=voices,
                progress=progress,
            )
        except ADVISOR_STREAM_ERRORS:
            if body.checks == ["reader_feedback"]:
                raise
            warnings.append(
                "Reader-style synthesis was unavailable; deterministic repetition and voice results are still included."
            )
    findings = synthesis["findings"]
    candidates = build_beta_reader_revision_candidates(
        overused_terms=overused_terms,
        character_voices=voices,
        findings=findings,
    )
    word_count = sum(len(text.split()) for text in usable_texts.values())
    report = {
        "report_id": str(uuid.uuid4()),
        "scope": body.scope,
        "request_hash": prepared["request_hash"],
        "source_fingerprint": prepared["source_fingerprint"],
        "created_at": beta_reader_report_timestamp(),
        "is_stale": False,
        "checks": body.checks,
        "coverage": {
            "requested_chapters": requested_chapters,
            "analyzed_chapters": [
                number for number in requested_chapters if number not in missing_chapters
            ],
            "missing_chapters": missing_chapters,
            "word_count": word_count,
            "character_count": len(voice_characters),
        },
        "overall_impression": synthesis["overall_impression"]
        or (
            "LoreVia completed the reader pass, but could not ground a reliable overall impression."
            if body.checks == ["reader_feedback"]
            else "The deterministic craft pass completed. Review the repetition and character-voice tabs for actionable findings."
        ),
        "reader_vibe": synthesis["reader_vibe"],
        "story_understanding": synthesis["story_understanding"],
        "strengths": synthesis["strengths"],
        "reader_questions": synthesis["reader_questions"],
        "prioritized_revisions": synthesis["prioritized_revisions"],
        "overused_terms": overused_terms,
        "character_voices": voices,
        "findings": findings,
        "revision_candidates": candidates,
        "warnings": list(dict.fromkeys(warnings)),
    }
    validated = bound_beta_reader_report(report)
    if validated is None:
        raise ValueError("AI beta reader produced an invalid report.")
    return validated


async def persist_beta_reader_report(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    report: dict[str, Any],
) -> dict[str, Any]:
    fresh_book = (
        await db.execute(select(Book).where(Book.id == book_id).with_for_update())
    ).scalar_one()
    workspace = writer_workspace.normalize_writer_workspace(
        fresh_book.writer_workspace if isinstance(fresh_book.writer_workspace, dict) else None
    )
    workspace["ai_beta_reader"] = merge_beta_reader_report(workspace.get("ai_beta_reader"), report)
    fresh_book.writer_workspace = workspace
    await db.commit()
    return report


async def list_beta_reader_reports(
    db: AsyncSession,
    *,
    book: Book,
    collaborator: BookCollaborator | None = None,
) -> list[dict[str, Any]]:
    state = normalize_ai_beta_reader_state(
        (book.writer_workspace or {}).get("ai_beta_reader")
        if isinstance(book.writer_workspace, dict)
        else None
    )
    chapters = await _book_chapters(db, book.id)
    chapters_by_number = {chapter.number: chapter for chapter in chapters}
    reports: list[dict[str, Any]] = []
    for source in state["reports"]:
        report = dict(source)
        requested_chapters = report["coverage"]["requested_chapters"]
        if collaboration_is_chapter_restricted(collaborator):
            if not requested_chapters or any(
                not collaboration_allows_chapter(collaborator, number)
                for number in requested_chapters
            ):
                continue
        if report["scope"] == "passage":
            report["is_stale"] = False
        else:
            selected = [
                chapters_by_number[number]
                for number in requested_chapters
                if number in chapters_by_number
            ]
            report["is_stale"] = (
                len(selected) != len(requested_chapters)
                or build_chapter_source_fingerprint(selected) != report["source_fingerprint"]
            )
        reports.append(BetaReaderReportOut.model_validate(report).model_dump(mode="json"))
    return reports
