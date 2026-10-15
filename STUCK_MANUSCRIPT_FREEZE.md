# Stuck Manuscript Freeze — Architecture, Protections, and Operations

Status: implemented and verified in the local Docker stack. Production freeze has NOT been executed.
Audience: operators and engineers responsible for the VPS deployment.

Recovery policy: **no automatic recovery.** Existing incomplete processing is frozen permanently (until explicitly released) and users are asked to upload again. The freeze is a one-time global operation over all incomplete books created before a fixed, persisted cutoff (`scripts/freeze_legacy_manuscripts.py`).

## 1. Confirmed root causes

Local reproduction (real upload through the local stack: API → local S3-compatible storage → Celery workers → Postgres) confirmed:

1. **RC-1 — Analysis crashed on every book whose extraction finished before analysis (P0).**
   Commit `87d204b6` added `queue_first_impression(...)` inside the analysis completion path. For a book that is not yet `status="ready"` (all books while their final analysis runs), the helper's quiet-exit path called `db.rollback()` on the caller's shared session, expiring every loaded ORM object. The next synchronous attribute access raised `sqlalchemy.exc.MissingGreenlet`; a second rollback in the handler raised again and escaped, marking the chapter analysis terminally failed. The book stayed `processing` forever, the repair sweep refused to promote it (`analysis.failed_chapters` present), and retry returned 409 because no retryable state existed.
   This explains a manuscript frozen at "Extracting story data" indefinitely.

2. **RC-2 — Terminal failures were invisible for non-rebuild runs (P0).**
   `settle_terminal_processing_failure` wrote book state only for editor-project rebuilds. Initial uploads that failed terminally kept `Book.status="processing"` with no `retry_actions`/`last_error`, so the retry endpoint returned 409 and the UI spun forever.

3. **RC-3 — Budget blocks showed as endless queueing (P0).**
   `extraction_budget_service` set `Book.status="error"` with a bare SQL update, leaving `writer_workspace.processing.stage == "queued"`. The UI derived "Queued for processing" forever. Trial accounts (which have Author access) skip the free token budget entirely (`has_paid_reading_access` treats trial as paid), so repeated uploads could accumulate processing without a visible allowance message.

4. **RC-4 — Corrupt documents became invisible failures (P1).**
   Corrupt but header-valid PDFs and broken DOCX packages raised library exceptions that produced 500s at preview and silent terminal failures in workers. `.scriv.zip` preview crashed outright.

5. **RC-5 — Errors were not surfaced to authors (P1).**
   Frontend collapsed non-axios and job errors into "Upload failed. Please try again."; there was no client-side size/type validation; import polling was fixed-delay with no visible server error.

6. **RC-6 — Library did not poll `pending` books (P2).** Fresh uploads could appear stale after refresh.

7. **Why the screenshot showed 0% despite word counts:** chapter rows are created and `total_words`/`total_tokens`/`total_chapters` are set during staging (Book row), but `writer_workspace.processing.progress_pct` is computed from completed chapters. Chapters that were staged but never extracted (because the run died at analysis/terminal failure) leave `chapters_completed=0` while Book-level totals show word counts.

8. **Processing + Retry simultaneously:** the pre-fix repair path could mark a book failed (retry button) while a stale `writer_workspace.processing.status` still said processing, or vice versa — the two states were allowed to diverge because `write_book_terminal_processing_state` only applied to rebuilds while the frontend derived stage from the workspace.

## 2. Additional defects discovered during this task

- **Duplicate uploads.** Rapid repeated uploads of an identical file create independent books and full analyses. Now blocked while an identical manuscript is actively processing (content SHA-256 scoped to the authenticated user).
- **Billing (WIP audit findings, fixed where safe):** see `FULL_CHANGE_AUDIT.md`. The reconciliation job crashed on its second run (`SubscriptionEvent.source_event_id` collision) and could not downgrade paused/canceled subscriptions; both are fixed and regression-tested.
- **`.scriv.zip` preview 500** (no scrivener branch) — fixed.

## 3. Freeze architecture and state handling

No database migration was added. The freeze flag lives inside `writer_workspace.processing`, which already round-trips through the existing normalizers:

```json
"processing": {
  "status": "failed",
  "stage": "failed",
  "frozen": true,
  "freeze_kind": "administrative_freeze",
  "freeze_reason": "interrupted_legacy_import",
  "freeze_message": "Import interrupted - please upload again. Your project and files have been preserved.",
  "frozen_at": "<iso8601>",
  "freeze_actor_user_id": "<uuid|absent>",
  "retry_actions": [],
  "last_error": "<same message>",
  "...": "previously recorded processing fields are preserved"
}
```

