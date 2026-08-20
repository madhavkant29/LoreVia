# LoreVia Production Readiness Audit

Last reviewed: 2026-08-13

## Executive assessment

LoreVia has a sound service-oriented application structure, explicit book-scoped authorization helpers, durable task-control models, signed Paddle webhooks, bounded upload parsing, structured logs, and a realistic VPS deployment topology. It was functional, but not ready to be treated as a strong multi-user production boundary: browser state could cross account boundaries on a shared profile, Supabase OAuth could link an account without explicit email confirmation, capability URLs could enter access logs, and several asynchronous workflows could duplicate work or preserve partial state.

This pass fixes the highest-confidence issues that do not change intended product behavior or require a schema migration. The most serious remaining risk is replacement-style manuscript processing: existing derived data can be removed before its replacement is completely available. Billing event ordering, crash-safe webhook leases, and several missing uniqueness constraints also require reviewed migrations. No migration was created, edited, applied, or tested during this audit, in accordance with repository policy.

## 1. Current architecture

The concise component and data-flow map is in [ARCHITECTURE.md](ARCHITECTURE.md). In summary:

- Next.js 15 and React 19 provide the browser application. Axios calls the same-origin `/api/v1` surface; TanStack Query owns server state and Zustand owns authentication and preferences.
- FastAPI runs under Gunicorn/Uvicorn. Routes delegate workflows to `services/` and reusable domain logic to `utils/`.
- PostgreSQL is the source of truth. pgvector stores book and character embeddings. Redis provides Celery transport, session/security state, rate limiting, leases, and derived caches.
- Dedicated Celery queues handle extraction, analysis, embeddings, intelligence, and scheduled maintenance.
- Cloudflare R2/S3-compatible storage holds uploads and generated assets. Paddle owns subscription billing; Supabase provides OAuth identity; OpenAI is the primary model provider with a configured Gemini fallback.
- Nginx, the API, Redis, workers, and Beat are represented in the VPS Compose stack. The tracked production topology does not fully represent frontend hosting.

## 2. Prioritized engineering backlog

Complexity is an implementation estimate: S is hours, M is several days, and L is a multi-stage design or migration.

### P0 — security and data-loss

| Status | Affected files | Exact problem and impact | Proposed fix | Complexity |
|---|---|---|---|---|
| Fixed | `frontend/src/lib/query/queryClient.ts`, `frontend/src/lib/stores/authStore.ts`, logout callers | The singleton query cache survived logout/account changes. User B could receive fresh cached books, chapters, chats, or notifications belonging to user A in the same SPA profile. | Cancel and clear all queries at every account boundary; reset persisted per-book state; test A→B transitions. | S |
| Fixed | `frontend/src/lib/offline/manuscriptOutbox.ts`, `frontend/src/components/author/ManuscriptOfflineSync.tsx` | IndexedDB manuscript entries were keyed only by book/chapter and globally enumerated. A later account could download or attempt to sync another user's draft. | Add user ownership and composite IDs/indexes, delete ownerless legacy rows during upgrade, scope every read/write/sync, and stop sync after identity change. | M |
| Fixed | `backend/app/api/v1/routes/auth.py`, `backend/app/utils/auth_utils.py` | Supabase OAuth could locate/link a local account from provider email without requiring explicit `email_confirmed_at`. This created a conditional account-takeover path. | Require a non-empty explicit email-confirmation timestamp before lookup/link/create; never use generic provider confirmation. | S |
| Fixed | `.github/workflows/database-migrations.yml` | The branch workflow could operate on a production database and upload a raw database dump artifact. This exposed private manuscripts, identities, billing data, and secrets while coupling deploy state to a push. | Keep CI migration validation isolated; remove production mutation and raw dump upload. Production migrations remain a separately approved VPS release operation. | S |
| Fixed | `backend/app/utils/logging/errors.py`, `backend/app/main.py`, `backend/start.sh`, `ops/nginx/nginx.conf` | Capability JWTs in guest paths, query strings, or referrers could enter application, Gunicorn, and Nginx logs. Log readers could replay them. | Scrub JWT-shaped values, sanitize middleware paths, disable raw Gunicorn request-line logging, and log only a safe path without query/referrer at Nginx. | S |
| Open | `backend/app/workers/consumers/extraction_consumer.py`, chapter/mention/chunk services | Reprocessing can commit deletion of last-known-good chunks/mentions before embeddings and downstream analysis finish. A transient provider/worker failure can leave a book with incomplete derived intelligence. | Introduce generation-scoped staging rows and atomically promote a complete processing generation; retain the prior generation until promotion. Requires schema design and migration. | L |
| Open | `backend/app/core/config.py`, recovery/email routes | Production safety depends on `DEBUG` being false; debug mode can expose development-only token behavior and reduce cookie/host protections. There is no explicit, independent production-mode fail-fast. | Add an explicit deployment environment setting and fail startup when production invariants conflict (`DEBUG`, local origins, weak secrets, local storage). Do not infer production only from a URL. | M |

