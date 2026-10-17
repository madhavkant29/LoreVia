# Stale documentation archive

Summary of completed/stale one-off documents that were removed from the repository root and `docs/` on 2026-10-17, including what problem each documented, how it was solved, and the evidence that the work shipped.

Context: the October 2026 release-hardening work documented by these files is committed on the `author` branch (`87cd1733` "feat: harden ingestion reliability, release gating, and workspace redesign" and follow-ups `db12ec03`, `5a42158e`, `6f813641`, etc.).

## Deleted files

| File | What it was |
|---|---|
| `FULL_CHANGE_AUDIT.md` | Audit of the uncommitted release working tree at `87d204b6` |
| `RELIABILITY_AUDIT.md` | Manuscript-ingestion reliability audit (root causes RC-1…RC-7) |
| `STUCK_MANUSCRIPT_FREEZE.md` | Design/ops doc for the administrative freeze of stuck manuscripts |
| `RELEASE_READINESS_AUDIT.md` | Pre-production certification of the release candidate |
| `FINAL_RELEASE_CHECKLIST.md` | One-time GO checklist and condensed deployment steps |
| `PRODUCTION_VERIFICATION.md` | One-off post-deploy smoke procedure for the ingestion fixes |
| `docs/frontend-professional-ui-redesign-tracker.md` | Redesign checklist, `Status: Complete` (2026-09-14 → 2026-09-30) |
| `docs/uiux-late-stage-startup-audit.md` | UX startup audit, closed 2026-09-30 |
| `docs/backend-latency-optimization-plan-2026-09-05.md` | Latency optimization plan (implemented locally) |
| `docs/openai-retry-storm-fixed.md` | Incident postmortem, `Status: Fixed` (2026-07-26) |
| `docs/pricing-cost-analysis-2026-05-09.md` | Dated pricing/cost analysis |

## What the audits found and what was done

### 1. Manuscript ingestion reliability (P0/P1) — fixed and committed

The user-facing symptom: uploaded manuscripts stayed "processing" forever ("Extracting story data" / "Queued for processing"), the retry button returned 409, and uploads failed with generic errors.

| # | Problem | Fix |
|---|---|---|
| RC-1 (P0) | Analysis crashed for every book still `processing` when its last analysis ran: `queue_first_impression` internally called `db.rollback()`, expiring ORM objects; the next attribute access raised `MissingGreenlet`, and the handler's second rollback re-raised and poisoned the session. Book stuck in `processing` forever, retry 409. | Quiet exits now commit instead of rollback (`first_impression_service`); `analysis_consumer` captures values pre-commit and uses a resilient canon guard; deterministic `complete_book_after_analysis` promotion. Regression test asserts loaded ORM objects are not expired. |
| RC-2 (P0) | Terminal failures of initial (non-rebuild) runs wrote no book state: `status="processing"` with no `retry_actions`/`last_error`, retry 409, UI spun. | `settle_terminal_processing_failure` writes an author-visible failed state for every run kind. |
| RC-3 (P0) | Budget-exhausted uploads set `Book.status="error"` via bare SQL, leaving stale `writer_workspace.processing.stage == "queued"` → endless "Queued for processing" and no retry. | Visible failed state + allowance message; task recorded terminally failed so run and book states agree. |
| RC-4 (P1) | Corrupt-but-header-valid PDFs / broken DOCX raised library exceptions → masked 500s at preview, silent worker failures. `.scriv.zip` preview crashed with `ValueError`. | Mapped to 400 with actionable messages; Scrivener preview implemented. |
| RC-5 (P1) | Frontend collapsed real errors into "Upload failed. Please try again."; no client-side size/type validation; import polling used fixed delays; progress bar jumped to 100% while queued. | `getApiErrorDetail` reads axios details; validation util matching backend limits; errors surfaced; backoff + visibility pause; `<100%` queued progress. |
| RC-6/7 (P2) | Library did not poll `pending` books; cover edit failures were silent. | Library polls `pending` + `processing`; cover edit errors surfaced. |
| — | `GET /books/series` returned 422: `core_router`'s `GET /{book_id}` was registered before `series_router` (route shadowing); the upload modal's series selector failed silently. | Router include order fixed + regression test. |
| — | Provider circuit-breaker message `"LLM provider capacity is temporarily unavailable."` bypassed the capacity-pause matcher, terminally failing in-flight chapters during provider outages. | Matcher broadened (`llm capacity`, `llm coordination`, `llm provider capacity`, `ai capacity`); 10 parametrized tests. |
| — | Cookie-consent banner intercepted the login submit on ≤720px-tall viewports. | Auth shell reserves bottom clearance while the banner is visible; verified sign-in at 1280×720 without dismissing. |
| — | `ReadingProgressRail` stopped rendering words-read while keeping the prop and test (real information regression). | Renders `{wordsRead} of {totalWords} words` again. |

