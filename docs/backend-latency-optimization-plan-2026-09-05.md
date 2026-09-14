# Backend and database latency optimization plan

Date: 2026-09-05. Updated: 2026-09-10. Status: application changes and an unpublished migration are implemented in the local checkout; production validation remains.

This plan combines the five spans in the supplied screenshot with a focused review of the current working tree. Many application files already have local edits; the findings describe that checkout, not a verified deployed revision. No production traces, database statistics, runtime configuration, or deployed indexes were inspected. Code patterns below are observed; their contribution to production latency remains to be measured.

Implemented locally:

- Notification list/read-all now use a service layer, bulk read-all updates, bounded pages, and no default revision digest rebuild.
- Missing cover generation was removed from library/cover read paths and moved to ingestion-time handling.
- Advisor Redis caches now use book/series version markers instead of request-time prefix scans, and in-flight writers are rejected when their captured version is stale.
- Large and multi-file manuscript imports now stage their source, persist a durable job, return `202 Accepted`, expose status/cancel/retry endpoints, recover undispatched or stale jobs, and report parsing/publication progress. Small imports retain the synchronous contract. Multi-chapter imports enqueue durable extraction instead of running extraction inline in the HTTP request.
- Chapter saves now download and compare the old revision before the final lock, stage immutable content and media keys outside the transaction, then reacquire and recheck book access, collaborator scope, rebuild state, content version, and word capacity before committing. Failed/conflicting writes clean unused staged objects.
- Critical manuscript workspace/bootstrap responses omit scene bodies unless explicitly requested.
- Initial character consumers request only the fields they need; the backend projects sparse navigation fields and skips optional relationship/state/voice queries unless requested.
- Revision intelligence now caches by the book version marker, coalesces cold fills, and limits chapter-version loading to the latest two rows per chapter with a stable tie-breaker.
- Revision digests refresh after relevant committed book changes through a coalesced maintenance task and update stored notifications only when their signature changes.
- Library reads now have stable cursor pagination over owned/shared books, database-side hidden filtering, page-bounded repair checks, and frontend load-more support. Read paths do not render or upload missing covers.
- Processing allowance display summaries use one aggregate statement instead of five sequential aggregate queries.
- Semantic chunk search now orders by pgvector cosine distance and computes similarity separately for output.
- S3 and embedding clients are reused per process/event loop, with shutdown cleanup.
- Redis cache operations have bounded connection/operation timeouts; optional cache failures degrade to direct work while correctness-critical lock callers retain failure semantics.
- `maintain_task_executions` now has Redis overlap protection. Book repair combines repeated counts, preloads candidate chapters, uses a fair cursor, and records per-step timing. Maintenance work has its own queue and also recovers durable import jobs. The DB pool has an explicit checkout timeout.
- Ingestion logs separate download, cover, copyright, parse, budget, stage, queue, and total duration.

The unpublished migration `backend/app/db/migrations/versions/20260909_add_manuscript_import_jobs_and_latency_indexes.py` creates the backend-only durable import-job table and the notification, library, chapter-version, scene-order, task dispatch/lease, and lexical-search indexes used by these query shapes. It has explicit upgrade/downgrade paths and idempotent existence checks. It has not been applied to staging or production and must be reviewed against live catalog state and representative query plans before rollout.

No production traces, database statistics, runtime configuration, or deployed indexes were inspected. The code addresses verified avoidable work, while its production effect still needs the measurement work below. The proposed p95 values remain acceptance targets rather than measured results.

## Priorities and evidence

| Order | Workstream | Evidence | Desired result |
| --- | --- | --- | --- |
| 0 | Baseline and query evidence | Screenshot gives aggregate p95 values but no query breakdown, request counts per span, payload sizes, or deployment revision | Reproducible before/after measurements |
| 1 | Notifications | Read-all p95 17,929 ms; response path also rebuilds revision intelligence for up to six books | A bounded update and list response |
| 2 | Library reads and cover generation | Library serialization downloads/renders/uploads missing covers sequentially | Library GET performs no cover generation or upload |
| 3 | Cache invalidation on writes | Advisor invalidation scans Redis once per namespace and awaits completion | Invalidation cost independent of unrelated Redis key count |
| 4 | Manuscript save and import | Import p95 14,490 ms; chapter saves and replacements hold row locks across storage work | Short transactions; responsive saves; durable background processing for large imports |
| 5 | Critical bootstrap and character lists | Critical manuscript bootstrap loads all scene bodies/HTML; sparse character fields are filtered after work | Small initial payload and work proportional to requested data |
| 6 | Revision intelligence and dashboard aggregates | Multiple whole-book reads and all historical chapter versions; stats compose several sequential aggregates | Reuse derived results and avoid redundant reads |
| 7 | Search query and indexes | Vector search orders by a transformed similarity expression despite a modeled HNSW index; lexical search computes tsvector expressions | Index-compatible queries with preserved relevance and spoiler boundaries |
| 8 | Connection and client reuse | Database pools are per process; storage clients are constructed per operation; embedding clients close per call | Predictable connection pressure and fewer connection setups |
| 9 | Ingestion and maintenance | process_book p95 4,726 ms; repair 971 ms; task maintenance 228 ms | Lower processing and recovery overhead without slower recovery |

