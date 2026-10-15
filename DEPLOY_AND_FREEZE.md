# Deploy and Freeze — Exact Production Runbook (Hetzner VPS)

This runbook matches the repository's actual deployment configuration:

- **Frontend**: Vercel serves the Next.js app at `www.getlorevia.com` (confirmed from `README.md`, `docs/ARCHITECTURE.md`, `docs/hetzner-service-management.md`; there is no frontend service in `docker-compose.yml`). `NEXT_PUBLIC_*` values are baked at Vercel build time, so the frontend release is a Vercel promotion step, not a VPS step.
- **Backend**: VPS Docker Compose at the repository root (nginx, backend, redis, worker-extraction, worker-analysis, worker-embedding, worker-intelligence, worker-maintenance, celery-beat; external DB/Supabase via `backend/.env`).
- `deploy.sh` (backup → build → **stop app stack** → Alembic → runtime schema check → **record one-time legacy cutoff** → systemd unit refresh → `up -d` → health checks) with defaults:
  - `APP_DIR=/opt/lorevia/current`, branch `main`, env file `./backend/.env`
  - systemd unit `lorevia-compose.service`
  - backups in `/opt/lorevia/backups/supabase`
- Database: external Supabase Postgres accessed through `ALEMBIC_DATABASE_URL` / `DATABASE_URL` in `backend/.env`.

Legend: **[READ-ONLY]** safe to run; **[⚠️ WRITES]** changes production data/state; **[APPROVAL]** stop and get explicit user approval before running.

The whole procedure is: **deploy (cutoff recorded automatically, transition gate active) → dry run → one confirmed freeze**. Workers do not need to be stopped for the manually-run freeze: the deployment transition gate already holds every pre-cutoff job before any provider call.

---

## 0. Preconditions (run on your workstation)

**[APPROVAL]** The working tree contains the reliability fixes, the one-time legacy freeze, and unrelated in-progress billing/redesign work. `deploy.sh` refuses a dirty checkout, so commit and push first (review `FULL_CHANGE_AUDIT.md` before doing this):

```bash
cd <repo>
git status --short
git diff --stat HEAD
git add -A
git commit -m "fix: stabilize manuscript ingestion, add one-time legacy freeze, harden billing reconciliation"
git push origin <your-branch>
```

Then merge into `main` per your process. Do not proceed until `main` contains the changes (`git log --oneline -1`).

---

## 1. VPS environment checks
**[READ-ONLY]** Do not assume Docker is running.

```bash
ssh <user>@<vps-host>
cd /opt/lorevia/current

docker --version
docker compose version
systemctl is-active docker || sudo systemctl start docker
systemctl status lorevia-compose.service --no-pager || true
docker compose --env-file ./backend/.env -f docker-compose.yml ps

grep -q '^REDIS_PASSWORD='        ./backend/.env && echo "REDIS_PASSWORD present"
grep -q '^DATABASE_URL='          ./backend/.env && echo "DATABASE_URL present"
grep -q '^JWT_SECRET\|^SECRET='   ./backend/.env && echo "JWT_SECRET present"
```

Anything missing: stop and report. Do not edit `backend/.env`.

---

## 2. Pre-deploy database checks
**[READ-ONLY]** The working tree ships one Alembic revision (`20260919_subscription_lifecycle`). Verify its assumptions.

```bash
cd /opt/lorevia/current
docker compose --env-file ./backend/.env -f docker-compose.yml run --rm backend \
  python -m alembic current -q
docker compose --env-file ./backend/.env -f docker-compose.yml run --rm backend \
  python -m alembic heads -q

docker compose --env-file ./backend/.env -f docker-compose.yml exec -T backend \
python -c "
import asyncio
from app.core.database import engine
from sqlalchemy import text
async def main():
    async with engine.connect() as conn:
        cols = await conn.execute(text(\"select column_name from information_schema.columns where table_name='subscriptions' and column_name in ('expires_at','current_period_end','cancel_at_period_end')\"))
        print('subscriptions columns:', [r[0] for r in cols])
        idx = await conn.execute(text(\"select indexname from pg_indexes where indexname in ('ix_subscriptions_current_period_end','ix_subscriptions_status_cancel_at_period_end','ix_subscription_email_events_status')\"))
        print('existing indexes:', [r[0] for r in idx])
        t = await conn.execute(text(\"select to_regclass('public.subscription_email_events')\"))
        print('subscription_email_events table:', t.scalar())
asyncio.run(main())
"
```

