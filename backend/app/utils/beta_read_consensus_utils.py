from __future__ import annotations

import hashlib
import re
import uuid
from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.beta_read import BetaReadAssignment, BetaReadFeedbackItem, BetaReadQuestion

_STOP_WORDS = {
    "about",
    "after",
    "again",
    "also",
    "because",
    "before",
    "being",
    "chapter",
    "could",
    "didn",
    "does",
    "felt",
    "from",
    "have",
    "into",
    "just",
    "more",
    "really",
    "scene",
    "some",
    "that",
    "their",
    "there",
    "they",
    "this",
    "very",
    "what",
    "when",
    "where",
    "which",
    "while",
    "with",
    "would",
    "your",
}


def _feedback_text(item: BetaReadFeedbackItem) -> str:
    return " ".join(
        part.strip() for part in (item.body or "", item.anchor_text or "") if part.strip()
    )


def _theme_words(text: str) -> set[str]:
    return {
        word for word in re.findall(r"[a-z][a-z'-]{3,}", text.lower()) if word not in _STOP_WORDS
    }


def build_beta_read_consensus_payload(
    assignments: list[BetaReadAssignment],
    items: list[BetaReadFeedbackItem],
    questions: list[BetaReadQuestion],
) -> dict[str, Any]:
    assignment_ids = {assignment.id for assignment in assignments}
    scoped_items = [item for item in items if item.assignment_id in assignment_ids]
    chapter_groups: dict[int, list[BetaReadFeedbackItem]] = defaultdict(list)
    for item in scoped_items:
        if item.chapter_number is not None:
            chapter_groups[int(item.chapter_number)].append(item)

    hotspots: list[dict[str, Any]] = []
    for chapter_number, chapter_items in chapter_groups.items():
        counts = Counter(item.kind for item in chapter_items)
        negative_readers = {
            item.assignment_id for item in chapter_items if item.kind in {"confusing", "boring"}
        }
        favorite_readers = {item.assignment_id for item in chapter_items if item.kind == "favorite"}
        disagreement = bool(
            negative_readers and favorite_readers and len(negative_readers | favorite_readers) > 1
        )
        score = (
            counts["confusing"] * 3
            + counts["boring"] * 2
            + counts["chapter_comment"]
            + counts["scene_reaction"]
            + (2 if disagreement else 0)
        )
        evidence = [_feedback_text(item) for item in chapter_items if _feedback_text(item)][:3]
        hotspots.append(
            {
                "chapter_number": chapter_number,
                "signal_score": score,
                "reader_count": len({item.assignment_id for item in chapter_items}),
                "confusing_count": counts["confusing"],
                "boring_count": counts["boring"],
                "favorite_count": counts["favorite"],
                "comment_count": counts["chapter_comment"] + counts["scene_reaction"],
                "disagreement": disagreement,
                "evidence": evidence,
            }
        )
    hotspots.sort(key=lambda item: (-item["signal_score"], item["chapter_number"]))

    theme_items: dict[str, list[BetaReadFeedbackItem]] = defaultdict(list)
    for item in scoped_items:
        for word in _theme_words(_feedback_text(item)):
            theme_items[word].append(item)
    themes = []
    for label, matched in theme_items.items():
        readers = {item.assignment_id for item in matched}
        if len(matched) < 2 and len(readers) < 2:
            continue
        themes.append(
            {
                "label": label,
                "mention_count": len(matched),
                "reader_count": len(readers),
                "chapter_numbers": sorted(
                    {int(item.chapter_number) for item in matched if item.chapter_number}
                ),
                "evidence": list(
                    dict.fromkeys(_feedback_text(item) for item in matched if _feedback_text(item))
                )[:3],
            }
        )
    themes.sort(key=lambda item: (-item["reader_count"], -item["mention_count"], item["label"]))

    question_groups: dict[str, list[BetaReadQuestion]] = defaultdict(list)
    for question in questions:
        prompt_key = " ".join(str(question.prompt or "").lower().split()).strip()
        if prompt_key:
            question_groups[prompt_key].append(question)

    question_consensus = []
    for grouped_questions in question_groups.values():
        question_ids = {question.id for question in grouped_questions}
        answers = [item for item in scoped_items if item.question_id in question_ids and item.body]
        if not answers:
            continue
        first_question = grouped_questions[0]
        question_consensus.append(
            {
                "question_id": str(first_question.id),
                "prompt": first_question.prompt,
                "answer_count": len(answers),
                "reader_count": len({item.assignment_id for item in answers}),
                "answers": [str(item.body).strip() for item in answers[:8]],
            }
        )

    revision_candidates = []
    for hotspot in hotspots:
        if hotspot["signal_score"] < 2:
            continue
        chapter_items = chapter_groups[hotspot["chapter_number"]]
        candidate_id = hashlib.sha1(
            f"beta-consensus:{hotspot['chapter_number']}".encode()
        ).hexdigest()[:20]
        revision_candidates.append(
            {
                "id": f"beta-{candidate_id}",
                "title": f"Review reader signals in Chapter {hotspot['chapter_number']}",
                "description": (
                    f"{hotspot['reader_count']} reader(s) left {len(chapter_items)} signal(s); "
                    f"{hotspot['confusing_count']} confusing and {hotspot['boring_count']} slow moment(s)."
                ),
                "severity": "high" if hotspot["signal_score"] >= 6 else "medium",
                "chapter_number": hotspot["chapter_number"],
                "feedback_item_ids": [str(item.id) for item in chapter_items],
            }
        )

    open_count = sum(
        1
        for item in scoped_items
        if str((item.metadata_json or {}).get("author_status") or "open") == "open"
    )
    submitted_states = {"submitted", "completed"}
    return {
        "summary": {
            "reader_count": len(assignments),
            "submitted_reader_count": sum(
                1 for item in assignments if item.state in submitted_states
            ),
            "feedback_item_count": len(scoped_items),
            "open_feedback_count": open_count,
            "hotspot_count": sum(1 for item in hotspots if item["signal_score"] >= 2),
            "disagreement_count": sum(1 for item in hotspots if item["disagreement"]),
        },
        "chapter_hotspots": hotspots,
        "themes": themes[:12],
        "question_consensus": question_consensus,
        "revision_candidates": revision_candidates[:12],
    }


async def build_beta_read_consensus(db: AsyncSession, *, book_id: uuid.UUID) -> dict[str, Any]:
    assignments = list(
        (await db.execute(select(BetaReadAssignment).where(BetaReadAssignment.book_id == book_id)))
        .scalars()
        .all()
    )
    items = list(
        (
            await db.execute(
                select(BetaReadFeedbackItem).where(BetaReadFeedbackItem.book_id == book_id)
            )
        )
        .scalars()
        .all()
    )
    questions = list(
        (await db.execute(select(BetaReadQuestion).where(BetaReadQuestion.book_id == book_id)))
        .scalars()
        .all()
    )
    return build_beta_read_consensus_payload(assignments, items, questions)
