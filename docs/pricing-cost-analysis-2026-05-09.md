# LoreVia Pricing, Cost, Profit, and Integration Analysis

Last updated: 2026-05-10

## Executive summary

LoreVia's current codebase is monetization-ready in the broad sense: pricing tiers exist in frontend and backend, Paddle checkout and portal endpoints are wired, webhook verification and idempotency exist, trial logic is enforced, and points/referrals/trial-email lifecycle tables are in place.

The most important conclusion is this:

- No, entering only the webhook secret is not the final remaining step.
- Billing needs more than the webhook secret: Paddle API key plus the six price IDs are also required.
- Trial email automation still needs an actual scheduler calling the protected internal job endpoint.
- Points are now spendable for same-day overflow, have a frontend wallet, and include rewarded-ad earning.
- Architect priority routing is code-complete in repo; the only remaining queue work is production worker command parity.

## What the repo currently sells

Canonical live pricing in code:

- Free: `$0`
- Reader: `$12/mo` or `$120/yr`
- Author: `$24/mo` or `$240/yr`
- Lore Architect: `$36/mo` or `$360/yr`

Current tier behavior from code:

- All new users get a 10-day Author trial.
- Free users get short summaries only, `5` semantic searches/day, and `3` prediction queries/day.
- Reader unlocks all summary modes and `10` prediction queries/day, but remains reader-only.
- Author is marketed as unlimited but is fair-use capped at `30` protected high-cost turns/day.
- Architect is marketed as unlimited but is fair-use capped at `60` protected high-cost turns/day.

Primary code references:

- Pricing UI: [frontend/src/components/billing/PricingPlans.tsx](/C:/Users/madha/.vscode/prod/LoreVia2/frontend/src/components/billing/PricingPlans.tsx:30)
- Trial + tier rules: [backend/app/utils/billing_utils.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/utils/billing_utils.py:18)
- Limits config: [backend/app/core/config.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/core/config.py:150)

## What points currently do

Points are live as a controlled same-day relief system, not as a subscription discount or general-purpose credit balance.

Implemented now:

- balance endpoint
- ledger endpoint
- referral summary/apply endpoints
- one-time first processed book reward
- referral rewards
- 90-day expiry
- frontend points wallet surface
- same-day spend for `search`, `prediction`, and author-tier protected overflow
- daily-cap upgrade/spend prompt in reader surfaces
- rewarded-ad earning flow for point grants

Current reward values:

- referrer reward: `50` points
- referred user reward: `25` points
- first processed book: `25` points

Not implemented now:

- no points checkout discount
- no subscription-price reduction at checkout
- no plan-tier unlocking through points
- no priority-queue unlocking through points

References:

- points constants: [backend/app/utils/monetization_utils.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/utils/monetization_utils.py:24)
- points/referral routes: [backend/app/api/v1/routes/monetization.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/api/v1/routes/monetization.py:27)
- points wallet UI: [frontend/src/app/(dashboard)/settings/page.tsx](/C:/Users/madha/.vscode/prod/LoreVia2/frontend/src/app/(dashboard)/settings/page.tsx:351)
- cap-hit spend prompt: [frontend/src/components/monetization/DailyCapPrompt.tsx](/C:/Users/madha/.vscode/prod/LoreVia2/frontend/src/components/monetization/DailyCapPrompt.tsx:1)
- rewarded-ad UI: [frontend/src/components/monetization/RewardedAdEarnCard.tsx](/C:/Users/madha/.vscode/prod/LoreVia2/frontend/src/components/monetization/RewardedAdEarnCard.tsx:1)
- reward triggers on completed processing: [backend/app/workers/consumers/extraction_consumer.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/workers/consumers/extraction_consumer.py:738)

## Revenue after Paddle fees

Assumption used here:

- Paddle pay-as-you-go fee: `5% + $0.50` per checkout transaction
- Source: [Paddle pricing](https://www.paddle.com/pricing)

Net revenue per successful subscription sale before infrastructure and model costs:

| Plan | List price | Est. Paddle fee | Net revenue |
| --- | ---: | ---: | ---: |
| Reader monthly | $12.00 | $1.10 | $10.90 |
| Author monthly | $24.00 | $1.70 | $22.30 |
| Architect monthly | $36.00 | $2.30 | $33.70 |
| Reader annual | $120.00 | $6.50 | $113.50 |
| Author annual | $240.00 | $12.50 | $227.50 |
| Architect annual | $360.00 | $18.50 | $341.50 |

Effective net revenue per month for annual plans:

- Reader annual: about `$9.46/mo`
- Author annual: about `$18.96/mo`
- Architect annual: about `$28.46/mo`

## Model cost assumptions

Current configured model defaults in backend:

- extraction: `gpt-4o-mini`
- intelligence/chat: `gpt-4o-mini`
- embeddings: `text-embedding-3-small`

Source references:

- config: [backend/app/core/config.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/core/config.py:73)
- OpenAI pricing: [OpenAI API pricing](https://openai.com/api/pricing/) and [OpenAI detailed pricing](https://platform.openai.com/docs/pricing/)

Official pricing used for estimates:

- `gpt-4o-mini` input: `$0.15 / 1M tokens`
- `gpt-4o-mini` output: `$0.60 / 1M tokens`
- `text-embedding-3-small`: `$0.02 / 1M tokens`

## Cost envelope by feature

These are code-shaped estimates, not exact accounting figures, because the repo does not currently store per-request token/cost telemetry.

### Protected authoring turn cost

The protected high-cost bucket is shared by Story Advisor and continuity-style authoring flows.

Rough per-turn envelope from current code:

- advisor turn: one query embedding + one `gpt-4o-mini` response up to `800` output tokens
- continuity/editorial flows: one `gpt-4o-mini` response up to roughly `1200` output tokens

Reasonable working estimate:

- protected high-cost turn: about `$0.0015` to `$0.0025`

If a user actually hits the full fair-use cap every day:

| Tier | Daily cap | Est. monthly protected-turn cost |
| --- | ---: | ---: |
| Trial | 20/day | about `$0.90` to `$1.50` |
| Author | 30/day | about `$1.35` to `$2.25` |
| Architect | 60/day | about `$2.70` to `$4.50` |

This is economically safe relative to plan price.

### Prediction cost

Prediction flow uses semantic retrieval plus one `gpt-4o-mini` completion capped at `1000` output tokens.

Reasonable working estimate:

- prediction query: about `$0.0010` to `$0.0020`

If a Reader uses all `10/day` prediction turns for 30 days:

- estimated monthly prediction cost: about `$0.30` to `$0.60`

That still leaves wide margin against Reader net revenue.

### Ingestion and embeddings cost

The heavier cost center is book ingestion, not daily chat.

Important code facts:

- free users are capped by a total ingestion token budget of `250000`
- extraction batches are capped at `7000` tokens per batch
- summary generation uses chapter text clipped to `9000` chars with `2200` max output tokens
- embeddings use `text-embedding-3-small`

Reasonable working estimate for a full free-tier budget user:

- embeddings: very cheap
- extraction + summaries: still likely measured in cents, not dollars, on `gpt-4o-mini`

Operational conclusion:

- current pricing is far more likely to be limited by worker throughput, abuse, or infrastructure operations than by raw `gpt-4o-mini` token cost
- if anyone accidentally deploys with `gpt-4o` instead of `gpt-4o-mini`, margins deteriorate quickly

## Profit / loss view

### Per-plan rough unit economics

Using the fee and model assumptions above:

| Plan | Net revenue | Likely recurring model cost | Gross contribution before infra/support |
| --- | ---: | ---: | ---: |
| Reader monthly | $10.90 | low, often well under `$1/mo` | strong positive |
| Author monthly | $22.30 | low-to-moderate, often low single digits | strong positive |
| Architect monthly | $33.70 | moderate, still likely low single digits to a few dollars | strong positive |

### Break-even intuition

Ignoring support labor and using only software cost:

- one Reader monthly subscriber nearly covers the repo's old `$30/mo` planning assumption by about three subscriptions
- one Author monthly subscriber contributes materially more headroom
- annual plans improve cash flow but lower net monthly equivalent due to the discount

### Business reality

The pricing is viable with current model choices.

The bigger P&L risk is not token pricing. It is one of these:

- stale env config accidentally using more expensive models
- weak abuse control on free ingestion or trials
- support/refund burden
- marketing/sales tax/payment friction
- shipping features that claims say exist but workers/queues do not fully support

## Integration and security readiness

### Implemented and good

- Paddle checkout route exists
- Paddle customer portal route exists
- Paddle webhook signature verification exists
- webhook replay/idempotency exists via Redis
- tier downgrade on canceled/past-due/paused exists
- auth/session/security headers are in place
- internal cron-style trial email endpoint is protected by a secret

References:

- billing routes: [backend/app/api/v1/routes/billing.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/api/v1/routes/billing.py:17)
- webhook route: [backend/app/api/v1/routes/webhooks.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/api/v1/routes/webhooks.py:27)
- Paddle service: [backend/app/services/paddle_service.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/services/paddle_service.py:23)
- webhook replay key: [backend/app/core/redis.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/core/redis.py:80)
- security headers middleware: [backend/app/main.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/main.py:59)

### Required before production billing is truly complete

You need all of these, not just the webhook secret:

- `PADDLE_API_KEY`
- `PADDLE_WEBHOOK_SECRET`
- `PADDLE_READER_MONTHLY_PRICE_ID`
- `PADDLE_READER_ANNUAL_PRICE_ID`
- `PADDLE_AUTHOR_MONTHLY_PRICE_ID`
- `PADDLE_AUTHOR_ANNUAL_PRICE_ID`
- `PADDLE_ARCHITECT_MONTHLY_PRICE_ID`
- `PADDLE_ARCHITECT_ANNUAL_PRICE_ID`

Recommended:

- `PADDLE_DEFAULT_CHECKOUT_URL`

Config reference:

- [backend/app/core/config.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/core/config.py:90)

### Also still needed outside pure billing

1. Trial email scheduler

- The code can send due trial emails, but something still has to call `POST /api/v1/internal/jobs/send-due-trial-emails`.
- That also requires `INTERNAL_JOB_SECRET`.
- Without a scheduler, trial email automation is not actually live.

References:

- internal route: [backend/app/api/v1/routes/internal.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/api/v1/routes/internal.py:13)
- config secret: [backend/app/core/config.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/core/config.py:113)

2. Resend credentials

- Trial and processing emails depend on `RESEND_API_KEY`.
- If this is missing, lifecycle and onboarding email flows are not complete.

Reference:

- [backend/app/core/config.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/core/config.py:109)

3. Architect priority queue rollout still needs production command parity

- App code routes Architect/Admin users to `extraction_priority` and `analysis_priority`.
- The repo now declares those queues and local Docker Compose consumes them.
- Production worker commands still need to consume those queues too, otherwise launch behavior can drift from local behavior.

This means the "priority processing" claim is code-ready in repo, but still depends on production worker command parity.

References:

- queue suffix logic: [backend/app/utils/queue_utils.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/utils/queue_utils.py:7)
- declared queues: [backend/app/workers/queues/queues.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/workers/queues/queues.py:3)
- worker commands: [backend/Dockerfile.worker](/C:/Users/madha/.vscode/prod/LoreVia2/backend/Dockerfile.worker:20)

4. Legacy Stripe remnants still exist in the data model, but the main deploy docs are now corrected

The repo still has stale Stripe references even though Paddle is the live integration path.

- `README.md` has been corrected to Paddle during this audit
- `Subscription` model still contains old Stripe columns

This is not a launch blocker by itself, but it is a real operator-risk and onboarding-risk.

References:

- stale README wording: [README.md](/C:/Users/madha/.vscode/prod/LoreVia2/README.md:53)
- stale README env example: [README.md](/C:/Users/madha/.vscode/prod/LoreVia2/README.md:139)
- legacy model columns: [backend/app/models/user.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/models/user.py:66)

5. Production origin hardening is optional, not guaranteed

- Cloudflare Tunnel support exists, but only if `CLOUDFLARE_TUNNEL_TOKEN` is configured and deployed that way.
- If you intend origin protection as part of final security posture, this still needs infra confirmation.

Reference:

- [backend/app/core/config.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/core/config.py:183)

## Final answer to the webhook question

If by "final touch" you mean "can users complete paid checkout and have tiers update correctly," then no, the webhook key alone is not enough.

Minimum remaining production setup checklist:

1. Set Paddle API key.
2. Set all six Paddle price IDs.
3. Set Paddle webhook secret.
4. Confirm webhook endpoint is registered in Paddle for the supported events.
5. Set `PADDLE_DEFAULT_CHECKOUT_URL` if you want approved-domain checkout URLs.
6. Set `RESEND_API_KEY`.
7. Set `INTERNAL_JOB_SECRET`.
8. Put a scheduler in place for the due-trial-emails internal job.
9. Make sure production worker commands consume the priority queues if Architect priority processing is part of launch claims.
10. Decide whether to keep or later remove the legacy Stripe columns in `Subscription`; they are no longer part of the active billing path.

## Recommended next actions

If you want the safest near-launch path, do these next:

1. Treat Paddle env completion, webhook registration, and scheduler setup as the real final integration milestone.
2. Market points carefully as overflow relief only, not as subscription replacement or broad account credit.
3. Mirror the repo's priority queue commands in production worker configuration before claiming priority processing is live.
4. Use `GET /api/v1/billing/status` as the source of truth for code-side readiness, supported webhook events, and remaining external action items.
