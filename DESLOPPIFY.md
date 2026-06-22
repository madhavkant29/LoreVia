# LoreVia Desloppify Backlog

Review date: 2026-06-22

Scope: current working tree across `backend/`, `frontend/`, tests, migrations, CI, Docker/VPS configuration, and repository hygiene. This review intentionally made no application-code changes. The worktree already contained extensive uncommitted changes; findings refer to that current state.

## How to use this backlog

- Select one item ID for the next task.
- Re-check overlapping user changes before editing because the current worktree is heavily modified.
- For each completed item, add or update focused tests, run the relevant verification, mark the item complete here, and display this backlog again.
- Do not combine critical correctness/security work with broad file-splitting unless the tests prove behavior is unchanged.

## Recommended order

1. `C1` — make durable task execution genuinely terminal and idempotent.
2. `C2` — stop attacker-controlled internal-job rate-limit keys.
3. `C3` — centralize trusted client identity for moderation, analytics, and audit paths.
4. `C4` — prevent local manuscript/media artifacts from entering Git or Docker contexts.
5. `M3` — remove module-level monkeypatch propagation before continuing route refactors.
6. `M1` and `M2` — reduce oversized backend and frontend units incrementally.

## 1. Critical issues

### [ ] C1 — Durable task records do not enforce terminal state or safe dispatch

- **Where:** `backend/app/services/task_execution_service.py`, especially `TERMINAL_EXECUTION_STATUSES`, `claim_task_execution()`, `fail_task_execution()`, and the extraction/analysis dispatch functions; worker entry points in `backend/app/workers/tasks/`; coverage in `backend/tests/unit/test_task_execution_service.py`.
- **Why it matters:** `claim_task_execution()` rejects only `succeeded` and `dismissed`; it can reclaim `failed_terminal`, and it never enforces `max_attempts`. A redelivered Celery message can therefore rerun work explicitly marked terminal, spending LLM capacity and mutating book state again. Broker publication also happens before the task-row commit, leaving a publish/commit failure window that can produce ambiguous or duplicate dispatch. Existing tests cover identity and fair dispatch but not terminal reclaim, attempt exhaustion, redelivery, or publish/commit failure.
- **Recommendation:** Make the status vocabulary authoritative; reject every terminal state in the claim path; enforce attempt limits atomically; define legal state transitions; add redelivery and failure-window tests. Use an outbox/dispatching state or an equivalent reconcileable protocol so database state and broker publication cannot silently diverge.
- **Fix timing:** **Safe and advisable now**, before the untracked processing-control-plane migration is shipped or enabled. Keep this as a focused correctness change, not a general worker refactor.

### [ ] C2 — Internal-job rate limiting can be bypassed and used to grow Redis keys

- **Where:** `backend/app/api/deps/rate_limit.py::rate_limit_internal_job()` and `backend/app/api/v1/routes/internal.py`.
- **Why it matters:** The dependency hashes any supplied `X-Internal-Job-Secret` and uses that hash as the rate-limit identity before the handler verifies the secret. An unauthenticated caller can rotate arbitrary fake secrets, bypass the per-key limit, and create many Redis keys. Verification still rejects the jobs, but the limiter does not constrain the abusive traffic or key growth.
- **Recommendation:** Rate-limit unverified requests by the trusted client identity, verify the secret before any secret-scoped limiter, and optionally apply a second fixed bucket for the authenticated scheduler. Add tests using many different invalid secret values from one client.
- **Fix timing:** **Safe to fix now.** This is isolated and should precede deployment.

### [ ] C3 — Client identity is inconsistent, spoofable in analytics, and collapsed in moderation

