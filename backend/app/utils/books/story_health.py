"""Focused book story health workflows."""

from __future__ import annotations

import re
import statistics
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import (
    Book,
    Chapter,
)
from app.models.character import (
    Character,
    CharacterState,
    CharacterVoiceProfile,
)
from app.models.intelligence import (
    CharacterRelationship,
    ContinuityFinding,
    ContinuityScan,
    PlotThread,
    WikiEntry,
    WorldBuildingDocument,
    WorldGapAnalysis,
)
from app.schemas.books import (
    StoryHealthOut,
)
from app.utils.books.consistency_reports import list_chapter_consistency_reports
from app.utils.plot_thread_utils import (
    derive_plot_thread_status,
    is_plot_thread_open,
)


def estimate_readability(text: str) -> dict[str, Any]:
    cleaned = " ".join((text or "").replace("\r", "\n").split())
    paragraphs = len([part for part in re.split(r"\n{2,}", text or "") if part.strip()]) or (
        1 if cleaned else 0
    )
    words = re.findall(r"[A-Za-z0-9']+", text or "")
    sentences = [part for part in re.split(r"[.!?]+", text or "") if part.strip()]
    word_count = len(words)
    sentence_count = len(sentences) or (1 if word_count else 0)
    syllables = sum(_estimate_syllables(word) for word in words)
    average_sentence_length = round(word_count / sentence_count, 2) if sentence_count else 0.0
    reading_ease = (
        206.835
        - (1.015 * average_sentence_length)
        - (84.6 * ((syllables / word_count) if word_count else 0))
    )
    grade_level = (
        0.39 * average_sentence_length
        + 11.8 * ((syllables / word_count) if word_count else 0)
        - 15.59
    )

    if reading_ease >= 80:
        label = "Very easy"
    elif reading_ease >= 65:
        label = "Easy"
    elif reading_ease >= 50:
        label = "Balanced"
    elif reading_ease >= 35:
        label = "Demanding"
    else:
        label = "Dense"

    return {
        "words": word_count,
        "sentences": sentence_count,
        "paragraphs": paragraphs,
        "average_sentence_length": round(average_sentence_length, 2),
        "reading_ease": round(reading_ease, 2),
        "grade_level": round(max(0.0, grade_level), 2),
        "label": label,
    }


def _clamp_score(value: float, *, minimum: int = 0, maximum: int = 100) -> int:
    return max(minimum, min(maximum, int(round(value))))


def _story_health_status(score: int) -> tuple[str, str]:
    if score >= 85:
        return "Excellent", "Story signals look strong across character, world, plot, and pacing."
    if score >= 70:
        return "Good", "Overall story health looks solid, with a few areas worth refining."
    if score >= 55:
        return "Fair", "The draft has momentum, but a couple of craft systems need attention."
    return (
        "Needs Attention",
        "Several story systems are under strain, so this is a good moment for a focused revision pass.",
    )


