# Final Release Checklist — LoreVia Release Candidate

Prepared as the closing artifact of the final hardening round. Branch: `author` @ `87d204b6` (uncommitted working tree; commit/push is a prerequisite for deploy — see `DEPLOY_AND_FREEZE.md` step 0).

## 1. Final round changes (what shipped in this round)

Deployment race / AI-cost safety:

- **Deployment transition gate.** Pre-cutoff work is held at every choke point before any provider call:
  - `dispatch_pending_extraction_tasks` / `dispatch_pending_analysis_tasks` / `dispatch_pending_embedding_tasks` filter `TaskExecution.created_at >= cutoff`.
  - `publish_task_dispatch_outbox` cancels pre-cutoff outbox rows (`last_error='legacy_cutoff'`).
  - `claim_task_execution` dismisses already-delivered pre-cutoff messages (`status='dismissed'`, `error_category='legacy_cutoff'`), cancels their outbox rows, and releases processing reservations.
  - `dispatch_pending_manuscript_import_jobs` skips pre-cutoff jobs; `process_manuscript_import_job` returns `held_legacy_cutoff` without touching the job.
  - `requeue_stalled_book_processing_if_needed` refuses pre-cutoff books.
  - `retry_book_processing` / `continue_book_processing` and `ensure_project_writable` (world-building, revision workflow, imports, reprocess) return 409 for pre-cutoff incomplete books.
- **Cutoff is recorded during deployment.** `deploy.sh` now: backup → build → stop app stack (redis stays) → migrations → runtime schema check → `freeze_legacy_manuscripts.py --record-cutoff` → systemd unit → start services → health checks. The cutoff therefore always exists before the API accepts uploads; `SKIP_LEGACY_CUTOFF_RECORD=1` is a documented emergency escape hatch only.
- **F1 fix.** `dispatch_manual_rebuild_with_reservations` reserves processed words (manual-reprocess semantics) before an editor-project retry rebuilds; closes the last paid-path allowance bypass.
- **Freeze script hardening.** Books with workspace processing activity newer than the cutoff are skipped (`skipped_processing_after_cutoff`) instead of frozen; dry-run reports it for manual review.
- **PostHog autocapture disabled** (`autocapture: false`).
- **Library project menu z-index raised to `z-[95]`** so the analytics consent banner can no longer cover the menu/delete action on short viewports.

## 1b. Pre-deployment safety hardening (final review round)

