from __future__ import annotations

import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
import jwt
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user import Subscription, User
from app.services.paddle_service import (
    PaddlePriceQuote,
    PaddleTransactionState,
    cancel_paddle_transaction,
    create_checkout_url,
    find_paddle_transaction_by_checkout_intent,
    get_paddle_price_quote,
    get_paddle_transaction_state,
)
from app.utils.billing_utils import (
    FREE_TIER,
    PLAN_DISPLAY_NAMES,
    PLAN_INTERVALS,
    PLAN_PRICES_USD,
    VALID_PAID_PLAN_CODES,
    normalize_plan_code,
    subscription_tier_for_user,
    trial_ends_at,
    trial_is_active,
)

TERMINAL_SUBSCRIPTION_STATUSES = {"canceled", "cancelled"}
BLOCKING_SUBSCRIPTION_STATUSES = {"active", "trialing", "past_due", "paused"}
OPEN_TRANSACTION_STATUSES = {"draft", "ready"}
PAID_TRANSACTION_STATUSES = {"billed", "completed", "paid", "past_due"}
PENDING_CHECKOUT_TTL = timedelta(minutes=30)
CHECKOUT_CREATION_GRACE = timedelta(minutes=2)
CHECKOUT_RECONCILIATION_CLOCK_SKEW = timedelta(minutes=2)
CHECKOUT_QUOTE_TOKEN_TYPE = "billing_checkout_quote"
CHECKOUT_QUOTE_TOKEN_TTL = timedelta(minutes=10)
logger = logging.getLogger(__name__)


class DuplicateSubscriptionError(RuntimeError):
    pass


class TrialCheckoutConfirmationRequired(RuntimeError):
    pass


class CheckoutQuoteError(RuntimeError):
    pass


@dataclass(frozen=True)
class CheckoutDisclosure:
    plan: str
    display_name: str
    billing_interval: str
    trial_status: str
    trial_active: bool
    trial_ends_at: datetime | None
    charge_today: str
    recurring_price: str
    confirmation_required: bool
    confirmation_text: str | None
    checkout_button_label: str
    default_action_label: str | None
    quote_token: str | None


@dataclass(frozen=True)
class CheckoutSession:
    checkout_url: str
    customer_id: str
    transaction_id: str


@dataclass(frozen=True)
class AbandonedCheckout:
    abandoned: bool
    transaction_id: str
    status: str


def build_checkout_disclosure(
    user: User,
    plan: str,
    *,
    price_quote: PaddlePriceQuote | None = None,
    now: datetime | None = None,
) -> CheckoutDisclosure:
    normalized_plan = normalize_plan_code(plan)
    if normalized_plan not in VALID_PAID_PLAN_CODES:
        raise ValueError("Invalid paid plan")

    current = now or datetime.now(UTC)
    is_trial_active = trial_is_active(user.created_at, current)
    ends_at = trial_ends_at(user.created_at)
    amount = (
        price_quote.formatted_total
        if price_quote is not None
        else f"${PLAN_PRICES_USD[normalized_plan]:,.2f} USD"
    )
    interval = PLAN_INTERVALS[normalized_plan]
    recurring_price = f"{amount} every {'month' if interval == 'monthly' else 'year'}"
    confirmation_text = (
        f"I understand my trial is already active and I will be charged {amount} now."
        if is_trial_active
        else None
    )
    return CheckoutDisclosure(
        plan=normalized_plan,
        display_name=PLAN_DISPLAY_NAMES[normalized_plan],
        billing_interval=interval,
        trial_status="active" if is_trial_active else "expired",
        trial_active=is_trial_active,
        trial_ends_at=ends_at,
        charge_today=amount,
        recurring_price=recurring_price,
        confirmation_required=is_trial_active,
        confirmation_text=confirmation_text,
        checkout_button_label=f"Pay {amount} now",
        default_action_label="Continue free trial" if is_trial_active else None,
        quote_token=(
            _create_checkout_quote_token(user, price_quote) if price_quote is not None else None
        ),
    )