async def build_story_health_payload(db: AsyncSession, book: Book) -> StoryHealthOut:
    from app.utils.characters.governance import is_displayable_character

    characters = (
        (
            await db.execute(
                select(Character)
                .where(Character.book_id == book.id)
                .order_by(Character.mention_count.desc(), Character.name)
            )
        )
        .scalars()
        .all()
    )
    visible_characters = [
        character for character in characters if is_displayable_character(character)
    ]

    relationships = (
        (
            await db.execute(
                select(CharacterRelationship).where(CharacterRelationship.book_id == book.id)
            )
        )
        .scalars()
        .all()
    )
    relationship_counts: dict[uuid.UUID, int] = {}
    for relationship in relationships:
        relationship_counts[relationship.character_a_id] = (
            relationship_counts.get(relationship.character_a_id, 0) + 1
        )
        relationship_counts[relationship.character_b_id] = (
            relationship_counts.get(relationship.character_b_id, 0) + 1
        )

    major_characters = [
        character
        for character in visible_characters
        if (character.mention_count or 0) >= 6 or character.role in {"mc", "sc"}
    ]
    if not major_characters:
        major_characters = visible_characters[: max(1, min(3, len(visible_characters)))]

    character_scores: list[float] = []
    for character in visible_characters:
        evidence_points = 0
        if character.role:
            evidence_points += 1
        if character.arc_summary:
            evidence_points += 1
        if character.personality_tags or character.archetype or character.trait_state:
            evidence_points += 1
        if character.motivations or character.fears:
            evidence_points += 1
        if character.growth_events:
            evidence_points += 1
        if relationship_counts.get(character.id, 0) > 0:
            evidence_points += 1
        character_scores.append((evidence_points / 6) * 100)

    state_rows = (
        await db.execute(
            select(CharacterState.character_id, func.count(CharacterState.id))
            .join(Character, Character.id == CharacterState.character_id)
            .where(Character.book_id == book.id)
            .group_by(CharacterState.character_id)
        )
    ).all()
    state_counts = {character_id: int(count or 0) for character_id, count in state_rows}
    major_with_states = sum(
        1 for character in major_characters if state_counts.get(character.id, 0) > 0
    )
    state_coverage = (major_with_states / len(major_characters)) if major_characters else 0.0

    character_score = _clamp_score(
        (statistics.fmean(character_scores) if character_scores else 0) * 0.78
        + (state_coverage * 22),
        minimum=0,
        maximum=100,
    )
    character_detail = (
        f"{len(visible_characters)} visible profiles scored from role, arc, trait, motive, growth, and relationship coverage; "
        f"{major_with_states}/{len(major_characters) or 1} major characters have tracked state snapshots."
    )

    chapter_reports = await list_chapter_consistency_reports(db, book, limit=6)
    continuity_issue_count = sum(len(report.continuity_flags) for report in chapter_reports)
    latest_continuity_scan = (
        await db.execute(
            select(ContinuityScan)
            .where(
                ContinuityScan.book_id == book.id,
                ContinuityScan.scope == "full_book",
                ContinuityScan.status == "ready",
            )
            .order_by(ContinuityScan.created_at.desc(), ContinuityScan.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if latest_continuity_scan is None:
        latest_continuity_scan = (
            await db.execute(
                select(ContinuityScan)
                .where(
                    ContinuityScan.book_id == book.id,
                    ContinuityScan.status == "ready",
                )
                .order_by(ContinuityScan.created_at.desc(), ContinuityScan.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    scan_findings = (
        list(
            (
                await db.execute(
                    select(ContinuityFinding).where(
                        ContinuityFinding.scan_id == latest_continuity_scan.id
                    )
                )
            )
            .scalars()
            .all()
        )
        if latest_continuity_scan is not None
        else []
    )
    analyzed_chapters = int(
        (latest_continuity_scan.coverage or {}).get("chapters_analyzed", 0)
        if latest_continuity_scan is not None
        else 0
    )
    total_chapters = max(int(book.total_chapters or 0), len(chapter_reports), 1)
    coverage_ratio = min(1.0, analyzed_chapters / total_chapters)
    verified_findings = sum(
        1
        for finding in scan_findings
        if not finding.is_stale and finding.confidence >= 0.9 and finding.status != "review_needed"
    )
    review_needed_findings = sum(
        1 for finding in scan_findings if not finding.is_stale and finding.status == "review_needed"
    )
    stale_findings = sum(1 for finding in scan_findings if finding.is_stale)
    data_gap_count = max(total_chapters - analyzed_chapters, 0)
    if latest_continuity_scan is None:
        continuity_score = 0
        continuity_detail = (
            "No verified continuity scan is available yet. Coverage, findings, and data gaps "
            "will replace this placeholder after the first scan."
        )
    else:
        continuity_score = _clamp_score(
            (coverage_ratio * 100)
            - (verified_findings * 14)
            - (review_needed_findings * 5)
            - (stale_findings * 3),
            minimum=0,
            maximum=100,
        )
        continuity_detail = (
            f"Coverage: {analyzed_chapters}/{total_chapters} chapters. "
            f"Verified high-confidence findings: {verified_findings}; review needed: "
            f"{review_needed_findings}; stale: {stale_findings}; data gaps: {data_gap_count}. "
            f"Scan result: {latest_continuity_scan.continuity_status}."
        )

    plot_threads = (
        (await db.execute(select(PlotThread).where(PlotThread.book_id == book.id))).scalars().all()
    )
    resolved_threads = sum(
        1
        for thread in plot_threads
        if derive_plot_thread_status(
            thread.status,
            introduced_at=thread.introduced_at,
            last_mentioned_at=thread.last_mentioned_at or thread.introduced_at,
            resolved_at=thread.resolved_at,
            current_chapter=book.total_chapters,
        )
        == "resolved"
    )
    abandoned_threads = sum(
        1
        for thread in plot_threads
        if derive_plot_thread_status(
            thread.status,
            introduced_at=thread.introduced_at,
            last_mentioned_at=thread.last_mentioned_at or thread.introduced_at,
            resolved_at=thread.resolved_at,
            current_chapter=book.total_chapters,
        )
        == "abandoned"
    )
    open_threads = sum(
        1
        for thread in plot_threads
        if is_plot_thread_open(
            derive_plot_thread_status(
                thread.status,
                introduced_at=thread.introduced_at,
                last_mentioned_at=thread.last_mentioned_at or thread.introduced_at,
                resolved_at=thread.resolved_at,
                current_chapter=book.total_chapters,
            )
        )
    )
    total_threads = len(plot_threads)
    anchored_threads = sum(1 for thread in plot_threads if thread.introduced_at is not None)
    chronology_conflicts = sum(
        1
        for thread in plot_threads
        if thread.introduced_at is not None
        and thread.resolved_at is not None
        and thread.resolved_at < thread.introduced_at
    )
    stale_open_threads = sum(
        1
        for thread in plot_threads
        if is_plot_thread_open(
            derive_plot_thread_status(
                thread.status,
                introduced_at=thread.introduced_at,
                last_mentioned_at=thread.last_mentioned_at or thread.introduced_at,
                resolved_at=thread.resolved_at,
                current_chapter=book.total_chapters,
            )
        )
        and (thread.last_mentioned_at or thread.introduced_at) is not None
        and (book.total_chapters or 0) - int(thread.last_mentioned_at or thread.introduced_at or 0)
        >= 8
    )
    timeline_score = _clamp_score(
        58
        + (((anchored_threads / total_threads) if total_threads else 1.0) * 22)
        + (
            (
                ((book.total_chapters or 0) - min(continuity_issue_count, book.total_chapters or 0))
                / (book.total_chapters or 1)
            )
            * 20
            if (book.total_chapters or 0) > 0
            else 10
        )
        - (continuity_issue_count * 4)
        - (chronology_conflicts * 12),
        minimum=0,
        maximum=96,
    )
    timeline_detail = (
        f"{anchored_threads}/{total_threads or 1} plot threads have chapter anchors, with {chronology_conflicts} chronology conflicts "
        f"and {continuity_issue_count} recent continuity flags. "
        "Timeline clarity should still be stress-tested for implied travel time, off-page gaps, and stale open beats."
    )

    plot_score = _clamp_score(
        52
        + (((resolved_threads / total_threads) if total_threads else 1.0) * 30)
        + min(total_threads * 2, 12)
        - (stale_open_threads * 7)
        - (abandoned_threads * 5)
        - max(0, open_threads - resolved_threads) * 2,
        minimum=0,
        maximum=96,
    )
    plot_detail = (
        f"{resolved_threads}/{total_threads or 1} plot threads resolved, {open_threads} still open, "
        f"and {stale_open_threads} have been hanging open for 8+ chapters."
    )

    wiki_count = (
        await db.scalar(select(func.count(WikiEntry.id)).where(WikiEntry.book_id == book.id))
    ) or 0
    world_document_count = (
        await db.scalar(
            select(func.count(WorldBuildingDocument.id)).where(
                WorldBuildingDocument.book_id == book.id,
                WorldBuildingDocument.is_active.is_(True),
                WorldBuildingDocument.archived_at.is_(None),
            )
        )
    ) or 0
    latest_world_gap_analysis = (
        await db.execute(
            select(WorldGapAnalysis)
            .where(WorldGapAnalysis.book_id == book.id)
            .order_by(WorldGapAnalysis.generated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    priority_gaps = (
        len(latest_world_gap_analysis.priority_gaps or []) if latest_world_gap_analysis else 0
    )
    consistency_flags = (
        len(latest_world_gap_analysis.consistency_flags or []) if latest_world_gap_analysis else 0
    )
    world_score = _clamp_score(
        58
        + min(world_document_count * 8, 24)
        + min(wiki_count * 2, 18)
        - (priority_gaps * 7)
        - (consistency_flags * 6),
        minimum=0,
        maximum=96,
    )
    world_issue_count = priority_gaps + consistency_flags
    world_detail = (
        f"{world_document_count} active world documents and {wiki_count} wiki entries. "
        + (
            f"{world_issue_count} cached world-analysis issue{'s' if world_issue_count != 1 else ''} are already on the board. "
            if world_issue_count
            else "The world-analysis review queue still needs a fresh pass so LoreVia can surface more contradiction and coverage targets. "
        )
        + "Lore coverage still benefits from ongoing contradiction hunts and missing-rule checks."
    )

    voice_profiles = (
        (
            await db.execute(
                select(CharacterVoiceProfile).where(CharacterVoiceProfile.book_id == book.id)
            )
        )
        .scalars()
        .all()
    )
    voice_profiles_by_character = {profile.character_id: profile for profile in voice_profiles}
    major_with_voice = sum(
        1
        for character in major_characters
        if (
            voice_profiles_by_character.get(character.id).sample_dialogue_count
            if voice_profiles_by_character.get(character.id)
            else 0
        )
        >= 3
    )
    voice_marker_profiles = sum(
        1
        for profile in voice_profiles
        if (profile.signature_phrases and len(profile.signature_phrases) > 0)
        or (profile.dominant_markers and len(profile.dominant_markers) > 0)
    )
    dialogue_score = _clamp_score(
        44
        + (((major_with_voice / len(major_characters)) if major_characters else 0.0) * 36)
        + (((voice_marker_profiles / len(voice_profiles)) if voice_profiles else 0.0) * 20)
        + min(sum(profile.sample_dialogue_count for profile in voice_profiles), 20),
        minimum=0,
        maximum=96,
    )
    dialogue_detail = (
        f"{major_with_voice}/{len(major_characters) or 1} major characters have reusable voice samples; "
        f"{voice_marker_profiles}/{len(voice_profiles) or 1} voice profiles include markers or signature phrases. "
        "Voice review should still keep looking for flattening, over-shared phrasing, and missing contrast."
    )

    chapter_word_counts = [
        int(word_count)
        for word_count in (
            await db.execute(
                select(Chapter.word_count)
                .where(
                    Chapter.book_id == book.id,
                    Chapter.word_count.is_not(None),
                    Chapter.word_count > 0,
                )
                .order_by(Chapter.number.asc())
            )
        )
        .scalars()
        .all()
    ]
    if len(chapter_word_counts) >= 2:
        mean_word_count = statistics.fmean(chapter_word_counts)
        stdev_word_count = (
            statistics.pstdev(chapter_word_counts) if len(chapter_word_counts) > 1 else 0.0
        )
        coefficient_of_variation = (stdev_word_count / mean_word_count) if mean_word_count else 1.0
        median_word_count = statistics.median(chapter_word_counts)
        outlier_count = sum(
            1
            for word_count in chapter_word_counts
            if word_count < median_word_count * 0.6 or word_count > median_word_count * 1.6
        )
        outlier_rate = outlier_count / len(chapter_word_counts)
        pacing_score = _clamp_score(
            100 - (coefficient_of_variation * 85) - (outlier_rate * 35),
            minimum=0,
            maximum=96,
        )
        pacing_detail = f"{len(chapter_word_counts)} chapter word counts measured; {outlier_count} pacing outliers against a {int(round(median_word_count))}-word median."
    elif len(chapter_word_counts) == 1:
        pacing_score = 65
        pacing_detail = "Only one chapter has a persisted word count, so pacing is based on limited manuscript data."
    else:
        pacing_score = 0
        pacing_detail = "No persisted chapter word counts are available yet for pacing analysis."

    overall_score = _clamp_score(
        statistics.fmean(
            [
                continuity_score,
                character_score,
                timeline_score,
                plot_score,
                world_score,
                pacing_score,
                dialogue_score,
            ]
        ),
        minimum=0,
        maximum=94,
    )
    status, summary = _story_health_status(overall_score)
    return StoryHealthOut(
        score=overall_score,
        status=status,
        summary=summary,
        metrics=[
            {"label": "Continuity", "score": continuity_score, "detail": continuity_detail},
            {
                "label": "Character consistency",
                "score": character_score,
                "detail": character_detail,
            },
            {"label": "Timeline clarity", "score": timeline_score, "detail": timeline_detail},
            {"label": "Plot thread closure", "score": plot_score, "detail": plot_detail},
            {"label": "Worldbuilding consistency", "score": world_score, "detail": world_detail},
            {"label": "Pacing", "score": pacing_score, "detail": pacing_detail},
            {
                "label": "Dialogue/voice consistency",
                "score": dialogue_score,
                "detail": dialogue_detail,
            },
        ],
    )


def _estimate_syllables(word: str) -> int:
    cleaned = re.sub(r"[^a-z]", "", word.lower())
    if not cleaned:
        return 1
    groups = re.findall(r"[aeiouy]+", cleaned)
    syllables = len(groups)
    if cleaned.endswith("e") and syllables > 1:
        syllables -= 1
    return max(1, syllables)
