# Cache Strategy

LoreVia uses cache-aside caching. Postgres, object storage, and external providers remain the source of truth; Redis and TanStack Query are acceleration layers only.

## Backend Redis

Redis stores JSON payloads, rate-limit counters, locks, Celery broker data, and short-lived tokens. Application data must be reconstructable from the durable source of truth.

| Namespace | Owner | TTL | Invalidation | Source of truth |
| --- | --- | ---: | --- | --- |
| `advisor:book:*` | Advisor | 5-10 minutes, synopsis 7 days | TTL plus namespace delete after semantic manuscript changes | Postgres intelligence tables and LLM recomputation |
| `advisor:series:*` | Advisor | 10 minutes | TTL plus namespace delete after series/book changes | Postgres series/book records and LLM recomputation |
| `story_context:*`, `series_story_context:*` | Advisor | 10 minutes | Version marker in key plus TTL | Postgres manuscript intelligence tables |
| `book_overview:*`, `writer_workspace:*` | Books | 2 minutes | Book cache-version marker in key plus TTL | Postgres book/workspace records |
| `writing_dashboard:*` | Dashboard | 2 minutes | User dashboard cache-version marker and day marker in key plus TTL | Postgres user/book/progress records |
| `reader_events:*`, `reader_timeline:*`, `reader_relationship_evolution:*` | Reader | 2 minutes | Book and reader-progress cache-version markers in key plus TTL | Postgres reader progress, event, and relationship records |
| `public:user_profile:*` | Public | 5 minutes | Public profile cache-version marker in key plus TTL | Postgres public profile/book/forum records |
| `public:forum:*` | Public | 2 minutes | Public forum cache-version marker in key plus TTL | Postgres forum records |
| `public:books`, `public:book:*`, `public:chapter:*` | Public | 5 minutes for lists/detail, 1 hour for chapters | Explicit delete or TTL after catalog/moderation changes | Postgres public book/chapter records |
| `character:profile:*` | Characters | `settings.REDIS_TTL_CHARACTER_PROFILE` | TTL | Postgres character records |
| `chapter:summary:*` | Reader | `settings.REDIS_TTL_SUMMARY` | TTL and recomputation | Postgres chapter summary records |
| `relationship:graph:*`, `book:search:*`, `recall:*` | Reader | Settings-driven TTLs | TTL | Postgres/vector search recomputation |
| `embedding:*` | Embeddings | 30 minutes | Text/model hash plus TTL | Embedding provider and tracked DB usage |
| `cross_book_intelligence:*` | Intelligence | 30 minutes | Input snapshot hash plus TTL | Postgres book/intelligence records |

## Version Markers

Mutable aggregate caches should include one of the version markers in the key:

- `cache_version:book:{book_id}` for book, character, chapter, relationship, workspace, and manuscript changes.
- `cache_version:series:{series_id}` for series-level advisor context.
- `cache_version:user_dashboard:{user_id}` for dashboard counts and writing stats.
- `cache_version:reader_progress:{book_id}:{user_id}` for reader-only progress views.
- `cache_version:public_profile:{user_id}` and `public:forum:version` for public surfaces.

When adding a mutation, update the relevant marker in the same service or route path that commits the durable change.

## Frontend Cache

TanStack Query is the browser cache. Query keys are namespaced in `frontend/src/lib/query/cacheKeys.ts`, with a default `staleTime` of 30 seconds and `gcTime` of 5 minutes. Mutation helpers should invalidate the narrowest stable key prefix that covers affected views.

The service worker is network-only. Do not cache authenticated API responses or reader/workspace data in the service worker unless a scoped offline product requirement is added first.

## Operations

Admin platform metrics and local preflight report Redis memory, key count, connected clients, and sampled key-prefix counts. Prefix counts are diagnostic samples, not billing or correctness data.
