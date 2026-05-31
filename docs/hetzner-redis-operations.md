# Hetzner Redis Operations

This document covers the Redis migration from Upstash to an internal Docker Redis service on the Hetzner VPS.

## Security Model

- Redis runs as a Docker service named `redis`.
- Redis is attached only to the internal `redis_internal` Docker network.
- Redis does not publish `6379` to the host.
- Only the API, workers, beat, and optional Flower service join the Redis network.
- Redis requires `REDIS_PASSWORD`.
- Redis is used only for cache, locks, rate limits, Celery broker traffic, and temporary task state.
- Postgres and Supabase remain the source of truth for durable app data.

## Required Environment

Create or update `backend/.env`.

Generate a strong Redis password:

```bash
openssl rand -base64 48 | tr -d '\n'; echo
```

Set these values in `backend/.env`:

```env
REDIS_PASSWORD=<generated secret>
CELERY_TASK_IGNORE_RESULT=true
CELERY_RESULT_EXPIRES_SECONDS=3600
CELERY_BROKER_VISIBILITY_TIMEOUT_SECONDS=7200
```

Set these runtime URLs directly in `backend/.env`:

```env
REDIS_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
CELERY_BROKER_URL=redis://:${REDIS_PASSWORD}@redis:6379/0
CELERY_RESULT_BACKEND=
```

Advisor async polling now stores job state in Postgres, so `CELERY_RESULT_BACKEND` can stay disabled by default.

## Deploy

From the VPS checkout:

```bash
chmod 600 backend/.env
vi backend/.env
./deploy.sh
```

Manual Docker Compose deployment:

```bash
docker compose -f docker-compose.yml up -d --build redis nginx backend worker-extraction worker-analysis worker-intelligence celery-beat
```

Only use the manual Compose command to restart an already-migrated release. Use `./deploy.sh` whenever application code or Alembic revisions change so the schema is upgraded before the containers restart.

## Verification

Redis container health:

```bash
docker compose -f docker-compose.yml exec redis redis-cli -a "$REDIS_PASSWORD" ping
docker compose -f docker-compose.yml logs redis
```

Confirm Redis is not bound on the host:

```bash
ss -tulpen | grep 6379 || true
docker compose -f docker-compose.yml ps
```

Restart async services after config changes:

```bash
docker compose -f docker-compose.yml restart worker-extraction worker-analysis worker-intelligence celery-beat
```

Application checklist:

- API boots and `/ready` returns successfully.
- All Celery workers connect without Redis authentication errors.
- Celery beat starts and keeps its schedule file healthy.
- Upload and extraction jobs enqueue successfully.
- A worker consumes the queued job.
- User-visible job state continues to come from the app database or app-managed cache, not from long-lived Celery result storage.
- `6379` is absent from public listeners.
- Upstash quota errors stop appearing in Sentry after the rollout.

## Backup And Restore

Find the Redis volume name:

```bash
docker volume ls | grep redis_data
```

Backup the volume:

```bash
docker run --rm -v <redis_volume_name>:/data -v "$PWD:/backup" alpine sh -c 'tar czf /backup/redis-data-backup.tgz -C /data .'
```

Restore the volume:

```bash
docker compose -f docker-compose.yml stop redis
docker run --rm -v <redis_volume_name>:/data -v "$PWD:/backup" alpine sh -c 'rm -rf /data/* && tar xzf /backup/redis-data-backup.tgz -C /data'
docker compose -f docker-compose.yml up -d redis
```

Redis should not be treated as the only copy of important application state. Backups are mainly for operational continuity, not canonical records.

## Rollback To Upstash

1. Edit `backend/.env`.
2. Replace `REDIS_URL` and `CELERY_BROKER_URL` with the previous Upstash `rediss://...` values. Set `CELERY_RESULT_BACKEND` back to Upstash only if you intentionally want Celery result storage there again.
3. Leave `REDIS_PASSWORD` set or unused; it will no longer matter once services stop talking to the internal Redis container.
4. Redeploy the application services:

```bash
docker compose -f docker-compose.yml up -d backend worker-extraction worker-analysis worker-intelligence celery-beat
```

5. After rollback is stable, optionally stop the internal Redis container:

```bash
docker compose -f docker-compose.yml stop redis
```

Do not delete the Redis volume until the rollback has been verified.
