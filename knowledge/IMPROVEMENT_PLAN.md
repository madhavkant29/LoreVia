# LoreVia — Modular Improvement Plan

How to improve the app incrementally as it grows. Each item is self-contained — you can do them in any order within a phase. Nothing requires rewriting what already works.

The rule: **ship working first, improve running**. Never optimise something before it's proven users want it.

---

## How to read this

Each improvement has:
- **What it is** — the change
- **Why now** — the trigger that tells you it's time
- **How hard** — S (a few hours) / M (a day or two) / L (a week+)
- **Where** — which file(s) to touch

---

## Phase 1 — Make it solid (Weeks 1–6, while building MVP)

These are things to do as you build, not after. They prevent pain later.

### 1.1 Add pytest fixtures for the extraction engine
**Why now:** Every time you change the extractor prompt, you need to know you didn't break character detection. Manual testing is too slow.
**How hard:** S
**Where:** `backend/tests/unit/test_extractor.py` — add 3–5 sample text chunks with known characters and assert they're extracted correctly.

### 1.2 Add a health check that tests DB + Redis
**Why now:** The current `/health` endpoint returns `ok` even if DB is down. Railway will show "healthy" on a broken deploy.
**How hard:** S
**Where:** `backend/app/main.py` — extend the `/health` endpoint to do `SELECT 1` on DB and `PING` on Redis, return 503 if either fails.

### 1.3 Add request logging middleware
**Why now:** When something goes wrong locally you have no visibility into what the API received.
**How hard:** S
**Where:** `backend/app/main.py` — add a simple middleware that logs `method + path + status + duration` for every request. One `@app.middleware("http")` block.

### 1.4 Add a `processing_errors` column to `books`
**Why now:** When extraction fails mid-book, the status stays `processing` forever. Users have no idea what happened.
**How hard:** S
**Where:** `backend/app/models/book.py` — add `error_message: Mapped[str | None]`. New Alembic migration. Update the extraction consumer to set it on exception.

### 1.5 Rate limit the `/books/upload` endpoint properly
**Why now:** Without it, a single user can spam uploads and burn your OpenAI quota.
**How hard:** S
**Where:** `backend/app/api/deps/rate_limit.py` — already has the pattern. Add `rate_limit_upload` dep. Apply it to `POST /books/upload`.

---

## Phase 2 — Make it fast (Weeks 4–8, once users are reading)

Do these when you have real users and can measure the impact.

### 2.1 Cache chapter text in Redis, not just summaries
**Why now:** Every Smart Tap call fetches chapter metadata from DB. At >10 concurrent readers, this adds up.
**How hard:** S
**Where:** `backend/app/api/v1/routes/reader.py` — cache the `get_chapter` response in Redis with TTL 1hr. Key: `chapter:data:{chapter_id}`.

### 2.2 Add a `book_chunks` full-text index for fast name lookup
**Why now:** The Smart Tap character name lookup does a `ILIKE '%query%'` scan. On a book with 300 characters it's slow.
**How hard:** S
**Where:** New Alembic migration — `CREATE INDEX idx_characters_name_trgm ON characters USING GIN (name gin_trgm_ops)`. Requires `pg_trgm` extension (already enabled in `events.py`).

### 2.3 Stream chapter summaries instead of waiting
**Why now:** Summary generation takes 3–8 seconds. User sees a spinner. Bad UX.
**How hard:** M
**Where:** `backend/app/engine/analysis/summariser.py` — use `stream=True` on the OpenAI call and return a `StreamingResponse` from FastAPI. Frontend: use `fetch` with `ReadableStream` instead of `axios`.

### 2.4 Add a `last_processed_at` timestamp to `characters`
**Why now:** When you update the extraction prompt, you have no way to re-process only old characters.
**How hard:** S
**Where:** `backend/app/models/character.py` — add `last_processed_at: Mapped[datetime | None]`. Update it in the extraction consumer. Later: a `scripts/reprocess_book.py` that re-runs extraction on characters processed before a given date.

### 2.5 Move from polling to WebSocket for book processing status
**Why now:** The library page currently requires a manual refresh to see when a book is done. Users don't know it finished.
**How hard:** M
**Where:** `backend/app/main.py` — add a WebSocket endpoint `/ws/book-status/{book_id}`. Extraction consumer sends a message when status changes. Frontend: `useEffect` with `new WebSocket(...)` on the library page.

### 2.6 Lazy-load character trait details
**Why now:** The `GET /books/{id}/characters` endpoint returns full trait_state JSONB for every character. On books with 50+ characters this payload is large.
**How hard:** S
**Where:** `backend/app/api/v1/routes/books.py` — return only `id, name, role, first_chapter` in the list endpoint. Add `GET /characters/{id}` for the full profile (already exists). Frontend: fetch details on click.

---

## Phase 3 — Make it smart (Weeks 8–14, once retention is proven)

Only start Phase 3 after Phase 2 retention metrics show users are actually coming back.

### 3.1 Improve extraction with few-shot examples
**Why now:** gpt-4o-mini sometimes misses secondary characters or invents traits. A few carefully chosen examples in the system prompt improve accuracy significantly.
**How hard:** M
**Where:** `backend/app/engine/character/extractor.py` — add 2–3 `{"role": "user"/"assistant"}` example pairs to the messages array showing ideal extraction output. Test against your public-domain test book.

