# LoreVia — Release Readiness Audit

Independent pre-production certification of the entire unreleased working tree. Prepared from repository inspection, local Docker execution, and browser-based end-to-end verification. No production system was accessed; nothing was committed, pushed, merged, or deployed.

## 1. Exact revision and working-tree scope examined

- Branch: `author`, HEAD `87d204b66888f1728e09086f625a554b0bbdda69` (`origin/author` identical). Local `main` (`c3d70039`) is an ancestor and stale; `origin/main` (`ab97caed`) is already contained in `author`. Nothing is staged.
- Compared against `main`/merge base: the release candidate is `author` + an uncommitted working tree of **507 modified/deleted tracked files (40 deleted binaries) and 172 untracked files** (inventory in `FULL_CHANGE_AUDIT.md`).
- Audit scope added by this session: every file this and the previous reliability sessions touched, plus the billing WIP, the frontend redesign risk surface, deployment configuration, migrations, and the e2e/unit suites.
- Assumption used throughout: **you deploy this branch's working tree** (backend via VPS Compose, frontend via Vercel). If only part of the tree is committed, re-run the checks in §9.

## 2. Unreleased features and major changes

| Area | Change |
|---|---|
| Ingestion reliability | MissingGreenlet analysis-crash fix, deterministic ready promotion, visible terminal failures, budget-block visibility, parser error mapping, empty-file/readable-text gates, upload validation + error surfacing |
| Legacy freeze | One-time global freeze of incomplete pre-cutoff jobs (persisted write-once cutoff), worker/sweep/entry-point guards, "Import interrupted" UI, duplicate-upload guard |
| Billing/subscriptions | Lifecycle fields + migration, webhook lifecycle emails, renewal reminders, Paddle reconciliation job, `/billing/subscription`, rate-limit messaging, Architect limit changes |
| Frontend redesign | ~450 changed files: auth, library, reader, characters, editor toolbar, workspace panels, marketing/content, assets (png→webp) |
| Reviews/fixes this session | `/books/series` route shadowing; cookie-banner/login overlap; LLM capacity matcher; E2E flag hardening; Sentry release tagging; six failing frontend tests |

## 3. Unmerged branches and integration risks

- `codex/remove-automatic-vps-deploy` @ `45ed818a`: **one commit not in `author`** (`feat: expand editorial library`) — content-only (MDX answers/blog + two content-loader tests). `author` contains the 712-file superset; the branch's parent is in HEAD. Risk: omitted editorial content only; no code/API impact. Do not merge blindly; cherry-pick if the content is wanted.
- `claude-refactor` and `codex/pr-58-review`: contain **no commits** absent from `author` (old/diverged pointers).
- `origin/staging`: ancestor of `author`.
- No merge performed.

## 4. Examined through code review (not merely tests)

Route/API layer, ingestion services and workers, freeze service and script, LLM control/usage/circuit-breaker, allowance reservations, billing webhook + reconciliation services, migration `20260919` and the 9 migrations added since `origin/main`, config/validation, nginx/compose/deploy scripts, auth/CSRF/cookie handling, middleware/CSP, admin server override, PostHog consent, workspace normalization, manuscript page/left-right rails, upload modal controller, library/reader runtime, Sentry init. Features verified in the browser are listed in §5 and §10.

## 5. Exercised through real local execution

- Full stack: FastAPI + Gunicorn, Postgres/pgvector, Redis, all five Celery workers, external-equivalent storage; Next.js dev server proxying `/api/v1` to the live API; Chromium automation with the seeded account.
- Workflows: sign-in (real cookies/CSRF), library load, frozen-project display and blocked Retry, book overview, manuscript workspace render, fresh upload through the modal, processing to Ready, duplicate upload rejection with the user-facing message, mobile library render, `/books/series` through the proxy.
- Backend: full unit+integration suite; migration gate on a disposable DB; freeze script dry-run/execute/idempotency rehearsal; new matcher/series tests.

