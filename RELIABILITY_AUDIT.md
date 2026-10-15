# LoreVia Reliability Audit — Manuscript Ingestion & Author Workflows

Scope: account creation → project creation → manuscript selection → upload → storage → database persistence → background processing → AI analysis → results visible to the author. Fixes were implemented and verified against a disposable local stack (`docker-compose-local.yml`). No production system was accessed.

Follow-up work added after the first audit round:
- Administrative freeze for stale manuscript-processing jobs (`STUCK_MANUSCRIPT_FREEZE.md`).
- Duplicate-upload protection (content fingerprint scoped to the authenticated user).
- Frozen/uninterrupted import UI state for authors.
- Fixes for confirmed billing reconciliation defects found by the full working-tree audit (`FULL_CHANGE_AUDIT.md`).

Architecture verified from the repository (not assumed):
- Frontend: Next.js App Router. Uploads are direct multipart `POST /api/v1/books/upload` and `POST /api/v1/books/{id}/manuscript/import` through the Next.js rewrite proxy.
- Backend: FastAPI + Gunicorn/Uvicorn workers. Uploaded files are buffered in the API process and written to S3-compatible object storage (Cloudflare R2 via boto3, `app/core/storage.py`). There is no presigned-URL browser upload flow.
- Processing: Celery + Redis with durable `TaskExecution`/`TaskDispatchOutbox` rows, queue-per-role workers, and maintenance/reconciliation sweeps.
- Database: PostgreSQL + pgvector.
- Auth: Supabase-backed credentials with cookie sessions + CSRF; Sentry/PostHog integration exists and is used when configured.

## 1. Root causes confirmed (reproduced locally or proven by code path + test)

### RC-1 (P0) Analysis crashed for every manuscript that finished extracting while still processing
- Path: `app/workers/consumers/analysis_consumer.py::_analyse_chapter_in_generation`.
- Introduced by commit `87d204b6`, which added a `queue_first_impression(...)` call in the analysis completion path. For any book that is not yet `status == "ready"` (i.e. essentially every book while its last analysis runs), `queue_first_impression` internally called `db.rollback()` as a quiet-exit. A rollback expires every ORM object loaded in the caller's session. The next synchronous attribute access after the commit (`book.id`, `chapter.number`, ... in the live canon-guard call) raised `sqlalchemy.exc.MissingGreenlet`; the `except SQLAlchemyError` handler then called `db.rollback()` again on a poisoned connection, which raised a second `MissingGreenlet` and escaped to the task boundary.
- Effect: the chapter's analysis was recorded as `failed` (non-retryable), `analysis.failed_chapters` was written into the pipeline, the book stayed `status="processing"` forever, the 5-minute repair sweep refused to promote it (blocking failure present), and the retry endpoint returned 409 because no retryable state was recorded anywhere.
- Reproduced with a local upload: book froze in `processing` with `stage: "ready"`, `is_fully_ready: true`, `pipeline.analysis.failed_chapters: [1]`, and worker logs showing the two `MissingGreenlet` tracebacks.
- This matches the user report: an uploaded manuscript that never becomes usable and gives no explanation.

### RC-2 (P0) Terminal processing failures were invisible and unrecoverable for non-rebuild runs
- Path: `app/services/processing_pause_service.py::settle_terminal_processing_failure` (only wrote book state when `execution.rebuild_run_id` was set).
- Any terminal failure of an initial upload run (parser crash, empty payload, exhausted attempts, stale lease release) left `Book.status="processing"` with no `retry_actions` and no `last_error` in `writer_workspace`. `_book_has_retryable_processing_state` then returned False, so `POST /books/{id}/processing/retry` responded 409.
- Effect: "stuck processing" book with no user-visible error and no recovery action.

### RC-3 (P0) Budget-limited uploads showed "Queued for processing" forever
- Path: `app/services/extraction_budget_service.py` — on `budget_exhausted` / `insufficient_remaining_budget` it set `Book.status="error"` via a bare SQL update without touching `writer_workspace`. The frontend derives stage from the stale `writer_workspace.processing.stage == "queued"`, so trials/free-access authors saw an endlessly queued book. The book also could not be retried (`_book_has_retryable_processing_state` false).
- Trials grant Author access (`billing_utils.billing_access_tier`), so a full manuscript that exceeds `FREE_TOTAL_TOKEN_BUDGET` (150,000 tokens) is a realistic trigger for the reported "complete manuscript would not work".

