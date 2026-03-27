# Database Schema

## Stack Decision
**PostgreSQL + pgvector** for all relational data and semantic embeddings.
**Redis** for cache, sessions, rate limits, Celery broker.
**No Qdrant** — pgvector with HNSW index handles all similarity search at MVP scale.

Enable extension: `CREATE EXTENSION IF NOT EXISTS vector;`

---

## Tables
- `book_chunks` — full-book text chunks + embeddings (powers semantic search)
- `character_relationships` — extracted relationship pairs, timeline-aware
- `plot_threads` — major arcs and subplots with status tracking
- `chapter_summaries` — cached LLM summaries in 3 modes
- `wiki_entries` — auto-generated locations, factions, items, events
- `reading_sessions` — session tracking for memory recall feature

---

## Schema

### users
```sql
CREATE TABLE users (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email         TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  tier          TEXT NOT NULL DEFAULT 'free',  -- 'free' | 'pro' | 'power' | 'admin'
  reading_mode  TEXT NOT NULL DEFAULT 'casual', -- 'casual' | 'analyst' | 'speed'
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### subscriptions
```sql
CREATE TABLE subscriptions (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id            UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  stripe_customer_id TEXT,
  stripe_sub_id      TEXT,
  plan               TEXT NOT NULL,   -- 'pro_monthly' | 'pro_annual' | 'power_monthly'
  status             TEXT NOT NULL,   -- 'active' | 'cancelled' | 'past_due'
  expires_at         TIMESTAMPTZ,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_sub_user ON subscriptions(user_id);
```

### books
```sql
CREATE TABLE books (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  title          TEXT NOT NULL,
  author         TEXT,
  genre          TEXT,
  format         TEXT NOT NULL,         -- 'pdf' | 'epub'
  s3_key         TEXT NOT NULL,
  isbn           TEXT,
  status         TEXT NOT NULL DEFAULT 'pending',
  -- 'pending' | 'processing' | 'ready' | 'failed'
  total_chapters INT,
  total_chunks   INT,
  language       TEXT DEFAULT 'en',
  created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_books_user ON books(user_id);
CREATE INDEX idx_books_status ON books(status);
```

### chapters
```sql
CREATE TABLE chapters (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id      UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  number       INT NOT NULL,
  title        TEXT,
  s3_key       TEXT NOT NULL,        -- raw chapter text in R2 (private)
  token_count  INT,
  processed    BOOLEAN NOT NULL DEFAULT false,
  UNIQUE(book_id, number)
);
CREATE INDEX idx_chapters_book ON chapters(book_id);
CREATE INDEX idx_chapters_unprocessed ON chapters(book_id) WHERE processed = false;
```

### book_chunks
```sql
-- Full-book text chunks with embeddings for semantic search.
-- One row per chunk (1,000–1,500 tokens). Core of semantic search.
CREATE TABLE book_chunks (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id      UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  chapter_id   UUID NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
  chunk_index  INT NOT NULL,          -- position within chapter
  text         TEXT NOT NULL,         -- actual chunk text (stored here, not S3)
  embedding    VECTOR(1536),          -- text-embedding-3-small
  token_count  INT,
  UNIQUE(chapter_id, chunk_index)
);
CREATE INDEX idx_chunks_book ON book_chunks(book_id);
CREATE INDEX idx_chunks_embedding ON book_chunks
  USING hnsw (embedding vector_cosine_ops);
-- Note: raw text stored here (not S3) because it's needed for similarity search.
-- This is private per-user data, not public. RLS enforced at application layer.
```

### characters
```sql
CREATE TABLE characters (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id          UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  name             TEXT NOT NULL,
  aliases          TEXT[],
  role             TEXT,              -- 'mc' | 'sc' | 'background'
  first_chapter    INT NOT NULL,

  -- Confidence-weighted trait model
  -- { "hair": {"value":"black","confidence":0.9,"type":"objective"}, ... }
  trait_state      JSONB DEFAULT '{}',

  -- Flat columns for fast access (derived from trait_state above threshold 0.45)
  hair             TEXT,
  eyes             TEXT,
  build            TEXT,
  age_descriptor   TEXT,
  distinguishing   TEXT,
  personality_tags TEXT[],

  -- Intelligence fields (new)
  motivations      TEXT[],            -- ["revenge", "protect family"]
  fears            TEXT[],            -- ["abandonment", "failure"]
  arc_summary      TEXT,              -- "starts as villain, becomes anti-hero by ch 40"
  archetype        TEXT,              -- "trickster", "mentor", "hero" etc.

  -- pgvector: identity anchor for deduplication
  embedding        VECTOR(1536),

  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_characters_book ON characters(book_id);
CREATE INDEX idx_characters_embedding ON characters
  USING hnsw (embedding vector_cosine_ops);
```

### character_states
```sql
-- Spoiler-free snapshot of character state at a given chapter.
CREATE TABLE character_states (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  character_id     UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
  at_chapter       INT NOT NULL,
  trait_snapshot   JSONB,             -- full trait_state at this chapter
  prompt_delta     TEXT,              -- human-readable change summary
  arc_note         TEXT,              -- narrative note about development
  UNIQUE(character_id, at_chapter)
);
CREATE INDEX idx_states_character ON character_states(character_id);
```

### character_relationships
```sql
-- Extracted relationship pairs, timeline-aware.
CREATE TABLE character_relationships (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id         UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  character_a_id  UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
  character_b_id  UUID NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
  rel_type        TEXT NOT NULL,
  -- 'ally' | 'enemy' | 'romantic' | 'family' | 'political' | 'mentor' | 'rival' | 'neutral'
  sentiment       FLOAT,             -- -1.0 (hostile) to 1.0 (warm)
  description     TEXT,              -- e.g. "John saved Mary in ch.5, owes a debt"
  from_chapter    INT NOT NULL,      -- when this relationship state begins
  to_chapter      INT,               -- null = still active at end of known text
  UNIQUE(character_a_id, character_b_id, from_chapter)
);
CREATE INDEX idx_rel_book ON character_relationships(book_id);
CREATE INDEX idx_rel_char_a ON character_relationships(character_a_id);
CREATE INDEX idx_rel_char_b ON character_relationships(character_b_id);
```

### plot_threads
```sql
CREATE TABLE plot_threads (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id          UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  title            TEXT NOT NULL,    -- "The revenge arc"
  description      TEXT,
  thread_type      TEXT,             -- 'main' | 'sub' | 'mystery' | 'romance' | 'political'
  status           TEXT DEFAULT 'introduced',
  -- 'introduced' | 'ongoing' | 'resolved' | 'abandoned' | 'unknown'
  introduced_at    INT,              -- chapter number
  resolved_at      INT,              -- chapter number, null if unresolved
  character_ids    UUID[],           -- characters involved
  importance       INT DEFAULT 5,    -- 1–10
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_threads_book ON plot_threads(book_id);
```

### chapter_summaries
```sql
-- Cached LLM summaries. Generated once, served forever.
CREATE TABLE chapter_summaries (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  chapter_id   UUID NOT NULL REFERENCES chapters(id) ON DELETE CASCADE,
  mode         TEXT NOT NULL,        -- 'short' | 'detailed' | 'key_points'
  content      TEXT NOT NULL,        -- the summary text
  key_events   JSONB,                -- [{"event":"...", "importance": 8}]
  char_changes JSONB,                -- [{"character_id":"...", "change":"..."}]
  clues        JSONB,                -- [{"clue":"...", "foreshadows":"..."}]
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(chapter_id, mode)
);
CREATE INDEX idx_summaries_chapter ON chapter_summaries(chapter_id);
```

### wiki_entries
```sql
-- Auto-generated wiki for locations, factions, items, events.
CREATE TABLE wiki_entries (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  book_id       UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  entry_type    TEXT NOT NULL,       -- 'location' | 'faction' | 'item' | 'event' | 'concept'
  name          TEXT NOT NULL,
  description   TEXT,
  first_mention INT,                 -- chapter number
  related_chars UUID[],
  embedding     VECTOR(1536),        -- for similarity search
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_wiki_book ON wiki_entries(book_id);
CREATE INDEX idx_wiki_type ON wiki_entries(book_id, entry_type);
```

### reading_sessions
```sql
-- Tracks reading sessions for memory recall feature.
CREATE TABLE reading_sessions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  book_id         UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  ended_at        TIMESTAMPTZ,
  chapters_read   INT[],             -- chapters touched in this session
  duration_secs   INT,
  recall_shown    BOOLEAN DEFAULT false
);
CREATE INDEX idx_sessions_user_book ON reading_sessions(user_id, book_id);
```

### reading_progress
```sql
CREATE TABLE reading_progress (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  book_id         UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  current_chapter INT NOT NULL DEFAULT 1,
  scroll_pct      FLOAT NOT NULL DEFAULT 0.0,
  session_seconds INT NOT NULL DEFAULT 0,
  last_read       TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(user_id, book_id)
);
CREATE INDEX idx_progress_user ON reading_progress(user_id);
```

---

## Redis Key Patterns

```
character:profile:{character_id}              → JSON CharacterProfile (TTL: 1hr)
chapter:summary:{chapter_id}:{mode}           → summary text (TTL: 7 days)
book:search_results:{book_id}:{query_hash}    → search results (TTL: 1hr)
relationship:graph:{book_id}:{chapter}        → serialised graph (TTL: 1hr)
session:{user_id}                             → JWT session (TTL: 24hr)
ratelimit:{user_id}:search                    → sliding window (TTL: 3600s)
ratelimit:{user_id}:chat                      → sliding window (TTL: 86400s)
book:processing_status:{book_id}              → status string (TTL: 1hr)
recall:{user_id}:{book_id}                    → memory recall text (TTL: 24hr)
```

---

## pgvector Usage

### Semantic Search
```sql
-- Find chunks most relevant to a natural language query
-- (embed query first, then search)
SELECT c.text, c.chunk_index, ch.number AS chapter_num,
       1 - (c.embedding <=> $1::vector) AS relevance
FROM book_chunks c
JOIN chapters ch ON ch.id = c.chapter_id
WHERE c.book_id = $2
  AND ch.number <= $3    -- spoiler gate: only up to user's current chapter
  AND 1 - (c.embedding <=> $1::vector) > 0.70
ORDER BY relevance DESC
LIMIT 10;
```

### Character Deduplication
```sql
-- Find characters with similar embeddings in same book
SELECT id, name, 1 - (embedding <=> $1::vector) AS similarity
FROM characters
WHERE book_id = $2
  AND embedding IS NOT NULL
  AND 1 - (embedding <=> $1::vector) > 0.88
ORDER BY similarity DESC
LIMIT 1;
```

### Wiki Similarity (for cross-book intelligence)
```sql
-- Find similar concepts/locations across different books
SELECT w.name, w.entry_type, w.book_id,
       1 - (w.embedding <=> $1::vector) AS similarity
FROM wiki_entries w
JOIN books b ON b.id = w.book_id
WHERE b.user_id = $2
  AND w.book_id != $3     -- exclude current book
  AND 1 - (w.embedding <=> $1::vector) > 0.75
ORDER BY similarity DESC
LIMIT 5;
```

---

## Migrations Strategy

Alembic with async engine. One migration per change, never edit after merge.
Run `alembic upgrade head` in CI/CD before starting API.

Initial migration must also run:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- for fast text search on names
```