### Cutoff model (fixed and persisted, never dynamic)

- The freeze cutoff is stored once as an `AdminAuditEvent` marker (`action_type="legacy_freeze_cutoff_recorded"`, `metadata_json={"cutoff": "<iso8601>"}`). No migration or new table is needed, and the audit table is not pruned.
- Resolution order: an explicit `--cutoff` value, then the persisted marker, then the current time (which is then persisted by the first execution).
- Write-once: if a persisted cutoff exists and a different `--cutoff` is passed, the script refuses to run.
- Only books with `created_at < cutoff` are candidates. Books created after the cutoff (fresh uploads) are never frozen, even when targeted explicitly with `--book-id` (they are reported as `skipped_after_cutoff`).
- Jobs already in flight at the cutoff are handled safely: the freeze dismisses running executions and the workers stop before their next provider call; an LLM HTTP request already in flight may still complete once (unavoidable), and the script reports the in-flight count before execution.

Freezing one book (`app/services/book_freeze_service.py::freeze_book_processing`) transactionally:

1. Takes a per-book advisory lock plus `SELECT ... FOR UPDATE` (race-safe against a concurrent freeze/retry).
2. Is idempotent — an already frozen book returns `already_frozen` without touching rows or writing a second audit event.
3. Refuses ready books; editor projects are frozen only when the caller opts in, which the one-time legacy freeze does (interactive flows do not).
4. Dismisses every `TaskExecution` in `pending_dispatch | queued | running | paused` with `error_category="administrative_freeze"`, cancels their `TaskDispatchOutbox` rows, and releases their processing-word reservations.
5. Marks non-terminal `BookProcessingRun` rows `failed_terminal`.
6. Cancels `ManuscriptImportJob` rows (`queued | running | cancel_requested`) with `cancel_requested=true` so a running job aborts cooperatively.
7. Sets `Book.status="failed"` and writes the freeze record above. Chapters, chapter files, cover, metadata, and any completed analysis results are untouched.
8. Writes an `AdminAuditEvent` (`action_type="book_processing_frozen"`, `target_book_id`, `metadata_json` counts: dismissed executions, runs, import jobs, preserved chapters, tokens).

`unfreeze_book_processing` clears the flag, leaves the book in a normal failed state with `retry_actions=["retry_extraction"]`, and never starts work itself.

User-facing behavior (`BookProcessingOut` / frontend):

- `stage: "frozen"`, `current_step_label: "Import interrupted"`, `frozen: true`, `freeze_message`, `retry_available: false`.
- Library cards, the book overview panel, and the status strip render "Import interrupted" with the message "Import interrupted - please upload again. Your project and files have been preserved." and an **Upload again** link to `/library`.
- No Retry button is shown, and the API rejects retry attempts with 409 + the same message.

## 4. Celery cancellation and cost protections

Freezing is cooperative and database-authoritative:

- **Queued tasks:** workers claim executions through `claim_task_execution`, which only accepts `queued/running`; dismissed rows make claims fail. Worker restarts re-deliver at most a no-op task.
- **Running tasks:** every book pipeline checks the freeze before provider calls:
  - `process_book_ingestion_and_queue` (entry) — skip.
  - `_process_chapter_in_generation` — checks after staging, before embeddings, before LLM extraction, before character resolution, and analysis dispatch is separately guarded.
  - `collect_chapter_llm_extraction` is preceded by the same authoritative check inside the caller immediately before the LLM wave.
  - `analyse_chapter` — checks at load, before summaries, before plot threads, and before the live canon guard.
  - `update_character_embedding_task` — checks after loading the book.
  - `write_book_pause_state` / `write_book_terminal_processing_state` refuse to overwrite frozen state (late failures cannot re-enable retry).
- **Sweeps:** frozen books are `status="failed"`, so the 5-minute repair scan and the stalled requeue (which both filter on `processing`) skip them; their paused executions are dismissed, so the capacity-resume sweep and stale-lease release cannot reactivate them.
- **Entry points:** `ensure_project_writable` (imports, reprocess) and `retry_book_processing` / `continue_book_processing` reject frozen books with 409.

Explicitly out of scope: an external LLM HTTP request that is already in flight cannot be cancelled and may still incur its cost. The freeze prevents all subsequent avoidable requests; the verification steps in `DEPLOY_AND_FREEZE.md` show how to confirm no new rows/runs appear after a worker restart.

## 5. Duplicate-processing protections