### P1 — reliability and correctness

| Status | Affected files | Exact problem and impact | Proposed fix | Complexity |
|---|---|---|---|---|
| Fixed | `backend/app/services/task_execution_service.py` | A duplicate delivery with the same Celery task ID could reclaim an already-running execution. Redis failures during cleanup could also downgrade a DB-committed success. | Make the locked DB row authoritative, reject every live running claim, treat Redis leases as advisory, and protect terminal states from late failure/pause writes. | M |
| Fixed | `backend/app/workers/celery_app.py` | Request context used publish signals, which run in the producer rather than around task execution. Worker logs/traces could lack request correlation or retain stale context. | Install context in `task_prerun` from task headers and clear it in `task_postrun`. | S |
| Fixed | `backend/app/services/paddle_webhook_service.py` | Unexpected ordinary exceptions such as `KeyError` could leave a delivery marked `processing`, preventing safe retry. | Catch all ordinary processing exceptions at the boundary, roll back, mark failed, and re-raise. | S |
| Open | `backend/app/services/paddle_webhook_service.py`, `backend/app/models/billing.py` | A hard process kill can still leave a webhook in `processing` forever; there is no processing lease/expiry. | Add claimed-at/lease fields or a lease table and permit atomic recovery after expiry. | M |
| Open | billing models and Paddle webhook handlers | Valid out-of-order provider events are applied in delivery order, so an old event can overwrite a newer subscription state. | Persist Paddle `occurred_at`/version and update aggregates only when the incoming event is newer. | M |
| Open | `backend/app/api/v1/routes/billing.py`, billing services | Checkout state can be mutated before the provider request succeeds, and provider creation lacks a durable application idempotency key. | Persist a checkout attempt/idempotency record, call Paddle with that key, and commit subscription transition only after a valid provider response. | M |
| Fixed | `backend/app/api/v1/routes/webhooks.py`, `backend/app/utils/webhook_request_utils.py` | Paddle bodies were unbounded in application code, allowing memory pressure before JSON parsing. | Stream-capture at most 1 MiB and use those exact bytes for signature verification and parsing. | S |
| Fixed | `backend/app/api/v1/routes/world_building_notes.py`, `backend/app/services/world_building_access_service.py` | A note could reference a world element from another book, violating tenant integrity even though the note itself was book-scoped. | Resolve the referenced element by both element ID and authorized book ID before write. | S |
| Fixed | `backend/app/api/v1/routes/beta_reads.py`, `backend/app/api/v1/router.py` | Public guest-review routes inherited the authenticated router limiter/dependency, coupling anonymous capability access to authenticated Redis policy. | Mount guest routes separately and retain their explicit public-asset limiter. | S |
| Fixed | `backend/app/api/v1/routes/books/lifecycle.py` | Capability-protected private covers could be cached as public content beyond the capability lifecycle. | Return `private, no-store`. | S |
| Fixed | frontend logout call sites and `frontend/src/lib/api/auth.ts` | Logout cleared CSRF state before attempting server revocation; the request could fail deterministically and leave the refresh session active. | Attempt bounded server logout while CSRF exists, then always clear local state in `finally`; bound Supabase cleanup. | S |
| Open | upload/book ingestion routes and storage service | Object upload and DB state changes are not a single atomic unit. Failures can leave orphaned objects or DB rows pointing to incomplete ingestion. | Use a durable upload state machine and compensating deletion; finalize the book only after object verification and dispatch persistence. | M |
| Open | advisor job routes/workers/models | Advisor async jobs lack the same atomic claim, lease, outbox, and retry controls as core processing. A crash can strand work and duplicate expensive LLM calls. | Adopt `TaskExecution`/outbox semantics or a domain-specific leased job record with terminal-state guards. | M |
| Open | analysis task wrappers and consumers | Some transient analysis failures are marked queued, but the wrapper does not actually schedule/retry them. The stored state and real queue state diverge. | Raise a retryable exception through one retry owner, apply exponential backoff/jitter, and mark terminal after the retry budget. | M |
| Open | `backend/app/models/book.py`, intelligence/reader models | Logical identities lack DB uniqueness for `(user_id, book_id)` reading progress, `(book_id, number)` chapter, `(book_id, chunk_index)` chunk, and `(chapter_id, mode)` summary. Races can create duplicate/corrupt reads. | Deduplicate existing rows and add reviewed unique constraints/indexes in new migrations. | M |
| Open | copyright-report routes/services | Anonymous reports can trigger product-visible enforcement without strong identity/reputation controls, enabling Sybil censorship. | Separate intake from enforcement, require moderation or corroboration, and rate-limit by multiple trustworthy signals. | M |
| Open | `frontend/src/app` autosave/pagehide paths | `sendBeacon` cannot attach the required CSRF header, so final pagehide saves may fail while appearing fire-and-forget. | Use `fetch(..., {keepalive:true})` with CSRF, or explicitly rely on the account-scoped durable outbox. | S |
| Open | `ops/nginx/nginx.conf`, rate-limit client-IP utilities | Trust in `X-LoreVia-Edge-Verified` is safe only while the API port is private to the tracked Nginx peer. Direct access lets a client spoof the signal. | Enforce network isolation/firewall and optionally authenticate the hop or derive trust from a known proxy CIDR/socket. | M |
| Open | Redis-backed authentication/rate-limit dependencies | Redis outages fail a wide set of requests uniformly. Availability and security behavior are not classified per endpoint. | Define fail-closed policy for auth/step-up and bounded fail-open or local degradation only for safe derived cache/read paths. | M |
| Open | production Compose/deploy files | The backend stack is represented, but frontend runtime/attachment is not. Releases can produce incompatible frontend/backend versions. | Document the actual frontend host or add it to the release manifest, health checks, and rollback contract. | M |

