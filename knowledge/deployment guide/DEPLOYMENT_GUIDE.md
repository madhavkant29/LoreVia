# LoreVia — Deployment Guide

Complete guide to go from local development to production.
Stack: Railway (backend) + Vercel (frontend) + Supabase + Upstash + Cloudflare R2.

---

## Part 1 — Supabase Setup (Do this first)

### 1.1 Create your project

1. Go to [supabase.com](https://supabase.com) → New project
2. Name: `lorevia-prod`
3. Database password: generate a strong one and **save it somewhere safe**
4. Region: pick closest to your users (ap-south-1 for India)
5. Wait ~2 minutes for provisioning

### 1.2 Enable required extensions

1. Dashboard → Database → Extensions
2. Search **vector** → enable it
3. Search **pg_trgm** → enable it

These power semantic search and character deduplication. The app will crash on startup without them.

### 1.3 Get your connection string

1. Dashboard → Settings → Database
2. Scroll to **Connection string**
3. Select **Transaction pooler** tab (not Session pooler — important)
4. Copy the URI — it looks like:
   ```
   postgresql://postgres.abcdef:YOUR_PASSWORD@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
   ```
5. Replace `[YOUR-PASSWORD]` with the password you saved in step 1.1

### 1.4 Get your API keys (needed for Google OAuth later)

1. Dashboard → Settings → API
2. Copy **Project URL** — `https://abcdef.supabase.co`
3. Copy **anon public** key
4. Copy **service_role** key (keep this secret — never expose it in frontend)

---

## Part 2 — Fill In Your Backend .env

Copy `backend/.env.example` to `backend/.env` and fill in every value:

```bash
APP_NAME=LoreVia
DEBUG=false
API_V1_PREFIX=/api/v1

# ── Database ─────────────────────────────────────────────────────────────────
# Paste the Transaction pooler URI from Supabase Part 1.3
DATABASE_URL=postgresql://postgres.abcdef:yourpassword@aws-0-ap-south-1.pooler.supabase.com:5432/postgres

# ── Redis (Upstash) ───────────────────────────────────────────────────────────
# upstash.com → Create database → copy Redis URL
REDIS_URL=rediss://default:yourpassword@your-endpoint.upstash.io:6380

# ── Storage (Cloudflare R2) ───────────────────────────────────────────────────
# dash.cloudflare.com → R2 → Create bucket → Manage API tokens
S3_BUCKET=lorevia-prod
S3_ENDPOINT_URL=https://YOUR_ACCOUNT_ID.r2.cloudflarestorage.com
AWS_ACCESS_KEY_ID=your_r2_access_key
AWS_SECRET_ACCESS_KEY=your_r2_secret_key

# ── OpenAI ────────────────────────────────────────────────────────────────────
# platform.openai.com → API Keys
OPENAI_API_KEY=sk-proj-...
OPENAI_EXTRACT_MODEL=gpt-4o-mini
OPENAI_INTEL_MODEL=gpt-4o
OPENAI_EMBED_MODEL=text-embedding-3-small
OPENAI_EMBED_DIM=1536

# ── Auth ──────────────────────────────────────────────────────────────────────
# Generate with: python3 -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET=your_64_char_random_hex_string

# ── Supabase (for Google OAuth) ───────────────────────────────────────────────
# From Supabase → Settings → API (Part 1.4)
SUPABASE_URL=https://abcdef.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGci...

# ── Stripe ────────────────────────────────────────────────────────────────────
# Skip for MVP — use placeholder values until you add payments
STRIPE_SECRET_KEY=sk_test_placeholder
STRIPE_WEBHOOK_SECRET=whsec_placeholder

# ── Email (Resend) ────────────────────────────────────────────────────────────
# resend.com → API Keys. Use onboarding@resend.dev as EMAIL_FROM until you have a domain
RESEND_API_KEY=re_...
EMAIL_FROM=onboarding@resend.dev

# ── Monitoring ────────────────────────────────────────────────────────────────
# sentry.io → New project → Python. Leave blank to disable.
SENTRY_DSN=

# ── Cloudflare Tunnel ─────────────────────────────────────────────────────────
# Fill in after Railway deploy (Part 4.3)
# Leave blank for now
CLOUDFLARE_TUNNEL_TOKEN=
```

### Generate JWT_SECRET right now

Run this in your terminal and paste the output:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## Part 3 — Fill In Your Frontend .env

Create `frontend/.env.local` (copy from `frontend/.env.local.example`):

```bash
# During development — points to your local backend
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

**After Railway deploy** — update to your live URLs:

```bash
# Production
NEXT_PUBLIC_API_URL=https://api.getlorevia.com/api/v1
NEXT_PUBLIC_APP_URL=https://getlorevia.com
```

---

## Part 4 — Deploy Backend to Railway

### 4.1 Set up Railway

1. Go to [railway.app](https://railway.app) → Login with GitHub
2. New project → Deploy from GitHub repo → select your repo
3. Railway auto-detects the Dockerfile

### 4.2 Create three Railway services

You need three separate services from the same repo:

**Service 1 — API**
- Root directory: `backend`
- Dockerfile: `Dockerfile.api`
- Start command: `./start.sh` (already set in Dockerfile)
- Port: `8000`

**Service 2 — Worker (extraction + analysis)**
- Root directory: `backend`
- Dockerfile: `Dockerfile.worker`
- Start command override:
  ```
  celery -A app.workers.celery_app worker -Q extraction,analysis,embedding -c 2 --loglevel=info
  ```

**Service 3 — Worker (intelligence)**
- Root directory: `backend`
- Dockerfile: `Dockerfile.worker`
- Start command override:
  ```
  celery -A app.workers.celery_app worker -Q intelligence -c 1 --loglevel=info
  ```

### 4.3 Add environment variables to Railway

Railway dashboard → your API service → Variables → Add all variables from your `backend/.env`.

**Do not paste the file directly** — add each key-value pair individually so Railway stores them securely.

### 4.4 Run database migrations

Once the API service is deployed and healthy:

1. Railway dashboard → API service → Settings → Deploy → Run command
2. Or use the Railway CLI:

```bash
npm install -g @railway/cli
railway login
railway run alembic upgrade head
```

This creates all your database tables including pgvector indexes. **Must be done before the app can function.**

### 4.5 Get your Railway API URL

Railway dashboard → API service → Settings → Networking → copy the public domain.
It looks like: `lorevia-api-production.up.railway.app`

---

## Part 5 — Set Up Cloudflare Tunnel (Origin Security)

This makes your Railway URL unreachable directly — all traffic must go through Cloudflare. Do this before going public.

### 5.1 Create the tunnel

1. [dash.cloudflare.com](https://dash.cloudflare.com) → Zero Trust → Networks → Tunnels
2. Create tunnel → name it `lorevia-prod` → Next
3. Copy the **tunnel token** (long string starting with `eyJ...`)

### 5.2 Configure the tunnel

Still in Cloudflare tunnel setup:

1. Add a public hostname:
   - Subdomain: `api`
   - Domain: `getlorevia.com` (your domain, must be on Cloudflare DNS)
   - Service: `http://localhost:8000`
2. Save

### 5.3 Add token to Railway

Railway → API service → Variables → add:

```
CLOUDFLARE_TUNNEL_TOKEN=eyJ...your_token...
```

Redeploy the API service. The `start.sh` script automatically starts `cloudflared` before uvicorn when this variable is set.

Now `api.getlorevia.com` routes through Cloudflare → your Railway service. The raw Railway URL stops working.

---

## Part 6 — Deploy Frontend to Vercel

### 6.1 Set up Vercel

1. Go to [vercel.com](https://vercel.com) → Login with GitHub
2. New project → Import your repo
3. Framework: **Next.js** (auto-detected)
4. Root directory: `frontend`
5. Build command: `npm run build` (default)
6. Output directory: `.next` (default)

### 6.2 Add environment variables in Vercel

Vercel dashboard → your project → Settings → Environment Variables:

```
NEXT_PUBLIC_API_URL = https://api.getlorevia.com/api/v1
NEXT_PUBLIC_APP_URL = https://getlorevia.com
```

### 6.3 Add your custom domain

1. Vercel → Settings → Domains → Add `getlorevia.com`
2. Vercel gives you DNS records to add in Cloudflare
3. Cloudflare → your domain → DNS → add the records Vercel shows you
4. Wait 2–5 minutes for propagation

---

## Part 7 — Verify Everything Works

Run through this checklist after deploy:

```
□ https://api.getlorevia.com/health returns {"status": "ok"}
□ https://getlorevia.com loads the landing page
□ Register a new account
□ Login works, JWT token issued
□ Upload a small PDF book
□ Railway worker logs show extraction starting
□ Book status changes from "processing" to "ready"
□ Open the book → chapter loads
□ Tap a character name → context card appears
□ Chapter summary loads
□ Supabase dashboard → Table Editor → characters table has rows
```

If `/health` fails — check Railway logs for the error. 99% of the time it's a wrong env variable.

If book processing never completes — check the worker service logs in Railway. Usually a missing `OPENAI_API_KEY` or wrong `REDIS_URL`.

---

## Part 8 — After Launch Checklist

Things to do in the first week after going live:

```
□ Set up Sentry — add SENTRY_DSN to Railway variables, watch for errors
□ Set spending limits on OpenAI — platform.openai.com → Billing → Limits
□ Set up Upstash rate limiting alerts — Upstash dashboard → Alerts
□ Test the full flow on mobile browser (not just desktop)
□ Check Supabase database size — Dashboard → Settings → Database → Database size
□ Set a Railway budget limit — Railway → Settings → Usage limits
```

---

## Summary — Service Checklist

| Service | What to do | Done? |
|---|---|---|
| Supabase | Create project, enable vector + pg_trgm, copy DB URL | |
| Upstash | Create Redis database, copy URL | |
| Cloudflare R2 | Create bucket, create API token, copy keys | |
| OpenAI | Create API key, add billing | |
| Railway | Deploy API + 2 workers, add all env vars, run migrations | |
| Cloudflare Tunnel | Create tunnel, add token to Railway | |
| Vercel | Deploy frontend, add env vars, add custom domain | |
| Resend | Create API key (use onboarding@resend.dev for now) | |
| Sentry | Create project, add DSN | |

---

## Common Errors

**`relation "books" does not exist`**
→ Migrations haven't run. Run `railway run alembic upgrade head`

**`could not translate host name`**
→ Wrong DATABASE_URL. Make sure you're using Transaction pooler, not Session pooler.

**`CORS error` in browser**
→ `NEXT_PUBLIC_API_URL` points to wrong URL. Check it includes `/api/v1` at the end.

**`401 Unauthorized` on every request**
→ JWT_SECRET is different between local and Railway. Make sure you copied the exact same value.

**Workers not processing books**
→ Check REDIS_URL is identical in all three Railway services. Workers use Redis to receive jobs from the API.

**`pgvector extension not found`**
→ Go to Supabase → Database → Extensions → enable vector. Then restart the Railway API service.