### 2. Duplicate processing protection — implemented

Rapid repeated uploads of an identical file created independent books and full analyses. Now blocked with a user-scoped SHA-256 fingerprint while an identical manuscript is pending/processing, race-safe via advisory lock. Failed/frozen books deliberately do not block a re-upload.

### 3. Administrative freeze for stuck manuscripts — implemented

Operators needed a way to stop stale pre-fix jobs from consuming tokens. Implemented `services/book_freeze_service.py` + `backend/scripts/freeze_legacy_manuscripts.py`: a one-time global freeze over incomplete books created before a fixed, persisted cutoff. It dismisses non-terminal executions/outbox rows, cancels import jobs, marks runs `failed_terminal`, releases reservations, writes an `AdminAuditEvent`, and records a `frozen` state that the UI renders as "Import interrupted - please upload again" with no Retry.

Deployment-race safety (deployment transition gate): `deploy.sh` records the cutoff during the deployment window (after migrations, before services start; `SKIP_LEGACY_CUTOFF_RECORD=1` is an emergency-only escape hatch). Pre-cutoff work is held at every provider choke point: dispatchers filter `TaskExecution.created_at >= cutoff`, outbox rows are cancelled (`legacy_cutoff`), worker claims dismiss delivered pre-cutoff messages, import jobs return `held_legacy_cutoff`, requeue refuses pre-cutoff books, and retry/continue/`ensure_project_writable` return 409. The freeze script skips books with post-cutoff processing activity (`skipped_processing_after_cutoff`) with a targeted `--include-processing-after-cutoff` override. A fail-closed rollback path (`backend/scripts/legacy_rollback_hold.py`) holds/restores legacy state at the data level; schema is never downgraded. Rehearsed locally: 7/7 transition-gate checks, freeze dry run over 140 candidates.

### 4. Billing reconciliation defects — found by audit, fixed

| # | Problem | Fix |
|---|---|---|
| D1 | `sync_subscription_from_paddle` used a constant `SubscriptionEvent.source_event_id` (`reconcile:<sub>:state`), colliding with the unique constraint; the exception was not caught, so every reconciliation run after the first failed. | Unique per-run event id + regression test for two consecutive syncs. |
| D2 | Reconciliation hardcoded `event_type="subscription.updated"`, so provider-side `paused`/`canceled` kept the paid tier. | Provider status maps to `subscription.paused`/`subscription.canceled`; tests assert tier `free`. |
| D3 | Migration `20260919` never created `ix_subscription_email_events_status` although the ORM declares `index=True`. | Guarded index creation added to the (then unpublished) revision. |
| D4 | Duplicate `pricing_url` assignment in `send_subscription_cancellation`. | Removed (cosmetic). |

### 5. Release-safety / security hardening (Phase 5) — implemented

- Production admin override requires the public mock flag **and** a non-empty secret **and** server-only `ADMIN_E2E_ALLOW_PRODUCTION=1`; otherwise real backend auth is used. `next.config.js` fails a production build when `NEXT_PUBLIC_E2E_MOCK_API=1` lacks the ack; `deploy.sh` refuses to run when `NEXT_PUBLIC_E2E_MOCK_API`, `ADMIN_E2E_TEST_SECRET`, or `ADMIN_E2E_ALLOW_PRODUCTION` is present anywhere in the deploy environment. Relationship-graph debug handle is development-only again.
- Sentry tags `release` (`RELEASE_SHA`) and `environment` for API and workers.
- Dependency/image hardening: Next.js `15.5.25`, Sharp `0.35.5`, Vitest/coverage `4.1.11`, gray-matter `js-yaml` `3.15.2`; retired `google-generativeai` replaced with `google-genai` (pinned `2.20.0` in `backend/requirements.txt`); Gemini fallback default moved to `gemini-2.5-flash`. Pinned Node 24.20.0 / Nginx 1.30.4 / Redis 7.4.11 images, non-root UIDs, read-only root filesystems, dropped capabilities, Trivy gates.
- Repository credential preflight and agent `git add -A` ban; area-scoped staging procedure.

