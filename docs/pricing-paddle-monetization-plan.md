# LoreVia Pricing, Paddle, And Monetization Plan

Last updated: 2026-05-14

## Purpose

This document is the pricing and monetization source of truth for LoreVia launch work. It exists to keep product copy, backend enforcement, Paddle catalog setup, settings display, trial behavior, and future points/ad work aligned.

This document is intentionally conservative. The launch goal is not maximum feature breadth. The launch goal is a pricing system that is:

- understandable
- hard to exploit
- economically safe
- easy to explain to users
- easy to enforce in code

## Core Philosophy

- Zero exploitation: collaboration access exists only to support author workflows such as beta reading, review, and manuscript feedback. No author tools may leak into that access mode through UI, API, points, ads, mode switching, or edge cases.
- Controlled unlimited: Author and Lore Architect may be marketed as unlimited, but backend fair-use caps must still exist.
- Refresh economy: high-cost AI usage resets daily at `00:00 UTC`.
- Infrastructure minded: pricing must cover the $30/month fixed base plus variable model cost.
- Natural conversion: when users hit limits, the primary path is upgrade. Points are a small relief valve, not a substitute for upgrading.
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

### Trial Fair-Use Rule

Trial users are not full paid Author users operationally. They are capped at a lighter daily allowance to prevent scraping and mass abuse while still letting them feel the product.

Launch rule:

- trial users get Author feature access
- trial users are capped at `20` high-cost turns/day across the protected authoring AI surfaces that need fair-use protection

In marketing and settings copy, we should keep the experience simple and say they are on a free Author trial. In backend enforcement, we should treat the trial cap as a stricter fair-use overlay.

## Trial Email Sequence

Approved MVP sequence for the next implementation pass:

| Day | Email |
| :-- | :---- |
| Day 0 | Trial started + what Author trial unlocks |
| Day 3 | Have you tried this yet? Product nudge based on usage |
| Day 9 | Your trial ends tomorrow + what stays vs what locks |
| Day 10 | Your trial has ended + upgrade CTA |

Implementation notes:

- use Resend for delivery
- automation is now part of the approved implementation scope
- keep the MVP to 4 emails, not 5
- if the user has not verified their email by a send window, skip non-transactional trial emails until they verify

## Launch Tiers

### Free

Price: `$0`

Who it is for:

- casual readers
- curious authors exploring after trial

Primary conversion trigger:

- 2-book cap

Feature policy:

| Feature | Limit |
| :------ | :---- |
| Active books | 2 |
| Public demo books | Yes |
| Invited beta reads | Yes |
| Smart Tap | Unlimited |
| Character profiles | Full access |
| Chapter summaries | Short mode only |
| Memory recall | Unlimited |
| Relationship graph | Yes |
| Plot tracker | Yes |
| Semantic search | 5 queries/day |
| Continuity checker | Locked |
| Story Advisor | Locked |
| Prediction engine | 3 queries/day |
| Character bible export | Locked |
| Manuscript editor | Locked |
| Points earning | Allowed later |

### Collaboration Access

Price: `Not sold as a standalone public plan`

Who it is for:

- invited beta readers
- critique partners
- editors and feedback collaborators supporting an author workflow

Feature policy:

| Feature | Limit |
| :------ | :---- |
| Access path | Author invite only |
| Book scope | Invite-scoped |
| Smart Tap | Unlimited |
| Character profiles | Full access |
| Chapter summaries | Allowed only within the shared scope |
| Memory recall | Unlimited |
| Relationship graph | Yes |
| Plot tracker | Yes |
| Semantic search | Allowed only within the shared scope |
| Story Advisor | Locked |
| Continuity checker | Locked |
| Manuscript editor | Locked |
| Character bible export | Locked |

Collaboration access remains important internally, but it should be framed as an author collaboration feature rather than a standalone product tier.

Important boundary:

- Free users can accept invited beta-read access and use curated public demos
- Free users do not inherit the old Reader tier as a broad reading subscription
- authoring upgrades should still be the path to deeper continuity and manuscript workflows

### Author

Price: `$29/month` or `$290/year`

Who it is for:

- active fiction authors
- long-form and serial writers
- users who need continuity tools as part of normal drafting

Feature policy:

| Feature | Limit |
| :------ | :---- |
| Active books | Unlimited |
| Smart Tap | Unlimited |
| Character profiles | Full + edit mode |
| Chapter summaries | All 3 modes |
| Memory recall | Unlimited |
| Relationship graph | Yes + export |
| Plot tracker | Yes + notes |
| Semantic search | Unlimited |
| Continuity checker | Unlimited marketed, `30/day` fair-use cap |
| Character bible export | Unlimited |
| Story Advisor | Unlimited marketed, `30/day` fair-use cap |
| Prediction engine | Unlimited |
| Manuscript editor | Chapter mode + full book mode |
| Insertion suggestions | Yes |
| Points earning | Allowed later |

### Lore Architect

Price: `$49/month` or `$490/year`

Who it is for:

- professional authors
- authors with very large back catalogs
- users with 500+ chapter style workloads
- users monetising their writing seriously

Feature policy for launch:

| Feature | Limit |
| :------ | :---- |
| Active books | Unlimited |
| Smart Tap | Unlimited |
| Character profiles | Full + edit + history when implemented |
| Chapter summaries | All 3 modes |
| Memory recall | Unlimited |
| Relationship graph | Yes + export + timeline when implemented |
| Plot tracker | Yes + notes + arc planning when implemented |
| Semantic search | Unlimited |
| Continuity checker | Unlimited marketed, `60/day` fair-use cap |
| Character bible export | Unlimited |
| Story Advisor | Unlimited marketed, `60/day` fair-use cap |
| Prediction engine | Unlimited |
| Manuscript editor | Chapter mode + full book mode |
| Insertion suggestions | Yes + more targeted placement later |
| Priority processing | Planned launch-facing value, backend queue priority still to be implemented |
| Early access | Allowed as a product policy |
| Points earning | Allowed later |

Important launch boundary:

- do not ship public-facing character pages yet
- do not market public character pages as available now
- do not market custom summary prompts, bulk scan, or custom bible templates as live if they are not fully implemented

## Note On Unlimited

"Unlimited" is a marketing label, not a literal removal of all safeguards.

Backend rule:

- all high-cost AI features must still be bounded by fair-use counters
- those counters refresh daily at `00:00 UTC`

User-facing limit message:

```text
Your daily limit refreshes tomorrow. Want higher limits now? Upgrade.
```

Marketing rule:

- do not show the backend cap number on the pricing card
- the cap exists to protect unit economics, not to become the headline

## Annual Billing

The pricing page should default to annual billing. Users can toggle to monthly.

| Tier | Monthly | Annual | Savings |
| :--- | :------ | :----- | :------ |
| Author | $29 | $290 | $58 |
| Lore Architect | $49 | $490 | $98 |

Reason:

- annual anchors value
- improves conversion
- reduces churn

## Early Adopter Launch Offer

For the first month after pricing launches:

- all existing users receive a 15-day Author trial extension
- first paid subscription gets 20% off the first 3 months
- anyone upgrading to Lore Architect in month 1 locks `$49` pricing for life while continuously subscribed

Important implementation note:

- this can be expressed through Paddle discounting and metadata
- price-lock logic must not silently grant Architect features without an active Architect subscription

## Paddle Catalog

The app expects these recurring Paddle prices:

```env
PADDLE_AUTHOR_MONTHLY_PRICE_ID=pri_...
PADDLE_AUTHOR_ANNUAL_PRICE_ID=pri_...
PADDLE_ARCHITECT_MONTHLY_PRICE_ID=pri_...
PADDLE_ARCHITECT_ANNUAL_PRICE_ID=pri_...
PADDLE_API_KEY=...
PADDLE_WEBHOOK_SECRET=...
PADDLE_DEFAULT_CHECKOUT_URL=https://getlorevia.com/pricing
```

Recommended catalog structure:

- one Paddle product per sellable tier, each with monthly and annual prices
- the live catalog currently sells Author and Lore Architect, with Free available without checkout
- keep the legacy `pro` and `power` aliases in code only while rollout is in progress

