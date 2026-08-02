from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.intelligence import WorldGapAnalysis


async def upsert_world_analysis(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    series_id: uuid.UUID | None,
    mode: str,
    gap_categories: dict,
    priority_gaps: list[dict],
    integration_opportunities: list[dict],
    consistency_flags: list[dict],
) -> WorldGapAnalysis:
    existing = (
        (
            await db.execute(
                select(WorldGapAnalysis)
                .where(
                    WorldGapAnalysis.book_id == book_id,
                    WorldGapAnalysis.series_id == series_id,
                    WorldGapAnalysis.analysis_mode == mode,
                )
                .order_by(WorldGapAnalysis.generated_at.desc())
            )
        )
        .scalars()
        .first()
    )
    if existing is None:
        existing = WorldGapAnalysis(book_id=book_id, series_id=series_id, analysis_mode=mode)
        db.add(existing)
    existing.gap_categories = gap_categories
    existing.priority_gaps = priority_gaps
    existing.integration_opportunities = integration_opportunities
    existing.consistency_flags = consistency_flags
    existing.generated_at = datetime.now(UTC)
    await db.flush()
    return existing
