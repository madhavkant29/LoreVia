# Auth principal cache decision gate

LoreVia intentionally keeps authorization database-backed until production measurements demonstrate that authentication lookup time is a material bottleneck. Request completion logs now include `auth_db_lookup_count` and `auth_db_lookup_time_ms` alongside total duration and database-query timing.

## Measurement window

Collect at least seven representative days from the VPS API logs. Group successful authenticated GET requests by normalized route, excluding health checks, admin, billing, destructive, and privilege-changing routes. Record sample count, auth lookup p50/p95/p99, total request p95, and the percentage of request time attributable to auth.

The repository includes a deterministic JSONL analyzer for the request-completion logs:

```powershell
Get-Content .\api-request-log.jsonl | python .\backend\scripts\analyze_auth_latency.py -
```

It normalizes UUID and numeric path segments, filters the excluded route classes, and marks only the routes that meet the numeric measurement threshold. Its output is aggregate-only and must not be treated as sufficient authorization to enable a cache without the corroboration and invalidation checks below.

A cache is justified only when all of these are true:

- The route group has enough traffic to be representative.
- Auth DB lookup p95 is at least 50 ms.
- Auth consumes at least 20 percent of end-to-end p95 latency on low-risk reads.
- Database pool pressure or query traces corroborate the lookup as a bottleneck.
- A tested invalidation source exists for token-version changes, account deletion, suspension, tier changes, and email/account identity changes.

If the gate is not met, keep database-backed authentication. If it is met, introduce a separate low-risk-read dependency with a short TTL; never use it for admin, billing, destructive writes, plan enforcement, usage reservation, or privilege-changing routes. Cache failures must fall back to the database and cache keys must be user-specific and token-version-specific.

## Rollout checks

Start with one low-risk read route and compare cache hit rate, auth p95, total p95, database query count, 401/403 rate, Redis error rate, and cross-user isolation tests. Expand only after the canary window is clean. Disabling the cache must immediately restore the current database-backed path.