## 6. Confirmed defects discovered this session

1. **P1 — `GET /books/series` returned 422.** `core_router` (with `GET /{book_id}`) was registered before `series_router`, so the literal path was parsed as a UUID and failed validation. The series selector in the upload modal failed silently and the console logged 422s.
2. **P1 — Provider-outage capacity errors terminally failed in-flight chapters.** `is_llm_coordination_retry_error` matched `"llm capacity"`/`"llm coordination"` only; the circuit breaker raises `"LLM provider capacity is temporarily unavailable."` so a started chapter was marked `failed_terminal` (reproduced: book `1d53edd5…`, execution error_detail `503: LLM provider capacity…`) instead of pausing for auto-resume. Under a real provider outage this would fail manuscripts instead of waiting.
3. **P1 — Cookie-consent banner intercepted the login submit on ≤720px-tall viewports.** On first visit the fixed banner covered the button (Playwright `element intercepts pointer events` at 1280×720); users could be unable to sign in until they found the banner buttons.
4. **P2 — ReadingProgressRail dropped words-read.** The redesign removed the fill bar (intentional) but also stopped rendering `wordsRead` while keeping the required prop and the test expectation — a real information regression.
5. **P1 (process) — Stale worker images during local verification.** Rebuilding only `api` left workers on older `writer_workspace` normalization, silently dropping upload fingerprints. This is a local verification hazard, not a production defect (`deploy.sh` rebuilds every service), but it invalidated part of the earlier duplicate-guard signal until all services were rebuilt.
6. **Flaky e2e budgets** — the two `launch-readiness` crawlers exceeded their 10/8-minute `test.setTimeout` (160/100 navigations on a dev server); the smoke search test timed out under the loaded full-suite run but passes in isolation.

## 7. Defects fixed (all verified)

1. Router order: `series_router` is now registered before `core_router`; regression test `test_series_list_endpoint_is_not_shadowed_by_book_lookup`; verified 200 through the browser proxy.
2. Capacity matcher broadened to `llm capacity`, `llm coordination`, `llm provider capacity`, `ai capacity`; 10 new parametrized tests (429/503, matching and non-matching messages). No other behavior changed.
3. Auth shell reserves bottom clearance while the consent banner is visible (`body:has(.lorevia-cookie-consent) .auth-shell`); verified real sign-in at 1280×720 **without dismissing the banner**.
4. `ReadingProgressRail` renders `{wordsRead} of {totalWords} words`; stale fill-bar assertion updated to the redesigned contract.
5. E2E flag hardening (explicit Phase-5 requirement):
   - Production admin override now requires the public mock flag **and** a non-empty secret **and** the server-only `ADMIN_E2E_ALLOW_PRODUCTION=1`; otherwise it falls back to real backend auth. Tests updated to assert both refusal and the fully-acked path.
   - Relationship-graph debug handle is development-only again.
   - `next.config.js` **fails the production build** when `NEXT_PUBLIC_E2E_MOCK_API=1` without the ack — verified: the build errors with "Refusing to build a production bundle…", and the normal production build succeeds.
6. Sentry now tags `release` (`RELEASE_SHA`) and `environment` for API and workers.
7. Six previously failing frontend specs resolved: editor toolbar harness (More-menu portal), ReadingProgressRail, and the four desktop manuscript specs (explicit desktop `matchMedia` stub for a responsive layout). Frontend suite is now fully green.
8. Launch-crawler budgets raised (test-only) so the audits complete; both crawlers re-run green.

## 8. Unresolved defects / accepted risks

