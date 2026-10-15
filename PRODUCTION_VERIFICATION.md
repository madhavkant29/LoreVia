# Production Verification Procedure — Manuscript Ingestion Fixes

Purpose: verify the ingestion reliability fixes after deployment without touching user manuscripts, without destructive database operations, and without accessing production data beyond what a normal signed-in test account produces.

Complete the checks in order. Each step lists the expected result and how to distinguish pass/fail. Stop and report immediately if any step produces a stuck book or a 5xx during the core journey.

## 0. Preconditions

- Backend deployed with the fixes; frontend deployed.
- Confirm the production frontend build was created **without** `NEXT_PUBLIC_E2E_MOCK_API=1` (and without `ADMIN_E2E_TEST_SECRET`). That flag enables test-only admin/graph escape hatches; it must not exist in production (see `FULL_CHANGE_AUDIT.md` §7).
- A dedicated verification account exists with Author (or Architect) access. Do not use a real author's account.
- Access to the existing Sentry project (and PostHog if available).
- No database writes beyond the verification account's own books are needed. All SQL below is read-only.

## 1. Confirm the deployment is live

1. `GET https://<api-host>/health` returns `{"status":"ok", ...}`.
2. `GET https://<api-host>/ready` returns `{"status":"ready"}`.
3. Check the release SHA shown by `/health` matches the deployed build.

Pass: both endpoints healthy and SHA matches. Fail: roll back per the standard procedure.

## 2. Happy path — small manuscript (the core user journey)

1. Sign in with the verification account.
2. Library → New project → upload a small TXT (2–3 chapters, a few hundred words), title it clearly as a verification upload (e.g. `VERIFY small txt`).
3. Observe the modal: upload progress percent, then "Handing off for processing".
4. Watch the library card / book overview without touching anything for up to 3 minutes.

Expected:
- The upload request returns 202 and never shows a generic "Upload failed. Please try again."
- The book moves `pending`/`processing (parsing → extracting → analyzing)` and reaches `ready`.
- It becomes `ready` shortly after analysis finishes (seconds, not a 5-minute wait for the repair sweep).
- Opening the book shows chapters and analysis without errors.

Fail indicators: book pinned at `processing` for >10 minutes; `pipeline.analysis.failed_chapters` non-empty in the book JSON; Sentry `MissingGreenlet` events.

## 2b. Regression checks from release certification

