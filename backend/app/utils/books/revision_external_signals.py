from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book, ManuscriptAnnotation
from app.models.intelligence import AdvisorSuggestionJob
from app.utils.beta_read_consensus_utils import build_beta_read_consensus
from app.utils.books.revision_decisions import _make_revision_action_item


def _severity(value: str | None) -> str:
    normalized = str(value or "").lower()
    if normalized in {"critical", "high", "warning"}:
        return "high"
    if normalized in {"medium", "direction", "opportunity"}:
        return "medium"
    return "low"


async def build_revision_external_signals(db: AsyncSession, *, book: Book) -> list[dict[str, Any]]:
    annotations = list(
        (
            await db.execute(
                select(ManuscriptAnnotation)
                .where(
                    ManuscriptAnnotation.book_id == book.id,
                    ManuscriptAnnotation.status == "open",
                )
                .order_by(ManuscriptAnnotation.updated_at.desc())
                .limit(25)
            )
        )
        .scalars()
        .all()
    )
    signals = []
    for annotation in annotations:
        item = _make_revision_action_item(
            category="annotation",
            title=f"Review {annotation.category} note in Chapter {annotation.chapter_number}",
            description=annotation.comment,
            severity="medium",
            chapter_ref=int(annotation.chapter_number),
            source_label="Editor annotation",
            recommendation="Resolve the note or turn it into a concrete revision task.",
        )
        item["evidence_strength"] = "strong" if annotation.quote else "moderate"
        if annotation.quote:
            item["evidence"] = [
                {
                    "chapter_ref": int(annotation.chapter_number),
                    "source_label": "Annotated manuscript",
                    "excerpt": annotation.quote[:500],
                    "source_content_version": 0,
                }
            ]
        signals.append(item)

    consensus = await build_beta_read_consensus(db, book_id=book.id)
    for candidate in consensus.get("revision_candidates") or []:
        item = _make_revision_action_item(
            category="beta_consensus",
            title=str(candidate["title"]),
            description=str(candidate["description"]),
            severity=str(candidate["severity"]),
            chapter_ref=candidate.get("chapter_number"),
            source_label="Beta reader consensus",
            recommendation="Compare the reader evidence before deciding whether to revise.",
        )
        item["evidence_strength"] = "strong"
        signals.append(item)

    advisor_job = (
        await db.execute(
            select(AdvisorSuggestionJob)
            .where(
                AdvisorSuggestionJob.book_id == book.id,
                AdvisorSuggestionJob.status == "complete",
            )
            .order_by(AdvisorSuggestionJob.updated_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    for suggestion in (
        ((advisor_job.result_json or {}).get("suggestions") or []) if advisor_job else []
    ):
        if not isinstance(suggestion, dict):
            continue
        signals.append(
            _make_revision_action_item(
                category="advisor",
                title=str(suggestion.get("title") or "Story advisor suggestion"),
                description=str(suggestion.get("description") or "Review this advisor signal."),
                severity=_severity(suggestion.get("severity")),
                chapter_ref=suggestion.get("chapter_ref"),
                source_label="Story Advisor",
                recommendation=str(suggestion.get("action_label") or "Review this suggestion."),
            )
        )
    return signals[:40]
