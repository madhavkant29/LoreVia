"""
Helper functions for grounded intelligence answers and citations.
"""
from __future__ import annotations

import re
import uuid
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.search.semantic import semantic_search
from app.models.book import Book, Chapter, SeriesBook
from app.models.character import Character
from app.models.intelligence import ChapterSummary, CharacterRelationship, PlotThread


def build_grounded_citation(
    chapter_num: int,
    chapter_title: str | None,
    excerpt: str,
    source_type: str,
    relevance: float | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "chapter_num": chapter_num,
        "chapter_title": chapter_title,
        "excerpt": excerpt.strip(),
        "source_type": source_type,
    }
    if relevance is not None:
        payload["relevance"] = round(float(relevance), 3)
    return payload


async def build_grounded_qa_context(
    db: AsyncSession,
    book: Book,
    user_id: uuid.UUID,
    question: str,
    current_chapter: int,
) -> tuple[list[str], list[dict[str, object]]]:
    summary_rows = (
        await db.execute(
            select(Chapter.number, Chapter.title, ChapterSummary.content)
            .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
            .where(
                Chapter.book_id == book.id,
                Chapter.number <= current_chapter,
                ChapterSummary.mode == "short",
            )
            .order_by(Chapter.number.desc())
            .limit(4)
        )
    ).all()
    semantic_hits = await semantic_search(
        db,
        book.id,
        question,
        current_chapter,
        limit=4,
        usage_user_id=user_id,
        usage_feature="grounded_qa_search",
    )

    context_blocks: list[str] = []
    citations: list[dict[str, object]] = []

    for chapter_num, chapter_title, content in reversed(summary_rows):
        summary_text = (content or "").strip()
        if not summary_text:
            continue
        context_blocks.append(
            f"Chapter {chapter_num}: {chapter_title or 'Untitled'}\nSummary: {summary_text[:500]}"
        )
        citations.append(
            build_grounded_citation(
                chapter_num=chapter_num,
                chapter_title=chapter_title,
                excerpt=summary_text[:240],
                source_type="summary",
            )
        )

    for hit in semantic_hits:
        chapter_num = int(cast(Any, hit["chapter_num"]))
        chapter_title = hit.get("chapter_title")
        excerpt = str(hit.get("text") or "").strip()
        if not excerpt:
            continue
        context_blocks.append(
            f"Passage from Chapter {chapter_num}: {chapter_title or 'Untitled'}\n{excerpt[:420]}"
        )
        citations.append(
            build_grounded_citation(
                chapter_num=chapter_num,
                chapter_title=chapter_title if isinstance(chapter_title, str) else None,
                excerpt=excerpt[:240],
                source_type="passage",
                relevance=float(hit.get("relevance") or 0.0),
            )
        )

    series_context = await build_prior_series_context(db, book, user_id)
    if series_context:
        context_blocks = series_context + context_blocks

    deduped_citations: list[dict[str, object]] = []
    seen: set[tuple[int, str, str]] = set()
    for citation in sorted(
        citations,
        key=lambda item: _citation_sort_key(item),
    ):
        key = (
            int(cast(Any, citation["chapter_num"])),
            str(citation["source_type"]),
            str(citation["excerpt"]),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped_citations.append(citation)
        if len(deduped_citations) >= 5:
            break

    return context_blocks, deduped_citations


def _citation_sort_key(item: dict[str, object]) -> tuple[int, float, int]:
    relevance = cast(float, item.get("relevance") or 0.0)
    chapter_num = cast(int, item["chapter_num"])
    return (
        0 if item["source_type"] == "passage" else 1,
        -float(relevance),
        -chapter_num,
    )


async def build_prior_series_context(db: AsyncSession, book: Book, user_id: uuid.UUID) -> list[str]:
    if not book.primary_series_id:
        return []

    series_rows = (
        await db.execute(
            select(Book, SeriesBook.position)
            .join(SeriesBook, SeriesBook.book_id == Book.id)
            .where(
                SeriesBook.series_id == book.primary_series_id,
                Book.user_id == user_id,
            )
            .order_by(SeriesBook.position.is_(None), SeriesBook.position, Book.created_at)
        )
    ).all()
    if not series_rows:
        return []

    ordered_books = [row[0] for row in series_rows]
    try:
        current_index = next(index for index, item in enumerate(ordered_books) if item.id == book.id)
    except StopIteration:
        return []

    previous_books = ordered_books[:current_index]
    if not previous_books:
        return []

    context_blocks: list[str] = []
    for prior_book in previous_books[-3:]:
        snapshot = await book_series_snapshot(db, prior_book.id, prior_book.title)
        if snapshot:
            context_blocks.append(snapshot)
    return context_blocks


async def book_series_snapshot(db: AsyncSession, book_id: uuid.UUID, title: str) -> str | None:
    summary_rows = (
        await db.execute(
            select(Chapter.number, Chapter.title, ChapterSummary.content, ChapterSummary.key_events)
            .join(ChapterSummary, ChapterSummary.chapter_id == Chapter.id)
            .where(
                Chapter.book_id == book_id,
                ChapterSummary.mode == "short",
            )
            .order_by(Chapter.number.desc())
            .limit(3)
        )
    ).all()
    character_rows = (
        await db.execute(
            select(Character.name, Character.role, Character.arc_summary)
            .where(Character.book_id == book_id)
            .order_by(Character.first_chapter, Character.name)
            .limit(8)
        )
    ).all()
    relationship_rows = (
        await db.execute(
            select(CharacterRelationship.rel_type, CharacterRelationship.description)
            .where(CharacterRelationship.book_id == book_id)
            .order_by(CharacterRelationship.from_chapter.desc())
            .limit(6)
        )
    ).all()
    thread_rows = (
        await db.execute(
            select(PlotThread.title, PlotThread.description, PlotThread.status)
            .where(PlotThread.book_id == book_id)
            .order_by(PlotThread.importance.desc(), PlotThread.created_at.desc())
            .limit(5)
        )
    ).all()

    blocks: list[str] = [f"Previous volume context: {title}"]

    if summary_rows:
        summary_lines = []
        for chapter_num, chapter_title, content, key_events in reversed(summary_rows):
            summary_lines.append(
                f"Chapter {chapter_num} ({chapter_title or 'Untitled'}): {(content or '')[:320]}"
            )
            event_line = flatten_key_events(key_events)
            if event_line:
                summary_lines.append(f"Key events: {event_line}")
        blocks.append("Story so far:\n" + "\n".join(summary_lines[:6]))

    if character_rows:
        cast = [
            f"{name}{f' ({role})' if role else ''}: {(arc_summary or 'role in progress')[:140]}"
            for name, role, arc_summary in character_rows
            if name
        ]
        if cast:
            blocks.append("Core cast:\n" + "\n".join(cast[:6]))

    if relationship_rows:
        relationship_lines = []
        for rel_type, description in relationship_rows:
            fallback = (rel_type or "connection").replace("_", " ")
            text = (description or fallback).strip()
            if text:
                relationship_lines.append(text[:180])
        if relationship_lines:
            blocks.append("Known relationships:\n" + "\n".join(relationship_lines[:4]))

    if thread_rows:
        thread_lines = []
        for thread_title, description, status in thread_rows:
            thread_lines.append(
                f"{thread_title} [{status or 'unknown'}]: {(description or 'No detail yet.')[:180]}"
            )
        if thread_lines:
            blocks.append("Major plot threads:\n" + "\n".join(thread_lines[:4]))

    if len(blocks) == 1:
        return None
    return "\n\n".join(blocks)


def flatten_key_events(key_events: object) -> str:
    if isinstance(key_events, list):
        items = [str(item).strip() for item in key_events if str(item).strip()]
        return "; ".join(items[:4])
    if isinstance(key_events, dict):
        flattened: list[str] = []
        for value in key_events.values():
            if isinstance(value, list):
                flattened.extend(str(item).strip() for item in value if str(item).strip())
            elif value:
                flattened.append(str(value).strip())
        return "; ".join(flattened[:4])
    return ""


VOICE_FORMALITY_WORDS = {
    "indeed", "perhaps", "therefore", "however", "certainly", "shall", "must", "rather", "precisely", "quite",
}
VOICE_CONTRACTION_WORDS = {
    "don't", "can't", "won't", "i'm", "it's", "you're", "we're", "they're", "didn't", "isn't", "wasn't",
}
VOICE_EMOTION_WORDS = {
    "love", "hate", "fear", "angry", "furious", "joy", "grief", "sorry", "please", "damn", "hell",
}
QUOTE_RE = re.compile(r"[\"“](.+?)[\"”]", re.DOTALL)


def build_character_name_candidates(character_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for row in character_rows:
        names = [str(row.get("name") or "").strip(), *[str(alias).strip() for alias in (row.get("aliases") or []) if str(alias).strip()]]
        names = [name for name in names if name]
        if names:
            candidates.append({**row, "name_candidates": list(dict.fromkeys(names))})
    return candidates


def extract_dialogue_samples_by_character(text: str, character_rows: list[dict[str, Any]]) -> dict[str, list[str]]:
    normalized_text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    candidates = build_character_name_candidates(character_rows)
    collected: dict[str, list[str]] = {}
    for match in QUOTE_RE.finditer(normalized_text):
        quote = " ".join(match.group(1).split()).strip()
        if not quote:
            continue
        window = normalized_text[max(0, match.start() - 160): min(len(normalized_text), match.end() + 160)].casefold()
        prefix_window = normalized_text[max(0, match.start() - 120): match.start()].casefold()
        suffix_window = normalized_text[match.end(): min(len(normalized_text), match.end() + 120)].casefold()
        best_name = None
        best_score = 0
        for row in candidates:
            score = 0
            nearest_distance: int | None = None
            for candidate in row["name_candidates"]:
                folded = candidate.casefold()
                prefix_idx = prefix_window.rfind(folded)
                suffix_idx = suffix_window.find(folded)
                if prefix_idx >= 0:
                    distance = len(prefix_window) - prefix_idx
                    score += max(0, 320 - distance)
                    nearest_distance = distance if nearest_distance is None else min(nearest_distance, distance)
                if suffix_idx >= 0:
                    distance = suffix_idx + 1
                    score += max(0, 90 - distance)
                    nearest_distance = distance if nearest_distance is None else min(nearest_distance, distance)
                if f" {folded} " in f" {window} ":
                    score += max(1, len(candidate.split()))
            if nearest_distance is not None:
                score += max(0, 60 - nearest_distance)
            if score > best_score:
                best_score = score
                best_name = str(row.get("name") or "").strip()
        if best_name and best_score > 0:
            collected.setdefault(best_name, []).append(quote)
    return collected


def compute_voice_metrics(dialogues: list[str]) -> dict[str, Any]:
    cleaned = [" ".join(dialogue.split()).strip() for dialogue in dialogues if " ".join(dialogue.split()).strip()]
    if not cleaned:
        return {
            "sample_dialogue_count": 0,
            "sample_word_count": 0,
            "avg_sentence_length": 0,
            "avg_word_length_x100": 0,
            "contraction_rate_x1000": 0,
            "question_rate_x1000": 0,
            "exclamation_rate_x1000": 0,
            "ellipsis_rate_x1000": 0,
            "dash_rate_x1000": 0,
            "uppercase_rate_x1000": 0,
            "formality_score_x1000": 0,
            "lexical_complexity_x1000": 0,
            "emotional_intensity_x1000": 0,
            "dominant_markers": {},
            "signature_phrases": [],
        }
    words = re.findall(r"[A-Za-z0-9']+", " ".join(cleaned))
    sentences = [part.strip() for dialogue in cleaned for part in re.split(r"[.!?]+", dialogue) if part.strip()]
    lower_words = [word.lower() for word in words]
    total_words = max(1, len(words))
    unique_words = {word.lower() for word in words}
    contractions = sum(1 for word in lower_words if word in VOICE_CONTRACTION_WORDS or "'" in word)
    question_rate = sum(dialogue.count("?") for dialogue in cleaned)
    exclamation_rate = sum(dialogue.count("!") for dialogue in cleaned)
    ellipsis_rate = sum(dialogue.count("...") for dialogue in cleaned)
    dash_rate = sum(dialogue.count("—") + dialogue.count("--") for dialogue in cleaned)
    uppercase_rate = sum(1 for word in words if word.isupper() and len(word) > 1)
    formal_rate = sum(1 for word in lower_words if word in VOICE_FORMALITY_WORDS)
    emotional_rate = sum(1 for word in lower_words if word in VOICE_EMOTION_WORDS)
    avg_sentence_length = int(round(sum(len(re.findall(r"[A-Za-z0-9']+", sentence)) for sentence in sentences) / max(1, len(sentences))))
    avg_word_length = int(round((sum(len(word) for word in words) / total_words) * 100))
    lexical_complexity = int(round((len(unique_words) / total_words) * 1000))
    dominant_markers = {
        "questions": question_rate,
        "exclamations": exclamation_rate,
        "ellipses": ellipsis_rate,
        "dashes": dash_rate,
        "formal_words": formal_rate,
        "emotion_words": emotional_rate,
    }
    phrase_counts: dict[str, int] = {}
    for dialogue in cleaned:
        for phrase in re.findall(r"\b[a-z']+\s+[a-z']+\b", dialogue.lower()):
            phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1
    signature_phrases = [phrase for phrase, count in sorted(phrase_counts.items(), key=lambda item: (-item[1], item[0])) if count > 1][:5]
    return {
        "sample_dialogue_count": len(cleaned),
        "sample_word_count": total_words,
        "avg_sentence_length": avg_sentence_length,
        "avg_word_length_x100": avg_word_length,
        "contraction_rate_x1000": int(round((contractions / total_words) * 1000)),
        "question_rate_x1000": int(round((question_rate / total_words) * 1000)),
        "exclamation_rate_x1000": int(round((exclamation_rate / total_words) * 1000)),
        "ellipsis_rate_x1000": int(round((ellipsis_rate / total_words) * 1000)),
        "dash_rate_x1000": int(round((dash_rate / total_words) * 1000)),
        "uppercase_rate_x1000": int(round((uppercase_rate / total_words) * 1000)),
        "formality_score_x1000": int(round((formal_rate / total_words) * 1000)),
        "lexical_complexity_x1000": lexical_complexity,
        "emotional_intensity_x1000": int(round((emotional_rate / total_words) * 1000)),
        "dominant_markers": dominant_markers,
        "signature_phrases": signature_phrases,
    }


def merge_voice_profile_metrics(existing: dict[str, Any] | None, incoming: dict[str, Any]) -> dict[str, Any]:
    current = existing if isinstance(existing, dict) else {}
    old_count = int(current.get("sample_dialogue_count") or 0)
    new_count = int(incoming.get("sample_dialogue_count") or 0)
    total_count = old_count + new_count
    if total_count <= 0:
        return incoming
    merged = dict(incoming)
    for key in (
        "avg_sentence_length",
        "avg_word_length_x100",
        "contraction_rate_x1000",
        "question_rate_x1000",
        "exclamation_rate_x1000",
        "ellipsis_rate_x1000",
        "dash_rate_x1000",
        "uppercase_rate_x1000",
        "formality_score_x1000",
        "lexical_complexity_x1000",
        "emotional_intensity_x1000",
    ):
        old_value = int(current.get(key) or 0)
        new_value = int(incoming.get(key) or 0)
        merged[key] = int(round(((old_value * old_count) + (new_value * new_count)) / total_count))
    merged["sample_dialogue_count"] = total_count
    merged["sample_word_count"] = int(current.get("sample_word_count") or 0) + int(incoming.get("sample_word_count") or 0)
    merged["dominant_markers"] = incoming.get("dominant_markers") or current.get("dominant_markers") or {}
    seen_phrases: list[str] = []
    for phrase in [*(current.get("signature_phrases") or []), *(incoming.get("signature_phrases") or [])]:
        if phrase and phrase not in seen_phrases:
            seen_phrases.append(phrase)
    merged["signature_phrases"] = seen_phrases[:6]
    return merged


def score_voice_match(profile: dict[str, Any], sample_metrics: dict[str, Any]) -> tuple[int, list[str]]:
    if int(profile.get("sample_dialogue_count") or 0) <= 0 or int(sample_metrics.get("sample_dialogue_count") or 0) <= 0:
        return 0, ["Not enough dialogue was attributed to score this voice yet."]
    checks = [
        ("avg_sentence_length", "sentence length"),
        ("formality_score_x1000", "formality"),
        ("contraction_rate_x1000", "contractions"),
        ("question_rate_x1000", "question frequency"),
        ("exclamation_rate_x1000", "exclamation use"),
        ("ellipsis_rate_x1000", "ellipsis use"),
        ("dash_rate_x1000", "dash use"),
        ("lexical_complexity_x1000", "vocabulary complexity"),
        ("emotional_intensity_x1000", "emotional register"),
    ]
    penalties = 0.0
    signals: list[str] = []
    for key, label in checks:
        baseline = float(profile.get(key) or 0)
        observed = float(sample_metrics.get(key) or 0)
        difference = abs(observed - baseline)
        tolerance = max(4.0, abs(baseline) * 0.25)
        delta = difference / tolerance
        penalties += min(1.5, delta)
        if delta > 0.75:
            direction = "higher" if observed > baseline else "lower"
            signals.append(f"{label} is {direction} than the established baseline")
    score = max(0, int(round(100 - min(85, penalties * 10))))
    return score, signals[:4]
