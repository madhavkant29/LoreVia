# LoreVia Render Production Launch Checklist

Last updated: 2026-05-10

This is the copy-paste launch checklist for getting LoreVia production-ready on Render.

## What `GET /api/v1/billing/status` means

Use [backend/app/api/v1/routes/billing.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/api/v1/routes/billing.py:17) as the readiness endpoint.

It now reports:

- whether Paddle keys and all four paid-plan price IDs are truly configured
- whether `RESEND_API_KEY` and `INTERNAL_JOB_SECRET` are present
- the supported Paddle webhook events
- the expected trial-email job path
- whether points wallet, points spending, rewarded ads, and priority processing are code-ready
- the remaining external action items that still must be done in Render or third-party dashboards

## Rewarded ads: what those two pieces are

`Added the GPT rewarded-ad playback`

- File: [frontend/src/lib/monetization/rewardedAds.ts](/C:/Users/madha/.vscode/prod/LoreVia2/frontend/src/lib/monetization/rewardedAds.ts:1)
- Purpose: loads Google Publisher Tag, requests a rewarded ad slot, listens for reward/close events, and returns the outcome to LoreVia.
- This is frontend browser code only.

`Added a reusable rewarded-ad earn card`

- File: [frontend/src/components/monetization/RewardedAdEarnCard.tsx](/C:/Users/madha/.vscode/prod/LoreVia2/frontend/src/components/monetization/RewardedAdEarnCard.tsx:1)
- Purpose: reusable UI card that:
  - checks rewarded-ad availability from the backend
  - starts a backend reward session
  - plays the ad in the browser
  - resolves the reward back to the backend
- It is currently mounted in:
  - [frontend/src/app/(dashboard)/settings/page.tsx](/C:/Users/madha/.vscode/prod/LoreVia2/frontend/src/app/(dashboard)/settings/page.tsx:437)
  - [frontend/src/components/monetization/DailyCapPrompt.tsx](/C:/Users/madha/.vscode/prod/LoreVia2/frontend/src/components/monetization/DailyCapPrompt.tsx:221)

## Where to set rewarded-ad env vars

These are backend env vars, not frontend env vars.

Definition:

- [backend/app/core/config.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/core/config.py:116)

Backend usage:

- [backend/app/services/monetization_service.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/services/monetization_service.py:173)

Frontend consumption:

- the frontend does **not** hardcode the ad unit path
- it gets the ad unit path from `/api/v1/monetization/rewarded-ads/status` and `/api/v1/monetization/rewarded-ads/session`

On Render, set these in the **backend web service** environment variables:

- `REWARDED_ADS_ENABLED=true`
- `REWARDED_AD_GPT_UNIT_PATH=/1234567/lorevia/rewarded`

Optional tuning in the same Render backend service:

- `REWARDED_AD_REWARD_POINTS=3`
- `REWARDED_AD_DAILY_CAP=1`
- `REWARDED_AD_SESSION_TTL_SECONDS=900`
- `REWARDED_AD_MIN_GRANT_SECONDS=5`

## Render env vars to set on the backend web service

Required for payments:

- `PADDLE_API_KEY`
- `PADDLE_WEBHOOK_SECRET`
- `PADDLE_AUTHOR_MONTHLY_PRICE_ID`
- `PADDLE_AUTHOR_ANNUAL_PRICE_ID`
- `PADDLE_ARCHITECT_MONTHLY_PRICE_ID`
- `PADDLE_ARCHITECT_ANNUAL_PRICE_ID`

Recommended:

- `PADDLE_DEFAULT_CHECKOUT_URL=https://your-frontend-domain/checkout`

Required for email/lifecycle:

- `RESEND_API_KEY`
- `INTERNAL_JOB_SECRET`
- `APP_URL=https://your-frontend-domain`

Optional for rewarded ads:

- `REWARDED_ADS_ENABLED=true`
- `REWARDED_AD_GPT_UNIT_PATH=/your/network/code`
- `REWARDED_AD_REWARD_POINTS=3`
- `REWARDED_AD_DAILY_CAP=1`
- `REWARDED_AD_SESSION_TTL_SECONDS=900`
- `REWARDED_AD_MIN_GRANT_SECONDS=5`

## Render worker commands to use

Use these queue commands in production so priority processing matches the repo:

- extraction worker:
  - `celery -A app.workers.celery_app worker -Q extraction,extraction_priority --loglevel=info -c 4`
- analysis worker:
  - `celery -A app.workers.celery_app worker -Q analysis,analysis_priority,embedding --loglevel=info -c 2`
- intelligence worker:
  - `celery -A app.workers.celery_app worker -Q intelligence --loglevel=info -c 1`

References:

- [backend/Dockerfile.worker](/C:/Users/madha/.vscode/prod/LoreVia2/backend/Dockerfile.worker:21)
- [backend/app/workers/queues/queues.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/workers/queues/queues.py:1)
- [backend/app/workers/celery_app.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/workers/celery_app.py:1)

## Paddle dashboard checklist

In Paddle, do all of these:

1. Create or confirm the four live price IDs for:
   - Author monthly
   - Author annual
   - Architect monthly
   - Architect annual
2. Register this webhook endpoint:
   - `https://api.getlorevia.com/api/v1/webhooks/paddle`
3. Subscribe the webhook to these supported events:
   - `transaction.completed`
   - `subscription.created`
   - `subscription.updated`
   - `subscription.canceled`
   - `subscription.past_due`
   - `subscription.paused`

## Trial-email automation checklist

Code is ready. Render still needs the recurring trigger.

Endpoint:

- `POST /api/v1/internal/jobs/send-due-trial-emails`

Header:

- `X-Internal-Job-Secret: <INTERNAL_JOB_SECRET>`

Alternative script:

- `python backend/scripts/run_due_trial_emails.py --limit 100`

Use one of these production patterns:

1. A Render cron job or external scheduler that hits the internal endpoint.
2. A scheduled worker command that runs the Python script on an interval.

Reference:

- [backend/scripts/run_due_trial_emails.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/scripts/run_due_trial_emails.py:1)

## Copy-paste verification flow

After setting env vars and redeploying:

1. Sign in to a real account.
2. Call:
   - `GET https://your-backend-domain/api/v1/billing/status`
3. Confirm:
   - `payments_ready: true`
   - `paddle_api_key_present: true`
   - `webhook_secret_present: true`
   - `resend_api_key_present: true`
   - `internal_job_secret_present: true`
   - `fully_configured_plan_count: 4`
4. Confirm the response also shows:
   - `trial_email_automation_code_ready: true`
   - `priority_processing_code_ready: true`
   - `points_wallet_ready: true`
   - `points_spend_ready: true`
   - `rewarded_ads_code_ready: true`

Then do these live checks:

1. Start a real or sandbox Paddle checkout from the app.
2. Confirm the checkout completes successfully.
3. Confirm Paddle sends the webhook.
4. Confirm the user's LoreVia tier updates after the webhook lands.
5. Trigger one trial-email run and confirm it sends successfully.
6. If using rewarded ads, confirm the ad loads and grants points once.

## Day-one truth

Code-complete in repo:

- Paddle checkout route
- Paddle portal route
- Paddle webhook signature verification
- webhook replay/idempotency
- subscription-to-tier updates
- trial-email send logic and protected job route
- points wallet UI
- points spending for same-day overflow
- rewarded-ad earning flow
- priority queue wiring

Still external:

- real Paddle dashboard registration
- real live/sandbox checkout verification
- Render env var setup
- trial-email scheduler
- production worker command parity
- real rewarded-ad inventory and fill validation
