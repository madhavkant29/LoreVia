# LoreVia Pricing, Cost, Profit, and Integration Analysis

Last updated: 2026-05-19

## Executive Summary

LoreVia's current launch monetization path is subscription-first.

The codebase supports:

- Paddle checkout and customer portal flows
- Paddle webhook verification and idempotent event handling
- trial enforcement and trial email automation
- tier-aware feature gating and fair-use limits
- priority processing support for higher tiers

The codebase no longer treats legacy wallet or ad-based experiments as active launch mechanics.

## What The Repo Currently Sells

Canonical live pricing in code:

- Free: `$0`
- Author: `$29/mo` or `$290/yr`
- Lore Architect: `$49/mo` or `$490/yr`

Public pricing catalog shape:

- 3 visible tiers
- 2 paid subscriptions
- collaboration-only access remains a backend-supported entitlement, but it is not sold as a public pricing card

Primary code references:

- Pricing catalog: [frontend/src/lib/billing/catalog.ts](/C:/Users/madha/.vscode/prod/LoreVia2/frontend/src/lib/billing/catalog.ts)
- Pricing UI: [frontend/src/components/billing/PricingPlans.tsx](/C:/Users/madha/.vscode/prod/LoreVia2/frontend/src/components/billing/PricingPlans.tsx)
- Trial + tier rules: [backend/app/utils/billing_utils.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/utils/billing_utils.py:18)
- Limits config: [backend/app/core/config.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/core/config.py:150)

## Revenue After Paddle Fees

Assumption used here:

- Paddle pay-as-you-go fee: `5% + $0.50` per checkout transaction
- Source: [Paddle pricing](https://www.paddle.com/pricing)

Net revenue per successful subscription sale before infrastructure and model costs:

| Plan | List price | Est. Paddle fee | Net revenue |
| --- | ---: | ---: | ---: |
| Author monthly | $29.00 | $1.95 | $27.05 |
| Architect monthly | $49.00 | $2.95 | $46.05 |
| Author annual | $290.00 | $15.00 | $275.00 |
| Architect annual | $490.00 | $25.00 | $465.00 |

## Model Cost Assumptions

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

## Launch Guidance

- Keep upgrade as the primary path when users hit free-tier limits.
- Keep launch billing surfaces aligned to Paddle checkout, portal, and subscription state.
- Treat any old non-subscription monetization planning notes as historical only, not current product scope.
