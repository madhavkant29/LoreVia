import uuid

from app.models.user import User
from app.services.revenue_ledger_service import record_completed_transaction_revenue


async def test_completed_transaction_revenue_is_idempotent(db):
    suffix = uuid.uuid4().hex[:8]
    user = User(
        email=f"revenue-{suffix}@lorevia.app",
        username=f"revenue{suffix}",
        password_hash="fake",
    )
    db.add(user)
    await db.flush()
    data = {
        "currency_code": "USD",
        "details": {"totals": {"total": "4900"}},
        "billing_period": {
            "starts_at": "2026-06-01T00:00:00Z",
            "ends_at": "2026-07-01T00:00:00Z",
        },
    }
    first = await record_completed_transaction_revenue(
        db,
        source_event_id=f"event-{suffix}",
        user_id=user.id,
        plan="architect_monthly",
        transaction_id=f"txn-{suffix}",
        data=data,
    )
    await db.flush()
    duplicate = await record_completed_transaction_revenue(
        db,
        source_event_id=f"event-{suffix}",
        user_id=user.id,
        plan="architect_monthly",
        transaction_id=f"txn-{suffix}",
        data=data,
    )

    assert first is not None
    assert duplicate is not None
    assert duplicate.id == first.id
    assert float(first.net_amount) == 46.05