Expected: exactly one head revision; either `expires_at` or `current_period_end` exists on `subscriptions`. Any unexpected naming conflict: stop and report.

---

## 3. Deploy the backend code (records the legacy cutoff automatically)
**[⚠️ WRITES]** `deploy.sh` takes an automatic `pg_dump` backup first, then:

1. builds images;
2. **stops nginx, backend, all workers, and celery-beat** (redis stays up) so no queued or retrying job can start a provider call during the deployment window, and no new book can be created before the cutoff exists;
3. runs the read-only release preflight and `alembic upgrade head` with a one-off container;
4. verifies runtime schema compatibility;
5. **records the write-once legacy cutoff** (`legacy_freeze_cutoff_recorded` audit marker; never touches a book) with:
   `backend python scripts/freeze_legacy_manuscripts.py --record-cutoff --execute --confirm YES_I_UNDERSTAND`;
6. refreshes the systemd unit and starts every runtime service;
7. runs health checks (`/nginx-health`, `/ready`).

```bash
cd /opt/lorevia/current
export ALEMBIC_DATABASE_URL="$(grep -E '^DATABASE_URL=' backend/.env | cut -d= -f2-)"
export ALEMBIC_CONFIRM_REMOTE=YES_I_AM_SURE
./deploy.sh
```

Do **not** set `SKIP_LEGACY_CUTOFF_RECORD=1` unless you have a reviewed reason: the cutoff must exist before the API accepts uploads, otherwise fresh manuscripts could be frozen later. If it is skipped, record the cutoff manually (section 5) before announcing the release.

Manual alternative (only if not using `deploy.sh`) — the same order matters:

```bash
cd /opt/lorevia/current
git fetch --prune origin && git checkout main && git pull --ff-only origin main
export RELEASE_SHA="$(git rev-parse HEAD)"
export ALEMBIC_DATABASE_URL="$(grep -E '^DATABASE_URL=' backend/.env | cut -d= -f2-)"
docker compose --env-file ./backend/.env -f docker-compose.yml build --pull
docker compose --env-file ./backend/.env -f docker-compose.yml stop \
  nginx backend worker-extraction worker-analysis worker-embedding worker-intelligence worker-maintenance celery-beat
docker compose --env-file ./backend/.env -f docker-compose.yml run --rm \
  -e ALEMBIC_DATABASE_URL="$ALEMBIC_DATABASE_URL" -e ALEMBIC_CONFIRM_REMOTE=YES_I_AM_SURE \
  backend python -m alembic upgrade head
docker compose --env-file ./backend/.env -f docker-compose.yml run --rm \
  -e ALEMBIC_DATABASE_URL="$ALEMBIC_DATABASE_URL" -e ALEMBIC_CONFIRM_REMOTE=YES_I_AM_SURE \
  backend python scripts/freeze_legacy_manuscripts.py --record-cutoff --execute --confirm YES_I_UNDERSTAND
docker compose --env-file ./backend/.env -f docker-compose.yml up -d \
  redis nginx backend worker-extraction worker-analysis worker-embedding worker-intelligence worker-maintenance celery-beat
```

---

## 4. Verify the release, the cutoff, and the transition gate
**[READ-ONLY]**

```bash
cd /opt/lorevia/current
docker compose --env-file ./backend/.env -f docker-compose.yml ps
curl -s https://api.getlorevia.com/health ; echo
curl -s https://api.getlorevia.com/ready ; echo

# New code present (freeze + legacy script)
docker compose --env-file ./backend/.env -f docker-compose.yml exec -T backend \
  python -c "from app.services.book_freeze_service import FROZEN_USER_MESSAGE; print(FROZEN_USER_MESSAGE)"

for svc in worker-extraction worker-analysis worker-embedding worker-intelligence worker-maintenance; do
  docker compose --env-file ./backend/.env -f docker-compose.yml exec -T "$svc" \
    celery -A app.workers.celery_app inspect ping -d "${svc}@\$(hostname)" --timeout=5 || echo "$svc NOT RESPONDING"
done
```

Cutoff marker + transition-gate state:

```bash
docker compose --env-file ./backend/.env -f docker-compose.yml exec -T backend \
python -c "
import asyncio
from app.core.database import engine
from sqlalchemy import text
async def main():
    async with engine.connect() as conn:
        cutoff = await conn.execute(text(\"select metadata_json->>'cutoff' from admin_audit_events where action_type='legacy_freeze_cutoff_recorded' order by created_at desc limit 1\"))
        print('persisted cutoff:', cutoff.scalar())
        held = await conn.execute(text(\"select count(*) from task_executions where error_category='legacy_cutoff'\"))
        print('executions held/dismissed by the gate:', held.scalar())
        pending = await conn.execute(text(\"select count(*) from task_executions where status='pending_dispatch'\"))
        print('pending_dispatch executions:', pending.scalar())
asyncio.run(main())
"
```

Expected: exactly one persisted cutoff; `pending_dispatch` may be nonzero (pre-cutoff rows are intentionally held there until the freeze runs — the dispatcher skips them). Pre-cutoff rows that were already delivered to a worker show `error_category='legacy_cutoff'` with `status='dismissed'`. Log lines to expect in workers/API: `legacy_cutoff_execution_dismissed` and, in the import dispatcher, `manuscript_import_job_held_by_legacy_cutoff`.

Also confirm Sentry shows the new release and no new `MissingGreenlet` issues.

---

## 4b. Deploy the frontend (Vercel)
**[⚠️ WRITES]** (frontend promotion only; no database access)

The frontend is hosted on Vercel, so the VPS deploy does not update it. Promote the **same commit** you just deployed to the backend.

1. In the Vercel dashboard, open the LoreVia project → Deployments, and confirm the Production deployment's commit SHA equals `git rev-parse HEAD` from step 3.
2. Before promoting, verify the Production environment variables do **not** include `NEXT_PUBLIC_E2E_MOCK_API` or `ADMIN_E2E_TEST_SECRET`. (The production build now refuses to compile when `NEXT_PUBLIC_E2E_MOCK_API=1` unless `ADMIN_E2E_ALLOW_PRODUCTION=1` is explicitly set, so a misconfigured build fails instead of shipping; see section 10.)
3. Verify these Production variables exist and point at the VPS API: `NEXT_PUBLIC_API_URL` (e.g. `https://api.getlorevia.com/api/v1`), `API_ORIGIN` (server-side origin used by the `/api/v1` rewrite), `NEXT_PUBLIC_APP_URL`, Paddle (`NEXT_PUBLIC_PADDLE_CLIENT_TOKEN`, `NEXT_PUBLIC_PADDLE_ENV`), Supabase (`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`), and the observability keys you use.
4. Promote/Redeploy the verified commit to Production (the release process in `docs/hetzner-service-management.md` describes the same-commit contract).
5. Cross-check the released SHA:

```bash
curl -s https://www.getlorevia.com/api/release ; echo
curl -s https://api.getlorevia.com/health ; echo
```

Both should report the same commit SHA. The frontend serving the previous SHA is the easiest thing to miss; re-check this after the smoke tests in `PRODUCTION_VERIFICATION.md`.

---

## 5. One-time legacy freeze — dry run
**[READ-ONLY]**

Workers keep running: the transition gate already prevents pre-cutoff work from spending tokens, so no second worker stop is needed.

```bash
cd /opt/lorevia/current
docker compose --env-file ./backend/.env -f docker-compose.yml exec -T backend \
  python scripts/freeze_legacy_manuscripts.py
```

The output prints the cutoff, its source, and one row per book: id, masked account email, status, stage, created date, age, word count, non-terminal executions, in-flight executions, and the planned action.

What to review:
- `cutoff_source=persisted` on every run after deployment (the deploy already recorded it). If it says `now`, the deploy skipped the record step; re-run with `--record-cutoff --execute --confirm YES_I_UNDERSTAND` first to pin it (write-once, never touches a book).
- All legacy rows should say `action=freeze` except:
  - `already_frozen` (previous run),
  - `skipped_ready` (completed books are never frozen),
  - `skipped_after_cutoff` (created after the cutoff; only possible with `--book-id`),
  - `skipped_processing_after_cutoff` — the book's workspace shows processing activity newer than the cutoff. This should not happen once the gate is active; treat it as a stop-and-investigate signal and freeze such a book only with explicit intent (the gate still holds its queued work meanwhile).