### P2 — performance and cost

| Status | Affected files | Exact problem and impact | Proposed fix | Complexity |
|---|---|---|---|---|
| Fixed | `backend/app/core/storage.py` | S3/R2 calls lacked explicit connect/read timeouts and bounded retry configuration. Network stalls could occupy workers indefinitely. | Configure finite connection/read timeouts, TCP keepalive, and standard bounded retries. | S |
| Fixed | `backend/app/services/email_service.py`, `backend/app/api/v1/routes/reader/core.py` | Synchronous provider/storage SDK calls ran on the async event loop in important paths, reducing API concurrency. | Offload blocking calls with `asyncio.to_thread`. | S |
| Open | remaining R2/storage call sites | Other synchronous S3 operations still run from async workflows and can serialize requests under latency. | Centralize async offload in the storage service or adopt an async-compatible adapter without changing its contract. | M |
| Open | Gemini fallback client | The fallback uses an API shape that may not match the pinned SDK and bypasses primary-provider timeout, usage accounting, rate limiting, and observability. | Put every provider behind the same controlled invocation service and add contract/failure tests. | M |
| Open | intelligence/advisor prompt and retrieval services | Similar prompts, embeddings, tokenization, and context assembly are repeated; cache keys are not consistently tied to content/model/prompt versions. | Cache immutable embeddings/token counts and selected deterministic results by content hash + model + prompt version; invalidate on generation promotion. | M |
| Open | RAG/vector queries | Retrieval must prefilter book and spoiler boundaries while preserving efficient vector plans; production selectivity and recall are not measured. | Capture `EXPLAIN (ANALYZE, BUFFERS)` on representative data, tune composite metadata indexes/search parameters, and add recall/latency evaluation. | M |
| Open | reader/export/advisor query services | Several collection builders perform repeated per-chapter/per-character lookups. Large manuscripts risk N+1 latency and connection pressure. | Batch eager loads/aggregates and add query-count regression tests for large fixtures. | M |
| Open | SQLAlchemy/database configuration | There is no clear per-statement timeout and pool saturation telemetry for long vector/analysis queries. | Add role-appropriate statement timeouts, pool wait metrics, and slow-query attribution before tuning pool size. | M |
| Open | Celery routing | Maintenance shares the single-concurrency intelligence queue, allowing periodic work to starve interactive advisor requests. | Route maintenance to a low-priority/dedicated queue and set explicit worker capacity. | S |
| Open | `frontend/src/lib/api/client.ts` and callers | General API calls have no consistent timeout/cancellation policy; stale requests can hold UI loading states. | Set sensible defaults by request class, preserve AbortSignal support, and give long-running/SSE routes explicit exceptions. | S |
| Open | large list/search endpoints | Pagination and response shaping are inconsistent across domains, creating growing payloads and serialization work. | Add cursor/page limits to unbounded collections while preserving current defaults during a deprecation window. | M |