- **Where:** trusted logic in `backend/app/api/deps/rate_limit.py::_client_identifier()` versus direct/header reads in `backend/app/api/v1/routes/reports.py`, `backend/app/api/v1/routes/books/publish.py`, `backend/app/api/v1/routes/public_shared.py`, `backend/app/services/admin_service.py`, and `backend/app/utils/public/requests.py::build_public_visitor_fingerprint()`; proxy headers in `ops/nginx/nginx.conf`.
- **Why it matters:** Public analytics trusts the leftmost `X-Forwarded-For` unconditionally, so a direct caller can forge visitor identities and inflate metrics. Copyright-report deduplication hashes `request.client.host`, which is normally the reverse proxy address and can collapse distinct reporters into one, preventing the three-reporter moderation threshold from working. Audit/publish paths use still other rules. Security, abuse prevention, and business analytics therefore disagree about who the caller is.
- **Recommendation:** Create one public trusted-client resolver outside the rate-limit module. Define the exact VPS/Nginx/optional-Cloudflare trust boundary, normalize and validate IP values, and use it everywhere an IP or visitor fingerprint affects enforcement or audit data. Test direct clients, trusted proxy headers, forged headers, IPv4/IPv6, and multiple reporters behind the deployed proxy topology.
- **Fix timing:** **Safe to fix now**, but verify against the actual VPS proxy path before release. Do not guess at Cloudflare behavior.

### [ ] C4 — Local user-upload artifacts are visible to Git

- **Where:** untracked `local/local-dev/covers/` and `local/local-dev/chapter-media/`; root `.gitignore` and `.dockerignore`.
- **Why it matters:** The current `git status` exposes generated cover and chapter-media files, and `/local/` is not ignored. These can contain user manuscript assets, can be accidentally committed, and can enlarge build contexts or backups. This is both repository hygiene and privacy risk.
- **Recommendation:** Add a root-anchored `/local/` ignore rule (and Docker-context exclusion where applicable), document the intended local-storage root, verify no local artifacts are already tracked, and add a lightweight repository-hygiene check. Do not delete the user’s existing local files as part of this fix.
- **Fix timing:** **Safe to fix now.** Preserve the files; change only tracking/build-context behavior.

## 2. Medium cleanup items

### [ ] M1 — Backend route files still contain service-sized workflows

- **Where:** `backend/app/api/v1/routes/books/characters.py` (~1,410 lines), `books/imports.py` (~1,039), `admin.py` (~1,097), plus substantial transformation/query logic in reader and public routes.
- **Why it matters:** These exceed the repository’s ~500-line route guideline and mix HTTP concerns with queries, transformation, orchestration, and error recovery. Authorization and transaction boundaries become difficult to review, and endpoint tests must patch implementation details.
- **Recommendation:** Move one cohesive workflow at a time into existing domain services/utils. Keep route handlers responsible for request parsing, dependency checks, service invocation, and response mapping only. Start with imports and character mutation flows because they combine storage, database, queues, and notifications.
- **Fix timing:** **Safe incrementally after C1–C3.** Avoid a single large mechanical split.

### [ ] M2 — Core backend and frontend units have become god modules

- **Where:** backend `export_utils.py` (~3,284 lines), `advisor_utils.py` (~2,954), `world_building_utils.py` (~2,770), `beta_read_utils.py` (~2,405), `extraction_consumer.py` (~3,028), and `engine/character/extractor.py` (~1,785); frontend manuscript page (~4,677), characters page (~4,254), `LibraryClient.tsx` (~1,893), `VaultNotesEditor.tsx` (~1,757), and `WorldbuildingWorkspace.tsx` (~1,710).
- **Why it matters:** Unrelated state, side effects, rendering, persistence, and domain rules share the same compilation and review unit. The manuscript page alone owns dozens of independent `useState` values. Small changes have broad regression surfaces, merge conflicts are frequent, and behavior is hard to test in isolation.
- **Recommendation:** Define domain seams before extracting: export format renderers, advisor retrieval/prompt/report layers, processing stages, and frontend feature hooks/components with explicit inputs. For React, move server-state and mutation lifecycles into feature hooks/reducers and keep page files as composition roots.
- **Fix timing:** **Safe only as staged refactors with characterization tests.** Wait until critical worker/security behavior is stable.

### [ ] M3 — Route-package splits depend on global monkeypatch propagation

