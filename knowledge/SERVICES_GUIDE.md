# LoreVia — External Services Guide

Every service the app depends on, what it does, where to sign up, and exactly what to copy into your `.env`.

---

## Required to run locally right now

These 4 services are the minimum. Nothing works without them.

---

### 1. OpenAI
**What it does:** All intelligence — character extraction, chapter summaries, embeddings for semantic search, character chat, predictions.

**Sign up:** [platform.openai.com](https://platform.openai.com)

**Steps:**
1. Create account → Billing → Add $5–10 credit (enough for ~500 book processings at gpt-4o-mini prices)
2. API Keys → Create new secret key
3. Copy the key — you only see it once

**`.env` values:**
```
OPENAI_API_KEY=sk-proj-...
OPENAI_EXTRACT_MODEL=gpt-4o-mini
OPENAI_INTEL_MODEL=gpt-4o
OPENAI_EMBED_MODEL=text-embedding-3-small
OPENAI_EMBED_DIM=1536
```

**Cost context:**
- `gpt-4o-mini`: ~$0.001–0.003 per chapter (extraction + summary)
- `gpt-4o`: ~$0.01–0.03 per chat turn (Power tier only)
- `text-embedding-3-small`: ~$0.00002 per 1k tokens — effectively free

**Free tier:** No free tier, but $5 credit lasts a long time during development.

---

### 2. Supabase (PostgreSQL + pgvector)
**What it does:** Your main database. Stores users, books, characters, relationships, summaries, plot threads, embeddings. The pgvector extension powers semantic search and character deduplication.

**Sign up:** [supabase.com](https://supabase.com)

**Steps:**
1. New project → choose a region close to you → set a DB password (save it)
2. Wait ~2 min for provisioning
3. Dashboard → Database → Extensions → search "vector" → enable it
4. Dashboard → Settings → Database → scroll to "Connection string" → copy the **Transaction pooler** URI (not Session pooler)
5. Replace `[YOUR-PASSWORD]` in the URI with your DB password

**`.env` value:**
```
DATABASE_URL=postgresql://postgres.abcdef:yourpassword@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
```

**Free tier:** 500MB database, 1GB file storage, 2 projects — enough for first ~500 users.

**Important after setup:** Run `alembic upgrade head` to create all tables.

---

### 3. Upstash (Redis)
**What it does:** Cache layer (character profiles, summaries, search results) + Celery task broker (coordinates background workers).

**Sign up:** [upstash.com](https://upstash.com)

**Steps:**
1. Create database → name it `lorevia-dev` → pick the same region as Supabase
2. Details page → copy the **Redis URL** (starts with `rediss://`)

**`.env` value:**
```
REDIS_URL=rediss://default:yourpassword@your-endpoint.upstash.io:6380
```

**Free tier:** 10,000 commands/day, 256MB — sufficient for development and early users.

**Note:** The double-s in `rediss://` is not a typo — it means TLS-encrypted Redis, which Upstash requires.

---

### 4. Cloudflare R2 (File Storage)
**What it does:** Stores user-uploaded PDFs and EPUBs privately. No images (we dropped image generation). S3-compatible API.

**Sign up:** [dash.cloudflare.com](https://dash.cloudflare.com) — needs a Cloudflare account (free)

**Steps:**
1. Left sidebar → R2 Object Storage → Create bucket → name it `lorevia-dev` → Create
2. R2 overview page → Manage R2 API Tokens → Create API Token
3. Permissions: Object Read & Write → Select bucket: `lorevia-dev` → Create
4. Copy: Access Key ID, Secret Access Key
5. Your endpoint is: `https://<YOUR_ACCOUNT_ID>.r2.cloudflarestorage.com`
   - Find account ID: top-right of any Cloudflare page, or R2 overview URL contains it

**`.env` values:**
```
S3_BUCKET=lorevia-dev
S3_ENDPOINT_URL=https://abc123.r2.cloudflarestorage.com
AWS_ACCESS_KEY_ID=your_key_id
AWS_SECRET_ACCESS_KEY=your_secret_key
```

**Free tier:** 10GB storage, 10M reads/month, 1M writes/month — free indefinitely.

---

## Required before launch (not needed to run locally)

---

### 5. Stripe (Payments)
**What it does:** Handles Pro and Power subscriptions. Webhooks notify the backend when subscriptions are created, cancelled, or fail payment.

**Sign up:** [stripe.com](https://stripe.com)

**Steps:**
1. Create account → Dashboard → Developers → API Keys
2. Copy the **Secret key** (starts with `sk_test_` for testing, `sk_live_` for production)
3. Create your products: Catalog → Products → Add product
   - "LoreVia Pro" — recurring, monthly and annual prices
   - "LoreVia Power" — recurring, monthly price
   - Copy each Price ID (starts with `price_`)
4. Update `PRICE_IDS` in `backend/app/services/stripe_service.py` with your actual price IDs
5. Webhooks: Developers → Webhooks → Add endpoint
   - URL: `https://your-api.railway.app/api/v1/webhooks/stripe`
   - Events to listen: `customer.subscription.created`, `customer.subscription.deleted`, `invoice.payment_failed`
   - Copy the Signing secret (starts with `whsec_`)

**`.env` values:**
```
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

**For local webhook testing:** install [Stripe CLI](https://stripe.com/docs/stripe-cli) and run:
```bash
stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe
# This gives you a local webhook secret to use during dev
```

**Free tier:** No monthly fee. Stripe takes 2.9% + $0.30 per transaction.

---

### 6. Resend (Transactional Email)
**What it does:** Sends emails — book processing complete, subscription confirmations, payment failures.

**Sign up:** [resend.com](https://resend.com)

**Steps:**
1. Create account → API Keys → Create API Key → Copy it
2. Domains → Add domain → verify your domain DNS (or use `onboarding@resend.dev` for testing without domain)

**`.env` value:**
```
RESEND_API_KEY=re_...
EMAIL_FROM=noreply@yourdomain.com
```

**Free tier:** 3,000 emails/month, 100/day — sufficient for a long time.

---

### 7. Sentry (Error Tracking)
**What it does:** Catches and reports runtime errors in the FastAPI backend and Next.js frontend. You want this on from day one — silent failures are worse than known ones.

**Sign up:** [sentry.io](https://sentry.io)

**Steps:**
1. Create account → New project → Python → FastAPI
2. Copy the DSN URL shown after creation
3. Optionally create a second project for Next.js frontend and add `SENTRY_DSN` to `frontend/.env.local`

**`.env` value:**
```
SENTRY_DSN=https://abc123@o123456.ingest.sentry.io/789
```

**Free tier:** 5,000 errors/month — enough for early stage.

---

## Required for production security

---

### 8. Cloudflare (WAF + Tunnel)
**What it does:** Two things:
- **WAF/DDoS protection** — your domain goes through Cloudflare, blocking bots and attacks before they reach Railway
- **Tunnel** — makes your Railway origin URL unreachable directly, so all traffic is forced through Cloudflare

**Sign up:** [cloudflare.com](https://cloudflare.com) — the account you created for R2 works here too

**Steps for Tunnel:**
1. Cloudflare dashboard → Zero Trust → Networks → Tunnels → Create tunnel
2. Name it `lorevia-prod` → Next
3. Copy the tunnel token (long string)
4. Set the public hostname: `api.lorevia.app` → Service: `http://localhost:8000`
5. Done — once you deploy to Railway and set `CLOUDFLARE_TUNNEL_TOKEN`, the tunnel starts automatically via `start.sh`

**`.env` value:**
```
CLOUDFLARE_TUNNEL_TOKEN=eyJhIjoiA...
```

**Free tier:** Tunnel is free. WAF basic rules are free.

---

## Optional — add when you need them

---

### 9. PostHog (Product Analytics)
**What it does:** Tracks user behaviour — which features get used, where users drop off, what chapters they read, how often they use Smart Tap.

**Sign up:** [posthog.com](https://posthog.com) — self-hostable or cloud

**When to add:** Once you have real users and want to understand what they're doing.

**Free tier:** 1M events/month free on cloud.

**Frontend setup:** Add to `frontend/src/app/layout.tsx`:
```tsx
import posthog from 'posthog-js'
posthog.init('your_project_api_key', { api_host: 'https://app.posthog.com' })
```

---

### 10. Railway (Backend Hosting)
**What it does:** Hosts your FastAPI API and Celery workers. Replaces running them locally.

**Sign up:** [railway.app](https://railway.app)

**When to add:** When you're ready to share the app with others.

**Free tier:** $5/month free credit — enough for a small hobby project. Pay as you grow.

---

### 11. Vercel (Frontend Hosting)
**What it does:** Hosts your Next.js frontend with automatic deploys on every git push.

**Sign up:** [vercel.com](https://vercel.com)

**When to add:** Same time as Railway.

**Free tier:** Generous — free for personal projects indefinitely.

---

## Quick reference — what's needed when

| Service | Needed for | When |
|---|---|---|
| OpenAI | Everything intelligence | **Now** |
| Supabase | Database | **Now** |
| Upstash | Cache + workers | **Now** |
| Cloudflare R2 | File storage | **Now** |
| Stripe | Payments | Before launch |
| Resend | Email | Before launch |
| Sentry | Error tracking | Before launch (ideally Day 1) |
| Cloudflare Tunnel | Origin security | Before going public |
| PostHog | Analytics | Once you have users |
| Railway | Deploy backend | When ready to share |
| Vercel | Deploy frontend | When ready to share |

**Total monthly cost at zero revenue:** ~$0 (all free tiers)
**Total monthly cost at 100 users:** ~$15–25 (Railway + Upstash paid + small OpenAI bill)
**Total monthly cost at 1,000 users:** ~$80–120 (mostly OpenAI + Railway scaling)