- **Billing/allowance accounting gaps (P2, documented, not fixed):** editor-project retry rebuilds and manuscript imports run paid extraction/analysis without processed-word reservations; rebuild cancellation releases in-flight reservations. These under-count usage rather than overcharge users; spend remains bounded by token windows and the per-user USD ceiling. Fixing needs billing-design review, out of scope per "no unnecessary rewrites".
- **Advisor endpoints without day quotas:** first-impression retry and synopsis rely on per-call reservations + the USD ceiling. Documented.
- **Upload-count entitlement dormant:** `AUTHOR_MAX_UPLOADS` is only displayed, never enforced (content is bounded by storage/word limits).
- **Trial accounts bypass `FREE_TOTAL_TOKEN_BUDGET`** by design (`PAID_READING_TIERS` includes trial access); documented in `STUCK_MANUSCRIPT_FREEZE.md` §6.
- **PostHog autocapture:** fixed in the final hardening round (`autocapture: false` in `PostHogClient.tsx`); pageviews/pageleave remain consent-gated.
- **Smoke search e2e flake under load** (passes in isolation); noted, not fixed.
- **Backend API export spool defaults to tmpfs RAM** on the API container (worker has a disk volume). Config-only mitigation documented.

## 9. Test commands and actual results

| Check | Command | Result |
|---|---|---|
| Backend unit+integration | `docker compose -f docker-compose-local.yml exec -T api pytest tests/unit tests/integration -q` | **2577 passed, 1 skipped** |
| Migration gate (disposable local DB) | `docker compose -f docker-compose-local.yml exec -T api python scripts/verify_migrations_temp_db.py` | **upgrade→downgrade→upgrade to `20260919_subscription_lifecycle`; passed** |
| Single-head check | `alembic heads` (repo venv) | exactly one head: `20260919_subscription_lifecycle` |
| Backend lint | `ruff check backend/app backend/tests backend/scripts` | clean |
| Frontend unit | `cd frontend && npm.cmd test` | **277 files / 1452 tests passed** |
| TypeScript | `npm.cmd run type-check` | clean |
| ESLint | `npm.cmd run lint` | clean |
| Next production build | `npm.cmd run build` | success |
| Build guard (negative) | `NEXT_PUBLIC_E2E_MOCK_API=1 npm.cmd run build` | **fails closed as designed** |
| Playwright (mock API) | `npx playwright test` | **399 passed, 3 failed**; all 3 then resolved/verified: both `launch-readiness` crawlers re-run green after budget fix, smoke search green in isolation |

## 10. Browser-based end-to-end verification (real backend, Chromium)

| Scenario | Result |
|---|---|
| Sign-in with seeded account through Next proxy (cookies + CSRF) | PASS |
| `/books/series` through the proxy after fix | PASS (200) |
| Library renders; frozen project shows "Import interrupted" | PASS |
| Frozen book detail: message present, **no Retry button** | PASS |
| Ready book overview + manuscript workspace render (real data) | PASS |
| Fresh upload via modal → `pending → processing → ready` | PASS (~16s; screenshots saved to `%TEMP%\opencode\real-e2e`) |
| Immediate identical duplicate upload → 409, modal shows the actionable message (not the generic fallback) | PASS (after all backend services were rebuilt) |
| Login at 1280×720 with consent banner visible, without dismissing it | PASS (before fix: click intercepted) |
| Mobile viewport (390×844) library | PASS (no empty render) |
| Large (5.5k-word) upload under local provider rate limits | Observed `usage_limited` pause with auto-resume messaging, then a terminal failure from defect #2 — the exact scenario the matcher fix addresses; the matcher regression tests now cover it. Post-fix re-verification of a full large-book completion was not repeated because the local provider key was rate-limited. |
| Playwright redesign coverage (`manuscript-ux`, `library-ux`, and 33 more specs) | PASS (mock API; exercised keyboard, mobile panels, error recovery, accessibility, launch audits) |

## 11. Security assessment

