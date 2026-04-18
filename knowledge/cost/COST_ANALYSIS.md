# LoreVia Cost Analysis

Updated: 2026-04-15

This replaces the old corrupted file and recalculates costs from the current codebase:

- Pricing tiers from [frontend/src/app/(dashboard)/pricing/page.tsx](/C:/Users/madha/.vscode/prod/LoreVia2/frontend/src/app/(dashboard)/pricing/page.tsx)
- Model configuration and free-tier limits from [backend/app/core/config.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/core/config.py)
- Current analysis pipeline from:
  - [backend/app/engine/character/extractor.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/engine/character/extractor.py)
  - [backend/app/engine/analysis/summariser.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/engine/analysis/summariser.py)
  - [backend/app/engine/analysis/plot_tracker.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/engine/analysis/plot_tracker.py)
  - [backend/app/engine/analysis/recall.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/engine/analysis/recall.py)
  - [backend/app/api/v1/routes/intelligence.py](/C:/Users/madha/.vscode/prod/LoreVia2/backend/app/api/v1/routes/intelligence.py)

## 1. Current product pricing

LoreVia no longer uses the old tier assumptions in the older planning docs.

Current live app pricing:

| Plan | Monthly | Annual | Effective monthly on annual |
|---|---:|---:|---:|
| Starter | $0 | $0 | $0.00 |
| Pro | $9 | $90 | $7.50 |
| Power | $17 | $170 | $14.17 |

Current plan positioning:

- `Starter`: core reading workspace
- `Pro`: more summaries, search, grounded Q&A, longer-book continuity
- `Power`: highest interaction capacity and best fit for dense or long reading arcs

## 2. Current AI stack

Current configured primary models:

- Extraction and summaries: `gpt-4o-mini`
- Intelligence / Q&A / chat: `gpt-4o-mini`
- Embeddings: `text-embedding-3-small`
- Gemini is present only as fallback in config, not the primary cost baseline

From the current code:

- chapter summaries are generated in all 3 modes: `short`, `detailed`, `key_points`
- plot-thread extraction is also run during analysis
- embeddings are generated for chunks and character records
- recall and grounded Q&A are additional runtime costs after processing

## 3. External pricing inputs used

These prices can change, so treat this as a snapshot as of 2026-04-15.

AI pricing sources:

- OpenAI pricing page: [openai.com/api/pricing](https://openai.com/api/pricing)
- OpenAI model docs showing `gpt-4o-mini` at `$0.15 / 1M` input and `$0.60 / 1M` output: [platform.openai.com/docs/models/gpt-4](https://platform.openai.com/docs/models/gpt-4)
- OpenAI embeddings docs for `text-embedding-3-small`: [platform.openai.com/docs/guides/embeddings](https://platform.openai.com/docs/guides/embeddings/embedding-models%20.class)

Infra pricing sources:

- Railway plans: [docs.railway.com/pricing/plans](https://docs.railway.com/pricing/plans)
- Supabase billing docs: [supabase.com/docs/guides/platform/your-monthly-invoice](https://supabase.com/docs/guides/platform/your-monthly-invoice)
- Cloudflare R2 pricing: [developers.cloudflare.com/r2/pricing](https://developers.cloudflare.com/r2/pricing/)
- Vercel plans: [vercel.com/docs/plans](https://vercel.com/docs/plans)
- Gemini pricing reference, if fallback becomes active: [ai.google.dev/gemini-api/docs/pricing](https://ai.google.dev/gemini-api/docs/pricing?authuser=5)

Pricing snapshot used in this document:

| Service | Price used |
|---|---:|
| `gpt-4o-mini` input | $0.15 / 1M tokens |
| `gpt-4o-mini` output | $0.60 / 1M tokens |
| `text-embedding-3-small` input | $0.02 / 1M tokens |
| Railway Hobby | $5 / month |
| Railway Pro | $20 / month |
| Supabase Pro | $25 / month |
| Vercel Hobby | $0 / month |
| Vercel Pro | $20 / month |
| Cloudflare R2 storage | $0.015 / GB-month |
| Cloudflare R2 Class A ops | $4.50 / 1M |
| Cloudflare R2 Class B ops | $0.36 / 1M |

## 4. Assumptions for the new AI cost model

To get a practical estimate, I used a standard-book profile that fits the current pipeline:

- 30 chapters
- about 4,000 raw tokens per chapter
- about 120,000 raw tokens per book

Why this is a better baseline than the old file:

- the app now uses `gpt-4o-mini` for both extraction and intelligence
- summaries are generated in 3 modes, not just one
- plot tracking is included
- embeddings are still cheap, but not zero
- the app now has series-aware Q&A, so ongoing runtime usage matters more than before

Working estimate for one 120k-token book:

| Step | Estimated input tokens | Estimated output tokens | Cost |
|---|---:|---:|---:|
| Character + relationship extraction | 150,000 | 18,000 | $0.0333 |
| 3 chapter summary modes | 375,000 | 28,000 | $0.0731 |
| Plot thread extraction | 126,000 | 6,000 | $0.0225 |
| Chunk + character embeddings | 133,000 | 0 | $0.0027 |
| Total book processing cost |  |  | **$0.1315** |

Rounded rule of thumb:

- `~$0.13` to fully process a normal 120k-token book
- `~$0.0011` per 1,000 raw book tokens processed

## 5. Runtime AI costs after processing

These are small compared with ingestion.

Estimated per-action runtime costs:

| Action | Assumed tokens | Estimated cost |
|---|---:|---:|
| Grounded Q&A answer | 2,200 input + 180 output | $0.0004 |
| Character chat turn | 2,600 input + 220 output + tiny embedding | $0.0005 |
| Resume recap | 900 input + 120 output | $0.0002 |

Practical reading:

- 1,000 grounded answers is still only about `$0.44`
- 1,000 character-chat turns is still only about `$0.52`
- book processing remains the main AI cost center

## 6. Starter free-tier exposure

Current free-tier hard limits from config:

- `FREE_MAX_BOOKS = 2`
- `FREE_TOTAL_TOKEN_BUDGET = 250000`
- `FREE_SEARCH_PER_HOUR = 20`
- `FREE_SUMMARY_PER_HOUR = 30`
- `FREE_CHAT_PER_DAY = 10`

If a free user fully exhausts the 250,000-token ingestion budget:

- `250,000 * $0.0010958 / 1,000 ~= $0.274`

So the current capped free-plan ingestion exposure is roughly:

- `~$0.27` per fully-maxed free user

That is much safer than the older estimates built around heavier models.

## 7. Margin by current plan

### Pro

Example monthly Pro reader:

- 2 new standard books processed
- 200 mixed Q&A / character-chat turns
- 20 recall generations

Estimated monthly AI cost:

- Book processing: `2 * $0.1315 = $0.263`
- Interactions: `200 * ~$0.00048 = ~$0.096`
- Recall: `20 * $0.0002 = ~$0.004`
- Total AI cost: `~$0.36`

Revenue comparison:

- Pro monthly revenue: `$9.00`
- Pro annual equivalent revenue: `$7.50 / month`

Estimated gross margin before infra:

- Monthly Pro: `~96.0%`
- Annual Pro equivalent: `~95.2%`

### Power

Example monthly Power reader:

- 6 new standard books processed
- 800 mixed Q&A / character-chat turns
- 60 recall generations

Estimated monthly AI cost:

- Book processing: `6 * $0.1315 = $0.789`
- Interactions: `800 * ~$0.00048 = ~$0.384`
- Recall: `60 * $0.0002 = ~$0.012`
- Total AI cost: `~$1.19`

Revenue comparison:

- Power monthly revenue: `$17.00`
- Power annual equivalent revenue: `$14.17 / month`

Estimated gross margin before infra:

- Monthly Power: `~93.0%`
- Annual Power equivalent: `~91.6%`

## 8. Infra cost floor

A realistic production floor for LoreVia today is:

| Infra component | Baseline monthly |
|---|---:|
| Railway Hobby | $5 |
| Supabase Pro | $25 |
| Vercel Hobby | $0 |
| Upstash Redis | usage-based |
| Cloudflare R2 | usage-based |
| Total fixed floor | **$30 / month** |

If you choose Vercel Pro for team/commercial workflow:

- fixed floor becomes `~$50 / month`

Important note:

- Railway and Upstash are usage-sensitive
- R2 is tiny at low scale unless you store very large libraries
- payment processor fees are not included here

## 9. Example monthly total cost scenarios

These scenarios combine infra plus AI.

### Scenario A: early production, 100 active users

Assumptions:

- 100 new books processed that month
- 10,000 mixed runtime AI actions
- modest Redis and R2 usage
- Vercel Hobby

Estimate:

| Component | Monthly cost |
|---|---:|
| Fixed infra floor | $30.00 |
| AI book processing | $13.15 |
| Runtime AI actions | $4.80 |
| R2 storage + requests | $0.50 |
| Upstash usage | $4.00 |
| Total | **~$52.45 / month** |

### Scenario B: 1,000 active users

Assumptions:

- 1,000 new books processed that month
- 100,000 mixed runtime AI actions
- noticeably higher Redis and R2 traffic
- Vercel Hobby

Estimate:

| Component | Monthly cost |
|---|---:|
| Fixed infra floor | $30.00 |
| AI book processing | $131.50 |
| Runtime AI actions | $48.00 |
| R2 storage + requests | $7.05 |
| Upstash usage | $40.00 |
| Total | **~$256.55 / month** |

If you move frontend hosting to Vercel Pro, add another `$20`.

## 10. What changed vs the old assumptions

The older cost thinking is too pessimistic for the current product.

Key reasons:

- LoreVia is no longer priced around old plan assumptions
- current reader plans are `Starter / Pro / Power`, not the older draft tiers
- `gpt-4o-mini` is now the main model for both extraction and intelligence
- the biggest cost is still ingestion, but ingestion is now cheap enough that margins are strong
- the current free-tier token budget is protective
- runtime Q&A, recall, and character chat are much cheaper than most people expect

## 11. Bottom line

For the product as currently built:

- fixed infra floor is about `~$30/month` on the leanest paid production setup
- a standard fully processed book costs about `~$0.13`
- a fully-maxed free user costs about `~$0.27` in ingestion exposure
- Pro and Power still have very healthy margin even under active usage

Current conclusion:

- the pricing tiers in the app are economically sound
- AI cost is no longer the thing most likely to break the business
- infra discipline, abuse prevention, and conversion will matter more than raw model cost

## 12. Recommendation

Keep the current tiers for now:

- Starter: $0
- Pro: $9 monthly / $90 annual
- Power: $17 monthly / $170 annual

Watch these three metrics in production:

- cost per processed book
- average processed-book count per paid user per month
- average Q&A and chat turns per paid user per month

If margins tighten later, the cleanest levers are:

- lower free ingestion budget
- reduce precomputed summary modes for Starter users
- move some runtime traffic to Gemini fallback
- gate cross-book intelligence more aggressively behind Pro or Power
