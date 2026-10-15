# Full Working-Tree Audit — Unreleased Product Version

Baseline: `HEAD = 87d204b6`. Staged: **none** (`git diff --cached` empty). Everything below is uncommitted working-tree state.

## 1. Inventory

| Area | Modified/deleted (tracked) | Untracked (new) |
|---|---|---|
| Backend (FastAPI, tests, scripts, migrations) | 51 | 13 |
| Frontend (Next.js app, components, content, public assets, e2e) | 454 (incl. 40 deleted binaries) | 153 |
| Docs (`docs/`) | 2 | 2 |
| Repo-root audit docs (created by this work) | 0 | 4 |
| **Total** | **507 (40 deleted)** | **172** |

Modified backend files (all shown by `git diff --name-only HEAD -- backend`):

- Reliability/freeze work (this session): `api/v1/routes/books/imports.py`, `services/book_freeze_service.py` (new), `services/book_upload_service.py`, `services/extraction_budget_service.py`, `services/first_impression_service.py`, `services/manuscript_import_job_service.py`, `services/manuscript_import_request_service.py`, `services/pipeline_state_service.py`, `services/processing_pause_service.py`, `utils/books/imports.py`, `utils/upload_security_utils.py`, `utils/processing_error_utils.py` (new), `workers/consumers/analysis_consumer.py`, `workers/tasks/extraction_tasks.py`, `workers/tasks/maintenance_tasks.py`, `workers/tasks/embedding_tasks.py`, `services/processing_allowance_service.py`, `services/extraction_chapter_processing_service.py`, `services/extraction_chapter_analysis_dispatch_service.py`, `services/extraction_book_processing_service.py`, `app/db/migrations/versions/20260919_add_subscription_lifecycle_fields.py` (edited index fix), `scripts/freeze_legacy_manuscripts.py` (new).
- Billing WIP (pre-existing, reviewed and partly fixed): `api/deps/rate_limit.py`, `api/v1/routes/billing.py`, `api/v1/routes/internal.py`, `core/config.py`, `data/pricing-catalog.json`, `models/user.py`, `schemas/billing.py`, `services/email_service.py`, `services/paddle_service.py`, `services/paddle_webhook_service.py`, `services/privacy_service.py`, `utils/billing_utils.py`, `workers/celery_app.py`, plus new `services/billing_status_service.py`, `services/subscription_email_service.py`, `services/subscription_reconciliation_service.py`, and the migration above.
- Tests: 11 modified/added unit files, 4 modified integration files.

Frontend categories (from the categorized audit; counts approximate):

- Reader workspace pages/components (~162), unit/coverage tests (~130), public assets (40 deleted, 15 new `.webp` + 6 modified), content/MDX (~50), misc components (~41), e2e (33 new `*-ux.spec.ts` + support changes), marketing/public (~35), dashboard/library (~27), core lib (~19), auth pages (8), settings (5), billing UI (5), API layer (4).

## 2. Review method (what was deeply reviewed vs. mechanically verified)

- **Deep manual review (line level):** every backend reliability/freeze change; the billing WIP via a dedicated sub-audit (webhook lifecycle, dedup, rates, emails, migration); frontend security-sensitive surfaces (`admin.server.ts` env gate, middleware/client/store files confirmed unchanged), deleted-asset references, removed exports, API contract points.
- **Mechanical coverage:** the 454 frontend file changes are otherwise covered by `tsc`, ESLint, jest/vitest (1451 tests), and `next build`. This audit does not claim line-by-line review of the ~270 changed UI component/page files or the 33 new e2e specs.
- **Explicit non-claims:** Playwright e2e was not executed; live Paddle webhooks were not exercised; no production data or infrastructure was accessed.

## 3. Confirmed defects

### 3.1 Manuscript ingestion (fixed)

- P0 `MissingGreenlet` analysis crash from a shared-session rollback in the first-impression path (`87d204b6` regression) → stuck `processing` forever with no retry. Fixed in `first_impression_service` (quiet exits commit) + `analysis_consumer` (pre-commit value capture, resilient canon guard) + deterministic `complete_book_after_analysis` promotion. Regression test: `test_queue_first_impression_ineligible_commit_keeps_session_state` (asserts loaded ORM objects are not expired).
- P0 terminal failures invisible for non-rebuild runs → book stuck with 409 retry. Fixed (`settle_terminal_processing_failure` now writes author-visible failed state for every run kind).
- P0 budget blocks rendered as an endless "Queued for processing". Fixed (visible failed state + allowance message; task recorded terminally failed so run and book states agree).
- P1 corrupt DOCX/PDF/EPUB became 500s or silent worker failures; `.scriv.zip` preview crashed. Fixed (mapped to 400 with actionable messages; scrivener preview implemented).
- P1 no readable-text/empty-file gates. Fixed (whitespace TXT rejected; zero-readable-word uploads rejected with OCR guidance).
- P1 frontend swallowed real errors, had no local validation, fixed-delay polling, progress bar jump. Fixed (validation util matching backend limits, error surfacing, backoff + visibility pause, `<100%` queued progress).
- P2 library did not poll `pending`; cover edit failures were silent. Fixed.