### 3.2 Add confidence tracking over time (trait history)
**Why now:** Right now when a trait is updated, the old value is lost. You can't show "Koyomi used to describe himself as plain, but by chapter 30 he's acknowledged as striking".
**How hard:** M
**Where:** New table `character_trait_history (character_id, trait_key, old_value, new_value, confidence, chapter, created_at)`. Update `_process_chapter` in the extraction consumer to write here when trait_state changes.

### 3.3 Add reading speed anomaly detection for scene highlights
**Why now:** The original design spec mentions triggering scene summaries when reading speed changes abnormally — a signal the reader is confused.
**How hard:** M
**Where:** `frontend/src/lib/hooks/useReader.ts` — track scroll speed with a `useRef` timestamp. If scroll speed drops >50% from rolling average, call `GET /reader/{id}/context` automatically. Show a subtle "confused? here's context" nudge.

### 3.4 Add a character importance ranking
**Why now:** Showing 80 characters in the sidebar is useless. Users want to see the top 5–10 relevant characters for where they're reading.
**How hard:** M
**Where:** `backend/app/models/character.py` — add `mention_count: Mapped[int] = 0`. Increment in extraction consumer each time a character is found in a chunk. `GET /reader/{id}/chapter/{n}` — sort characters by `mention_count DESC` and return top 10.

### 3.5 Build the Auto Wiki page
**Why now:** `wiki_entries` table and `WikiEntry` model exist but nothing generates entries and no UI displays them.
**How hard:** L
**Where:**
- `backend/app/workers/tasks/intelligence_tasks.py` — implement `generate_wiki_task`: iterate chapters, extract locations/factions/items with a targeted LLM prompt, deduplicate by name similarity, store in `wiki_entries`
- `frontend/src/app/(reader)/[bookId]/wiki/page.tsx` — new page, grouped by entry_type, searchable

### 3.6 Add cross-chapter relationship timeline
**Why now:** The relationship graph shows current state. Users want to see "when did X and Y become enemies?"
**How hard:** M
**Where:** `backend/app/api/v1/routes/reader.py` — new endpoint `GET /reader/{book_id}/relationships/{char_id}/timeline` that returns all `character_relationships` rows where `character_a_id` or `character_b_id` matches, ordered by `from_chapter`. Frontend: timeline component in the relationship panel.

---

## Phase 4 — Make it scale (Weeks 14+, once you have 500+ users)

### 4.1 Move from Supabase to dedicated RDS
**When:** Supabase free tier is 500MB. You'll hit it around 500–1,000 fully processed books.
**How hard:** S (it's just a DATABASE_URL change + `alembic upgrade head`)
**Where:** `.env` only. No code changes.

### 4.2 Move workers to dedicated Railway services
**When:** Worker queue depth consistently >50 (visible in Flower at `:5555`).
**How hard:** S
**Where:** Railway dashboard — duplicate the worker service, change the CMD to pin each service to one queue (`-Q extraction`, `-Q analysis`, `-Q intelligence`). Already documented in `Dockerfile.worker`.

### 4.3 Add result caching for prediction queries
**When:** Multiple users ask the same prediction question on the same popular book.
**How hard:** S
**Where:** `backend/app/engine/intelligence/predictor.py` — hash `(book_id, question, chapter)` → Redis cache with TTL 6hr. Check cache before calling GPT-4o.

### 4.4 Add pgvector HNSW tuning
**When:** Semantic search latency p95 exceeds 200ms (visible in Grafana).
**How hard:** S
**Where:** New Alembic migration — `ALTER INDEX idx_chunks_embedding SET (m = 32, ef_construction = 128)`. Tune `ef_search` at query time for speed/recall tradeoff.

### 4.5 Add a job retry UI in the admin panel
**When:** Extraction failures start happening in production and you're manually querying the DB to find them.
**How hard:** M
**Where:** `backend/app/api/v1/routes/admin.py` — add `GET /admin/failed-books` (query `books` where `status = 'failed'`) and `POST /admin/retry/{book_id}` (re-queues `process_book_task`). Frontend: simple table in a `/admin` page.

### 4.6 Add mobile-responsive reader
**When:** Analytics show >30% mobile traffic (PostHog).
**How hard:** L
**Where:** `frontend/src/components/reader/ReaderView.tsx` — context panel currently slides in as a fixed-width sidebar. On mobile it should be a bottom sheet. `frontend/src/components/reader/ContextPanel.tsx` — add `isMobile` detection and conditional layout.

### 4.7 Implement cross-book intelligence
**When:** Average user has 5+ processed books.
**How hard:** L
**Where:**
- `backend/app/api/v1/routes/intelligence.py` — implement `GET /intelligence/cross-book`: query `wiki_entries` and `characters` across all user's books, find similar embeddings via pgvector cosine, return archetype clusters
- `frontend/src/app/(dashboard)/insights/page.tsx` — new page showing character archetypes across books

---

## Monitoring checklist — add these as you grow

At each scale milestone, add one more observability tool:

| Users | Add |
|---|---|
| 1–10 | Sentry (errors) — should be Day 1 |
| 10–100 | PostHog (feature usage — which features do people actually use?) |
| 100–500 | Grafana + Prometheus (infra — queue depth, latency, DB connections) |
| 500+ | OpenAI usage dashboard alerts (cost spikes) |

---

## The one rule

At every phase, before starting anything new: **look at Sentry errors and PostHog funnels first**. The most important improvement is always the thing that's actually breaking for real users, not the thing that seems interesting to build.

If nobody is using the relationship graph, don't optimise it. If the extraction worker is failing on EPUBs, fix that before adding character chat.
