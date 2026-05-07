# Onboarding, Trial, Points, Referral, and Queue Priority Plan

Last updated: 2026-05-07

This document is the execution plan for the next monetization/onboarding phase.

Implementation status: backend MVP implemented on 2026-05-07.

Approved scope:

- onboarding and free-trial email automation
- at least 4 emails during the 10-day trial
- Resend-based delivery
- points ledger
- referral rewards
- Architect queue priority backend enforcement

Explicitly deferred:

- public feature rollout
- ad watch ledger

## Implemented Backend MVP

The backend implementation now includes:

- `trial_email_events` scheduling for 4 trial lifecycle emails:
  - `trial_started`
  - `trial_nudge`
  - `trial_ending`
  - `trial_ended`
- Resend-backed trial email delivery through `backend/app/services/email_service.py`.
- `lifecycle_tasks.send_due_trial_emails` Celery scanner for due verified-user trial emails.
- If a user verifies late and multiple lifecycle emails are already due, the worker skips older pending trial emails and sends the latest due message only.
- Immutable `point_ledger_entries` with grant and expiry entries.
- Referral codes on users and `referrals` records.
- Referral rewards only after the referred user has verified email and completed first book processing.
- First processed book point reward.
- Read endpoints for points balance, points ledger, referral link, and referral reward history.
- Referral application through signup/OAuth and authenticated `/monetization/referrals/apply`.
- Architect/Admin task dispatch to priority queues for extraction and analysis dispatch points.

Still not implemented in this phase:

- public feature rollout
- ad watch ledger
- point spending against rate-limit overflow
- paid-conversion referral bonus
- frontend settings/pricing surfaces for points/referrals

## Goals

This phase should do four things well:

1. make new users understand the trial quickly
2. increase trial-to-paid conversion without weakening Reader vs Author boundaries
3. introduce points in a tightly controlled way
4. make Lore Architect feel operationally better for heavy workloads

## Current codebase anchors

Relevant existing pieces:

- `backend/app/services/email_service.py`
  - already wraps Resend
  - already sends onboarding, verification, reset, processing, and subscription emails
- `backend/app/api/v1/routes/auth.py`
  - creates users
  - verifies email
  - already sends verification and onboarding mail
- `backend/app/utils/billing_utils.py`
  - computes effective tier vs purchased tier
  - already knows trial state
- `backend/app/workers/celery_app.py`
  - already defines extraction, analysis, embedding, and intelligence queues
- `backend/app/api/v1/routes/books.py`
  - dispatches extraction work
- `backend/app/api/v1/routes/reader.py` and advisor/manuscript surfaces
  - already enforce most tier behavior

## Recommended rollout order

1. schema and docs
2. points ledger backend
3. referral reward backend
4. trial email templates and scheduling
5. Architect queue priority enforcement
6. settings/pricing UI for points and referrals

This order keeps the hard data model stable before automations and UI are layered on top.

## Trial email plan

### MVP sequence

Use exactly 4 automated emails in the first pass:

| Day | Email | Goal |
| :-- | :---- | :--- |
| Day 0 | Trial started | orient the user and push first action |
| Day 3 | Have you tried this yet? | reactivate inactive or shallow-use trial users |
| Day 9 | Trial ends tomorrow | urgency + clear downgrade explanation |
| Day 10 | Trial ended | convert to paid |

### Delivery rules

- Use Resend through `backend/app/services/email_service.py`.
- Keep transactional mail separate:
  - verification email stays transactional
  - password reset stays transactional
  - trial emails are lifecycle/marketing-operational mail
- Recommended rule:
  - schedule trial emails from `users.created_at`
  - only send non-transactional trial emails after `email_verified_at` is present
  - if the user verifies late, send the next due message only, not the whole backlog

### Email content plan

#### 1. Trial started

Subject direction:

- `Your LoreVia Author trial has started`

Body should include:

- what the 10-day trial unlocks
- first action CTA:
  - upload your first manuscript/book
- 3 concrete trial features to try:
  - Story Advisor
  - continuity checking
  - character bible / manuscript editor

#### 2. Day 3 nudge

Subject direction:

- `Have you tried LoreVia on a real manuscript yet?`

Recommended branching:

- no book uploaded:
  - push upload CTA
- book uploaded but no authoring usage:
  - push Story Advisor / continuity
- active user:
  - push manuscript editor or character bible export

This should be usage-aware if possible, but it can ship as a simple generic nudge first.

#### 3. Trial ends tomorrow

Subject direction:

- `Your trial ends tomorrow`

Body should include:

- exact downgrade explanation:
  - Free keeps Smart Tap, recall, full profiles, short summaries
  - Author-only tools lock again
- primary CTA:
  - upgrade to Reader / Author / Architect
- secondary CTA:
  - compare plans

#### 4. Trial ended

Subject direction:

- `Your Author trial has ended`

Body should include:

- current effective access is now Free unless a paid plan exists
- what features are now locked
- clean upgrade CTA
- optional launch promo if currently active

## Trial email automation plan

### Data model

Recommended new table:

- `trial_email_events`

Suggested fields:

- `id`
- `user_id`
- `email_type`
  - `trial_started`
  - `trial_nudge`
  - `trial_ends_tomorrow`
  - `trial_ended`
- `scheduled_for`
- `sent_at`
- `status`
  - `pending`
  - `sent`
  - `skipped`
  - `failed`
- `resend_message_id`
- `last_error`
- `metadata_json`
- `created_at`
- `updated_at`

Why:

- idempotency
- retry safety
- reporting
- clear audit trail for lifecycle messaging

### Scheduling strategy

Recommended implementation:

- create schedule rows when the user registers
- run an hourly worker or cron-triggered task that:
  - selects due unsent emails
  - checks eligibility
  - sends via Resend
  - marks sent/failed/skipped

Do not rely only on delayed single-shot tasks at signup. A reconciliation scanner is safer if workers restart or tasks are lost.

### Eligibility checks

Before sending each trial email:

- user still exists
- email is verified for non-transactional trial mail
- email type not already sent
- for day 9/day 10:
  - compute current trial state from `created_at`
  - if user already upgraded, adjust copy or skip the upgrade-heavy version

## Points ledger plan

### Core rule

Implement points as an immutable ledger first, not as a loose mutable balance only.

### Data model

Recommended new tables:

1. `point_ledger_entries`
2. optional cached balance on `users.points_balance`

Suggested ledger fields:

- `id`
- `user_id`
- `entry_type`
  - `grant`
  - `spend`
  - `expire`
  - `reversal`
- `source_type`
  - `referral_reward`
  - `first_processed_book`
  - `daily_login`
  - `admin_grant`
  - `search_overflow`
  - `prediction_overflow`
  - `author_advisor_overflow`
  - `author_continuity_overflow`
- `source_id`
- `points_delta`
- `expires_at`
- `metadata_json`
- `created_at`

Why:

- prevents silent balance corruption
- makes expiry/reversal explicit
- supports future reporting and anti-abuse review

### MVP grant sources

For this next phase, recommended live point grants are:

- referral reward
- first processed book reward
- optional admin/manual grant

Recommended to delay daily login bonus until the ledger is stable.

### MVP spend rules

Allowed early spends:

- `+5` semantic searches for Free
- `+1` prediction query for Free or Reader
- `+1` Author same-tier advisor overflow turn
- `+1` Author same-tier continuity overflow turn

Do not allow:

- Reader -> author unlocks
- Free -> author unlocks
- Author -> Architect queue priority unlocks
- any points purchase path with cash

### Expiry

Recommended expiry policy:

- referral and promo points expire in 90 days
- earned non-promo points can either:
  - not expire in MVP
  - or use a 180-day expiry if cost pressure matters

Also add a weekly cleanup worker for expiry processing.

## Referral rewards plan

### Referral model

Keep this simple.

Recommended new table:

- `referrals`

Suggested fields:

- `id`
- `referrer_user_id`
- `referred_user_id`
- `referral_code`
- `status`
  - `pending`
  - `qualified`
  - `rewarded`
  - `rejected`
- `qualified_at`
- `rewarded_at`
- `metadata_json`
- `created_at`

### Referral code strategy

Recommended:

- generate a stable invite code per user
- do not use raw user ids in public links

Example:

- `https://getlorevia.com/register?ref=ABCD1234`

### Qualification rule

To reduce abuse, do not reward on signup alone.

Recommended qualification event:

- referred user verifies email
- and completes first processed book

Optional stricter alternative:

- referred user becomes paid

Recommendation:

- use `verified + first processed book` for MVP
- leave paid-conversion bonuses for later if needed

### Reward amount

Keep rewards small enough that they help, but do not simulate a subscription.

Recommended MVP:

- referrer: `50` points
- referred user: `25` points

Implemented MVP:

- referrer: `50` points
- referred user: `25` points
- first processed book: `25` points

One-time only:

- one reward per referred user
- no self-referrals
- no duplicate rewards across multiple accounts on the same device if fraud checks trip

## Architect queue priority backend plan

### Goal

Lore Architect should feel faster for heavy workloads, especially:

- book extraction
- chapter analysis
- intelligence-heavy author workflows

### Recommended enforcement model

Because the current stack uses Celery with Redis, prefer queue separation over relying only on numeric task priorities.

Recommended new queues:

- `extraction_priority`
- `analysis_priority`
- `intelligence_priority`

Routing rule:

- `architect` -> priority queues
- `author`, `reader`, `free`, `trial` -> standard queues

### Dispatch points to update

Primary candidates:

- book upload / processing dispatch
- chapter analysis dispatch
- user-facing intelligence tasks that already go through Celery

### Guardrails

- points must never unlock priority
- Reader must never gain author/Architect processing paths
- do not claim queue priority in UI until the worker routing is actually live

## API and UI plan

### Backend

Add:

- points balance read endpoint
- points ledger history endpoint
- referral code/status endpoint
- referral apply endpoint during signup or pre-signup capture

### Frontend

Recommended first surfaces:

- settings page:
  - current plan
  - trial status
  - points balance
  - referral link
- pricing page:
  - explain trial
  - explain points only as minor overflow relief

Do not add:

- ad wallet
- public profile/share surfaces

## Testing plan

### Unit tests

Add coverage for:

- trial email schedule generation
- email eligibility rules
- points grant/spend/expiry logic
- referral qualification and duplicate-prevention logic
- Architect queue routing helper

### Integration tests

Add coverage for:

- signup with referral code
- email-verification + first processed book -> reward issuance
- day-9/day-10 trial email send conditions
- Architect task dispatch lands on priority queue

## Recommended implementation decisions

To keep this phase safe and shippable:

- use Resend through the existing email service
- store lifecycle email delivery state in SQL, not only Redis
- use an immutable points ledger
- make referral rewards qualify only after meaningful user activity
- enforce Architect priority through dedicated queues
- keep ad watch ledger and public rollout fully out of scope