### 3.2 Administrative freeze (new capability; defects prevented by design)

- Stale jobs could be auto-requeued by maintenance and consume tokens; retry buttons re-ran failed books; there was no operator-visible "interrupted import" state. Implemented `book_freeze_service` + worker/sweep/entry-point guards + a one-time global legacy script with a fixed persisted cutoff + frozen UI ("Import interrupted - please upload again", no Retry). See `STUCK_MANUSCRIPT_FREEZE.md`.

### 3.3 Duplicate processing (new protection)

- Identical rapid re-uploads created independent books and full analyses. Fixed with user-scoped SHA-256 duplicate blocking while an identical manuscript is pending/processing and a race-safe advisory lock. Failed/frozen books deliberately do not block a re-upload.

### 3.4 Billing WIP (pre-existing defects found by audit; fixed where safe)

- **D1 [fixed] — Reconciliation crashed on the second sync.** `sync_subscription_from_paddle` used a constant `SubscriptionEvent.source_event_id` (`reconcile:<sub>:state`), colliding with the unique constraint; the exception was not in the caught tuple, so the job (and the new internal endpoint) failed every run after the first. Fix: unique per-run event id. Regression test covers two consecutive syncs.
- **D2 [fixed] — Reconciliation could not downgrade paused/canceled subscriptions.** The sync hardcoded `event_type="subscription.updated"`, so provider-side `paused`/`canceled` kept the paid tier. Fix: map the provider status to `subscription.paused` / `subscription.canceled`. Regression tests assert tier `free`.
- **D3 [fixed] — Missing ORM index in the migration.** `SubscriptionEmailEvent.status` declares `index=True` but `20260919` never created `ix_subscription_email_events_status`. Fix: guarded index creation added to the (unpublished, untracked) revision.
- **D4 [fixed, cosmetic] — duplicate `pricing_url` assignment** in `send_subscription_cancellation`.

### 3.5 Pre-existing repository defects fixed while in scope

- `test_books_routes::test_get_book_overview_and_writer_workspace_use_cache` failed at HEAD because `build_book_world_stats` (added in `87d204b6`) added three DB calls the fake did not return. Test fake updated.
- `test_support_retrieval_service.py` had a Ruff import-order violation at HEAD. Fixed.
- Six frontend test failures from the uncommitted redesign were triaged in the release-readiness round: three were harness/environment drift (editor toolbar moved into a More-menu portal; the desktop manuscript specs needed an explicit desktop `matchMedia` stub) and one was a real information regression (`ReadingProgressRail` stopped rendering words-read). All six are fixed and the frontend suite is fully green; details in `RELEASE_READINESS_AUDIT.md`.
- `GET /books/series` returned 422 because `core_router`'s `GET /{book_id}` was registered before `series_router` (route shadowing). Fixed by include order + regression test.
- Provider circuit-breaker 503 wording ("LLM provider capacity…") bypassed the capacity-pause matcher and terminally failed in-flight chapters. Matcher broadened + parametrized tests.

## 4. Areas reviewed with no confirmed defect

- **Migrations:** `20260919` has both `upgrade()`/`downgrade()`, idempotency guards, no destructive upgrade operations; single Alembic head (verified by AST over all revisions); downgrade is intentionally blocked by policy and is not a true inverse on clean-bootstrap databases (documented).
- **Rate limits:** no new fail-open path; keys scoped by user/trusted client IP + edge token; Architect limit reduction 75→60/day is an intentional commercial change mirrored in the pricing catalog.
- **Auth/session frontend:** `middleware.ts`, `lib/api/client.ts` (CSRF, 401 refresh), Supabase clients, and `authStore` are unchanged by the WIP.
- **Webhook security:** signature verification precedes processing; internal job endpoints require `INTERNAL_JOB_SECRET`; webhook event dedup is race-safe.
- **Deleted assets/imports:** all 40 deleted binary assets have replacement references (`.png`→`.webp`, icon set); zero stale references; no TS modules deleted.
- **Debug code:** no `console.log`/`debugger`/TODO additions in the frontend diff.
- **API contracts:** changed call sites were checked against backend routes; the WIP's `messages: []` addition to advisor requests matches the backend's required field (it fixes a 422); no new raw endpoint strings introduced.

