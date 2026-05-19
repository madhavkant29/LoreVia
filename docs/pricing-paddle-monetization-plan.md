# LoreVia Pricing, Paddle, and Monetization Plan

Last updated: 2026-05-19

## Purpose

This document is the current pricing and billing source of truth for LoreVia launch work.

It exists to keep product copy, backend enforcement, Paddle catalog setup, settings display, trial behavior, and subscription messaging aligned.

LoreVia is currently subscription-first. Legacy wallet and ad-based experiments are not part of the active launch monetization model.

## Core Philosophy

- Zero exploitation: collaboration access exists only to support author workflows such as beta reading, review, and manuscript feedback.
- Controlled unlimited: Author and Lore Architect may be marketed as unlimited, but backend fair-use caps must still exist.
- Refresh economy: high-cost AI usage resets daily at `00:00 UTC`.
- Infrastructure minded: pricing must cover fixed infrastructure plus variable model cost.
- Natural conversion: when users hit limits, the primary path is upgrade.
- No hidden features: users should understand what their tier includes and what it does not include.

## Canonical Tier Names

All new product, backend, and frontend code should use these canonical tier names:

- `free`
- `reader` internally for collaboration-only access
- `author`
- `architect`
- `admin`

Legacy compatibility mappings remain in code only:

- `pro` maps to `author`
- `power` maps to `architect`
- `pro_monthly` and `pro_annual` map to internal collaboration access codes
- `power_monthly` and `power_annual` map to Author checkout codes

Do not use legacy names in product copy.

## Trial Model

Every new user gets 10 days of Author-tier access from signup with no credit card required.

Important implementation detail:

- The purchased or permanent plan stays in `users.tier`.
- Trial access is computed from `users.created_at`.
- Trial access should not overwrite the purchased plan.

Frontend display during trial:

```text
Author (free trial)
```

When the trial ends:

- if the user never upgraded, effective access becomes `free`
- if the user has collaboration-only access, effective access becomes `reader`
- if the user bought Author, effective access becomes `author`
- if the user bought Architect, effective access becomes `architect`

## Launch Tiers

### Free

Price: `$0`

Primary conversion trigger:

- 2-book cap

### Collaboration Access

Price: `Not sold as a standalone public plan`

Collaboration access remains important internally, but it should be framed as an author collaboration feature rather than a standalone product tier.

### Author

Price: `$29/month` or `$290/year`

### Lore Architect

Price: `$49/month` or `$490/year`

## Launch Scope

Active monetization scope:

- Paddle checkout for paid plans
- Paddle customer portal
- subscription webhooks
- trial enforcement
- subscription-aware feature gating
- fair-use caps for high-cost AI workflows
- priority processing support for higher tiers

Out of scope for the active launch model:

- alternate wallet or credit economies
- ad-based unlock mechanics
- non-subscription monetization experiments

## Implementation References

- Billing routes: [backend/app/api/v1/routes/billing.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/api/v1/routes/billing.py)
- Billing logic: [backend/app/utils/billing_utils.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/utils/billing_utils.py)
- Pricing catalog: [frontend/src/lib/billing/catalog.ts](/C:/Users/madha/.vscode/prod/LoreVia2/frontend/src/lib/billing/catalog.ts)
- Pricing UI: [frontend/src/components/billing/PricingPlans.tsx](/C:/Users/madha/.vscode/prod/LoreVia2/frontend/src/components/billing/PricingPlans.tsx)