- **Where:** `backend/app/api/v1/routes/books/__init__.py`, `advisor/__init__.py`, and `reader/__init__.py` use custom `ModuleType.__setattr__` classes, import large compatibility surfaces, and propagate assignments into child modules.
- **Why it matters:** Test seams now mutate global production modules. Import order and attribute names control whether a patch reaches the real dependency, and one patch can affect several child modules. This obscures dependency ownership and keeps package `__init__` files coupled to internal functions, schemas, workers, and utilities.
- **Recommendation:** Update tests to patch dependencies where they are consumed, or inject explicit service objects/dependencies. Reduce each package initializer to router composition and intentional public exports, then remove placeholders such as `build_repair_plan = None`.
- **Fix timing:** **Safe now as a dedicated test-architecture task**, after confirming the current route split is complete. Do not mix with endpoint behavior changes.

### [ ] M4 — Optional authentication converts service outages into anonymous requests

- **Where:** `backend/app/api/deps/auth.py::get_optional_current_user()` and consumers in billing confirmation, email preferences, reports, and public catalog/forum routes.
- **Why it matters:** Both `401` and `503` become `None`. A database or Redis outage is therefore treated as “anonymous,” which can change personalization, cache selection, attribution, and error semantics. Billing confirmation also catches every exception around this helper, further hiding infrastructure failures.
- **Recommendation:** Swallow only expected invalid/missing-credential `401` cases. Propagate `503` and unexpected failures. If a public endpoint intentionally degrades anonymously, make that policy explicit per endpoint and ensure it cannot cache or return a less-authorized representation under the wrong key.
- **Fix timing:** **Safe now**, with focused tests for missing credentials versus Redis/database failure.

### [ ] M5 — Local-storage code is duplicated and lacks an explicit containment guard

- **Where:** `backend/app/core/storage.py` repeats the same permission-recovery directory creation in `upload_book`, `upload_book_bytes`, `upload_binary`, and `upload_text`; `_local_path()` simply joins a key to the storage root.
- **Why it matters:** Permission behavior can drift between write methods, and future caller-provided keys containing absolute or parent segments could escape the configured root in local mode. Current keys appear internally generated, but the storage API does not enforce that assumption.
- **Recommendation:** Centralize safe path resolution and parent creation. Resolve the target, verify it remains under the configured bucket root, reject unsafe keys, and test absolute paths, `..`, separators, missing directories, and permission failures.
- **Fix timing:** **Safe now** after preserving existing local-storage behavior and tests.

### [ ] M6 — New processing-control schema uses unconstrained string state machines

- **Where:** `backend/app/models/operations.py` and `backend/app/db/migrations/versions/20260622_add_processing_control_plane.py` for run/task/incident/quality statuses, kinds, outcomes, and severities.
- **Why it matters:** Application code already uses several similar but different values (`pending_dispatch`, `queued`, `running`, `paused`, `failed_terminal`, `succeeded`). Plain strings permit invalid database states, and state-transition bugs are discovered only at runtime. Migration formatting also compresses many columns/index declarations, making manual production review harder.
- **Recommendation:** Define shared typed constants/enums and legal transitions; add appropriate check constraints where operational flexibility permits; format the migration for review; add model/migration parity and upgrade/downgrade tests on a fresh local database.
- **Fix timing:** **Fix before applying the new migration outside local development.** If it has already shipped, add a follow-up migration rather than editing history.

### [ ] M7 — Backend runtime ownership depends on a frontend source file

- **Where:** `backend/app/utils/billing_utils.py` reads `frontend/src/lib/billing/pricing-catalog.json`; both backend Dockerfiles manually recreate `/frontend/src/lib/billing` and copy the JSON there.
- **Why it matters:** Backend import/startup depends on a frontend directory layout and custom Docker-copy convention. Packaging the backend independently, running tools from another layout, or moving frontend files can break billing initialization.
- **Recommendation:** Move the canonical catalog to a neutral root package/artifact or a backend-owned data module and generate/import the frontend representation. Keep the existing consistency tests, but remove runtime dependence on another application’s source tree.
- **Fix timing:** **Safe as a bounded packaging task**, preferably before the next pricing change.

### [ ] M8 — Frontend tests pass while emitting a large warning stream

- **Where:** broad `*.coverage.test.tsx` suites, including upload, forum, collaboration, timeline, scenes, and editor coverage tests.
- **Why it matters:** The full Vitest run passed, but emitted many React “not wrapped in act(...)” warnings and a non-boolean `prefetch` warning from a test double. A noisy green suite trains maintainers to ignore stderr and can hide real lifecycle bugs. Omnibus coverage tests also exercise many behaviors in one test, making failures hard to localize.
- **Recommendation:** Make unexpected console warnings fail tests, fix async interaction waits/`act` usage, make Next `Link` mocks consume framework-only props, and split large coverage tests into behavior-focused cases.
- **Fix timing:** **Safe now**, in small test-only batches.