## 5. Test results (exact commands and outcomes)

Backend (Docker Compose Local):

```
docker compose -f docker-compose-local.yml exec -T api pytest tests/unit tests/integration -q
→ 2577 passed, 1 skipped
```

Frontend:

```
cd frontend && npm.cmd run type-check   → pass
cd frontend && npm.cmd run lint         → pass
cd frontend && npm.cmd test             → 277 files / 1452 tests passed (all six previously failing specs fixed)
cd frontend && npm.cmd run build        → success (Next.js production build)
```

Browser (Playwright, mock API): `npx playwright test` → 399 passed; the 3 failures were resolved and re-verified individually (both launch crawlers after raising their time budgets, smoke search green in isolation). Real-backend Chromium run: see `RELEASE_READINESS_AUDIT.md` §10.

Static analysis: `ruff check backend/app backend/tests backend/scripts` → clean.

Local end-to-end rehearsal (freeze + duplicate + fresh re-upload) executed against the local stack; results in `STUCK_MANUSCRIPT_FREEZE.md` §7. These are automated/local tests, not production verification.

## 6. Features not fully verified and why

- **Uncommitted frontend redesign (~450 files):** verified by typecheck/lint/unit tests/production build and targeted audits, but not visually reviewed or exercised in Playwright. 6 coverage tests in three unrelated WIP files fail standalone (pre-existing).
- **Billing WIP:** the critical paths (webhook dedup/lifecycle, reconciliation, emails) were audited and the two blocking defects fixed, but there is **no automated coverage** for `subscription_reconciliation_service` beyond my new tests, no tests for the new internal job endpoints, and no coverage for renewal-email crash recovery, unverified-email policy, or concurrent webhook delivery for lifecycle fields.
- **Trial budget policy:** trial accounts bypass `FREE_TOTAL_TOKEN_BUDGET` by design (`PAID_READING_TIERS` includes trial access). Documented, not changed.
- **Infrastructure:** production VPS, nginx timeouts under real large uploads, R2 (local stack uses the file-backed fallback), Celery queue depth/backlog behavior, and Sentry/PostHog delivery were not exercised.
- **Playwright e2e suite:** not run (33 new specs included in the tree).

## 7. Remaining risks and blockers

1. **E2E escape hatches — hardened in the release-readiness round.** The production admin override now requires the public mock flag **and** a non-empty secret **and** the server-only `ADMIN_E2E_ALLOW_PRODUCTION=1`; the graph debug handle is development-only; and `next.config.js` fails a production build when `NEXT_PUBLIC_E2E_MOCK_API=1` without the ack (verified). Remaining condition: confirm the Vercel Production environment does not set these variables anyway.
2. **Legacy stuck books require the operator freeze**; they will not self-heal. The repair sweep now emits `book_processing_stuck` for anything similar.
3. **Billing WIP test gaps** listed in §6; D1/D2 fixed but the broader billing surface remains thinly tested.
4. **Reconciliation time budget:** the daily reconcile task can make up to 25 Paddle calls at a 20s timeout on the shared maintenance queue with 5/10-minute soft/hard limits. Consider lowering `limit` or splitting later (documented, not changed).
5. **Duplicate guard scope:** only identical-file, same-user, actively-processing duplicates are blocked. Ready duplicates still re-analyze if uploaded deliberately.
6. Production migration must be applied with the standard Alembic safety checklist (`DEPLOY_AND_FREEZE.md` §2-3); the billing migration ships in the same tree.

## 8. Final GO / NO-GO

**CONDITIONAL GO** — see `RELEASE_READINESS_AUDIT.md` for the full certification, including the three P1 defects found and fixed after this table was written (series route shadowing, provider-capacity failure classification, consent-banner click blocking), the complete test matrix, and the exact production prerequisites. Conditions:

1. Commit the tree (currently uncommitted) and run the standard review.
2. Confirm the production frontend build does not set `NEXT_PUBLIC_E2E_MOCK_API` (and does not ship `ADMIN_E2E_TEST_SECRET`), and promote the same commit on Vercel.
3. Follow `DEPLOY_AND_FREEZE.md` for the migration pre-checks, backup, deploy, worker verification, worker-stop freeze cutover, and fresh-upload checks.
4. Treat the freeze itself as a separately approved action: **NO-GO for any automatic freeze**; the one-time global freeze is dry-run first, then one confirmed `--execute` command; the persisted cutoff guarantees fresh uploads are never affected.

The billing WIP remains thinly tested beyond the fixed reconciliation defects; the release-readiness audit recommends shipping it only with the full post-deploy verification run.
