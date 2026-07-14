# Latency And Postgres Runbook

Use this when validating reader, manuscript, library, character graph, and world-building latency changes on staging or production. Do not edit `.env` files for these checks; set temporary shell variables or inspect the deployed VPS service configuration directly.

## Critical Routes

Measure these routes before and after backend or database changes:

- `GET /api/v1/books`
- `GET /api/v1/books/{book_id}/reader/bootstrap?profile=critical`
- `GET /api/v1/books/{book_id}/reader/bootstrap?profile=full`
- `GET /api/v1/books/{book_id}/manuscript/bootstrap?profile=critical`
- `GET /api/v1/books/{book_id}/manuscript/bootstrap?profile=full`
- `GET /api/v1/reader/{book_id}/chapter/{chapter_number}`
- `GET /api/v1/reader/{book_id}/relationships`
- `GET /api/v1/reader/{book_id}/timeline`
- World-building bootstrap and gap/integration endpoints used by the manuscript workspace

The API logs slow route timings through `SLOW_REQUEST_LOG_MS`. Keep the threshold conservative in production, for example `800`, unless log volume becomes noisy.

## Query Evidence

`pg_stat_statements` must be enabled by the database before this query returns rows. The local Docker database may not have it enabled.

```sql
select
    round(total_exec_time::numeric, 2) as total_ms,
    calls,
    round(mean_exec_time::numeric, 2) as mean_ms,
    rows,
    left(query, 240) as query
from pg_stat_statements
where query ilike any (array[
    '%from books%',
    '%from chapters%',
    '%from characters%',
    '%from character_relationships%',
    '%from world_building_documents%',
    '%from world_elements%',
    '%from world_notes%'
])
order by total_exec_time desc
limit 30;
```

For individual hot queries, run:

```sql
explain (analyze, buffers)
select ...
```

Check for:

- sequential scans on large author-owned tables when a selective `book_id`, `user_id`, `chapter_number`, `created_at`, or `updated_at` predicate exists
- large `Rows Removed by Filter` counts
- sort nodes that spill or sort many rows before pagination
- nested loops where the inner relation lacks an index on the join/filter columns
- queries building unpaginated graph or timeline payloads when the caller only needs the first page

## Composite Indexes Added For Latency

The latency migration adds workload-matched composite indexes for:

- library ownership and hidden-book sorting
- collaborator invite lookup
- note and annotation chapter/update filters
- series book ordering
- character and character-state chapter lookups
- book chunk ordering
- relationship graph book/chapter and character/chapter filters
- chapter summary mode lookup
- wiki and quote lookups
- world-building document, element, identity, and note filters

Verify representative indexes after migration:

```sql
select indexname
from pg_indexes
where schemaname = 'public'
  and indexname in (
    'ix_books_user_hidden_created',
    'ix_book_collaborators_email_status_invited',
    'ix_characters_book_first_name',
    'ix_character_relationships_book_from',
    'ix_character_relationships_book_a_from',
    'ix_character_relationships_book_b_from',
    'ix_world_building_documents_book_active_updated',
    'ix_world_elements_book_usage_name',
    'ix_world_notes_book_type_created'
  )
order by indexname;
```

## Supabase And PgBouncer Safety

The backend uses psycopg with `prepare_threshold=None`, which avoids server-side prepared statement issues through transaction-pooling PgBouncer. Preserve this behavior unless the deployment is confirmed to use direct database connections or session pooling.

For Supabase-hosted Postgres:

- use the pooler connection string for normal web/API traffic when appropriate for the deployment
- keep direct database URLs for migrations and administrative checks
- do not grant `anon` or `authenticated` table access unless the table is intentionally exposed through the Supabase Data API
- do not add RLS policies for backend-only tables just because a migration adds indexes

## VPS Pool Sizing

For each deployed process type, estimate worst-case application connections:

```text
connections = process_count * (DATABASE_POOL_SIZE + DATABASE_MAX_OVERFLOW)
```

Add API, worker, beat/scheduler, one-off job runners, and migration/admin shells separately. Keep the total below the database or PgBouncer usable connection budget after reserving headroom for:

- migrations
- psql/admin sessions
- Supabase internal connections
- connection spikes during deploy overlap

For a small VPS, prefer smaller per-process pools and more predictable worker concurrency over large overflow. Example starting points:

- API process: `DATABASE_POOL_SIZE=3`, `DATABASE_MAX_OVERFLOW=2`
- Worker process: `DATABASE_POOL_SIZE=2`, `DATABASE_MAX_OVERFLOW=1`
- If multiple API or worker processes run on the same VPS, recalculate total connections before increasing either value.

Do not apply these values blindly. Confirm actual process counts and database connection limits on the VPS before changing service configuration.