The code should continue to normalize legacy codes during rollout, but all new checkout UI should use:

- `author_monthly`
- `author_annual`
- `architect_monthly`
- `architect_annual`

## Webhook Rules

Listen to:

- `transaction.completed`
- `subscription.created`
- `subscription.updated`
- `subscription.canceled`
- `subscription.past_due`
- `subscription.paused`

Rules:

- verify signature against the raw request body before parsing business state
- keep idempotency for event replay safety
- update the latest subscription row
- set `users.tier` from the Paddle plan code on active events
- revert `users.tier` to `free` on cancellation, pause, or past-due loss of service

We should stay conservative here. If payment status is uncertain, do not leave high-cost access open.

## Settings And Plan Display

The settings page should show the user's effective access tier, not just their purchased tier.

Examples:

- new user in trial: `Author (free trial)`
- invited beta reader or collaborator: `Collaboration access`
- expired non-paying user: `Free`

The app should also preserve the purchased plan internally so trial state and paid state do not overwrite one another.

## Anti-Exploit Rules For Points

Points are intentionally small, not gamechanging.

Points must never:

- unlock Story Advisor for Free or collaboration-only access
- unlock continuity checker for Free or collaboration-only access
- unlock manuscript editor for Free or collaboration-only access
- unlock character bible export for Free or collaboration-only access
- unlock any Architect-only benefit for Author
- unlock queue priority
- unlock bulk scan
- unlock future custom templates
- unlock future public features
- be purchasable with money
- be transferable between users
- stack into a shadow subscription

Points may only do minor overflow inside the user's existing entitlement class.

Safe examples:

- Free can buy a tiny number of extra searches or predictions
- Free can rent one temporary extra book slot for 30 days
- Author can buy one or two extra same-tier turns after hitting the daily fair-use cap
- Architect can buy a small same-tier overflow for convenience

Unsafe examples:

- collaboration-only access spending points to access Story Advisor
- Author spending points to access Architect queue priority
- Free hoarding points to simulate Author
- any bundle that effectively turns points into a second subscription economy

Launch policy:

- points are supplemental only
- points should feel helpful, not transformational
- if a points rule starts weakening upgrade pressure, the rule is wrong

## Anti-Exploit Rules For Ads

Ads are opt-in only. They must not become an alternate pricing lane.

Ads must:

- never appear automatically
- never appear while reading
- never appear while the manuscript editor is open
- only appear in settings, points wallet, or post-limit "earn more" flows
- remain capped at 5/day server-side

Ads must never:

- directly unlock a higher tier
- directly unlock an author feature for collaboration-only access
- grant Architect-level capabilities to Author
- let a user loop ads into practical unlimited access

Ad reward philosophy:

- small, occasional relief
- never enough to undermine tier pricing

## Recommended Points Scope For Launch

Approved scope for the next implementation pass:

Suggested earn rules:

- watch one ad: 10 points
- daily login bonus:
  - Free: 5
  - collaboration-only access: 10
  - Author: 15
- monthly Architect grant: 500
- first processed book one-time reward: 25

Suggested spend rules:

- +5 semantic searches: 3 points
- +1 prediction query: 6 points
- +1 extra active book slot for Free for 30 days: 150 points
- +1 Author same-tier Story Advisor overflow turn: 10 points
- +1 Author same-tier continuity overflow turn: 10 points

Explicit launch exclusions:

- no collaboration-only or Free unlock path into authoring
- no point-spend path into Architect-only value
- no character bible export unlock for Free or collaboration-only access
- no public feature unlocks
- no complex referral economy at launch

Referral rule for the next pass:

- keep referral rewards simple and points-based
- do not build a multi-level or cash-like referral system
- qualify the referral only after the invited user completes a meaningful anti-abuse event such as email verification plus first processed book or first paid conversion

## Launch Decision On Public Features

Public features should be enabled, but their roles need to stay separate.

Launch rule:

- keep a curated public demo library for public-domain books and safe showcase projects
- keep public sharing available without turning it into a pricing-tier differentiator
- do not bundle public access claims into paid-plan positioning unless the workflow is actually polished and trustworthy