async def get_checkout_preview(
    db: AsyncSession,
    user: User,
    plan: str,
    *,
    client_ip: str | None,
    billing_enabled: bool,
) -> CheckoutDisclosure:
    subscriptions = await _subscriptions_for_user(db, user.id)
    _ensure_no_existing_subscription(user, subscriptions)
    if billing_enabled:
        changed, _ = await _reconcile_pending_checkouts(db, subscriptions)
        if changed:
            await db.commit()
        _ensure_no_existing_subscription(user, subscriptions)

    existing_customer_id = _existing_customer_id(subscriptions)
    price_quote = (
        await get_paddle_price_quote(
            plan,
            customer_ip_address=client_ip,
            existing_customer_id=existing_customer_id,
        )
        if billing_enabled
        else None
    )
    disclosure = build_checkout_disclosure(user, plan, price_quote=price_quote)
    _ensure_pending_checkout_matches_plan(subscriptions, disclosure.plan)
    return disclosure


async def create_checkout_session(
    db: AsyncSession,
    user: User,
    plan: str,
    *,
    confirmed_immediate_charge: bool,
    quote_token: str | None,
    client_ip: str | None,
) -> CheckoutSession:
    locked_user = (
        await db.execute(select(User).where(User.id == user.id).with_for_update())
    ).scalar_one()
    subscriptions = await _subscriptions_for_user(db, locked_user.id)
    _ensure_no_existing_subscription(locked_user, subscriptions)
    reconciled, transaction_states = await _reconcile_pending_checkouts(db, subscriptions)
    if reconciled:
        await db.commit()
        locked_user = (
            await db.execute(select(User).where(User.id == user.id).with_for_update())
        ).scalar_one()
        subscriptions = await _subscriptions_for_user(db, locked_user.id)
    _ensure_no_existing_subscription(locked_user, subscriptions)

    existing_customer_id = _existing_customer_id(subscriptions)
    price_quote = await get_paddle_price_quote(
        plan,
        customer_ip_address=client_ip,
        existing_customer_id=existing_customer_id,
    )
    disclosure = build_checkout_disclosure(
        locked_user,
        plan,
        price_quote=price_quote,
    )
    _ensure_pending_checkout_matches_plan(subscriptions, disclosure.plan)
    if disclosure.confirmation_required and not confirmed_immediate_charge:
        raise TrialCheckoutConfirmationRequired(disclosure.confirmation_text or "")
    if not _checkout_quote_token_matches(quote_token, locked_user, price_quote):
        raise CheckoutQuoteError(
            "Payment details changed or expired. Review the current amount before continuing."
        )

    pending = _pending_checkout(subscriptions)
    if pending is not None:
        transaction_id = pending.paddle_transaction_id or ""
        state = transaction_states.get(transaction_id)
        if state is not None and _pending_transaction_matches(
            pending,
            state,
            locked_user,
            price_quote,
        ):
            return CheckoutSession(
                checkout_url=state.checkout_url,
                customer_id=pending.paddle_customer_id or "",
                transaction_id=transaction_id,
            )
        if state is not None and state.status in OPEN_TRANSACTION_STATUSES:
            await cancel_paddle_transaction(transaction_id)
            pending.status = "canceled"
            await db.flush()
        else:
            raise DuplicateSubscriptionError(
                "The existing Paddle checkout cannot be safely replaced yet. "
                "Close it or contact support before starting another checkout."
            )

    creating = _creating_checkout(subscriptions)
    if creating is not None:
        raise DuplicateSubscriptionError(
            "A Paddle checkout is already being prepared for this account. Try again shortly."
        )

    intent = Subscription(
        user_id=locked_user.id,
        plan=disclosure.plan,
        status="creating",
    )
    db.add(intent)
    await db.flush()
    checkout_intent_uuid = intent.id
    checkout_intent_id = str(checkout_intent_uuid)
    await db.commit()

    checkout_url, customer_id, transaction_id = await create_checkout_url(
        str(locked_user.id),
        locked_user.email,
        disclosure.plan,
        existing_customer_id=existing_customer_id,
        checkout_intent_id=checkout_intent_id,
        expected_total_minor=price_quote.amount_minor,
        currency_code=price_quote.currency_code,
    )
    try:
        durable_intent = (
            await db.execute(
                select(Subscription)
                .where(Subscription.id == checkout_intent_uuid)
                .with_for_update()
            )
        ).scalar_one()
        durable_intent.status = "pending"
        durable_intent.paddle_customer_id = customer_id
        durable_intent.paddle_transaction_id = transaction_id
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        try:
            await cancel_paddle_transaction(transaction_id)
        except (RuntimeError, httpx.HTTPError):
            logger.exception(
                "Unable to cancel Paddle transaction %s after local persistence failed",
                transaction_id,
            )
        raise
    return CheckoutSession(
        checkout_url=checkout_url,
        customer_id=customer_id,
        transaction_id=transaction_id,
    )