- `Book.writer_workspace.source_fingerprint` stores SHA-256 of the uploaded file bytes (first-class workspace field, preserved by normalization).
- On upload, the API computes the fingerprint and rejects (409) when the same user already has an **identical file in `pending` or `processing`**:
  "This exact manuscript is already being processed in another project. Wait for that import to finish, or upload a revised file."
- The check is scoped to the authenticated user, uses only the caller's own books, never merges or deletes projects, and deliberately does **not** block re-uploads after failure or freeze (required for the post-incident workflow) and does not block revised files.
- Race-safe: an advisory lock keyed `(user, fingerprint)` wraps the duplicate check and the book insert, so two simultaneous identical uploads cannot both proceed.
- Retries remain idempotent through `TaskExecution.identity_key` + `TaskDispatchOutbox` (re-dispatch reuses the same Celery task id).

## 6. Free-tier usage safeguards

- Free allowances remain server-enforced at three points: `require_author_access` (upload/import/reprocess), `ensure_active_word_capacity` / `ensure_source_storage_capacity` (pre-upload), and `reserve_processing_words` / `apply_ingestion_token_budget` (processing). No limits were raised or bypassed.
- Freezing releases reserved (not consumed) processing-word reservations for dismissed executions, so the freeze does not charge for work that never runs.
- Budget-blocked uploads now show a visible failed state with the allowance message instead of an endless queue.
- Known policy note (not changed): trial accounts are treated as paid for the ingestion token budget (`PAID_READING_TIERS`), so a trial user can exceed `FREE_TOTAL_TOKEN_BUDGET`. The duplicate guard and the freeze cover the observed abuse path (repeated identical uploads). Changing trial budget policy requires a product decision and is documented, not implemented.

## 7. Automated test results

Backend (`docker compose -f docker-compose-local.yml exec -T api pytest tests/unit tests/integration -q`): **2567 passed, 1 skipped**.
New freeze/duplicate/billing regression files (all passing):

- `tests/unit/test_legacy_freeze.py` — cutoff parsing, write-once persistence, conflicting explicit cutoff refusal, dry-run does not modify or persist, global execute freezes pending/failed/editor-project legacy books, post-cutoff books never frozen, repeat runs idempotent, `--record-cutoff` touches no book, targeted unfreeze requires `--book-id` and starts no work, explicit `--book-id` cannot bypass the cutoff.
- `tests/unit/test_book_freeze_service.py` — freeze marks/dismisses (queued and paused)/cancels/audits, idempotency, ready/editor skips, unfreeze leaves no work, retry + writability guards, frozen state cannot be overwritten, repair sweeps skip frozen books, payload contract, workspace round-trip.
- `tests/unit/test_upload_duplicate_guard.py` — fingerprint determinism, per-user scoping, failed/ready re-upload allowed, missing fingerprint.
- `tests/unit/test_freeze_task_guards.py` — analysis skips without provider calls, process_book skips, chapter extraction skips, analysis dispatch skips, payload reports frozen.
- `tests/unit/test_subscription_reconciliation_fixes.py` — repeatable reconciliation sync, paused/canceled downgrades.

Frontend (`cd frontend && npm.cmd test`): **1445 passed**; 6 failures are pre-existing, unrelated to this work (editor/reader coverage specs belonging to the uncommitted redesign; verified failing standalone). New tests: `processingStatus.test.ts` frozen cases and `ResponsivenessStatus.test.tsx` (no retry, "Import interrupted", "Upload again" link). `npm run type-check`, `npm run lint`, and `npm run build` all pass.

Local end-to-end rehearsal (real API, workers, Postgres, global legacy freeze):

- Dry run listed every incomplete pre-cutoff book (139 candidates on the local dev database, including a deliberately stale queued job and an editor project) and skipped the already-frozen one.
- Execute: `changed=138 skipped=1`; the cutoff was persisted. A repeat execute reported `cutoff_source=persisted changed=0 skipped=139` (fully idempotent).
- The stale queued job was dismissed: `task_executions` non-terminal = 0, outbox pending = 0, run = `failed_terminal`.
- After restarting extraction/analysis/maintenance workers and waiting 75 seconds: 139 frozen books, `non_terminal_work=0`, `active_runs=0`.
- A fresh upload after the freeze reached `ready` in ~16 seconds and was never frozen.
- A book created after the persisted cutoff stayed `processing`/unfrozen and was reported `skipped_after_cutoff`, even when targeted with `--book-id`.
- API surface for a frozen book: `stage=frozen`, `current_step_label="Import interrupted"`, `retry_available=false`; retry returns 409 with the message.

## 8. Remaining unverified assumptions

