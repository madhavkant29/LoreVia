# 02 — Technical Architecture

## Stack (Revised — No Image Generation)

| Layer | Technology | Reason |
|---|---|---|
| Frontend | Next.js 15 (App Router) | SSR for reader, React for UI |
| Backend | FastAPI (Python) | Async, fast, ML-native |
| Task Queue | Celery + Redis | Async book processing, analysis jobs |
| Primary DB | PostgreSQL + pgvector | Relational data + semantic embeddings in one DB |
| Cache | Redis | Character profile cache, session, rate limits, Celery broker |
| Object Storage | Cloudflare R2 | User PDFs/EPUBs only (no images to store) |
| LLM | OpenAI GPT-4o-mini / GPT-4o | Extraction, summaries, predictions, character chat |
| Embeddings | OpenAI text-embedding-3-small | Semantic search, deduplication, similarity |
| CDN / WAF | Cloudflare | DDoS protection, WAF — no longer needed for image delivery |
| Auth | Supabase Auth (MVP) → custom JWT | Row-level security |
| Payments | Stripe | Subscriptions |
| Email | Resend | Transactional |

---

## Full Request Flow

```
User Browser (Next.js)
    ↓
Cloudflare WAF
    ↓
Rate Limiter (Redis sliding window — per user, tier-aware)
    ↓
FastAPI (API Gateway + Business Logic)
    ↓                    ↓
Sync reads/writes    Celery Worker Queue (Redis broker)
(PostgreSQL)              ↓
                     [Extraction Worker]      ← parse + chunk + LLM extract
                     [Analysis Worker]        ← summaries, plot tracking
                     [Embedding Worker]       ← pgvector upserts
                     [Intelligence Worker]    ← predictions, wiki generation
                          ↓
                     OpenAI API → PostgreSQL + pgvector
```

---

## Service Breakdown (FastAPI)

### Auth Service
- JWT access + refresh tokens
- Subscription gating middleware (free / pro / power tiers)
- Supabase Row Level Security at MVP

### Book Service
- PDF parsing: **PyMuPDF (fitz)**
- EPUB parsing: **ebooklib + BeautifulSoup4**
- Chunking: tiktoken, 1,000–1,500 tokens, 100-token overlap, chapter-boundary-first
- Upload to Cloudflare R2 with private ACL
- Triggers `process_book` Celery task on upload

### Character Intelligence Engine ("The Brain")
- LLM extraction with **confidence + trait type** per field (objective / subjective / abstract)
- Spoiler-free state evolution: trait_state updated per chapter, never ahead of reader
- pgvector deduplication: cosine similarity > 0.88 → merge aliases
- Relationship extraction: who interacts with whom, how, with what sentiment
- Archetype inference when description is sparse

### Summary Service
- Per-chapter summaries in three modes: Short / Detailed / "What matters for later"
- Cached in Redis (TTL 7 days) — generated once, served forever
- Key events, character changes, important clues, foreshadowing flagged separately

### Semantic Search Service
- Full-book embeddings stored in pgvector (one vector per chunk)
- Natural language queries → embedding → cosine similarity → ranked results
- Filters: character mentions, location mentions, event types
- Spoiler gate: only searches chunks ≤ user's current chapter

### Relationship Graph Service
- Extracts relationship pairs from each chapter: (character_a, character_b, type, sentiment)
- Types: ally, enemy, romantic, family, political, mentor, rival
- Timeline-aware: relationship state can change chapter to chapter
- Serialised as adjacency list → served to frontend for D3/Cytoscape rendering

### Plot Tracker Service
- Extracts plot threads from chapter analysis
- Tracks status: introduced / ongoing / resolved / unknown
- Links threads to character_ids involved
- Flags foreshadowing and callbacks

### Intelligence Service (Phase 3)
- **Prediction Engine**: RAG over full book embeddings + LLM reasoning → theories with confidence
- **Character Chat**: system prompt built from character's trait_state + chapter history, LLM responds in-character
- **Auto Wiki**: structured extraction of locations, factions, items, events per book
- **Cross-Book**: compares character embeddings across books, detects archetypes, recommends

### Memory Recall Service
- On session resume: fetches last reading position
- Generates "What you need to remember" summary: key characters met, last events, open threads
- Personalised to user's reading depth and mode preference

---