Pricing pages, docs, and in-app billing comparisons should treat public demos as trust-building product exposure, not as the core monetization story.

## Revenue And Cost Assumptions

Fixed monthly infrastructure:

- `$30`

Estimated monthly model cost:

| Tier | Estimated monthly cost |
| :--- | :--------------------- |
| Free | ~$10 per 1,000 users |
| Collaboration-only access | ~$25 per user |
| Author | ~$45 per user |
| Lore Architect | ~$80 per user |

Scenario model at 1,000 users:

| Scenario | Free | Collaboration-only | Author | Lore Architect | MRR | Est. OpenAI | Net Profit |
| :------- | :--- | :----- | :----- | :------------- | :-- | :---------- | :--------- |
| Conservative | 970 | 15 | 10 | 5 | $390 | ~$150 | ~$210 |
| Realistic | 930 | 35 | 25 | 10 | $1,110 | ~$280 | ~$800 |
| Good | 880 | 55 | 50 | 15 | $1,924 | ~$420 | ~$1,474 |

These numbers exist to keep enforcement honest. If a monetization mechanic weakens tier separation, it is not just a product problem, it is a unit economics problem.

## Technical Guardrails

### Already In Motion

- canonical tiers exist in code: `free`, `reader`, `author`, `architect`
- annual-first pricing is enabled
- settings shows effective trial status
- collaboration-only author-feature lockdown exists in UI and backend author-mode guards
- Paddle plan mapping exists for internal collaboration access plus Author and Architect

### Required Guardrails

1. Collaboration access lockdown
   `AuthorFeatureComponent` must return `null` or locked state for `tier === 'reader'`.

2. Daily high-cost counters
   High-cost AI usage must be tracked server-side and reset at `00:00 UTC`.

3. Trial cap overlay
   Trial Author users must remain under a reduced daily cap.

4. Rate-limit messaging
   Use:
   `Your daily limit refreshes tomorrow. Want higher limits now? Upgrade.`

5. Ad cap enforcement
   Max 5 ads/day server-side.

6. Points expiry
   Weekly cleanup for expired points once the ledger exists.

7. No pricing bypass through mode switching
   Collaboration-only users must not convert uploads into author workspaces.

8. No pricing bypass through export routes
   Author-only and Architect-only exports must stay server-enforced.

9. No pricing bypass through public feature flags
   Deferred public features must not be half-open through hidden URLs or stale API routes.

10. Paddle remains the source of paid truth
   Do not create alternative "paid" states outside subscription and verified launch promotions.

## Current Implementation Status

Implemented in the current pricing pass:

- new canonical tier model
- trial-aware effective access
- local Architect access in debug
- internal collaboration access plus Author and Architect Paddle plan codes
- annual-first pricing page
- settings display of effective tier plus purchased plan
- collaboration-only lockdown of author workflows in UI and backend
- Paddle webhook tier mapping and conservative downgrade behavior
- pricing strategy doc
- points ledger schema, service, and read APIs
- referral code capture and referral rewards after verified first-book processing
- trial email event scheduling and protected internal cron delivery endpoint
- lazy point expiry on points reads
- Architect/Admin priority queue dispatch for extraction and analysis tasks

Not implemented yet:

- ad watch ledger
- Architect-only advanced prompt/template surfaces
- public feature rollout
- point spending against same-tier overflow limits
- frontend points/referral display surfaces

## Approved Next Phase

The approved backend MVP phase has been implemented for:

- points ledger
- referral rewards
- trial email automation with at least 4 Resend emails across the 10-day trial
- Architect queue priority backend enforcement

Explicitly not in scope for this phase:

- public feature rollout
- ad watch ledger

## Final Launch Guidance

If there is ever a choice between generosity and tier integrity, choose tier integrity.

The pricing system only works if:

- Author feels clearly necessary for writers
- Architect feels clearly better for heavy professional use
- points and ads feel like small relief, not a loophole
- public features are not prematurely used as fake differentiation

The cleanest launch is:

- strong collaboration-only isolation
- strong authoring upsell
- strict same-tier-only points relief later
- no public rollout yet
- conservative backend enforcement everywhere that costs real money

