# Pricing, Paddle, and Monetization Implementation Summary

Last updated: 2026-05-07

This note explains what was implemented from `docs/pricing-paddle-monetization-plan.md`.

## What was implemented

### 1. Canonical tier and trial logic

Implemented in:

- `backend/app/utils/billing_utils.py`

What changed:

- Tier normalization now treats these as the canonical live tiers:
  - `free`
  - `reader`
  - `author`
  - `architect`
  - `admin`
- Legacy aliases still normalize in code only:
  - `pro` -> `author`
  - `power` -> `architect`
  - `pro_monthly` -> `reader_monthly`
  - `pro_annual` -> `reader_annual`
  - `power_monthly` -> `author_monthly`
  - `power_annual` -> `author_annual`
- Trial access is computed from `users.created_at` and does not overwrite the purchased plan in `users.tier`.
- Effective access for a new free user during the first 10 days is `author`.
- Trial presentation is surfaced as `Author (free trial)`.

### 2. Launch limit helpers

Implemented in:

- `backend/app/utils/billing_utils.py`
- `backend/app/core/config.py`

What changed:

- Added backend helpers for launch rules instead of scattering numbers across routes:
  - free semantic search limit per day
  - prediction limit per day by tier
  - protected authoring limit per day by tier
  - summary mode gating
- Config was aligned to the launch plan:
  - Free search: `5/day`
  - Free prediction: `3/day`
  - Reader prediction: `10/day`
  - Trial protected authoring cap: `20/day`
  - Author protected authoring cap: `30/day`
  - Architect protected authoring cap: `60/day`
- Standardized the user-facing limit message:
  - `Your daily limit refreshes tomorrow. Want higher limits now? Upgrade.`

### 3. UTC-reset daily counters

Implemented in:

- `backend/app/api/deps/rate_limit.py`

What changed:

- Added UTC-day bucket logic in Redis.
- High-cost counters now reset at the next `00:00 UTC` instead of relying only on rolling windows.
- Enforcement now works like this:
  - `rate_limit_search`:
    - applies to Free only
    - uses a daily UTC bucket
  - `rate_limit_chat`:
    - now acts as the prediction-query limiter
    - uses daily per-tier caps
  - `rate_limit_advisor`:
    - uses the shared protected-authoring daily bucket
  - `rate_limit_continuity_checker`:
    - uses the same shared protected-authoring daily bucket
- This means trial users, Author users, and Architect users consume from the same protected surface family for advisor and continuity usage, which matches the launch fair-use intent.

### 4. Reader and free entitlement enforcement

Implemented in:

- `backend/app/api/v1/routes/reader.py`

What changed:

- Free users can no longer access detailed or key-point summaries after trial expiry.
- Summary mode enforcement is now:
  - Free: `short` only
  - Reader and above: all summary modes
- Thematic search now also runs through the search limiter dependency.
- Existing author-only protections stayed in place elsewhere for manuscript/editor/advisor surfaces.

### 5. Paddle webhook hardening

Implemented in:

- `backend/app/api/v1/routes/webhooks.py`

What changed:

- Webhook handling remains signature-verified and idempotent.
- Active events now upsert the latest subscription state more reliably by checking:
  - `paddle_sub_id`
  - user id from `custom_data`
  - Paddle customer id
- If no matching subscription row exists and `user_id` is present, a new subscription row is created.
- `users.tier` is updated from the normalized Paddle plan code only when service should be considered active.
- Cancellation, pause, and past-due events now conservatively revert the user to `free`.
- This matches the plan rule that uncertain payment state should not leave high-cost access open.

### 6. Tier-limit payload alignment

Implemented in:

- `backend/app/schemas/auth.py`
- `backend/app/api/v1/routes/auth.py`
- `frontend/src/lib/api/auth.ts`

What changed:

- The tier-limits response now exposes the new launch-facing fields:
  - `free_search_per_day`
  - `free_prediction_per_day`
  - `reader_prediction_per_day`
  - `author_prediction_per_day`
  - `architect_prediction_per_day`
  - `trial_high_cost_turns_per_day`
  - `author_high_cost_turns_per_day`
  - `architect_high_cost_turns_per_day`

### 7. Pricing and settings copy alignment

Implemented in:

- `frontend/src/app/(dashboard)/pricing/page.tsx`
- `frontend/src/app/page.tsx`
- `frontend/src/app/(dashboard)/settings/page.tsx`

What changed:

- Pricing copy now reflects the launch plan more closely:
  - Free search/prediction numbers
  - Reader isolation wording
  - Author and Architect fair-use language
  - annual savings messaging
- Settings now explain trial reversion more clearly and show the formatted trial end date when available.

## What was intentionally not implemented

Still deferred, matching the plan:

- points ledger
- ad watch ledger
- referral rewards
- trial email automation
- Architect queue priority backend enforcement
- public feature rollout

## Verification completed

Verified in this pass:

- frontend type-check passed
- backend unit tests for:
  - `test_billing_utils.py`
  - `test_rate_limit.py`
- backend Python syntax compilation passed for the changed modules

Not fully runnable in this environment:

- new DB-backed integration tests were added, but the repo safety guard blocked execution because the current `DATABASE_URL` is not local

## Files changed for this implementation

Primary backend files:

- `backend/app/utils/billing_utils.py`
- `backend/app/core/config.py`
- `backend/app/api/deps/rate_limit.py`
- `backend/app/api/v1/routes/reader.py`
- `backend/app/api/v1/routes/webhooks.py`
- `backend/app/api/v1/routes/auth.py`
- `backend/app/schemas/auth.py`

Primary frontend files:

- `frontend/src/lib/api/auth.ts`
- `frontend/src/app/(dashboard)/pricing/page.tsx`
- `frontend/src/app/page.tsx`
- `frontend/src/app/(dashboard)/settings/page.tsx`

Primary tests:

- `backend/tests/unit/test_billing_utils.py`
- `backend/tests/unit/test_rate_limit.py`
- `backend/tests/integration/test_webhooks.py`
- `backend/tests/integration/test_pricing_enforcement.py`