### RC-4 (P1) Corrupt documents either 500'd or, in the worker, became invisible terminal failures
- Paths: `app/utils/books/imports.py` (docx/pdf/epub/scrivener parsing) and `build_import_preview`.
- Corrupt-but-valid-header PDFs and broken DOCX packages raised library-specific exceptions (`fitz.FileDataError`, `PackageNotFoundError`, `BadZipFile`, ...) that were not mapped: `/books/upload/preview` returned a masked 500, and in the ingestion worker they became terminal failures combined with RC-2.
- `.scriv.zip`/`.scrivzip` uploads (accepted by the backend) crashed preview with `ValueError("Unsupported format for preview")` because `build_import_preview` had no scrivener branch.

### RC-5 (P1) Authors could not tell why uploads failed
- Frontend: `getApiErrorDetail` only read axios `response.data.detail`. Import-job polling threw plain `Error`s (`waitForManuscriptImport`), which were replaced with the generic "Upload failed. Please try again."; there was no size/type validation anywhere in the upload modal; the accept list omitted backend-supported formats (`.fountain`, Scrivener) and advertised Fountain in screenplay copy while filtering it out; the progress bar jumped to 100% during "Queued".
- Backend: no readable-text gate for scanned PDFs / whitespace-only text files, so the failure surfaced later in the worker instead of at the door.

### RC-6 (P2) Library did not poll `pending` books
- `LibraryClient.tsx` polled only `status === "processing"`. A freshly uploaded book sits in `pending` until the worker claims it, so the library card could stay stale after refresh.

### RC-7 (P2) Cover edit failures were silent
- `CoverEditOverlay` had no validation and no catch; failed `updateCover`/`deleteCover` calls were unhandled rejections with no user feedback.

## 2. Potential causes requiring production verification (not reproducible locally)

Distinguish these from confirmed root causes:
- Free/reader-tier uploads: `POST /books/upload` and import routes require Author/Architect access and return 403 otherwise. The UI hides author mode for those tiers, but any stale client or aged trial could surface a 403 the user cannot interpret. Confirm the reported user's tier/access state at the time of failure.
- Large-file network behavior: 100 MB uploads are buffered by nginx (`client_max_body_size 110m`, `client_body_timeout 300s`, `proxy_read_timeout 600s`) and the API before storage. Slow connections can still hit proxy timeouts; local reproduction used small files. Check nginx access/error logs for 499/504 around the reported time window.
- Historical stuck rows: books stuck `processing` before this fix will not self-heal once `analysis.failed_chapters` is recorded (the repair sweep intentionally refuses to promote them). They now emit an alertable `book_processing_stuck` log but need operator retry/resolution.
- Redis/Celery outages: broker failures leave rows `pending_dispatch`; the outbox reconciler recovers them. Verify broker availability around the incident window.
- Sentry finding: search for `MissingGreenlet` / `analysis_task_non_retryable` events produced by the last release; their count estimates how many users were affected.

## 3. Files modified

Backend:
- `backend/app/workers/consumers/analysis_consumer.py` — pre-commit value capture, quiet rollback helper, deterministic ready promotion, resilient canon-guard failure handling.
- `backend/app/services/first_impression_service.py` — quiet exits commit instead of rolling back the caller's session.
- `backend/app/services/pipeline_state_service.py` — new `complete_book_after_analysis()` and shared `_write_ready_book_state()`; public `book_processing_has_blocking_failure()`.
- `backend/app/services/processing_pause_service.py` — terminal failures now write author-visible failed state for all run kinds; user-safe error text.
- `backend/app/services/extraction_budget_service.py` — budget blocks write a visible failed state.
- `backend/app/services/book_upload_service.py` — structured upload success/failure logs.
- `backend/app/services/manuscript_import_job_service.py` — Sentry capture with sanitized job context.
- `backend/app/services/manuscript_import_request_service.py` — pass real filenames into parsing for accurate error messages.
- `backend/app/utils/processing_error_utils.py` (new) — maps raw errors to author-safe, actionable messages.
- `backend/app/utils/books/imports.py` — parser error mapping to HTTP 400, scrivener preview support, real filename propagation.
- `backend/app/utils/upload_security_utils.py` — reject whitespace-only text uploads.
- `backend/app/workers/tasks/extraction_tasks.py` — budget-blocked books report a terminal task failure instead of success.
- `backend/app/workers/tasks/maintenance_tasks.py` — alertable `book_processing_stuck` detection.
- `backend/app/api/v1/routes/books/imports.py` — upload gate: reject files with no readable text (e.g. scanned PDFs) with a clear 400.