- **Fail-closed rollback.** New `backend/scripts/legacy_rollback_hold.py`: before any code rollback, holds legacy state at the data level (hides frozen/pre-cutoff incomplete books from owned-book lookups, cancels every non-terminal legacy execution and outbox row, records the previous hidden state). The runbook now requires: stop the app stack → run the hold with the current image → verify zero non-terminal legacy executions → only then swap code. Schema is never downgraded; `/ready` verifies the older code can run on the migrated schema, and if it cannot, the stack stays stopped (fail-closed) with dump-restore as the recovery path. `--release` restores exactly the books the hold touched.
- **Freeze override for skipped books.** `--include-processing-after-cutoff` (targeted `--book-id` only) lets an operator freeze a book skipped by `skipped_processing_after_cutoff` after investigation. Skipped books remain fail-closed automatically (gate holds dispatchers, claims, outbox, requeue, retry/continue and `ensure_project_writable`); the runbook documents the investigation + override procedure and the proof queries.
- **Deploy-time E2E flag guard.** `deploy.sh` refuses to run when `NEXT_PUBLIC_E2E_MOCK_API`, `ADMIN_E2E_TEST_SECRET`, or `ADMIN_E2E_ALLOW_PRODUCTION` is present anywhere in the deploy environment (including leaked `backend/.env` values). Combined with the build guard and the three-switch `admin.server.ts` requirement, production cannot carry a live admin/mock bypass.
- **Safer release staging.** The runbook replaced blanket `git add -A` with area-scoped staging, secret/junk pattern scans before and after staging, and a mandatory `git diff --cached` review.
- **Provider spend verification (#2).** Confirmed: every customer-attributed provider call reserves tokens/cost **before** the call under a per-user advisory lock, so per-user USD ceilings (paid tiers) and tier token/window caps (all tiers) cannot be crossed jointly by concurrent calls (`test_concurrent_reservations_cannot_jointly_cross_author_ceiling`). All processing entry points reserve processed words first (initial ingestion, continue, manual reprocess, admin reprocess, editor auto-first, editor manual retry — the last one added this round, with a new regression test proving an exhausted allowance returns 403 and dispatches nothing). Editor rebuild/import reconciliation undercounting is an accounting under-count only; it is bounded by the token/USD caps and cannot produce uncontrolled spend. System-funded calls are rate-limited via `enforce_system_llm_rate_limit`.
- **Post-freeze verification strengthened.** The runbook now requires two snapshots (immediately and ≥10 minutes after the freeze) proving zero non-terminal legacy executions, zero pending outbox rows, zero active runs/imports, and **zero new LLM/processing usage events for legacy books** — logs are supporting evidence only.

## 2. Verification ledger (this round, on the pinned local stack)

| Check | Command | Result |
| --- | --- | --- |
| Backend suite | `docker compose -f docker-compose-local.yml exec -T api pytest tests -q` | **2598 passed, 1 skipped** |
| Frontend unit suite | `cd frontend && npm.cmd test` | **1452 passed (277 files)** |
| Frontend type-check | `npm.cmd run type-check` | clean |
| Frontend lint | `npm.cmd run lint` | clean |
| Frontend production build | `npm.cmd run build` | clean |
| Playwright smoke | `npm.cmd run test:e2e -- smoke.spec.ts` (after removing `frontend/.next`) | **108 passed** |
| Launch-readiness E2E | `npm.cmd run test:e2e` (earlier full run) | 399 passed |
| Migration gate | disposable-DB upgrade → downgrade → upgrade (`verify_migrations_temp_db.py`) | passed |
| Transition-gate rehearsal | `rehearsal_transition.py` against the live local stack | **7/7 checks passed** |
| Freeze dry run | `python scripts/freeze_legacy_manuscripts.py` | 140 candidates, 0 changed, no anomalies |
| Cutoff idempotency | `--record-cutoff --execute --confirm YES_I_UNDERSTAND` on existing marker | "already persisted (no change)" |

New regression tests added this round: `backend/tests/unit/test_legacy_cutoff_gates.py` (helper guards, 409s, requeue gate, claim dismissal, dispatcher holds, outbox cancel, import-job hold, editor-retry reservation + allowance bypass block), `backend/tests/unit/test_legacy_rollback_hold.py` (hold/release/idempotency/previous-hidden restoration), freeze-script `skipped_processing_after_cutoff` + targeted override, plus updated fakes in existing suites (`_RetryDB.scalar`, `_FakeDB.scalar` for the audit-table lookup, `_FakeDb.scalar`).

E2E note: run Playwright after deleting `frontend/.next` if you previously ran `next build` in the same checkout; a stale dev cache caused four order-dependent failures that vanished with a clean cache (one of the four was a real menu/banner overlap, fixed above).

## 3. Deployment checklist (condensed; full runbook in `DEPLOY_AND_FREEZE.md`)

- [ ] Commit and merge to `main` using the area-scoped staging procedure in `DEPLOY_AND_FREEZE.md` section 0 (no `git add -A`; scan for secrets, review `git diff --cached`).
- [ ] Confirm production assumptions: Vercel env has no `NEXT_PUBLIC_E2E_MOCK_API`/`ADMIN_E2E_TEST_SECRET`; VPS `backend/.env` complete (`DEBUG=false`, `PROCESSING_ALLOWANCES_MODE=enforce`, provider keys); production Alembic revision matches section 16 of `RELEASE_READINESS_AUDIT.md`; host `pg_dump` available.
- [ ] `./deploy.sh` (it records the cutoff; watch for `legacy_freeze_cutoff_recorded` in the log and the health checks).
- [ ] Verify release + cutoff + gate state (section 4 of the runbook).
- [ ] Promote the **same commit** on Vercel; cross-check `/api/release` vs API `/health`.
- [ ] Freeze dry run; review every row's action (`freeze`, `already_frozen`, `skipped_ready`, or investigate `skipped_processing_after_cutoff`).
- [ ] Freeze execute (explicit approval) → verify frozen counters are zero → watch ~10 minutes for regressions.
- [ ] `PRODUCTION_VERIFICATION.md` smoke pass, including one fresh upload to Ready and one frozen project's UI state.

## 4. Rollback triggers

- Any legacy book starts processing or spends tokens after the cutoff (runbook section 7 proof queries).
- A fresh (post-cutoff) upload stays stuck or gets frozen.
- Frozen-book verification counters become nonzero after the freeze.
- `PRODUCTION_VERIFICATION.md` fails on stuck/frozen-state or duplicate-guard deviation.

Rollback procedure is data-first and fail-closed (runbook section 8): stop the app stack → `legacy_rollback_hold.py --execute` with the current image → verify zero non-terminal legacy executions → swap code → verify `/ready` (schema) → start; release the hold after the gated revision is redeployed. Database rollback is restore-from-dump only; downgrades are blocked by policy.

## 5. Known/deferred items (do not block this release)

- Processed-word accounting still undercounts editor rebuild/import paths (under-count, never over-spend; capped by provider USD limits).
- Advisor synopsis / first-impression quotas are not rate-limited beyond allowance reservations; abusive re-try potential is small and visible.
- `AUTHOR_MAX_UPLOADS` is display-only (storage/word limits bound content).
- Trial accounts bypass `FREE_TOTAL_TOKEN_BUDGET` by design.
- API export spool defaults to tmpfs (RAM) on the API container; config-only mitigation documented.
- Playwright: the full smoke file is order-sensitive in places; always run it on a clean `.next` and treat isolation-only failures as harness state first.

## 6. Final verdict

**GO — deploy the backend via `deploy.sh` and the frontend via the same-commit Vercel promotion, then run the one-time freeze per `DEPLOY_AND_FREEZE.md`.**

The deployment race is closed in code and verified end-to-end on the live local stack; every automated suite is green on the pinned environment; the only remaining pre-deploy items are the operational prerequisites in section 3 (commit, environment confirmation, Vercel promotion, manual freeze approval).
