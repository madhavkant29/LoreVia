from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operations import RevenueLedgerEvent
from app.utils.billing_utils import billing_interval_for_plan

REVENUE_PRICING_VERSION = "paddle-estimate-2026-05-24"
PADDLE_PERCENT_FEE = Decimal("0.05")
PADDLE_FIXED_FEE = Decimal("0.50")


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


async def record_completed_transaction_revenue(
    db: AsyncSession,
    *,
    source_event_id: str,
    user_id: uuid.UUID,
    plan: str,
    transaction_id: str | None,
    data: dict[str, Any],
) -> RevenueLedgerEvent | None:
    existing = await db.scalar(
        select(RevenueLedgerEvent).where(RevenueLedgerEvent.source_event_id == source_event_id)
    )
    if existing is not None:
        return existing
    totals = (data.get("details") or {}).get("totals") or {}
    total_minor = totals.get("total")
    if total_minor is None:
        return None
    gross = Decimal(str(total_minor)) / Decimal(100)
    interval = billing_interval_for_plan(plan)
    period = data.get("billing_period") or {}
    start = _parse_datetime(period.get("starts_at")) or datetime.now(UTC)
    end = _parse_datetime(period.get("ends_at")) or start + timedelta(
        days=365 if interval == "annual" else 30
    )
    fee = gross * PADDLE_PERCENT_FEE + PADDLE_FIXED_FEE
    event = RevenueLedgerEvent(
        user_id=user_id,
        source_event_id=source_event_id,
        transaction_id=transaction_id,
        plan=plan,
        billing_interval=interval,
        currency=str(data.get("currency_code") or "USD")[:3].upper(),
        gross_amount=gross,
        fee_amount=fee,
        net_amount=gross - fee,
        pricing_version=REVENUE_PRICING_VERSION,
        service_period_start=start,
        service_period_end=end,
        metadata_json={"estimated_paddle_fee": True},
    )
    db.add(event)
    return event


async def record_refund_revenue(
    db: AsyncSession,
    *,
    source_event_id: str,
    user_id: uuid.UUID,
    transaction_id: str,
) -> RevenueLedgerEvent | None:
    if await db.scalar(
        select(RevenueLedgerEvent.id).where(RevenueLedgerEvent.source_event_id == source_event_id)
    ):
        return None
    original = (
        await db.execute(
            select(RevenueLedgerEvent)
            .where(
                RevenueLedgerEvent.transaction_id == transaction_id,
                RevenueLedgerEvent.net_amount > 0,
            )
            .order_by(RevenueLedgerEvent.created_at.desc())
        )
    ).scalars().first()
    if original is None:
        return None
    refund = RevenueLedgerEvent(
        user_id=user_id,
        source_event_id=source_event_id,
        transaction_id=transaction_id,
        plan=original.plan,
        billing_interval=original.billing_interval,
        currency=original.currency,
        gross_amount=-original.gross_amount,
        fee_amount=-original.fee_amount,
        net_amount=-original.net_amount,
        pricing_version=original.pricing_version,
        service_period_start=original.service_period_start,
        service_period_end=original.service_period_end,
        metadata_json={"refund": True},
    )
    db.add(refund)
    return refund