## Worker Layer (Celery)

| Worker | Queue | Task | Priority |
|---|---|---|---|
| `extraction_worker` | extraction | LLM entity extraction per chunk | High |
| `embedding_worker` | embedding | pgvector upsert for chunks + characters | Medium |
| `analysis_worker` | analysis | Chapter summaries, plot tracking, relationship extraction | Medium |
| `intelligence_worker` | intelligence | Predictions, wiki generation (Phase 3) | Low |

**Lazy processing rule:** Process first 3 chapters immediately on upload. Queue remaining chapters in background. Always stay 3 chapters ahead of the user's reading position.

---

## Database: What Changed

### Removed tables
- `character_images` — no longer generating images
- `creator_art` — no community art feature

### New tables
- `character_relationships` — extracted relationship pairs per chapter
- `plot_threads` — tracked arcs and subplots
- `chapter_summaries` — cached LLM summaries (3 modes)
- `book_chunks` — chunk text + embeddings for semantic search
- `wiki_entries` — auto-generated wiki: locations, factions, items
- `reading_sessions` — session tracking for memory recall

### Unchanged tables
- `users`, `subscriptions`, `books`, `chapters`
- `characters` (with `trait_state` JSONB confidence model)
- `character_states` (spoiler-free evolution snapshots)
- `reading_progress`

---

## Cost Control

| Strategy | Impact |
|---|---|
| Cache summaries in Redis | LLM call once per chapter, served forever after |
| Lazy processing | Only analyse chapters user approaches |
| GPT-4o-mini for extraction | 10× cheaper than GPT-4o, sufficient for entity extraction |
| GPT-4o only for chat/predictions | Reserve expensive model for high-value features |
| pgvector for semantic search | No separate vector DB service |
| Batch embedding | Embed whole chapter in one API call, not chunk-by-chunk |

**API cost estimates (revised):**
- Extraction (GPT-4o-mini): ~$0.001–0.003 per chapter chunk
- Summary (GPT-4o-mini): ~$0.003–0.008 per chapter
- Character chat (GPT-4o): ~$0.01–0.03 per conversation turn
- Embeddings: ~$0.00002 per 1k tokens (text-embedding-3-small)
- **Total per book (200 chapters):** ~$1.50–$4.00 — recovered from one month of Pro subscription

---

## Deployment (Unchanged from old stack — image infra removed)

### MVP Stack
- **Frontend:** Vercel
- **Backend:** Railway (FastAPI + Celery workers)
- **DB:** Supabase (Postgres + pgvector)
- **Redis:** Upstash
- **Storage:** Cloudflare R2 (PDFs/EPUBs only — much smaller than before)
- **LLM:** OpenAI API
- **Cost:** ~$0 until traction. No GPU bill ever.

### Growth Stack (10k+ users)
- **Backend:** AWS ECS Fargate
- **DB:** RDS Postgres with pgvector
- **Redis:** ElastiCache
- **Storage:** S3

---

## Observability

| Tool | Purpose |
|---|---|
| Sentry | Error tracking (Day 1) |
| PostHog | Product analytics |
| Grafana + Prometheus | Infra metrics |

**PostHog events (revised):**
`book_uploaded`, `character_tapped`, `summary_viewed`, `summary_mode_changed`, `search_query`, `relationship_graph_opened`, `prediction_requested`, `character_chat_started`, `memory_recall_shown`, `chapter_completed`

**Key product metrics:**
- Smart tap rate (taps per chapter read) — measures intelligence utility
- Summary view rate — do users actually read summaries?
- Search queries per session — measures engagement depth
- Return session rate — does memory recall bring users back?
- Character chat turns per session — measures Phase 3 value

---

## Rate Limiting (Revised)

Redis sliding window, per user, tier-aware:
- Smart tap / context lookup: 200/min (all tiers — this should never be limited)
- Summary generation: 30/hr free, unlimited paid
- Semantic search: 20/hr free, unlimited paid
- Character chat: 10 turns/day free, 100 turns/day pro, unlimited power
- Book upload: 2/day free, unlimited paid
- API calls: 300/min per user

---

## Copyright Compliance (Unchanged)

- ISBN check against Open Library on upload
- User confirms ownership before processing
- Raw text never stored publicly — S3 with private ACL
- Only embeddings + metadata in DB
- No book sharing between users