- The freeze mechanism has not run against production data (by instruction). Review the dry-run list before executing; the cutoff becomes permanent at the first execution (or at `--record-cutoff` if you use it), so run the dry run and execute close together.
- Production queue backlog depth is unknown; a task message already delivered to a worker will be claimed and immediately skipped, but confirm via logs after freeze.
- Sentry/PostHog event pipelines were not exercised (no DSN locally).

## 9. Exact safe deployment steps

See `DEPLOY_AND_FREEZE.md` (tailored to this repository's `docker-compose.yml` + `deploy.sh`, including the migration pre-checks and the freeze commands). Nothing deploy-related should be executed without the user's explicit approval.

## 10. Production dry-run procedure

```bash
cd /opt/lorevia/current
docker compose --env-file ./backend/.env -f docker-compose.yml exec -T backend \
  python scripts/freeze_legacy_manuscripts.py
```

Review the output: the cutoff and its source, then one row per legacy book (id, masked email, status, stage, created date, age, words, non-terminal executions, in-flight executions, planned action). Confirm every row says `action=freeze` or `already_frozen`, and that the cutoff matches the deployment boundary you intend.

## 11. Approved freeze execution procedure

```bash
docker compose --env-file ./backend/.env -f docker-compose.yml exec -T backend \
  python scripts/freeze_legacy_manuscripts.py --execute --confirm YES_I_UNDERSTAND
```

- Global by design (all incomplete books before the cutoff). Use `--book-id` only for narrower verification runs.
- Idempotent; re-running is safe and reports `changed=0`.
- Every action writes an `AdminAuditEvent`; no manuscript content is printed or modified.
- Rollback (clears the flag only, does not resume work; requires explicit ids):

```bash
docker compose --env-file ./backend/.env -f docker-compose.yml exec -T backend \
  python scripts/freeze_legacy_manuscripts.py \
  --unfreeze --book-id <book-uuid> --execute --confirm YES_I_UNDERSTAND
```

The complete deploy → dry-run → execute sequence with verification queries is in `DEPLOY_AND_FREEZE.md`.

## 12. How to confirm no frozen job can initiate new AI requests

Run after freezing (read-only):

```sql
-- 1. No non-terminal work remains for frozen books
SELECT b.id, b.status,
       b.writer_workspace->'processing'->>'frozen' AS frozen,
       (SELECT count(*) FROM task_executions e
         WHERE e.book_id = b.id
           AND e.status IN ('pending_dispatch','queued','running','paused')) AS non_terminal,
       (SELECT count(*) FROM book_processing_runs r
         WHERE r.book_id = b.id AND r.status IN ('queued','running','paused')) AS active_runs,
       (SELECT count(*) FROM manuscript_import_jobs j
         WHERE j.book_id = b.id AND j.status IN ('queued','running','cancel_requested')) AS active_imports
FROM books b
WHERE b.writer_workspace->'processing'->>'frozen' = 'true';
```

Expected: `non_terminal = 0`, `active_runs = 0`, `active_imports = 0` for every row.

Then, after restarting workers (`docker compose ... restart worker-extraction worker-analysis worker-maintenance`), rerun the same query after 10 minutes — values must remain zero, and `task_executions` rows for those book ids must not appear in `queued`/`running`/`pending_dispatch`. Optionally watch logs for `book_processing_frozen` and confirm no new `ingestion_timing` lines for those books.

## 13. Fresh-upload verification

1. Sign in and upload a small manuscript. It must process to Ready normally (created after the cutoff, so never a freeze candidate).
2. Frozen legacy projects stay "Import interrupted" and never receive new work.
3. An immediate second upload of the identical file is rejected with the duplicate message (expected).
4. If the fresh upload exceeds the account's allowance, the book shows the allowance failure message — do not promise free processing the plan cannot fund.

## 14. Rollback strategy

- Code: redeploy the previous `main` revision (see `DEPLOY_AND_FREEZE.md` rollback section). No migration is introduced by the freeze feature, so no database rollback is required for it.
- Data: `--unfreeze --book-id <uuid>` clears the flag per book without resuming processing. Audit rows remain as history.
- Cutoff marker: the persisted cutoff is a single audit row; removing it would re-derive a fresh cutoff on the next run, so leave it in place unless redefining the cutover.
- Duplicate guard: revert the `book_upload_service` changes; stored `source_fingerprint` values are inert metadata.

## 15. GO / NO-GO recommendation

**Conditional GO for deployment; NO-GO for automatic freeze execution.**
Deploy the code after the checks in `DEPLOY_AND_FREEZE.md` (including the Alembic safety checklist for the billing migration that ships in the same working tree). Then: one dry run, review, one confirmed global freeze command. The cutoff is persisted at first execution, so fresh uploads are never affected.