1. **Series endpoint**: `GET https://api.getlorevia.com/api/v1/books/series` with a signed-in browser session must return 200 (not 422). Then open the upload modal and confirm the series selector loads without console errors.
2. **First-visit consent banner**: in a fresh private window at a laptop viewport (1280×720), load `/login` and click "Sign in" **without dismissing** the analytics banner. Sign-in must submit and reach `/library`; the banner must not cover the button.
3. **Provider-capacity pauses**: if Sentry/logs show `usage_limited`/`llm_capacity` pauses during an outage, confirm they resolve by auto-resume (or via the UI's resume action) and that books do not fail with the generic "Processing stopped…" message for capacity-only errors.
4. **Duplicate mount**: upload a manuscript, then immediately upload the same file again from the same account in a second tab. The second attempt must return 409 with "This exact manuscript is already being processed…" and must not create a second active book.

## 3. Happy path — DOCX and single chapter

1. Upload a small DOCX as a new project.
2. In an existing project, use "Add New Chapter" → Upload file with a single-chapter TXT/PDF/DOCX.

Expected: both reach ready/imported with no error banner; single-chapter import returns the chapter inserted at the expected number.

## 4. Input rejection paths (must fail fast and clearly)

For each case, the request must be rejected with a readable 400-level message and must NOT create a stuck book:

1. Corrupt PDF: rename a text file to `.pdf` and prepend `%PDF-1.4`. Upload it.
   Expected message: "We couldn't read this manuscript. The file may be corrupted or partially saved..."
2. Whitespace-only TXT.
   Expected message: "... is empty. Choose a file that contains manuscript text."
3. Unsupported extension (e.g. `.png`) — blocked client-side before any request.
4. Oversized file (>100 MB) — blocked client-side with the 100 MB limit named.
5. Scanned PDF with no text layer (if available) — rejected with the OCR guidance message.

## 5. Refresh during processing

1. Upload a slightly larger manuscript (several chapters).
2. While the library card shows processing, hard-refresh the browser twice.
3. Stop interacting for a few minutes, then reload.

Expected: status/progress continue from the server state; the book completes to ready without any user action.

## 6. Failure visibility and retry (only if a failure reproduces)

Preferred trigger on production is a legacy stuck book or an operator-induced failure; do not corrupt production data to force this.

1. Find a book that is `processing` with a stale timestamp (operator SQL in step 9) or intentionally fail a verification upload by an operator-approved method.
2. Open the book.

Expected:
- The UI shows "Processing failed" with an actionable message (not an endless "Queued for processing").
- A Retry button is offered and `POST /api/v1/books/{id}/processing/retry` succeeds (200), restarting processing.

## 7. Frozen legacy imports (only after an approved freeze execution)

Prerequisite: the operator has completed `DEPLOY_AND_FREEZE.md` steps 5–7 for the verified account.

1. Open a frozen project in the UI.

Expected:
- The panel reads "Import interrupted" with the explanation "Import interrupted - please upload again. Your project and files have been preserved." and an "Upload again" action; there is no Retry button.
- Stored chapters/content remain readable; nothing was deleted.
- `POST /api/v1/books/{id}/processing/retry` returns 409 with the same message (check the Network tab).
- After the freeze, restarting `worker-extraction`, `worker-analysis`, and `worker-maintenance` produces no new work for the frozen book (verify with the SQL canary in `STUCK_MANUSCRIPT_FREEZE.md` §12 after 10+ minutes) and no new Sentry/LLM activity.
- A new upload from the same account processes normally; the frozen projects stay paused.

## 8. Duplicate upload guard

1. Upload a supported manuscript, then immediately upload the identical file again (same account).

Expected: the second request returns 409 "This exact manuscript is already being processed in another project..." and no second book appears in the library. Uploading a revised file, or re-uploading after a freeze/failure, still works.

## 9. Budget-limited behavior (trial/free access only)

Only run if a verification account without paid access exists and its free token budget is already exhausted.

1. Upload a manuscript sized to exceed the remaining allowance (or reuse a project after exhausting `FREE_TOTAL_TOKEN_BUDGET` in a non-production environment).

Expected: the book shows a visible failed state with the allowance/upgrade message; it does not sit at "Queued for processing". Retrying before upgrading fails gracefully with the same message, not a 5xx.

## 10. Observability verification

1. In Sentry, confirm the release is registered (deployment tracking / release tag).
2. Create a failed manuscript import (e.g. corrupt chapter file). Confirm a Sentry event appears tagged with `job_id`, `book_id`, `user_id`, and a failure category, and that the event contains no manuscript text, tokens, or signed URLs.
3. Search Sentry for `MissingGreenlet` created after the deploy. Expected: zero new events. Any new event is a release blocker.
4. Confirm structured logs include `book_upload_stored` for successful uploads and no filenames/contents in the payloads.
5. Optional: confirm the `book_processing_stuck` alert fires when a stuck book is present (it is emitted by the 5-minute maintenance sweep).

## 11. Read-only database canaries

Run against the production database in read-only mode (SELECT only). These queries contain no user content.

1. Books stuck longer than 30 minutes:

```sql
SELECT id, user_id, status, created_at
FROM books
WHERE status = 'processing'
  AND created_at < now() - interval '30 minutes'
ORDER BY created_at
LIMIT 50;
```

Interpretation: rows here after the deploy indicate either legacy stuck books (expected; resolve via retry/admin tooling) or a new failure mode (escalate, do not bulk-update).

2. Recent terminal run failures:

```sql
SELECT book_id, run_kind, status, completed_at
FROM book_processing_runs
WHERE status = 'failed_terminal'
  AND completed_at > now() - interval '1 hour'
ORDER BY completed_at DESC
LIMIT 50;
```

3. Import job failures in the last hour:

```sql
SELECT id, book_id, status, left(error_detail, 200) AS error_preview, completed_at
FROM manuscript_import_jobs
WHERE status = 'failed'
  AND completed_at > now() - interval '1 hour'
ORDER BY completed_at DESC
LIMIT 50;
```

These are diagnostic only. Do not run UPDATE/DELETE without a separate, explicitly approved remediation plan.

## 12. Post-verification cleanup

Delete the verification account's books through the product UI (or the standard account-deletion flow) so verification uploads do not remain in the library. Do not delete other users' data.

## Rollback criteria

Roll back the backend and frontend to the previous release if any of the following is observed:
- Any new `MissingGreenlet` events in Sentry tied to analysis.
- A verification upload that cannot reach ready and has no visible failed state.
- A 5xx rate increase on `/api/v1/books/*`.
- Data inconsistency: books marked `ready` without completed chapter analysis, or failed chapters counted as success.
- A frozen book that shows new executions/runs or receives Retry actions after a worker restart.
- An identical-duplicate upload that creates a second actively processing book.

Record the outcome of every step with the verification account username, timestamps, and relevant Sentry/log links. Never paste manuscript contents, tokens, or signed URLs into tickets or chats.