### 6. Reliability baseline established

- Legacy cutoff gates and freeze/rollback scripts covered by `backend/tests/unit/test_legacy_cutoff_gates.py` and `test_legacy_rollback_hold.py`.
- Full suites green at release: backend 2,598 passed / 1 skipped; frontend 1,452 unit tests; Playwright smoke 108 passed; full E2E 399 passed; migration gate upgrade→downgrade→upgrade on a disposable DB.

## Still-open operational items (carried over, not resolved by this cleanup)

- **One-time legacy production freeze has NOT been executed.** Run the dry run then the confirmed freeze per `DEPLOY_AND_FREEZE.md` (kept) before/at next deploy.
- **Credential rotation.** `docs/PRODUCTION_READINESS.md` (kept as partially outdated) records that a local diagnostic transcript exposed secret-bearing env values; rotate OpenAI, Paddle, Supabase, R2/AWS, Redis/JWT, Docker Hub, Resend, and Sentry credentials at their providers before release.
- **Manual migration/rollout checklist** for `20260909_add_book_data_generations.py` lives in `docs/generation-migration-spec.md` (kept as partially outdated).
- **Known/deferred (do not block release):** processed-word accounting undercounts editor rebuild/import paths (capped by provider USD limits); advisor synopsis quotas limited by allowance reservations only; `AUTHOR_MAX_UPLOADS` display-only; trial accounts bypass `FREE_TOTAL_TOKEN_BUDGET` by design; export spool defaults to tmpfs; Playwright smoke order-sensitivity (run on clean `.next`).

## Kept as partially outdated (not deleted)

- `docs/PRODUCTION_READINESS.md` — 2026-09-10 audit whose blockers were largely resolved; retained because the credential-rotation obligation and migration prereqs remain open.
- `docs/generation-migration-spec.md` — generation-migration rollout checklist; retained because the manual production rollout steps remain outstanding.
- `DEPLOY_AND_FREEZE.md` (root) — retained because the production freeze/rollback runbook has not yet been executed. Note: its staging section still references the deleted audit files (`git add FULL_CHANGE_AUDIT.md RELIABILITY_AUDIT.md ...`); update it before reusing that section.
- `docs/page-by-page-ux-verification.md` — many routes still marked `Pending`; needs a done/abandon decision.
- One-off rollout/measurement runbooks (`performance-rollout-runbook.md`, `processing-allowances-rollout.md`, `backend-stabilization-runbook.md`, `latency-postgres-runbook.md`, `auth-cache-measurement.md`) — small operational gates that may still be needed or can be consolidated.
- `docs/revenue-scenarios-2026-05-24.md` — dated revenue modeling, initially marked stale but restored on request; its pricing-cost-analysis cross-reference now points to a file that was removed from `docs/`.

## Where the shipped behavior lives now (instead of these docs)

- Freeze ops: `backend/app/services/book_freeze_service.py`, `backend/scripts/freeze_legacy_manuscripts.py`, `backend/scripts/legacy_rollback_hold.py`, `DEPLOY_AND_FREEZE.md` §9–10.
- Ingestion fixes: `backend/app/services/first_impression_service.py`, `processing_pause_service.py`, `extraction_budget_service.py`, `workers/consumers/analysis_consumer.py`, `utils/books/imports.py`.
- Regression coverage: `backend/tests/unit/test_legacy_cutoff_gates.py`, `test_legacy_rollback_hold.py`, parametrized capacity-matcher tests, series-shadowing test.
- Release machinery: `deploy.sh` (E2E flag guard, cutoff recording, preflight), `next.config.js` build guard.