Frontend:
- `frontend/src/lib/validation/manuscriptUpload.ts` (new) + test — client-side limits matching backend config (100 MB upload, 20 MB/file, 20 files, 60 MB total, 5 MB cover), format checks, legacy `.doc` guidance.
- `frontend/src/components/modals/upload/useUploadModalController.ts` — real error surfacing (axios details, job errors, timeouts, offline), pre-submit validation, cover validation, retry error handling.
- `frontend/src/components/modals/UploadModal.tsx` — progress bar no longer jumps to 100% while queued.
- `frontend/src/components/modals/upload/UploadSourceStep.tsx`, `ExistingProjectImportStep.tsx`, `AdvancedImportSettings.tsx` — validation wiring, corrected accept lists (`.fountain`, Scrivener), format/limit copy.
- `frontend/src/lib/api/books.ts` — import polling with backoff + tab-visibility pause; server error text preserved.
- `frontend/src/app/(dashboard)/library/LibraryClient.tsx` — poll `pending` books.
- `frontend/src/components/ui/CoverEditOverlay.tsx` — cover validation and visible failures.

Tests:
- `backend/tests/unit/test_ingestion_reliability.py` (new).
- Updated: `test_analysis_consumer.py`, `test_extraction_budget_service.py`, `test_first_impression_service.py`, `test_books_routes.py` (pre-existing fake-DB mismatch from `87d204b6`), `test_support_retrieval_service.py` (pre-existing Ruff import order).
- Frontend: `manuscriptUpload.test.ts` (new), `UploadModal.test.tsx`, `runtime-reader-more.coverage.test.tsx`, `books-lifecycle-contracts.test.ts`.

Not touched: the uncommitted billing/subscription work in the working tree, and unrelated frontend redesign work. No `.env` files, migrations, or production systems were modified.

## 4. Fixes implemented

1. Root-cause fix for RC-1: `first_impression_service` quiet exits now `commit()` (releases advisory/row locks without expiring caller state). `analysis_consumer` captures plain values (`book_id_value`, `book_user_id_value`, `chapter_number_value`, `content_version`, `author_mode`, title) before commits/rollbacks and uses them after; canon-guard/rollback failures can no longer mark the chapter failed.
2. Deterministic completion: when the final analysis succeeds, `complete_book_after_analysis` promotes the book to `ready` immediately (row-locked, idempotent, skips rebuilds/blocking failures) instead of waiting up to 5 minutes for the repair sweep.
3. Failure visibility: `settle_terminal_processing_failure` now writes `status="failed"`, `retry_actions=["retry_extraction"]`, and an author-safe `last_error` for non-rebuild runs too, so the retry endpoint works and the UI shows "Processing failed" with an actionable message.
4. Budget blocks produce the same visible failed state with an allowance/upgrade message; the task is recorded as terminally failed so run state and book state agree.
5. Input hardening: corrupt DOCX/PDF/EPUB/Scrivener files map to HTTP 400 with a clear message; whitespace-only text files and documents with zero readable words (scanned PDFs) are rejected at upload; Scrivener preview works.
6. Frontend truthfulness: client-side size/type/count validation with the same numbers as the backend; real server/job error messages instead of the generic fallback; queued/percent progress fixed; import polling backs off (1.5s → 8s) and pauses in hidden tabs; `pending` books polled in the library; cover failures surfaced.
7. Observability: `book_upload_stored`/`book_upload_failed` structured logs (no filenames or contents), `book_processing_stuck` error log for alerting, Sentry exception capture for import jobs with job/book/user tags and a failure category, and author-safe error text that never leaks internals into `writer_workspace`.
8. Administrative freeze (`app/services/book_freeze_service.py` + `scripts/freeze_legacy_manuscripts.py`): one-time global freeze of legacy incomplete jobs (books created before a fixed, persisted cutoff) without deleting content or resuming work — dismisses non-terminal executions/outbox rows, cancels import jobs, marks runs failed_terminal, releases reservations, writes an `AdminAuditEvent`, and records a `frozen` state the UI renders as "Import interrupted - please upload again" with no Retry. Workers, sweeps, retries, imports, reprocess entry points, and fresh uploads all behave correctly (details in `STUCK_MANUSCRIPT_FREEZE.md`).
9. Duplicate-upload protection: `source_fingerprint` (SHA-256) stored on the book workspace; a user-scoped, race-safe check rejects an identical file while another copy is pending/processing, without blocking re-uploads after failure/freeze or revised versions.