- **Admin E2E bypass:** now requires three independent switches, two of which are server-only; production builds cannot compile with the public flag alone. Residual: if an operator deliberately sets all three, the override exists by design for approved test builds.
- Auth/middleware/CSRF/CSP code was not otherwise changed by the redesign; cookie attributes remain HttpOnly/SameSite=Lax/Secure-in-production, CSRF double-submit is enforced, admin API authorization is backend-enforced.
- No tracked secrets; `.env`/certs are ignored; webhook signature verification precedes processing; internal jobs require `INTERNAL_JOB_SECRET`.
- Logging scrub rules cover tokens/URLs/jwts; verified no manuscript text in the new structured upload logs.
- PostHog autocapture is now disabled (`autocapture: false` in `PostHogClient.tsx`), closing the remaining privacy item.

## 12. Billing and AI cost-safety assessment

- Per-call reservations enforce token windows and a per-user USD ceiling under an advisory lock; reservations are unique-keyed and consume/release idempotently; free tier is blocked before any reservation; chapter saves cannot trigger paid analysis; continuity/world scans are deterministic (zero LLM cost).
- Confirmed gaps under-count usage (editor rebuild/import paths) rather than overspend; worst-case platform exposure is capped by `*_LLM_PROVIDER_COST_LIMIT_USD` and token windows.
- Reconciliation defects from the earlier audit (crash-on-second-run, paused/canceled downgrade) are fixed with regression tests.
- New this session: transient provider capacity errors now pause with auto-resume instead of failing (removes retry-driven re-spend and false failures).
- Trial-account budget policy unchanged by design; duplicate guard + freeze close the observed abuse path.

## 13. Database migration assessment

- 10 migrations apply on top of the deployed revision: 9 from `author` (including the batched identity/generation backfill) + the untracked `20260919_subscription_lifecycle` (idempotent, no destructive upgrade operations, single head).
- Local disposable-DB gate: upgrade → downgrade → upgrade passed; temp DB dropped.
- Static destructive-scan caveat: `20260909_add_book_data_generations` drops constraints through helpers, so `deploy.sh`'s scanner will not flag it. It is guarded and asserts internally; expect a long, write-heavy upgrade window.
- `bootstrap_db.py` is local-only; `FROZEN_SCHEMA_MANIFEST` is logged but unused (dead metadata).
- Backup: `deploy.sh` runs `pg_dump` before upgrades; rollback of schema is intentionally not automated.

## 14. Deployment and rollback risks

- `deploy.sh` refuses a dirty checkout and deploys `main`; this tree is uncommitted, so commit/push is a prerequisite.
- The frontend is on Vercel: a backend-only "deploy" silently leaves the old UI live. The runbook now includes the same-commit Vercel promotion and an `/api/release` cross-check.
- Zero-spend cutover: the deployment transition gate now holds every pre-cutoff execution at dispatch, outbox publish, worker claim, import-job, requeue, and user-action choke points, so no legacy job can start a provider call between deploy and freeze. deploy.sh stops the app stack, records the write-once cutoff after migrations, and only then starts services, so no upload can predate the cutoff either.
- `CLOUDFLARE_TUNNEL_TOKEN` + edge-token middleware: a partial rollout (new backend, old nginx) would 403 all traffic until nginx is recreated. Deploy all runtime services together, or leave the tunnel token unset.
- No automated rollback; code rollback is manual, DB downgrades are blocked by policy. The backup from `deploy.sh` is the recovery path.
- Host `pg_dump` availability and write access to `/opt/lorevia/backups/supabase` are prerequisites.

## 15. Features not fully verified

- Real Paddle checkout/webhook traffic (sandbox+live), and the two new internal subscription jobs against real Paddle.
- Production Vercel build/promotion and actual env scopes (cannot be inspected from the repo).
- Production R2 paths (local run used the file-backed fallback), nginx timeouts under real large uploads, Redis persistence/queued-message backlog behavior.
- Large-manuscript full completion under provider rate limits (local key throttling; matcher fix covered by tests).
- Visual regression of the redesigned UI beyond the browser checks and Playwright audits performed; no pixel-diff baselines.
- The 9 author-branch migrations were validated via the disposable-DB gate, not against a production-sized dataset.

