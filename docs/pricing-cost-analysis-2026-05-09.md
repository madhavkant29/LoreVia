# LoreVia Pricing, Cost, Profit, and Integration Analysis

> **Superseded pricing notice (2026-07-24):** This dated analysis preserves the former $29/$249 Author and $49/$449 Architect catalog for historical context. Current pricing is $19/month or $190/year for Author and $39/month or $390/year for Architect.

Last updated: 2026-05-25

## Executive Summary

LoreVia's current monetization path is a three-tier subscription model with a free baseline, a 10-day Author trial, and two paid Paddle subscription plans.

The repo currently supports:

- Paddle checkout initiation and hosted checkout fallback
- Paddle webhook verification and subscription event ingestion
- 10-day trial access with follow-up trial email automation
- tier-aware usage limits and authoring gates
- higher-tier priority processing queues

The repo does not currently position legacy wallet, points, or ad-based monetization as launch revenue mechanics.

## Current Pricing In Code

Canonical sellable pricing from the shared catalog:

- Free: `$0`
- Author: `$29/mo` or `$249/year`
- Architect: `$49/mo` or `$449/year`

Commercial shape visible to users:

- 3 public tiers
- 2 paid checkout-enabled plans
- Free never requires checkout
- new accounts start with 10 days of Author access and no credit card

Primary source references:

- Shared pricing catalog: [frontend/src/lib/billing/pricing-catalog.json](/C:/Users/madha/.vscode/prod/LoreVia2/frontend/src/lib/billing/pricing-catalog.json)
- Pricing helpers: [frontend/src/lib/billing/catalog.ts](/C:/Users/madha/.vscode/prod/LoreVia2/frontend/src/lib/billing/catalog.ts)
- Pricing UI and trial copy: [frontend/src/components/billing/PricingPlans.tsx](/C:/Users/madha/.vscode/prod/LoreVia2/frontend/src/components/billing/PricingPlans.tsx)
- Trial, tier, and checkout rules: [backend/app/utils/billing_utils.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/utils/billing_utils.py:18)
- Configured limits and model defaults: [backend/app/core/config.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/core/config.py:81)

## Entitlements And Limit Posture

The current codebase positions the tiers like this:

| Tier | Price | Core monetization posture | Important configured limits |
| --- | ---: | --- | --- |
| Free | $0 | acquisition and fallback plan after trial | 1 upload total, 3 searches/day, 1 prediction/day, 2 recall/day, 1 advisor/day, 1 continuity tool use/day |
| Author | $29/mo or $249/year | main working plan for active authors | 15 uploads, 30 predictions/day, 30 high-cost turns/day |
| Architect | $49/mo or $449/year | heavy-use and series-scale plan | unlimited uploads, 60 predictions/day, 60 high-cost turns/day, priority processing |

Implementation notes:

- Free upload capacity is enforced by `FREE_MAX_BOOKS = 1`.
- Author upload capacity is enforced by `AUTHOR_MAX_UPLOADS = 15`.
- Architect is effectively unlimited for uploads through the `UNLIMITED_OWNER_UPLOAD_TIERS` path.
- Worldbuilding documents also count against upload capacity, and series-linked worldbuilding can cost more than one upload on Author.

## Revenue After Paddle Fees

Using Paddle's published pay-as-you-go pricing as of 2026-05-24:

- Fee assumption: `5% + $0.50` per checkout transaction
- Source: [Paddle pricing](https://www.paddle.com/pricing)

Estimated net revenue per successful transaction before infrastructure, support, and model spend:

| Plan | List price | Est. Paddle fee | Net revenue |
| --- | ---: | ---: | ---: |
| Author monthly | $29.00 | $1.95 | $27.05 |
| Architect monthly | $49.00 | $2.95 | $46.05 |
| Author annual | $249.00 | $12.95 | $236.05 |
| Architect annual | $449.00 | $22.95 | $426.05 |

Effective net revenue per active month if annual plans are recognized ratably:

| Plan | Net annual revenue | Effective monthly revenue |
| --- | ---: | ---: |
| Author annual | $236.05 | $19.67 |
| Architect annual | $426.05 | $35.50 |

Commercial read:

- Annual billing improves cash collection and reduces churn risk, but lowers recognized monthly revenue versus the monthly plan.
- The current annual discount is `$99` on Author and `$139` on Architect.

## Model Cost Assumptions

Current configured backend defaults:

- extraction: `gpt-4o-mini`
- intelligence/chat: `gpt-4o-mini`
- embeddings: `text-embedding-3-small`

Source references:

- Config defaults: [backend/app/core/config.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/core/config.py:81)
- `gpt-4o-mini` model pricing: [OpenAI model page](https://developers.openai.com/api/docs/models/gpt-4o-mini)
- `text-embedding-3-small` model pricing: [OpenAI model page](https://developers.openai.com/api/docs/models/text-embedding-3-small)
- General pricing index: [OpenAI API pricing](https://openai.com/api/pricing/)

Official prices used in this document as of 2026-05-24:

- `gpt-4o-mini` input: `$0.15 / 1M tokens`
- `gpt-4o-mini` cached input: `$0.075 / 1M tokens`
- `gpt-4o-mini` output: `$0.60 / 1M tokens`
- `text-embedding-3-small`: `$0.02 / 1M tokens`

Useful unit-cost shortcuts:

- 1M input + 1M output tokens on `gpt-4o-mini` costs about `$0.75`
- 100k embedded tokens on `text-embedding-3-small` costs about `$0.002`
- 1M embedded tokens costs about `$0.02`

Implication:

- LoreVia's current model mix is cost-disciplined enough that paid tier gross margins should stay strong unless prompts, summaries, or repeated reprocessing become extremely heavy.
- The bigger unit-economics risk is likely repeated long-context workflows, support burden, and storage/processing overhead rather than baseline token pricing alone.

## Integration And Ops Readiness

The repo is already wired for:

- Paddle API key based checkout enablement
- plan-to-price-id mapping for Author and Architect monthly and annual SKUs
- webhook endpoint handling for transaction and subscription events
- trial email automation hooks
- priority queue names for higher-tier processing

Operational dependencies still matter:

- Paddle live workspace setup
- webhook registration
- valid checkout return URL approval
- scheduler coverage for due trial emails
- production worker coverage for priority queues

The most relevant implementation surface for readiness checks is [backend/app/utils/billing_utils.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/utils/billing_utils.py:478).

## Launch Guidance

- Keep Free as the acquisition and collaboration-safe fallback tier.
- Keep Author as the primary conversion target because it maps best to active manuscript work.
- Keep Architect positioned around unlimited uploads, multi-book continuity, and faster processing rather than around generic "power user" language.
- Treat old monetization notes about wallets, points, or ads as historical unless the product strategy changes explicitly.
- Re-check Paddle and OpenAI pricing before using this document for investor, budgeting, or public pricing decisions, because those external assumptions can change independently of the repo.