Idempotency/duplicates: retries reuse `TaskExecution.identity_key` and the outbox, so re-dispatch cannot double-create work. New uploads still create a new book on repeat submission (see remaining risks).

## 5. Tests added and actual results

Executed via the repository's Docker Compose Local stack (`docker compose -f docker-compose-local.yml exec -T api pytest ...`):
- Full backend suite: `2567 passed, 1 skipped` (`tests/unit` + `tests/integration`).
- New regression files: `tests/unit/test_ingestion_reliability.py` (17 tests: friendly error mapping, terminal-failure book state, the `queue_first_impression` session-expiry regression, deterministic ready promotion, budget-block visibility, blank/corrupt input rejection, scrivener preview), `tests/unit/test_book_freeze_service.py` (10 tests), `tests/unit/test_upload_duplicate_guard.py` (4 tests), `tests/unit/test_freeze_task_guards.py` (5 tests), `tests/unit/test_subscription_reconciliation_fixes.py` (3 tests).
- Updated tests assert the new contracts: quiet first-impression exits commit (not rollback); budget blocks write visible failed state; analysis calls `complete_book_after_analysis` on the final analysis.

Frontend (`cd frontend && npm.cmd test`): `1445 passed`; 6 failures in 3 files are pre-existing failures of unrelated uncommitted redesign work (`SharedRichTextEditor.coverage.test.tsx`, `reader-large-pages.coverage.test.tsx`, `runtime-zero-client-extra.coverage.test.tsx` — verified failing standalone; their source files are modified by that pending work, and no file in this audit is involved in the failing assertions). New/updated tests: 12 validation tests, 3 `UploadModal` tests (local rejection, server error surfacing, progress under 100%), cover error-path test, `processingStatus` frozen cases, `ResponsivenessStatus` frozen rendering (no Retry, message + fresh-upload link), and the updated import-poll backoff contract (16/16 passing).

Static checks: `ruff check backend/app backend/tests backend/scripts` — clean; frontend `npm run type-check` — clean; frontend `npm run lint` — clean; frontend `npm run build` — success.

End-to-end verification on the local stack (real API → storage → Celery workers → Postgres):
- Fresh TXT upload: `pending → processing (parsing → analyzing) → ready` in ~24s, `pipeline.analysis.status=succeeded`, `failed_chapters=[]`.
- Corrupt PDF upload: HTTP 400 with "We couldn't read this manuscript. The file may be corrupted or partially saved..."
- Whitespace-only TXT upload: HTTP 400 "empty.txt is empty. Choose a file that contains manuscript text."
- Corrupt chapter import: HTTP 400 with the real filename; valid chapter import: 200 with imported chapter and analysis dispatched.
- Freeze rehearsal: dry-run identified only the stale book; execute froze it; `stage=frozen`, `retry_available=false`, retry API 409; worker restart left 0 non-terminal executions/runs; a fresh upload of the same manuscript reached `ready`; an immediate identical duplicate was rejected 409.
This is local verification only; it is not production end-to-end verification.

## 6. Remaining risks