The screenshot's total duration is accumulated span time, not CPU utilization. Prioritize user-visible latency and frequent workloads alongside total time. Proposed targets below are acceptance goals, not promised speedups.

## Stage 0 — Establish the baseline

Extend the existing latency runbook rather than introducing another observability system. Its bootstrap URLs need checking: current decorators use `/books/{book_id}/reader-bootstrap` and `/books/{book_id}/manuscript-bootstrap`, not the slash-separated bootstrap paths listed in the runbook.

1. Record the deployed revision, API process count, Celery child-process counts, PostgreSQL/pgvector versions, actual DB/pooler topology, and VPS-to-DB/Redis/storage latency. Repository defaults do not prove deployed settings.
2. Capture p50/p95/p99, sample count, errors, query count, SQL time, pool checkout wait, transaction/lock duration, Redis time, storage/provider time, response bytes, and event-loop delay for the paths below. Distinguish cache hits, cold misses, retries, and concurrent refreshes.
3. Measure job acceptance, queue wait, worker runtime, and total completion separately. Preserve the existing ingestion stage timing logs.
4. Read `pg_stat_statements` if already available; rank by total time and mean time with call counts. It does not supply route p95. Have the maintainer arrange instrumentation if unavailable; do not implicitly install extensions or restart production.
5. Inspect representative SELECT plans with `EXPLAIN (ANALYZE, BUFFERS)` on a local representative dataset first. ANALYZE executes the statement; production diagnosis must use an explicitly confirmed target and bounded read-only workload.
6. Inspect active locks, idle-in-transaction connections, dead tuples, autovacuum/analyze history, sort spills, table/index sizes, and deployed index validity. Use evidence to distinguish expensive SQL from time waiting for connections or remote services.

Use small and large libraries, short and long manuscripts, many historical versions, missing covers, simultaneous saves, cold/warm caches, and concurrent background processing. Record exact fixture sizes so comparisons remain meaningful. Start with modest concurrency, then increase within the confirmed connection budget.

