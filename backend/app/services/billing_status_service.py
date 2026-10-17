from __future__ import annotations

from typing import cast

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Subscription, User
from app.schemas.billing import (
    BillingDisplayState,
    BillingSubscriptionOut,
    BillingSubscriptionPriceOut,
)
from app.utils.billing_utils import (
    FREE_TIER,
    build_tier_presentation,
    normalize_plan_code,
    normalize_tier,
    plan_price_payload,
    subscription_auto_renews,
    subscription_display_state,
    subscription_tier_for_user,
    tier_from_plan_code,
)


async def get_billing_subscription_state(
    db: AsyncSession,
    user: User,
) -> BillingSubscriptionOut:
    subscription = (
        (
            await db.execute(
                select(Subscription)
                .where(
                    Subscription.user_id == user.id,
                    or_(
                        Subscription.paddle_customer_id.is_not(None),
                        Subscription.paddle_sub_id.is_not(None),
                    ),
                )
                .order_by(Subscription.created_at.desc())
            )
        )
        .scalars()
        .first()
    )

    if subscription is None:
        return _empty_state(user)

    raw_status = (subscription.status or "").strip().lower()
    raw_plan = normalize_plan_code(subscription.plan)
    plan = raw_plan if raw_plan else FREE_TIER
    plan_tier = tier_from_plan_code(plan)
    if plan_tier == FREE_TIER:
        plan_tier = normalize_tier(subscription_tier_for_user(user))

    cancel_at_period_end = bool(subscription.cancel_at_period_end)
    auto_renew = subscription_auto_renews(raw_status, cancel_at_period_end)
    presentation = build_tier_presentation(user)
    display_state = cast(
        BillingDisplayState,
        subscription_display_state(
            status=raw_status,
            cancel_at_period_end=cancel_at_period_end,
            trial_active=presentation.trial_active and plan_tier == FREE_TIER,
        ),
    )

    priced_plan = plan if plan_tier != FREE_TIER else FREE_TIER
    price_payload = plan_price_payload(priced_plan)

    return BillingSubscriptionOut(
        plan=priced_plan,
        plan_tier=plan_tier,
        status=raw_status or "free",
        display_state=display_state,
        price=BillingSubscriptionPriceOut(
            amount=price_payload["amount"],
            currency=price_payload["currency"],
            interval=price_payload["interval"],
        ),
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        cancel_at_period_end=cancel_at_period_end,
        cancellation_scheduled_at=subscription.cancellation_scheduled_at,
        next_charge_at=subscription.current_period_end if auto_renew else None,
        auto_renew=auto_renew,
        last_payment_status=subscription.last_payment_status,
        has_paddle_subscription=bool(subscription.paddle_sub_id),
    )


def _empty_state(user: User) -> BillingSubscriptionOut:
    presentation = build_tier_presentation(user)
    return BillingSubscriptionOut(
        plan=FREE_TIER,
        plan_tier=FREE_TIER,
        status="free",
        display_state="trial" if presentation.trial_active else "free",
        price=BillingSubscriptionPriceOut(
            amount=0,
            currency="USD",
            interval="month",
        ),
        cancel_at_period_end=False,
        next_charge_at=None,
        auto_renew=False,
        has_paddle_subscription=False,
    )