## 16. Production assumptions requiring manual confirmation

1. Vercel Production env contains **neither** `NEXT_PUBLIC_E2E_MOCK_API` nor `ADMIN_E2E_TEST_SECRET`, and the same-commit frontend promotion happens with the backend deploy.
2. VPS `backend/.env` provides every startup-required variable (EDGE_PROXY_SECRET, JWT_SECRET ≥32 chars, the seven Paddle values, Redis password URL, Supabase DATABASE_URL, S3/R2 keys, OPENAI_API_KEY, RESEND_API_KEY) and `DEBUG=false`, `PROCESSING_ALLOWANCES_MODE=enforce`.
3. Whether `CLOUDFLARE_TUNNEL_TOKEN` is set on the VPS (drives the edge-token requirement) and that nginx/backend update atomically.
4. Current production Alembic revision (expected `20260912_public_asset_ready` or later) and that `subscriptions.expires_at` vs `current_period_end` matches what the migration expects.
5. `pg_dump` availability/version on the host and writable backup directory.
6. Sentry `SENTRY_DSN` present so the new release/environment tags and alerts flow.

## 17. Overall release readiness

**GO for deployment (via the runbook), conditional on the operational prerequisites below.**

Final hardening round (same session, after this audit's first pass):

- Deployment race closed: the transition gate holds all pre-cutoff work at every choke point (dispatchers, outbox publish, worker claim, import jobs, stall recovery, retry/continue, ensure_project_writable), and deploy.sh now stops the app stack, migrates, records the write-once cutoff, and only then starts services — so the cutoff always exists before the API accepts uploads and no legacy job can start a provider call in the window. Live local rehearsal: 7/7 checks passed against the running stack.
- F1 fixed: editor-project manual retries now reserve processed words before rebuilding (same reservation semantics as the manual reprocess endpoint), closing the paid-path allowance bypass.
- Freeze script hardened: books whose workspace shows processing activity newer than the cutoff are skipped (skipped_processing_after_cutoff) instead of frozen, and the freeze CLI remains idempotent (verified locally: cutoff_source=persisted, changed=0 on repeat).
- Library project menu could be covered by the analytics consent banner on short viewports (delete action unclickable); menu z-index raised to the app's dropdown convention (z-[95]).
- PostHog autocapture disabled.

Verification ledger for this round: backend 2598 passed / 1 skipped (Docker Compose Local); frontend 1452 passed / 277 files, type-check, lint, production build clean; Playwright smoke 108/108 with a clean .next (4 earlier failures were a stale dev cache after next build plus the one real menu-overlap bug, now fixed); deployment-transition rehearsal 7/7; freeze dry-run 140 candidates / 0 changed and --record-cutoff no-op on repeat.

Conditions for the GO:
1. Commit and review the tree; deploy per DEPLOY_AND_FREEZE.md (deploy.sh records the cutoff automatically; do not set SKIP_LEGACY_CUTOFF_RECORD).
2. Confirm the production assumptions in section 16 (Vercel env flags, VPS env completeness, tunnel/edge coupling, production Alembic revision) before upgrading.
3. Schedule the migration set in a low-traffic window; keep the pre-deploy pg_dump.
4. Run the one-time freeze (dry run, then approved execute) and PRODUCTION_VERIFICATION.md immediately after deploy; treat any stuck/frozen-state, duplicate-guard, or legacy-spend deviation as a rollback signal.
5. Track the documented P2 items (billing accounting gaps, advisor quotas, dormant upload cap, API export spool) as follow-up work; none block this deployment.

Residual risk is concentrated in production-only integrations (Paddle, Vercel, R2, real provider quotas) that cannot be exercised from this environment; the manual checks in PRODUCTION_VERIFICATION.md and DEPLOY_AND_FREEZE.md cover them.