async def abandon_checkout_session(
    db: AsyncSession,
    user: User,
    transaction_id: str,
) -> AbandonedCheckout:
    normalized_transaction_id = transaction_id.strip()
    await db.execute(select(User).where(User.id == user.id).with_for_update())
    pending = (
        (
            await db.execute(
                select(Subscription).where(
                    Subscription.user_id == user.id,
                    Subscription.paddle_transaction_id == normalized_transaction_id,
                    Subscription.status == "pending",
                    Subscription.paddle_sub_id.is_(None),
                )
            )
        )
        .scalars()
        .first()
    )
    if pending is None:
        return AbandonedCheckout(
            abandoned=False,
            transaction_id=normalized_transaction_id,
            status="not_pending",
        )

    state = await get_paddle_transaction_state(normalized_transaction_id)
    if state is None or state.status == "canceled":
        pending.status = "canceled"
        await db.commit()
        return AbandonedCheckout(True, normalized_transaction_id, "canceled")
    if state.status in OPEN_TRANSACTION_STATUSES:
        status = await cancel_paddle_transaction(normalized_transaction_id)
        pending.status = "canceled"
        await db.commit()
        return AbandonedCheckout(True, normalized_transaction_id, status)

    pending.status = _local_status_for_transaction(state.status)
    await db.commit()
    return AbandonedCheckout(False, normalized_transaction_id, pending.status)


async def _subscriptions_for_user(db: AsyncSession, user_id) -> list[Subscription]:
    return list(
        (
            await db.execute(
                select(Subscription)
                .where(Subscription.user_id == user_id)
                .order_by(Subscription.created_at.desc())
            )
        )
        .scalars()
        .all()
    )


def _ensure_no_existing_subscription(user: User, subscriptions: list[Subscription]) -> None:
    if subscription_tier_for_user(user) != FREE_TIER:
        raise DuplicateSubscriptionError(
            "This account already has paid access. Manage the existing subscription in Billing."
        )

    for subscription in subscriptions:
        status = _normalized_status(subscription.status)
        if status in BLOCKING_SUBSCRIPTION_STATUSES or (
            subscription.paddle_sub_id and status not in TERMINAL_SUBSCRIPTION_STATUSES
        ):
            raise DuplicateSubscriptionError(
                "This account already has a Paddle subscription. Manage it in Billing instead of starting another checkout."
            )


def _ensure_pending_checkout_matches_plan(subscriptions: list[Subscription], plan: str) -> None:
    checkout = _checkout_in_progress(subscriptions)
    if checkout is not None and normalize_plan_code(checkout.plan) != plan:
        raise DuplicateSubscriptionError(
            "Another Paddle checkout is already pending for this account. Complete or close that checkout before choosing a different plan."
        )


def _pending_checkout(subscriptions: list[Subscription]) -> Subscription | None:
    return next(
        (
            subscription
            for subscription in subscriptions
            if _normalized_status(subscription.status) == "pending"
            and subscription.paddle_transaction_id
            and not subscription.paddle_sub_id
        ),
        None,
    )


def _creating_checkout(subscriptions: list[Subscription]) -> Subscription | None:
    return next(
        (
            subscription
            for subscription in subscriptions
            if _normalized_status(subscription.status) == "creating"
            and not subscription.paddle_sub_id
        ),
        None,
    )


def _checkout_in_progress(subscriptions: list[Subscription]) -> Subscription | None:
    return _pending_checkout(subscriptions) or _creating_checkout(subscriptions)


def _existing_customer_id(subscriptions: list[Subscription]) -> str | None:
    return next(
        (
            subscription.paddle_customer_id
            for subscription in subscriptions
            if subscription.paddle_customer_id
        ),
        None,
    )


