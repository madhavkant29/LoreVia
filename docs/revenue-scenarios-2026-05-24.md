# LoreVia Revenue, Cost, and Profit/Loss Scenarios

> **Superseded pricing notice (2026-07-24):** This dated scenario model preserves the former $29/month Author and $49/month Architect assumptions for historical context. Current pricing is $19/month or $190/year for Author and $39/month or $390/year for Architect.

Last updated: 2026-05-24

## Purpose

This document is a planning model for LoreVia's monthly unit economics at:

- 10 total users
- 100 total users
- 1,000 total users
- 10,000 total users

It is meant to answer a practical question:

- if LoreVia keeps the current pricing and current stack, what does monthly profit or loss roughly look like at each scale?

This is not accounting-grade reporting. It is a founder planning model with explicit assumptions.

## Current Revenue Model In Repo

Canonical public pricing in code:

- Free: `$0`
- Author: `$29/mo`
- Architect: `$49/mo`

Net revenue after Paddle per monthly paid subscriber:

- Author monthly net: `$27.05`
- Architect monthly net: `$46.05`

Source references:

- Pricing catalog: [frontend/src/lib/billing/pricing-catalog.json](/C:/Users/madha/.vscode/prod/LoreVia2/frontend/src/lib/billing/pricing-catalog.json)
- Existing cost analysis: [pricing-cost-analysis-2026-05-09.md](/C:/Users/madha/.vscode/prod/LoreVia2/docs/pricing-cost-analysis-2026-05-09.md)
- Paddle pricing: [Paddle pricing](https://www.paddle.com/pricing)

## Vendor Pricing Snapshot

These are the external pricing inputs used in this model as of 2026-05-24:

| Service | Pricing assumption used here | Source |
| --- | ---: | --- |
| Hetzner CCX13 | `$19.99/mo` in US pricing after the 2026-04-01 adjustment | [Hetzner price adjustment](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/) |
| Hetzner CCX23 | `$33.99/mo` in US pricing after the 2026-04-01 adjustment | [Hetzner price adjustment](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/) |
| Hetzner CCX33 | `$76.99/mo` in US pricing after the 2026-04-01 adjustment | [Hetzner price adjustment](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/) |
| Supabase Pro | `$25/mo` | [Supabase pricing](https://supabase.com/pricing) |
| Vercel Pro | `$20/mo` platform fee with `$20` monthly credit | [Vercel Pro plan](https://vercel.com/docs/plans/pro-plan) |
| ChatGPT Pro / Codex access | `$100/mo` | [OpenAI Help Center](https://help.openai.com/en/articles/9793128-about-chatgpt-pro-plans) |
| Cloudflare R2 | `10 GB` free, then `$0.015/GB-month`, no egress fees, plus request pricing | [Cloudflare R2 pricing](https://developers.cloudflare.com/r2/pricing/) |
| Resend Free | `$0`, `3,000 emails/mo` | [Resend pricing](https://resend.com/pricing) |
| Resend Pro | `$20/mo`, `50,000 emails/mo` | [Resend pricing](https://resend.com/pricing) |
| Resend Scale | `$90/mo`, `100,000 emails/mo` | [Resend pricing](https://resend.com/pricing) |
| PostHog product analytics | first `1M` events free, then `$0.0000500/event` for the next band | [PostHog pricing](https://posthog.com/pricing) |
| Sentry Developer | `$0/mo` | [Sentry pricing](https://sentry.io/pricing/) |
| Sentry Team | `$26/mo` | [Sentry pricing](https://sentry.io/pricing/) |
| Sentry Business | `$80/mo` | [Sentry pricing](https://sentry.io/pricing/) |
| OpenAI `gpt-4o-mini` | `$0.15 / 1M` input, `$0.60 / 1M` output | [OpenAI model pricing](https://developers.openai.com/api/docs/models/gpt-4o-mini) |
| OpenAI `text-embedding-3-small` | `$0.02 / 1M` tokens | [OpenAI model pricing](https://developers.openai.com/api/docs/models/text-embedding-3-small) |

Important correction:

- Supabase Pro is not `$20/mo` on the pricing page I checked on 2026-05-24. It is `$25/mo`.
- Hetzner CCX23 is also closer to `$33.99/mo` in the current US pricing snapshot than a flat `$35/mo`.

## Base-Case Assumptions

To keep this model usable, I picked one clear base case.

### User mix

For every 100 total users, assume:

- `85` Free users
- `10` Author users
- `5` Architect users

That means average net revenue per total registered user is:

- `0.10 * 27.05 + 0.05 * 46.05 = $5.01/user/month`

### AI cost reserve

Raw OpenAI token pricing is quite low for the current model mix, but real production usage includes retries, repeated context windows, ingestion passes, summaries, embeddings, and background jobs.

So this model uses a padded monthly AI reserve per user:

- Free user: `$0.20/mo`
- Author user: `$1.50/mo`
- Architect user: `$4.00/mo`

Weighted average AI cost across all users in this model:

- `0.85 * 0.20 + 0.10 * 1.50 + 0.05 * 4.00 = $0.52/user/month`

### Infra progression

This model assumes:

- 10 users: current single Hetzner `CCX13`
- 100 users: still single `CCX13`
- 1,000 users: move to single `CCX23`
- 10,000 users: run `2 x CCX23` to separate app and worker pressure instead of betting everything on one box

Alternative:

- a single `CCX33` is also a valid 10k-user planning option, but I did not use it for the main scenario because a two-VPS layout is operationally safer for worker-heavy AI workloads.

### Other variable assumptions

- Resend email volume: `4 emails/user/month` on average
- PostHog product analytics: `150 events/user/month`
- Cloudflare R2 storage footprint: `0.15 GB/user` average stored content
- Sentry stays on Developer while very small, then moves to Team at 10k users for a more realistic operational setup
- Supabase is modeled at the base Pro subscription only, without extra compute/storage overages
- Vercel is modeled at the base Pro fee only, assuming usage stays inside the included credit envelope

## Monthly Scenario Table

All values below are monthly.

| Total users | Expected paid mix | Net revenue after Paddle | AI cost reserve | Hetzner | Supabase | Vercel | Codex | Resend | PostHog | Sentry | R2 | Total monthly cost | Profit / loss |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 10 | `1` Author, `0.5` Architect | `$50.08` | `$5.20` | `$19.99` | `$25.00` | `$20.00` | `$100.00` | `$0.00` | `$0.00` | `$0.00` | `$0.00` | `$170.19` | `-$120.12` |
| 100 | `10` Author, `5` Architect | `$500.75` | `$52.00` | `$19.99` | `$25.00` | `$20.00` | `$100.00` | `$0.00` | `$0.00` | `$0.00` | `$0.08` | `$217.07` | `$283.69` |
| 1,000 | `100` Author, `50` Architect | `$5,007.50` | `$520.00` | `$33.99` | `$25.00` | `$20.00` | `$100.00` | `$20.00` | `$0.00` | `$0.00` | `$2.10` | `$721.09` | `$4,286.41` |
| 10,000 | `1,000` Author, `500` Architect | `$50,075.00` | `$5,200.00` | `$67.98` | `$25.00` | `$20.00` | `$100.00` | `$20.00` | `$25.00` | `$26.00` | `$22.35` | `$5,506.33` | `$44,568.67` |

## What These Numbers Mean

### At 10 users

- LoreVia is still meaningfully loss-making.
- The biggest issue is fixed tooling and platform overhead, especially the `Codex $100` line and the always-on core stack.
- At this stage, founder time is the real investment and MRR will not yet cover stack cost.

### At 100 users

- The business becomes modestly profitable in this base case.
- The stack is still mostly fixed-cost dominated.
- AI cost is visible, but still not the main problem.

### At 1,000 users

- LoreVia becomes strongly profitable if conversion and churn are healthy.
- AI spend matters, but fixed infra remains surprisingly small relative to revenue.
- Resend starts to matter a little, but still not much.

### At 10,000 users

- LoreVia is very profitable in this model.
- AI cost becomes a real budget line.
- You will likely need more operational maturity than this table shows:
  - stronger worker isolation
  - more Supabase headroom
  - better observability
  - maybe higher Vercel or Sentry usage costs

## Break-Even Estimate

Using the same base-case assumptions:

- average net revenue per total user: about `$5.01/mo`
- average AI variable cost per total user: about `$0.52/mo`
- contribution margin per total user: about `$4.49/mo`

With the small-stack fixed-cost baseline:

- Hetzner CCX13: `$19.99`
- Supabase Pro: `$25.00`
- Vercel Pro: `$20.00`
- Codex: `$100.00`

Base fixed monthly stack:

- `$164.99/mo`

Approximate break-even point:

- `$164.99 / $4.49 ~= 37 total users`

That is a useful rule of thumb:

- if LoreVia can hold roughly this conversion mix and usage profile, the business can cover its direct monthly software stack surprisingly early

## Sensitivity Notes

This model is directionally useful, but a few variables can move the outcome a lot:

### If conversion is weaker

If fewer total users convert into Author or Architect, revenue drops much faster than cost.

The biggest revenue sensitivities are:

- free-to-paid conversion
- Architect share
- churn
- annual-vs-monthly mix

### If AI usage is heavier

This model intentionally uses an AI reserve larger than the raw token floor, but it still may be low if users:

- upload many long manuscripts every month
- repeatedly re-run extraction
- heavily use advisor, continuity, and recall flows
- create long-running multi-book sessions

### If infra becomes more production-heavy

At 10,000 users, real-world cost could be materially above the table if you add:

- larger Supabase compute or storage
- a dedicated Postgres or Redis strategy outside the current plan
- more than one Vercel seat
- more aggressive Sentry usage
- more than two Hetzner boxes
- CI/CD, backups, staging, and other non-production-but-real founder costs

## Practical Takeaways

- LoreVia's current pricing is high enough to support the current stack if you can get to a healthy paid mix.
- Hetzner is not the thing that breaks the model. AI usage and conversion quality matter more.
- Cloudflare R2 is cheap enough that it is unlikely to be a top-three cost driver for a long time.
- Paddle's cut matters, but it still leaves strong room for margin at the current subscription prices.
- Supabase, Vercel, and Codex are the main fixed-cost lines early on.
- If you want a more conservative planning model, lower paid conversion and double the AI reserve before making runway decisions.

## Suggested Next Step

The next useful version of this doc would be a second table with:

- pessimistic case
- base case
- optimistic case

That would make it much easier to reason about runway and break-even without relying on a single conversion assumption.


| Model basis        | Values used                                                                                         |
| ------------------ | --------------------------------------------------------------------------------------------------- |
| Source assumptions | Author net `$27.05`, Architect net `$46.05`, base AI reserve from uploaded LoreVia economics model  |
| User levels        | `10`, `100`, `1,000`, `10,000`, `100,000`, `1,000,000`                                              |
| Output             | Monthly numbers only                                                                                |
| ChatGPT lean case  | `$50/mo`, representing the `$40–60/mo` subscription path                                            |

### Case 1 — Pessimistic

|     Users | Paid mix                |     Net revenue | Total monthly cost |   Profit / loss |
| --------: | ----------------------- | --------------: | -----------------: | --------------: |
|        10 | 4% Author, 1% Architect |        `$15.43` |          `$167.89` |      `-$152.47` |
|       100 | 4% Author, 1% Architect |       `$154.25` |          `$194.07` |       `-$39.82` |
|     1,000 | 4% Author, 1% Architect |     `$1,542.50` |          `$491.09` |     `$1,051.41` |
|    10,000 | 4% Author, 1% Architect |    `$15,425.00` |        `$3,206.33` |    `$12,218.67` |
|   100,000 | 4% Author, 1% Architect |   `$154,250.00` |       `$31,564.85` |   `$122,685.15` |
| 1,000,000 | 4% Author, 1% Architect | `$1,542,500.00` |      `$314,899.85` | `$1,227,600.15` |

### Case 2 — Base Case

|     Users | Paid mix                 |     Net revenue | Total monthly cost |   Profit / loss |
| --------: | ------------------------ | --------------: | -----------------: | --------------: |
|        10 | 10% Author, 5% Architect |        `$50.08` |          `$170.19` |      `-$120.12` |
|       100 | 10% Author, 5% Architect |       `$500.75` |          `$217.07` |       `$283.69` |
|     1,000 | 10% Author, 5% Architect |     `$5,007.50` |          `$721.09` |     `$4,286.41` |
|    10,000 | 10% Author, 5% Architect |    `$50,075.00` |        `$5,506.33` |    `$44,568.67` |
|   100,000 | 10% Author, 5% Architect |   `$500,750.00` |       `$54,564.85` |   `$446,185.15` |
| 1,000,000 | 10% Author, 5% Architect | `$5,007,500.00` |      `$544,899.85` | `$4,462,600.15` |

### Case 3 — Base Case With `$40–60` ChatGPT Spend

|     Users | Paid mix                 | ChatGPT/Codex spend |     Net revenue | Total monthly cost |   Profit / loss |
| --------: | ------------------------ | ------------------: | --------------: | -----------------: | --------------: |
|        10 | 10% Author, 5% Architect |               `$50` |        `$50.08` |          `$120.19` |       `-$70.12` |
|       100 | 10% Author, 5% Architect |               `$50` |       `$500.75` |          `$167.07` |       `$333.69` |
|     1,000 | 10% Author, 5% Architect |               `$50` |     `$5,007.50` |          `$671.09` |     `$4,336.41` |
|    10,000 | 10% Author, 5% Architect |               `$50` |    `$50,075.00` |        `$5,456.33` |    `$44,618.67` |
|   100,000 | 10% Author, 5% Architect |               `$50` |   `$500,750.00` |       `$54,514.85` |   `$446,235.15` |
| 1,000,000 | 10% Author, 5% Architect |               `$50` | `$5,007,500.00` |      `$544,849.85` | `$4,462,650.15` |

### Case 4 — Optimistic

|     Users | Paid mix                 |     Net revenue | Total monthly cost |   Profit / loss |
| --------: | ------------------------ | --------------: | -----------------: | --------------: |
|        10 | 15% Author, 8% Architect |        `$77.42` |          `$171.98` |       `-$94.57` |
|       100 | 15% Author, 8% Architect |       `$774.15` |          `$234.97` |       `$539.19` |
|     1,000 | 15% Author, 8% Architect |     `$7,741.50` |          `$900.09` |     `$6,841.41` |
|    10,000 | 15% Author, 8% Architect |    `$77,415.00` |        `$7,296.33` |    `$70,118.67` |
|   100,000 | 15% Author, 8% Architect |   `$774,150.00` |       `$72,464.85` |   `$701,685.15` |
| 1,000,000 | 15% Author, 8% Architect | `$7,741,500.00` |      `$723,899.85` | `$7,017,600.15` |

### Case 5 — Strong Upside

|     Users | Paid mix                  |      Net revenue | Total monthly cost |   Profit / loss |
| --------: | ------------------------- | ---------------: | -----------------: | --------------: |
|        10 | 20% Author, 10% Architect |        `$100.15` |          `$173.39` |       `-$73.24` |
|       100 | 20% Author, 10% Architect |      `$1,001.50` |          `$249.07` |       `$752.44` |
|     1,000 | 20% Author, 10% Architect |     `$10,015.00` |        `$1,041.09` |     `$8,973.91` |
|    10,000 | 20% Author, 10% Architect |    `$100,150.00` |        `$8,706.33` |    `$91,443.67` |
|   100,000 | 20% Author, 10% Architect |  `$1,001,500.00` |       `$86,564.85` |   `$914,935.15` |
| 1,000,000 | 20% Author, 10% Architect | `$10,015,000.00` |      `$864,899.85` | `$9,150,100.15` |