- Books already stuck in production (pre-fix) will not self-heal; they now log `book_processing_stuck`, and the one-time legacy freeze (`scripts/freeze_legacy_manuscripts.py`, see `STUCK_MANUSCRIPT_FREEZE.md`) pauses them without deleting content or resuming work. Operators must run the freeze (dry run first) — it is not automatic.
- Analysis completion now also promotes books whose extraction finished earlier; concurrent chapter analyses are protected by a `SELECT ... FOR UPDATE` on the book row, but production load testing for many-chapter books was not performed here.
- Uploads remain fully buffered (nginx + API memory) with a 100 MB cap; very slow clients can still hit proxy timeouts, and concurrent large uploads can pressure API worker memory. No streaming/multipart upload was introduced (deliberate; avoids new infrastructure).
- No upload-level duplicate detection: submitting the same manuscript twice creates two books. The UI disables submit while uploading, but a timeout-then-retry can duplicate. Left as a documented product decision.
- Import polling still has a 30-minute client deadline; a legitimate job slower than that requires the user to retry from the library.
- Analysis failures of already-processed chapters are retried through `retry_extraction`, which re-queues unprocessed chapters; a fully processed book with one failed analysis is recovered by the repair sweep only if the failure is not in `failed_chapters`. With RC-1 fixed this path should be rare; monitor for `book_processing_stuck`.

## 7. Required environment configuration

No new environment variables are required. Confirm the production environment already provides:
- `SENTRY_DSN` (API + workers) so the new import-job capture and stuck-book signals reach the existing Sentry project.
- Standard storage/Celery/Redis/DB variables (unchanged).
- nginx `client_max_body_size` ≥ 110m and generous proxy timeouts (already in `ops/nginx/nginx.conf`).
- `GUNICORN_TIMEOUT` is not the limiting factor for Uvicorn workers but leave the current default.
Do not change `.env` files as part of this work.

## 8. Recommended production monitoring

All through the existing Sentry project (no new paid services):
1. Alert on `book_processing_stuck` log events (maintenance sweep) — one per affected book with `book_id`/`user_id` only.
2. Alert on Sentry issues tagged `job_id`/`book_id` from the manuscript import job capture (`manuscript_import_job_failed`).
3. Track `MissingGreenlet` occurrences: should drop to zero after deploy (RC-1).
4. Track upload/import 4xx/5xx rates and `book_upload_failed` logs.
5. PostHog already captures `upload_failed`, `processing_failed`, `processing_completed`; monitor the ratio for regressions in the new funnel.
6. Optional: count books in `status='processing'` older than 30 minutes daily (SQL) as a data-quality canary.

## 9. Manual verification checklist

See `PRODUCTION_VERIFICATION.md` for the full procedure. Minimal list:
- [ ] Upload a small valid TXT/DOCX as an Author-tier account; book reaches `ready` without a 5-minute delay; analysis shows no failed chapters.
- [ ] Upload a corrupt PDF; upload is rejected with a readable message (no 500, no stuck book).
- [ ] Upload a whitespace-only TXT; rejected with "is empty".
- [ ] Add a corrupt chapter file to an existing book; error message states the file may be corrupted.
- [ ] Refresh during processing; progress continues from the server state.
- [ ] Force-fail a processing book (or use a known-stuck legacy book); UI shows "Processing failed" with a working Retry.
- [ ] Trigger a budget-limited trial upload if feasible; UI shows the allowance message, not an endless queue.
- [ ] Check Sentry for new tags (job_id/book_id) and no sensitive content.

## 10. Remaining deployment steps

1. Review `FULL_CHANGE_AUDIT.md` and commit the change set separately from the in-flight billing/redesign work where practical (everything is currently uncommitted in the working tree).
2. Follow `DEPLOY_AND_FREEZE.md` for the VPS deployment: environment checks, migration pre-checks, backup, deploy, worker verification.
3. No database migration is required by the ingestion reliability or freeze fixes themselves; the working tree also ships the billing migration `20260919_subscription_lifecycle` (see the deploy runbook).
4. After deploy, run the `PRODUCTION_VERIFICATION.md` checklist (now including frozen/duplicate scenarios).
5. Operators review legacy `processing` books using the `book_processing_stuck` log/SQL canary and run the freeze dry run for the verified affected account before any `--execute`.
