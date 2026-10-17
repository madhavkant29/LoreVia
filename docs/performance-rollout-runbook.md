# Performance rollout runbook

This runbook covers the staged release of durable manuscript exports, direct
public chapter assets, and the auth database timing measurement gate. It does
not authorize a deployment or a remote database migration.

## 1. Pre-deployment gates

- Run the full backend and frontend test suites, type checking, linting, and
  migration-chain verification against a disposable Docker Compose Local
  database.
- Confirm the deployment includes both API and worker images from the same
  revision. The worker must register `export_tasks.*` and
  `maintenance_tasks.*` on the maintenance queue.
- Confirm `worker-maintenance` has the writable `export_spool` volume mounted
  at `/var/lib/lorevia-export-spool`. Production `/tmp` is a memory-backed
  `tmpfs` and must not hold rolled-over large artifacts.
- Review `20260912_add_manuscript_export_jobs.py` and
  `20260912_track_public_asset_readiness.py`. Confirm their upgrades contain
  only the backend-only job table/indexes and the nullable chapter readiness
  column.
- Keep `DIRECT_PUBLIC_ASSETS_ENABLED=false` for the first deployment.

## 2. Compatible application and schema rollout

After explicit authorization for the named environment:

1. Deploy the compatible API and worker code.
2. Apply the migration using an explicit `ALEMBIC_DATABASE_URL` and the safety
   checklist in `docs/db-migration-guide.md`.
3. Verify the API and maintenance worker are healthy and the database reports
   the expected Alembic head.
4. Exercise one small synchronous export and one forced asynchronous export.
   Verify job state transitions, authenticated download, expiry, and artifact
   cleanup.

Rollback: disable export-job creation by setting thresholds above the largest
expected manuscript while retaining the job table and worker code. Do not
downgrade the database while jobs or artifacts may still be active.

## 3. Direct public asset canary

Follow `docs/public-asset-delivery.md` to provision a read-only public origin
that exposes only the `public-assets/` prefix. Never expose the private book or
export prefixes.

1. Set the HTTPS `PUBLIC_ASSET_BASE_URL`, retain a short cache maximum age, and
   leave `DIRECT_PUBLIC_ASSETS_ENABLED=false`.
2. Confirm the origin cannot list objects and cannot access any key outside
   `public-assets/`. Run `backend/scripts/verify_public_asset_origin.py` with a
   known-readable public asset and a known-existing private object before
   enabling the flag.
3. Enable the flag on a canary instance. Let the bounded hourly backfill create
   versioned assets.
4. Validate public reads, edits, publication, moderation hide/reject, unpublish,
   and deletion. Revoked content may remain cached only for the configured
   maximum age.
5. Expand only if asset publish failures, public 404s, and storage latency stay
   within the service's normal error budget.

Rollback: set `DIRECT_PUBLIC_ASSETS_ENABLED=false`. Revocation continues to
delete previously generated assets even while delivery is disabled.

## 4. Auth measurement gate

Deploy the auth database timing metric, then follow
`docs/auth-cache-measurement.md` for at least seven representative production
days. Do not add an auth cache unless the recorded latency, request contribution,
and invalidation evidence meet that document's thresholds.

If caching is justified, ship it as a separate low-risk canary with a short TTL,
explicit invalidation for account and authorization changes, and an immediate
disable switch. If the threshold is not met, record the decision and leave auth
uncached.

## 5. Completion evidence

Capture the deployed revision, migration head, worker registration, export job
success/failure/expiry counts, public asset publish and 404 rates, auth timing
percentiles, and the final cache decision. Local verification alone must not be
reported as a completed production rollout.