- The `WARNING: N execution(s) are currently running` line can appear if a legacy execution was claimed just before the cutoff was recorded. Those are dismissed and stop before their next provider call; an LLM request already in flight may still complete once.

---

## 6. One-time legacy freeze — execute
**[APPROVAL] [⚠️ WRITES]** Stop here until the user explicitly approves this command for the production data.

```bash
cd /opt/lorevia/current
docker compose --env-file ./backend/.env -f docker-compose.yml exec -T backend \
  python scripts/freeze_legacy_manuscripts.py --execute --confirm YES_I_UNDERSTAND
```

Expect `mode=execute ... changed=<N> skipped=<M>` and one `book_processing_frozen` log line per book. Re-running the command is always safe: the cutoff is reused (`cutoff_source=persisted`) and already-frozen books report `already_frozen` with `changed=0`.

Verify immediately (read-only):

```bash
docker compose --env-file ./backend/.env -f docker-compose.yml exec -T backend \
python -c "
import asyncio
from app.core.database import engine
from sqlalchemy import text
async def main():
    async with engine.connect() as conn:
        rows = await conn.execute(text('''
            SELECT count(*) AS frozen_books,
                   coalesce(sum(non_terminal), 0) AS non_terminal_work,
                   coalesce(sum(active_runs), 0) AS active_runs,
                   coalesce(sum(active_imports), 0) AS active_imports
            FROM (
              SELECT b.id,
                     (SELECT count(*) FROM task_executions e WHERE e.book_id=b.id AND e.status IN ('pending_dispatch','queued','running','paused')) AS non_terminal,
                     (SELECT count(*) FROM book_processing_runs r WHERE r.book_id=b.id AND r.status IN ('queued','running','paused')) AS active_runs,
                     (SELECT count(*) FROM manuscript_import_jobs j WHERE j.book_id=b.id AND j.status IN ('queued','running','cancel_requested')) AS active_imports
              FROM books b
              WHERE b.writer_workspace->'processing'->>'frozen' = 'true'
            ) frozen
        '''))
        for r in rows:
            print(dict(r._mapping))
asyncio.run(main())
"
```

Expected: `non_terminal_work=0`, `active_runs=0`, `active_imports=0`.

Audit trail:

```bash
docker compose --env-file ./backend/.env -f docker-compose.yml exec -T backend \
python -c "
import asyncio
from app.core.database import engine
from sqlalchemy import text
async def main():
    async with engine.connect() as conn:
        rows = await conn.execute(text(\"select target_book_id, action_type, reason, result, created_at from admin_audit_events where action_type in ('book_processing_frozen','legacy_freeze_cutoff_recorded') order by created_at desc limit 20\"))
        for r in rows:
            print(dict(r._mapping))
asyncio.run(main())
"
```

---

## 7. Verify frozen projects and fresh uploads
**[READ-ONLY]** (through the web UI and the queries above)

Frozen projects:
1. Show **"Import interrupted"** with the message "Import interrupted - please upload again. Your project and files have been preserved."
2. Have no Retry button; an "Upload again" link goes to the library.
3. Keep existing chapters/content readable; nothing was deleted.
4. `POST /api/v1/books/<id>/processing/retry` returns 409 (Network tab).

Fresh manuscripts (created after the cutoff — never touched by the freeze):
1. Upload a small manuscript as a test account; it must process to Ready normally.
2. Uploading an identical file twice in a row shows: "This exact manuscript is already being processed in another project..."
3. If the account's allowance is insufficient, the book fails visibly with the allowance message.

Wait ~10 minutes and re-run the step 6 verification query: every counter must remain zero and frozen books must not receive new executions. Optionally confirm no new ingestion logs for them:

```bash
docker compose --env-file ./backend/.env -f docker-compose.yml logs --since 15m worker-extraction \
  | grep -Ei 'book_processing_frozen' || true
```

---

## 8. Backup and rollback

The deploy created `/opt/lorevia/backups/supabase/pre_deploy_<timestamp>.dump`. Verify:

```bash
ls -lh /opt/lorevia/backups/supabase/ | tail -5
```

Manual pre-freeze backup (optional extra safety):