Sources: [PostgreSQL statement statistics](https://www.postgresql.org/docs/current/pgstatstatements.html) and [EXPLAIN](https://www.postgresql.org/docs/current/sql-explain.html).

## Stage 1 — Remove avoidable work from common requests

### Notifications

Evidence: `backend/app/api/v1/routes/notifications.py:93`; `backend/app/utils/notification_utils.py:547`.

- Extract notification update/list orchestration into the appropriate service; route handlers should call that service rather than other route handlers.
- Replace loading and mutating all unread ORM objects with one user-scoped SQL UPDATE, preserving the unread predicate and one shared timestamp.
- Explicitly disable revision synchronization in the response path. Direct Python calls currently omit the parameter whose default is a FastAPI Query object; eliminate reliance on endpoint defaults in internal calls.
- Return the normal bounded notification page and a count consistent with concurrent notifications. Do not unconditionally return zero unread.
- Move digest refresh toward durable events after relevant manuscript/analysis changes. Coalesce repeated refreshes; preserve idempotency and define whether genuinely new findings reset read state.
- Once background refresh is reliable, ordinary notification listing should read stored notifications rather than synchronously rebuilding book intelligence.

Acceptance: proposed read-all p95 under 500 ms on the agreed workload; zero digest builder calls; no unbounded ORM notification load; other users untouched; empty, already-read, concurrent arrival, changed-digest, and failure cases covered.

### Library covers and pagination

Evidence: `backend/app/api/v1/routes/books/core.py:169`; `backend/app/utils/books/serialization.py:54` and `:381`.

- Generate and persist covers at upload/import or through a deduplicated repair job. Return the existing cover or a stable placeholder immediately from reads.
- The current helper only flushes the cover key. The normal library GET has no explicit commit, so generated objects can outlive an uncommitted key and work can repeat. Make cover persistence an explicit worker transaction and verify retry behavior.
- Keep existing batched progress/word-count queries. They already address part of the N+1 problem.
- Add cursor pagination for growing owned/shared libraries, with a stable ordering, deduplication, hidden-book filtering, and a compatible frontend contract. Avoid processing-state repair dispatch loops over an entire library on each GET; retain targeted, deduplicated recovery.

Acceptance: no storage upload, PDF rendering, or cover mutation during library GET; bounded page size; no duplicate or missing books across pages; correct sharing permissions; proposed warm first-page p95 under 500 ms.

### Redis invalidation

Evidence: `backend/app/core/redis.py:351`; `backend/app/utils/advisor_utils.py:116`; chapter save and manuscript import await these helpers.

- Replace request-time prefix scans with versioned advisor keys, extending the version-marker design already used by other caches. Old entries should expire through TTL.
- Update every affected cache reader and writer before removing namespace deletion. Ensure in-flight fills use the version they read so they cannot overwrite fresh results.
- Batch independent version-marker operations. Preserve monotonic/atomic invalidation semantics and all book/series dependencies.
- Use bounded cache timeouts and coalesce expensive cache misses. Keep authorization, locks, quotas, and durable task coordination semantics distinct from optional cache fallback.

Acceptance: save/import paths issue no Redis SCAN; invalidation command count depends on touched entities, not keyspace size; edits invalidate all affected advisor results; concurrent fills and cache outages tested. [Redis pipelining](https://redis.io/docs/latest/develop/using-commands/pipelining/) supports reducing independent command round trips.

## Stage 2 — Shorten manuscript transactions and large imports

Evidence: `backend/app/services/chapter_content_service.py:90`; `backend/app/services/manuscript_import_service.py:90`; `backend/app/api/v1/routes/books/imports.py:254`.

### Chapter save

- Instrument the time from FOR UPDATE until commit/rollback. Currently it includes reading old content, comparing content, capacity checks, snapshots, and content persistence.
- Design a prepare-then-commit flow: validate and stage immutable content outside the final row-lock window; reacquire/recheck the expected version; commit the version, snapshot reference, accounting, and content pointer atomically.
- Revalidate permissions, quota, and mutable project state at the authoritative write boundary as needed. Do not make a stale preliminary check authoritative.
- Never overwrite the live storage object before winning the version check. Define cleanup of unused staged objects and behavior after storage success followed by DB failure.
- Preserve client mutation IDs, existing unchanged-save behavior, 409 conflict handling, history, and word accounting. Move expensive derived analysis to existing durable task infrastructure.

Acceptance: no remote I/O while holding the final chapter row lock; proposed unchanged save p95 under 300 ms and normal single-chapter save under 1 s for an agreed chapter size; no lost updates, duplicate word charges, or missing snapshots in concurrent-save tests.

### Import

- Batch existing chapter/media lookups and post-import chapter queries. Consolidate commits where they do not represent a necessary recovery boundary.
- Use bounded parallelism for independent parsing/storage work. CPU-heavy parsing should not monopolize the API event loop.
- Keep small single-chapter imports responsive. Large uploads use the new durable `manuscript_import_jobs` record: stage source objects before returning 202, expose progress/status/cancel/retry, and recover undispatched or stale jobs from maintenance.
- Replace direct inline chapter extraction on applicable non-editor branches with durable execution. Preserve replace-existing and structure/scene behavior.
- Decide import atomicity explicitly: all-or-nothing or resumable per-chapter publication. The UI must accurately represent partial completion and failures.

Acceptance: proposed acceptance latency under 1 s after the upload is durably stored; measure upload transfer and storage time separately. Benchmark total completion by file format, bytes, words, and chapter count; returning 202 alone is not a throughput improvement. Test duplicate submission, worker crash, retry, cancellation, version conflict, malformed file, and quota exhaustion. Add frontend progress/error E2E coverage.

Do not run concurrent operations on the same AsyncSession. Batch SQL first; use separate bounded sessions only for work with genuinely independent transaction semantics. [SQLAlchemy concurrency guidance](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#using-asyncsession-with-concurrent-tasks).

## Stage 3 — Reduce read volume and repeated computation

### Critical bootstrap and sparse characters

Evidence: `backend/app/api/v1/routes/books/bootstrap.py:184`; `backend/app/utils/books/workspace_search.py:46`; `backend/app/utils/books/scene_serialization.py:16`; `backend/app/services/character_listing_service.py:26`.

- The frontend already requests critical reader and manuscript profiles. Preserve this existing optimization.
- Critical manuscript bootstrap still loads all scenes and serializes both body and HTML through the workspace tree. Add a metadata-only tree contract; fetch active scene/chapter content on demand. Audit frontend consumers before changing required fields.
- Return only required character fields for initial navigation. Currently voice profiles and aliases are eagerly loaded, relationships are fetched, and sparse fields are filtered after serialization. Plan query projections from requested fields, while retaining evidence needed for visibility scoring and permission checks.
- Fetch optional panels when opened. Avoid repeating chapter reports inside full bootstrap and revision intelligence; reuse a request-scoped read context where practical.

Acceptance: critical tree has no manuscript bodies/HTML; navigation and editing still work; collaborator chapter limits preserved; recorded response-byte reduction on large manuscripts; proposed warm critical bootstrap p95 under 750 ms.

### Revision intelligence and dashboard stats

Evidence: `backend/app/utils/books/revision_service.py:51`; `backend/app/api/v1/routes/books/core.py:215`; `backend/app/services/processing_allowance_service.py:124`.

- Revision intelligence loads chapters, characters, plots, scenes, wiki, voice profiles, and all chapter-version history. Load only columns and history needed by each computation; use latest-per-chapter queries where that matches semantics rather than arbitrarily truncating history.
- Cache derived book results by relevant content/analysis/workspace versions. Coalesce simultaneous cold builds and regenerate after relevant writes; scope caches by viewer permissions wherever output varies by viewer.
- Dashboard writing stats are already cached and library aggregates are already batched. Optimize the remaining composed aggregate work, including the five sequential allowance sums.
- Consolidate related aggregates using subqueries/CTEs that avoid join multiplication. Cache display-only snapshots with mutation invalidation and time-window rollover. Keep quota enforcement authoritative and transactionally correct; do not reuse stale display caches for write authorization.

Acceptance: warm requests avoid repeated whole-book/history scans; query-count reduction is demonstrated; cache invalidation covers edits, analysis completion, imports, deletions, archive state, and billing changes; proposed warm stats p95 under 500 ms.

## Stage 4 — Search and targeted database improvements

Evidence: `backend/app/engine/search/semantic.py:58`; `backend/app/models/intelligence.py:29`.

1. Rewrite vector ordering to ascending cosine distance (`embedding <=> query_vector`), calculating similarity for output separately. The current `ORDER BY relevance DESC`, where relevance is `1 - distance`, matches pgvector's documented non-index-compatible expression. Verify the actual plan and installed index before attributing production time to it.
2. Evaluate nearest-candidate retrieval and threshold filtering without weakening book/chapter restrictions. An approximate index can reduce recall under selective filters; compare against exact search, test result count/recall, and inspect whether the installed pgvector version supports suitable iterative scans. Retain exact search when it wins for small per-book datasets.
3. Lexical search uses `to_tsvector('simple', bc.text)`. The new model definition and unpublished migration add a matching GIN expression index. Verify its use and cost with a representative plan after the migration is reviewed and applied.
4. Keep the existing query-embedding cache. Measure hit rate and provider latency separately from SQL latency.

Indexes authored in the unpublished latency migration:

| Query shape | Candidate if missing and justified |
| --- | --- |
| Notification user + newest-first page | notifications(user_id, created_at DESC, id DESC), aligning query tie-breaker |
| Notification unread update/count | Partial notifications(user_id) WHERE read_at IS NULL |
| Latest/history chapter versions | chapter_versions(book_id, chapter_number, created_at DESC, id DESC) |
| Per-chapter scene ordering | novel_scenes(book_id, chapter_number, sort_order, created_at), after examining NULL ordering and actual plan |
| Pending task dispatch | Compare task/status/order composites or a partial pending-dispatch index against the actual task-name filters and global ordering |
| Expired running task leases | Partial task_executions(locked_until) WHERE status = 'running' |
| Lexical chunk retrieval | GIN on the exact to_tsvector('simple', text) expression |

Existing modeled indexes already cover library ownership/hidden sorting, chapter book/number, characters, character states, relationships, and several outbox filters. Verify that these exist and are valid on the deployment before proposing more. Assess write amplification, index size, and vacuum cost as well as read latency. No blanket JSONB GIN index, partitioning, or denormalized counter rollout is justified yet.

Acceptance: plan comparison on realistic row counts, improved search DB p95, agreed recall threshold against exact results, no spoiler or tenant leakage, and acceptable write overhead. Migration execution remains a separate reviewed rollout step; this task does not apply the revision.

Sources: [pgvector query/index and filtering guidance](https://github.com/pgvector/pgvector#troubleshooting), [PostgreSQL text search indexes](https://www.postgresql.org/docs/current/textsearch-tables.html).

## Stage 5 — Connections, ingestion, and maintenance

### Connections and clients

- `backend/app/core/database.py:51` enables pre-ping and uses per-process pools; repository Compose settings specify pool size 5 and overflow 5. Compute the upper bound as the sum of process_count × (pool_size + max_overflow), including Celery child processes and deployment overlap. Pools grow on demand; this is not the number of currently open connections.
- Measure checkout and transaction duration before resizing. Shorten sessions held across network calls and reserve database headroom for API traffic. Preserve pre-ping and disabled server-side prepared statements until the actual connection topology supports a change.
- `backend/app/core/storage.py:92` constructs a new S3 client per operation. Evaluate process-local client reuse with lifecycle handling, bounded thread concurrency, and an appropriate connection pool. Never reuse a client across forked processes. If production uses local file storage, this S3 optimization does not apply. [Boto3 client guidance](https://docs.aws.amazon.com/boto3/latest/guide/clients.html).
- `backend/app/engine/embeddings/embedder.py:40` constructs embedding clients and closes them after each call. Evaluate process/event-loop-scoped HTTP client reuse and shutdown handling while preserving usage attribution, retry ownership, limits, and the existing embedding cache.

### Ingestion

- Use existing download, parse, stage-chapters, queue-chapters, and total timing logs in `extraction_book_processing_service.py`. Add missing cover/copyright/provider spans if needed.
- Chapter payload uploads already have a concurrency setting. Tune only after measuring storage saturation; avoid introducing duplicate parallelization.
- Batch chapter stub persistence and durable enqueue operations where safe. Preserve cancellation checks and recovery checkpoints while reducing redundant reads/commits.
- Compare books of equal size/format. The process_book span primarily stages ingestion and queues later tasks; measure time to usable first chapter and full analysis separately.

### Maintenance

- Task maintenance runs every minute and repair every five minutes in `celery_app.py`. Preserve prompt dispatch and existing SKIP LOCKED/outbox safeguards.
- Instrument each maintenance substep, scanned/repaired/dispatched counts, and no-op cost. Add task-level overlap protection where absent, respecting lease duration and owner-token release.
- Repair already has a Redis lock. Improve candidate selection toward genuinely stalled books, batch per-book state queries, and use fair pagination so a persistent oldest batch does not starve later books.
- Move heavy accounting/reconciliation work to its own schedule if measurements justify it. Evaluate queue isolation because maintenance shares the intelligence queue with other work; additional queues require matching workers and a resource budget.
- Review retention and autovacuum for high-churn task/outbox/notification tables. Do not delete history or change retention without a defined retention policy.

Acceptance: lower queries/time per idle tick and per repaired book, no duplicate dispatch, no starvation, unchanged or improved recovery delay, no increase in API pool wait under worker load.

## Delivery and verification

The local implementation follows this order: notifications and cover reads; cache invalidation; save transactions and import jobs; bootstrap/projections; derived aggregates; search; client reuse; maintenance. Production baseline and after-deployment comparison remain operational work.

Focused unit, contract, and chapter-save integration coverage exercises the new logic and important failure paths. All remaining backend verification commands must use `--no-deps` so Compose cannot start its migration dependency. The authored migration remains unapplied by this task.

Local verification completed for the implemented code paths:

- Fresh Docker API image build: passed.
- FastAPI application import with the new routes: passed.
- Ruff over all changed latency modules, tests, and the unpublished migration: passed.
- Focused backend unit regression suite: 265 passed after the final request-service extraction and cancellation recovery change.
- Chapter-save integration test: 1 passed. Compose also started its local migration dependency; inspection confirmed the local application database stayed at `20260805_add_user_ui_preferences` and `manuscript_import_jobs` was not created. No authored revision was applied.
- Final chapter-save and durable-import API lifecycle integration checks: 2 passed together with `--no-deps` against the disposable test database.
- Frontend API, library, and upload-modal tests: 46 passed after upload-progress wiring.
- Frontend TypeScript check: passed after upload-progress wiring.

Maintain a scorecard per change: fixture size, concurrency, p50/p95/p99, request/query count, DB and lock time, response size, errors, cache hit rate, job completion time, and correctness checks. Set explicit relative improvement thresholds after baseline for paths without measured values. Compare warm/cold runs under the same workload; avoid claiming success from a single fast request.

Production rollout requires explicit authorization for the exact deployment. Apply the unpublished migration before deploying application code that uses durable import jobs. Keep rollback possible per workstream and monitor errors, stale cache behavior, search recall, queue age, import-job age, connection pressure, and save conflicts as well as latency. No environment or deployment configuration was changed by this work.