async def _reconcile_pending_checkouts(
    db: AsyncSession,
    subscriptions: list[Subscription],
    *,
    now: datetime | None = None,
) -> tuple[bool, dict[str, PaddleTransactionState]]:
    current = now or datetime.now(UTC)
    changed = False
    transaction_states: dict[str, PaddleTransactionState] = {}
    for subscription in subscriptions:
        status = _normalized_status(subscription.status)
        if status == "creating" and not subscription.paddle_sub_id:
            created_at = subscription.created_at
            state = None
            if created_at is not None:
                created = created_at if created_at.tzinfo else created_at.replace(tzinfo=UTC)
                state = await find_paddle_transaction_by_checkout_intent(
                    str(subscription.id),
                    customer_id=subscription.paddle_customer_id,
                    created_after=created - CHECKOUT_RECONCILIATION_CLOCK_SKEW,
                )
            if state is not None and state.transaction_id:
                subscription.paddle_transaction_id = state.transaction_id
                subscription.paddle_customer_id = (
                    state.customer_id or subscription.paddle_customer_id
                )
                transaction_states[state.transaction_id] = state
                if state.status == "canceled":
                    subscription.status = "canceled"
                elif state.status in PAID_TRANSACTION_STATUSES:
                    subscription.status = _local_status_for_transaction(state.status)
                else:
                    subscription.status = "pending"
                changed = True
                status = _normalized_status(subscription.status)
            elif _checkout_creation_is_stale(subscription, current):
                subscription.status = "canceled"
                changed = True
                continue
            else:
                continue

        if (
            status != "pending"
            or not subscription.paddle_transaction_id
            or subscription.paddle_sub_id
        ):
            continue

        transaction_id = subscription.paddle_transaction_id
        state = transaction_states.get(transaction_id)
        if state is None:
            state = await get_paddle_transaction_state(transaction_id)
        if state is None:
            subscription.status = "canceled"
            changed = True
            continue
        transaction_states[transaction_id] = state
        if state.status == "canceled":
            subscription.status = "canceled"
            changed = True
        elif state.status in PAID_TRANSACTION_STATUSES:
            subscription.status = _local_status_for_transaction(state.status)
            changed = True
        elif state.status in OPEN_TRANSACTION_STATUSES and _pending_is_stale(subscription, current):
            await cancel_paddle_transaction(transaction_id)
            subscription.status = "canceled"
            changed = True

    if changed:
        await db.flush()
    return changed, transaction_states


def _pending_is_stale(subscription: Subscription, now: datetime) -> bool:
    created_at = subscription.created_at
    if created_at is None:
        return False
    created = created_at if created_at.tzinfo else created_at.replace(tzinfo=UTC)
    current = now if now.tzinfo else now.replace(tzinfo=UTC)
    return current - created >= PENDING_CHECKOUT_TTL


def _checkout_creation_is_stale(subscription: Subscription, now: datetime) -> bool:
    created_at = subscription.created_at
    if created_at is None:
        return False
    created = created_at if created_at.tzinfo else created_at.replace(tzinfo=UTC)
    current = now if now.tzinfo else now.replace(tzinfo=UTC)
    return current - created >= CHECKOUT_CREATION_GRACE


def _pending_transaction_matches(
    pending: Subscription,
    state: PaddleTransactionState,
    user: User,
    quote: PaddlePriceQuote,
) -> bool:
    return (
        state.status in OPEN_TRANSACTION_STATUSES
        and state.total_minor == quote.amount_minor
        and state.currency_code == quote.currency_code
        and state.customer_id == (pending.paddle_customer_id or "")
        and state.price_ids == (quote.price_id,)
        and state.quantities == (1,)
        and state.custom_user_id == str(user.id)
        and state.custom_plan == quote.plan
        and state.collection_mode == "automatic"
        and not state.discount_id
        and bool(state.checkout_url)
    )


def _local_status_for_transaction(status: str) -> str:
    return "past_due" if status == "past_due" else "active"


def _create_checkout_quote_token(user: User, quote: PaddlePriceQuote) -> str:
    return jwt.encode(
        {
            "sub": str(user.id),
            "plan": quote.plan,
            "amount": quote.amount_minor,
            "currency": quote.currency_code,
            "jti": secrets.token_urlsafe(24),
            "exp": datetime.now(UTC) + CHECKOUT_QUOTE_TOKEN_TTL,
            "type": CHECKOUT_QUOTE_TOKEN_TYPE,
        },
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def _checkout_quote_token_matches(
    token: str | None,
    user: User,
    quote: PaddlePriceQuote,
) -> bool:
    if not token:
        return False
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except jwt.PyJWTError:
        return False
    return (
        str(payload.get("type") or "") == CHECKOUT_QUOTE_TOKEN_TYPE
        and str(payload.get("sub") or "") == str(user.id)
        and str(payload.get("plan") or "") == quote.plan
        and str(payload.get("amount") or "") == quote.amount_minor
        and str(payload.get("currency") or "").upper() == quote.currency_code
        and bool(str(payload.get("jti") or "").strip())
    )


def _normalized_status(value: str | None) -> str:
    return (value or "").strip().lower()