### P3 — maintainability and safeguards

| Status | Affected files | Exact problem and impact | Proposed fix | Complexity |
|---|---|---|---|---|
| Fixed | `backend/Dockerfile.api`, `backend/worker-start.sh` | API/worker processes could remain root after startup preparation. | Create a fixed unprivileged user and drop privileges after the optional local volume normalization step. | S |
| Open | baseline Alembic migration | The baseline dynamically reflects current ORM metadata, making historical schema recreation depend on current code and masking drift. | Freeze immutable explicit DDL in a new reviewed baseline strategy; never rewrite shipped history. | L |
| Open | CI dependency audit configuration | Some dependency/security checks are non-blocking (`|| true`), so known actionable vulnerabilities do not protect merges. | Establish severity/allowlist policy and make violations fail after current findings are triaged. | S |
| Open | frontend E2E and backend integration fixtures | Frontend E2E is primarily network-mocked and does not exercise cookie/CSRF/proxy/database contracts end to end. | Add a small Compose-backed acceptance suite for login, tenant isolation, upload, billing webhook, and task replay. | M |
| Open | frontend lint/type surface | Several lint rules are disabled and large client components combine fetching, state, and rendering. This raises regression cost and unnecessary renders. | Re-enable rules incrementally and split only components with measured churn/render or testability problems. | M |
| Open | browser observability | Backend Sentry is stronger than browser exception, Web Vitals, and failed-request telemetry. Client failures are hard to correlate with request IDs. | Add consent-aware frontend error/performance reporting and propagate/display request IDs in support diagnostics. | M |
| Open | accessibility-critical flows | Dialog focus, status announcements, keyboard paths, and error associations are not consistently regression-tested. | Add axe/component checks and keyboard E2E coverage for upload, reader, billing, and destructive confirmation flows. | M |
| Open | route/service size boundaries | Some domain route/helper modules exceed the repository's intended size and mix orchestration with transformation. | Extract focused services only when modifying those workflows; avoid a cosmetic rewrite. | M |

## 3. Changes implemented

- Enforced browser tenant isolation for TanStack Query, per-book persisted state, and offline manuscript drafts.
- Hardened logout ordering and bounded remote/provider cleanup.
- Required explicit confirmed-email evidence for Supabase OAuth linking and stopped provider-body logging; new OAuth users now record current legal acceptance.
- Validated world-element ownership at the note/book boundary.
- Bounded Paddle webhook bodies and made unexpected ordinary failures retryable.
- Hardened durable task claims, terminal states, Redis-outage behavior, and Celery request-context propagation.
- Added storage network timeouts/retries and moved selected synchronous SDK calls off the event loop.
- Prevented private-cover caching and capability-token logging across application, Gunicorn, and Nginx layers.
- Removed production mutation and raw database dumps from CI migration validation.
- Dropped API/workers to an unprivileged runtime user.
- Added focused tests for authorization, OAuth, webhook limits/retries, task duplicate claims, Redis cleanup failures, cache/account transitions, offline-draft ownership, logout failures, storage timeouts, blocking-call offload, and logging redaction.