### [ ] M9 — Rate-limit and entitlement configuration contains no-op/dead contracts

- **Where:** `backend/app/api/deps/rate_limit.py::rate_limit_summary()` returns `None`, while `FREE_SUMMARY_PER_HOUR`, the admin override field, and auth config output advertise a real limit. Several legacy/manual-reprocess/provider settings also appear unused or only partially wired.
- **Why it matters:** Operators and UI code can believe a control is enforced when it is not. Dead settings increase deployment complexity and make pricing/entitlement reviews unreliable.
- **Recommendation:** Inventory every setting against runtime reads and public config output. Implement the summary limit if it remains a product rule; otherwise remove the setting, override field, and UI contract together. Mark intentional compatibility aliases with a removal plan.
- **Fix timing:** **Safe now after a product decision** on summary limits; the inventory itself is read-only and safe immediately.

### [ ] M10 — Broad exception handling often degrades silently

- **Where:** numerous `except Exception` blocks in Redis/storage/LLM helpers, advisor/export/world extraction utilities, routes, and workers; examples include silent `pass` paths in `core/storage.py`, `core/redis.py`, `analysis_consumer.py`, `summariser.py`, and large utility modules.
- **Why it matters:** Some best-effort behavior is intentional, but broad catches mix optional degradation with correctness failures. Missing context or metrics can leave books partially processed while presenting fallback output as valid.
- **Recommendation:** Classify catches as retryable, user-visible, best-effort, or invariant failure. Catch expected exception types, log structured context without manuscript content/secrets, and attach explicit degraded-state diagnostics. Add tests for each fallback contract.
- **Fix timing:** **Safe incrementally.** Start with worker state transitions and data persistence; leave genuinely optional telemetry cleanup until later.

### [ ] M11 — Operational scripts are inconsistent, and one root script is broken

- **Where:** `backend/fix_book_status.py` imports nonexistent `app.models.chapter`, mutates up to 20 books with no explicit apply confirmation, and lives outside `backend/scripts/`; `backend/extract_targets.py` is a one-off test-refactor helper with no references.
- **Why it matters:** A stale repair script can fail during an incident or, after a hurried import fix, mutate whichever database app settings select. One-off scripts at the backend root obscure which tools are supported.
- **Recommendation:** Delete truly obsolete helpers or move supported operations under `backend/scripts/` with dry-run defaults, explicit target reporting, confirmation tokens for writes, structured logging, and tests for selection logic.
- **Fix timing:** **Safe now** for the unreferenced extractor. Treat the status fixer as potentially operational: confirm replacement/ownership before deletion.

### [ ] M12 — Backend local verification is not reproducible from the checked workspace state

- **Where:** `backend/.venv` points at a missing host Python executable; Docker Compose local services were not running during this review.
- **Why it matters:** The required Docker-based backend test path could not be executed immediately, while the repository currently includes three untracked migrations and a new processing control plane. This increases the chance that frontend-green changes mask backend migration/runtime failures.
- **Recommendation:** Use `docker-compose-local.yml` as the single documented path, add a fast preflight command that reports Docker/database/extension readiness, and ensure contributors do not depend on a machine-specific checked-local venv. Run migrations and the full backend suite before shipping current changes.
- **Fix timing:** **Environment cleanup is safe now.** Do not edit `.env` files; start local services and repair/recreate tooling through documented commands when the selected implementation task needs backend verification.

## 3. Nice-to-have polish

### [ ] N1 — Replace native browser prompts with product dialogs

- **Where:** scene folder creation, library permanent delete, character destructive actions, editor link insertion, and vault folder moves (`window.prompt` usages across frontend pages/components); `ConfirmDialog` still falls back to `window.confirm` when no provider exists.
- **Why it matters:** Native dialogs are visually inconsistent, difficult to validate inline, weak on accessibility/context, and block richer error/help states.
- **Recommendation:** Add reusable text-entry and typed-confirmation dialogs with labels, validation, focus management, escape/cancel behavior, and loading/error states.
- **Fix timing:** **Safe incrementally** after higher-risk work.

