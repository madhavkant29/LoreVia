from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.operations import AiQualityEvent


def record_quality_review(
    db: AsyncSession,
    *,
    book_id: uuid.UUID,
    user_id: uuid.UUID,
    entity_type: str,
    entity_id: object,
    outcome: str,
    evidence: dict[str, Any] | None = None,
) -> None:
    source = evidence or {}
    db.add(
        AiQualityEvent(
            user_id=user_id,
            actor_user_id=user_id,
            book_id=book_id,
            entity_type=entity_type,
            entity_id=str(entity_id),
            outcome=outcome,
            model=str(source.get("model") or settings.OPENAI_EXTRACT_MODEL),
            extractor_version=str(
                source.get("extractor_version") or settings.PROCESSING_PIPELINE_VERSION
            ),
            metadata_json=source,
        )
    )