```bash
cd /opt/lorevia/current
export ALEMBIC_DATABASE_URL="$(grep -E '^DATABASE_URL=' backend/.env | cut -d= -f2-)"
mkdir -p /opt/lorevia/backups/supabase
pg_dump "$ALEMBIC_DATABASE_URL" -F c -f "/opt/lorevia/backups/supabase/pre_freeze_$(date +%Y%m%d_%H%M%S).dump"
```

Rollback code to the previous good revision:

```bash
cd /opt/lorevia/current
git log --oneline -5
git checkout <previous-good-sha>
export RELEASE_SHA="$(git rev-parse HEAD)"
docker compose --env-file ./backend/.env -f docker-compose.yml build
docker compose --env-file ./backend/.env -f docker-compose.yml up -d \
  redis nginx backend worker-extraction worker-analysis worker-embedding worker-intelligence worker-maintenance celery-beat
```

Release frozen projects (targeted only; never resumes processing):
**[⚠️ WRITES]**

```bash
docker compose --env-file ./backend/.env -f docker-compose.yml exec -T backend \
  python scripts/freeze_legacy_manuscripts.py \
  --unfreeze --book-id <book-uuid> --execute --confirm YES_I_UNDERSTAND
```

Full database restore (destructive; review with the team first):
**[⚠️ WRITES]**

```bash
export ALEMBIC_DATABASE_URL="$(grep -E '^DATABASE_URL=' /opt/lorevia/current/backend/.env | cut -d= -f2-)"
pg_restore --clean --if-exists --no-owner --no-privileges \
  -d "$ALEMBIC_DATABASE_URL" \
  /opt/lorevia/backups/supabase/pre_deploy_<timestamp>.dump
```

Then redeploy the matching code revision. `alembic downgrade` is intentionally not used (the repository blocks destructive downgrades; the billing migration's downgrade is not a true inverse on databases bootstrapped from the current schema).

---

## 9. Deployment transition gate (what holds legacy work)

Between deployment and the manual freeze, pre-cutoff work must not spend tokens. The gate applies everywhere a provider call could begin:

- **Dispatcher** (`dispatch_pending_extraction_tasks`, `dispatch_pending_analysis_tasks`, `dispatch_pending_embedding_tasks`): SQL filter `TaskExecution.created_at >= cutoff`; pre-cutoff rows stay `pending_dispatch` and occupy no dispatch slots.
- **Outbox publish** (`publish_task_dispatch_outbox`): pre-cutoff rows are cancelled with `last_error='legacy_cutoff'`.
- **Worker claim** (`claim_task_execution`): already-delivered Celery messages for pre-cutoff executions are dismissed (`error_category='legacy_cutoff'`) before any provider call; their dispatch outbox rows are cancelled and processing reservations released.
- **Import jobs**: `dispatch_pending_manuscript_import_jobs` skips pre-cutoff jobs; `process_manuscript_import_job` returns `held_legacy_cutoff` without touching the job.
- **Recovery paths**: `requeue_stalled_book_processing_if_needed` returns False for pre-cutoff books.
- **User actions**: retry/continue endpoints and `ensure_project_writable` (world-building, revision workflow, imports, reprocess) return 409 for pre-cutoff incomplete books.
- **Editor-project retries** reserve processed words before rebuilding, so user-triggered retries cannot bypass allowances.

Fresh work (created after the cutoff) is unaffected: new uploads process normally, and reprocessing a legacy **ready** book still works because `ready` books are never treated as legacy.

Production verification of the gate: run the query in section 4. The live local rehearsal (same code path, disposable database) verified all choke points: dispatcher holds, outbox cancels, claim dismisses, import job holds, requeue holds, fresh work dispatches, repeated `--record-cutoff` is a no-op.

---

## 10. Automated cutoff recording (implemented)

`deploy.sh` now records the cutoff during the deployment window (after migrations and the runtime schema check, before services start), so the cutoff equals the deployment boundary exactly and cannot drift to the first manual freeze run. `SKIP_LEGACY_CUTOFF_RECORD=1` exists only as a documented escape hatch; do not use it for a normal release.

---

## 11. Stop point

Steps 0–2, 4, and 5 are read-only. Step 3 changes production (including recording the write-once cutoff). Step 6 and the destructive rollback/unfreeze commands modify production data. The first execution of each destructive command must be explicitly approved by the user in the current session.