### [ ] N2 — Demo page metadata duplicates the brand

- **Where:** `/demo/workspace`; rendered title is `Interactive manuscript demo | LoreVia | LoreVia`.
- **Why it matters:** It looks unpolished in tabs and search/social surfaces and suggests page metadata and the root title template both append the brand.
- **Recommendation:** Make child metadata provide the unbranded page title or adjust the root template contract; add a metadata test.
- **Fix timing:** **Safe now.** Very small isolated change.

### [ ] N3 — Landing page is repetitive and unusually long

- **Where:** `frontend/src/app/page.tsx`, `frontend/src/lib/content.ts`, and marketing components.
- **Why it matters:** The rendered page repeats manuscript-analysis claims, workflow explanations, comparison content, audience tabs, and CTAs. The breadth is useful for SEO, but the first-time decision path is diluted and content maintenance is spread across a ~1,786-line content module.
- **Recommendation:** Use analytics to identify low-value sections, tighten repeated copy, preserve dedicated comparison/answer pages for long-form SEO, and split marketing content by section/domain.
- **Fix timing:** **Wait for product/SEO review.** Safe technically, but not a blind cleanup.

### [ ] N4 — Frontend linting is absent from CI and uses a deprecated command

- **Where:** `frontend/package.json` uses `next lint`; `.github/workflows/ci-cd.yml` runs tests, type-check, build, and E2E but not lint.
- **Why it matters:** Local lint passes today but warns that `next lint` is deprecated. Because CI does not invoke it, future lint regressions can merge unnoticed.
- **Recommendation:** Migrate to the ESLint CLI using the existing Next configuration and add the lint command to the frontend CI job.
- **Fix timing:** **Safe now** as a tooling-only change after confirming local and Linux CI parity.

### [ ] N5 — Naming retains multiple generations of the product model

- **Where:** reader/free/collaborator, pro/author, power/architect aliases in config and billing utilities; historical Obsidian-to-vault names remain in tests/migrations and some compatibility paths.
- **Why it matters:** Compatibility is necessary, but without a boundary it is easy to use a collaboration role as a subscription tier or add new code against legacy names.
- **Recommendation:** Keep immutable migration history, centralize normalization at ingress, use only canonical names internally, document compatibility aliases and removal criteria, and add lint/test assertions against new legacy-name usage.
- **Fix timing:** **Safe as documentation and guardrails now;** wait to remove aliases until stored data and deployed env names are migrated.

### [ ] N6 — Add automated size and repository-hygiene guardrails

- **Where:** repository-wide CI/tooling.
- **Why it matters:** The current architecture rules rely on manual review, so 1,000–4,000-line files and unignored runtime artifacts accumulated despite clear guidance.
- **Recommendation:** Add non-blocking reports first for route/page/module line counts, forbidden local artifact paths, route-inline schemas/models, and prohibited import aliases. Convert only high-confidence checks to blocking after the current backlog is reduced.
- **Fix timing:** **Safe now as non-blocking reporting.** Avoid freezing existing debt with an indiscriminate hard limit.

## Verification performed during this review

- Frontend TypeScript check: passed.
- Frontend Vitest suite: passed, with substantial React/test-double warning noise captured under `M8`.
- Frontend lint: passed; deprecation and CI omission captured under `N4`.
- In-app browser smoke check: landing page and `/demo/workspace` rendered without console errors; the demo “Add to revision plan” interaction updated the UI; the demo workspace had no horizontal overflow at a 390×844 viewport. Browser screenshot capture timed out, so no screenshot artifact was added.
- Backend blocking Ruff check: not run because the checked local venv references a missing Python executable.
- Backend Docker tests/migrations: not run because local Compose services were stopped. They remain required before any backend item is declared complete.

## Completion template

When an item is completed, update it to `[x]` and append:

- **Implemented:** concise description and changed files.
- **Verified:** exact tests/checks run and their result.
- **Follow-up:** any intentionally deferred work or `None`.

Then display the remaining backlog so the next item can be selected.
