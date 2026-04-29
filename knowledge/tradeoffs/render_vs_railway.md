Honest comparison for your specific stack.

---

## Railway vs Render for LoreVia

### Where Railway wins for you

**Celery workers are first-class.** You have three worker types (extraction, analysis, intelligence). On Railway each is a separate service with its own start command, logs, and scaling — takes 2 minutes to set up. On Render, background workers are a paid feature ($7/worker/month minimum) and the configuration is more painful.

**Persistent disk isn't needed.** LoreVia stores everything in Supabase, Upstash, and R2 — nothing on disk. Railway's ephemeral filesystem is fine for you.

**Logs are better.** Railway's log viewer is real-time, filterable, and shows all services together. When a Celery worker fails during book processing you need to see why immediately. Render's logs are clunkier.

**Deploy speed.** Railway deploys in ~60 seconds after a git push. Render takes 3–5 minutes. When you're iterating fast this matters.

**Pricing is simpler.** Railway charges for actual usage (CPU + RAM + network consumed). Render charges per service per month whether it's idle or not.

---

### Where Render wins

**Free tier is more generous.** Render gives you a free web service that sleeps after 15 minutes of inactivity. Railway's free tier ($5 credit/month) is consumed even when idle.

**Sleep on inactivity.** For a side project with no users yet, Render's free tier costs literally $0. Railway's $5 credit runs out in ~3 weeks on an idle service.

**More predictable billing.** Some founders prefer knowing exactly what they'll pay. Railway's usage-based billing can surprise you if a worker goes into a retry loop.

---

## The Honest Recommendation

**Right now, before users: use Render's free tier.**

Your API sleeps when not in use, costs $0, and is fine for showing people the app and getting early feedback. The 30-second cold start on first request doesn't matter when you have zero users.

**When you have consistent traffic: switch to Railway.**

The moment you have real users, Render's sleep behaviour becomes a problem — the first request after idle takes 30 seconds, which is a terrible first impression. At that point Railway's worker setup, better logs, and faster deploys are worth the ~$10–20/month.

The switch is trivial — same Dockerfiles, same environment variables, different dashboard.

---

## What to do

| Stage | Platform | Cost |
|---|---|---|
| Building + early testing | Render free tier | $0 |
| First real users | Railway | ~$10–20/month |
| Scale | Railway or ECS | Depends on traffic |

Start on Render. The deployment guide works identically — just create a Render Web Service instead of a Railway service, point it at the same Dockerfile, and add the same environment variables.