## 4. Remaining technical debt

The open rows above are not cosmetic follow-ups. The generation-staging reprocessing design, billing event ordering/leases, and uniqueness constraints are the highest correctness risks. They require deliberate schema migrations and data backfills, so they were not attempted here. Upload compensation, advisor job control, production environment fail-fast validation, Redis outage policy, and frontend deployment ownership should follow closely.

## 5. Security assumptions

1. `JWT_SECRET`, Paddle webhook secrets, Supabase credentials, R2 credentials, and database credentials are high-entropy, unique per environment, stored outside the repository, and rotated on exposure.
2. Production runs with `DEBUG=false`, HTTPS at the first trusted edge, secure cookies, a correct public application origin, and no localhost CORS origin.
3. The backend port is not internet-accessible around Nginx; only the trusted edge can supply verified forwarding headers.
4. PostgreSQL and Redis are private-network services. Redis persistence, memory policy, authentication/network ACLs, and backups match the state stored there.
5. R2 buckets are private by default; all private access is authorized server-side or uses short-lived, scoped capabilities.
6. Every child object is authorized through its owning book/user. UUID unpredictability is not an access control.
7. Manuscript text, retrieved RAG context, user prompts, filenames, model output, and webhook JSON are untrusted input.
8. Database backups are encrypted, access-audited, retention-limited, and never attached as ordinary CI artifacts.
9. Paddle is authoritative for billing, but local application of provider events must remain signature-verified, idempotent, and order-aware.
10. Late-acknowledged Celery tasks can execute more than once; replay safety is mandatory.

## 6. Scaling bottlenecks

- Intelligence has a single-concurrency worker and shares capacity with maintenance; interactive latency will rise first there.
- Replacement-style extraction/analysis keeps long workflows coupled and makes safe horizontal retries difficult until generation promotion exists.
- Synchronous R2 calls remain in several async code paths.
- PostgreSQL carries transactional, full-text/domain, and vector retrieval load without documented production query plans or pool saturation metrics.
- Redis is simultaneously broker, cache, limiter, and security/session dependency, expanding its failure blast radius.
- Large manuscripts amplify per-chapter queries, serialized payloads, prompt construction, embedding volume, and LLM spend.
- Frontend deployment is not versioned in the same tracked release topology as the API.
- Browser/server observability is asymmetric, making client-side regressions slower to identify.

## 7. Recommended next 10 engineering tasks

1. Design generation-scoped staging and atomic promotion for chunks, mentions, embeddings, summaries, and downstream intelligence.
2. Add Paddle webhook processing leases and provider-time ordering, with replay/out-of-order integration tests.
3. Deduplicate data and add reviewed uniqueness constraints for chapters, chunks, summaries, and reading progress.
4. Make checkout creation a durable idempotent workflow and enqueue post-commit billing email through an outbox.
5. Move advisor jobs onto durable atomic claim/lease/outbox/retry infrastructure; fix the analysis retry owner at the same time.
6. Add explicit production-environment validation and fail startup on debug, weak secrets, unsafe CORS, or unintended local storage.
7. Make upload/ingestion finalization compensating and observable so storage and database state cannot diverge silently.
8. Profile representative pgvector/RAG and large-book query plans; then batch N+1 paths and version content/model caches.
9. Separate maintenance from interactive intelligence capacity and add queue age, retry, poison-job, LLM usage, DB pool, and cache metrics.
10. Unify frontend/backend release ownership and add a small real-stack acceptance suite covering login, cross-tenant denial, upload, Paddle replay, and Celery redelivery.

## Validation notes

Frontend validation completed successfully: the full unit suite passed (224 files, 1,013 tests), a focused isolation/logout rerun passed (5 files, 56 tests), TypeScript passed, and targeted ESLint passed. Ruff passed across the affected backend application and test files, and `git diff --check` passed. Docker-backed pytest could not be executed because the local Docker daemon was stopped and Windows denied starting its service; it should be the first follow-up verification. Migration execution and migration tests were intentionally excluded because agent-driven migration operations are prohibited by repository policy.
