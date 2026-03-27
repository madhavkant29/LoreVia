# 04 — Build Plan & Implementation Guide

## Guiding Principles

1. **The core loop is: Upload → Extract → Read with intelligence.** Everything else is additive.
2. **Spoiler-free always.** Every feature is gated to `chapter <= user.current_chapter`.
3. **Cache aggressively.** Summaries generated once, served forever. Graphs built once per chapter boundary crossed.
4. **Lazy process.** First 3 chapters immediately. Queue remaining. Stay 3 ahead of reader.
5. **GPT-4o-mini for extraction/summaries. GPT-4o only for chat/predictions.** Cost discipline.
6. **Intelligence on demand, never pushed.** User taps to reveal. Never interrupts reading.

---

## Phase 1 — MVP (Weeks 1–6)

**Goal:** Upload a book → read it with smart tap context + character profiles + chapter summaries.

### Week 1–2: Foundation (identical to old plan)
- FastAPI + Supabase + Upstash Redis + Cloudflare R2
- JWT auth, book upload endpoint, S3 storage
- PDF/EPUB parsing workers
- Deploy to Railway + Vercel immediately

### Week 3–4: Character Intelligence Engine

**Extraction prompt (updated — adds motivations, fears, arc):**
```python
SYSTEM_PROMPT = """
Extract all named characters. For each, return JSON with confidence-weighted traits.
Include:
- name, aliases
- traits: {hair, eyes, build, age, face, distinguishing}
  each as {value, confidence: 0.0-1.0, type: objective|subjective|abstract}
- personality_tags: max 3
- motivations: what drives them
- fears: what they're afraid of
- archetype: japanese high school boy | mentor | trickster | villain | hero | etc.
- first_appearance_context: 1 sentence

Return only JSON array. No commentary.
"""
```

**Relationship extraction (new — runs same pass as character extraction):**
```python
RELATIONSHIP_PROMPT = """
From this chunk, extract character relationships. For each pair that interacts:
{
  "character_a": "name",
  "character_b": "name",
  "type": "ally|enemy|romantic|family|political|mentor|rival|neutral",
  "sentiment": -1.0 to 1.0,
  "description": "one sentence"
}
Return only JSON array.
"""
```

### Week 5–6: Smart Tap + Chapter Summaries

**Smart Tap backend (`GET /reader/{book_id}/context`):**
```python
# User taps a name/word → frontend sends it → backend returns context card
async def get_context(book_id, query, chapter, user_id):
    # 1. Try exact character name match first
    char = find_character_by_name(book_id, query)
    if char:
        state = get_spoiler_free_state(char.id, chapter)
        relationships = get_relationships_at(char.id, chapter)
        return {"type": "character", "data": state, "relationships": relationships}

    # 2. Try wiki entry match (location, item, faction)
    wiki = find_wiki_entry(book_id, query)
    if wiki and wiki.first_mention <= chapter:
        return {"type": "wiki", "data": wiki}

    # 3. Semantic search fallback
    results = semantic_search(book_id, query, max_chapter=chapter, limit=3)
    return {"type": "search", "data": results}
```

**Chapter summary generation:**
```python
SUMMARY_PROMPT = {
    "short": "Summarise this chapter in 3-4 sentences. Key events only.",
    "detailed": """Analyse this chapter:
      - Key events (with importance 1-10)
      - Character changes or developments
      - Important clues or foreshadowing
      - Unresolved questions raised
      Return structured JSON.""",
    "key_points": "List only the 5 most important things that happen. Numbered. Brief."
}
# Generated once per chapter per mode. Cached in Redis + stored in DB.
```

**Reader frontend (MVP UI):**
- Fullscreen text reader (novel-first)
- Tap any word → context slide-in panel from right
- Character panel: names sidebar with spoiler-free mini-profiles
- Chapter summary button in toolbar: opens modal, 3 mode tabs
- Memory recall card: auto-shown if >24h since last session

---

## Phase 2 — Retention (Weeks 7–12)

### Relationship Graph

**Data model:** adjacency list from `character_relationships` table, serialised and cached.

**Frontend:** Cytoscape.js or D3 force-directed graph.
- Nodes: character avatars (letter + colour, no images)
- Edges: relationship type → colour coded (red=enemy, green=ally, pink=romantic)
- Click node → character detail panel
- Slider: drag to chapter → graph updates to that point in time

```python
async def get_relationship_graph(book_id, up_to_chapter, user_id):
    rels = await db.fetch("""
        SELECT * FROM character_relationships
        WHERE book_id = $1
          AND from_chapter <= $2
          AND (to_chapter IS NULL OR to_chapter >= $2)
    """, book_id, up_to_chapter)
    return build_graph_json(rels)  # nodes + edges format for Cytoscape
```

### Semantic Search

```python
async def semantic_search(book_id, query, max_chapter, limit=10):
    query_embedding = await embed_text(query)
    results = await db.fetch("""
        SELECT c.text, c.chunk_index, ch.number AS chapter,
               1 - (c.embedding <=> $1::vector) AS relevance
        FROM book_chunks c
        JOIN chapters ch ON ch.id = c.chapter_id
        WHERE c.book_id = $2
          AND ch.number <= $3
          AND 1 - (c.embedding <=> $1::vector) > 0.65
        ORDER BY relevance DESC
        LIMIT $4
    """, query_embedding, book_id, max_chapter, limit)
    return results
```

Frontend: search bar in reader sidebar. Results show chapter number + excerpt. Click → jump to chapter.

### Plot Tracker

Extracted during chapter analysis pass. Displayed as:
```
Main Plot:
✅ Kingdom collapse — resolved ch. 12
🔄 Revenge arc — ongoing
❓ Hidden identity — unknown

Subplots:
✅ Guild conspiracy — resolved ch. 8
🔄 Romance (Aria × Marcus) — ongoing
```

### Memory Recall

Triggered when: time since `reading_progress.last_read` > 24 hours.

```python
RECALL_PROMPT = """
The user is resuming reading. They last read chapter {last_chapter}.
They are now about to read chapter {current_chapter}.

Based on the story so far, generate a "Previously on..." recap:
- Last 3 key events they should remember
- 3 most important characters active in the story
- 1 open mystery or unresolved thread

Keep it brief, no spoilers past chapter {last_chapter}. Friendly tone.
"""
```

Cached per (user_id, book_id) with TTL 24hr. Shown as a dismissable card before chapter loads.

---

## Phase 3 — Differentiation (Weeks 13–20)

### Prediction Engine

```python
PREDICTION_PROMPT = """
You are analysing a novel up to chapter {chapter}.
The user asks: "{question}"

Based only on what has been revealed so far (no spoilers):
Generate 2-3 theories. For each:
{
  "theory": "concise statement",
  "confidence": 0.0-1.0,
  "evidence": ["quote or event from ch.X", "..."],
  "reasoning": "1-2 sentences"
}

Be specific. Cite evidence from the text. Do not invent facts.
"""

# RAG: retrieve top-10 most relevant chunks first, pass as context
async def predict(book_id, question, chapter):
    context_chunks = await semantic_search(book_id, question, max_chapter=chapter, limit=10)
    context = "\n\n".join(c.text for c in context_chunks)
    return await llm_call(PREDICTION_PROMPT, context=context, model="gpt-4o")
```

### Character Chat

```python
CHARACTER_SYSTEM_PROMPT = """
You are {character_name} from {book_title}.

Your personality: {personality_tags}
Your motivations: {motivations}
Your fears: {fears}
Current arc: {arc_summary}

What you know (up to chapter {chapter}):
{trait_snapshot_summary}
{recent_events_summary}

RULES:
- Stay completely in character
- Only reference events up to chapter {chapter}
- Never break the fourth wall
- If asked about something you don't know yet in the story, say so in character
- Speak in a way consistent with your personality and role
"""

# History management: keep last 10 turns in context, summarise older turns
```

### Auto Wiki

Generated per book after full processing. Triggered manually or on `book.status = 'ready'`.
Each entry embedded for cross-book similarity search (Phase 3 moat).

### Cross-Book Intelligence

When user has 3+ processed books:
- Embed all character descriptions
- Cluster by similarity
- Surface: "You tend to like trickster characters. Here are similar ones from your other books."
- Recommend books with similar archetypes, themes, relationship dynamics

---

## API Endpoints Reference

```
# Auth
POST   /auth/register
POST   /auth/login
POST   /auth/refresh
GET    /auth/me

# Books
POST   /books/upload
GET    /books
GET    /books/{id}
GET    /books/{id}/status
GET    /books/{id}/characters
GET    /books/{id}/wiki
GET    /books/{id}/plot-threads
DELETE /books/{id}

# Reader (core feature set)
GET    /reader/{book_id}/chapter/{n}          → text + character list
GET    /reader/{book_id}/context?q=X&ch=N    → smart tap: character/wiki/search result
GET    /reader/{book_id}/summary/{n}?mode=X  → chapter summary (short/detailed/key_points)
GET    /reader/{book_id}/relationships?ch=N  → graph data up to chapter N
GET    /reader/{book_id}/search?q=X&ch=N     → semantic search
GET    /reader/{book_id}/recall              → memory recall card
PUT    /reader/{book_id}/progress

# Characters
GET    /characters/{id}                      → full profile
GET    /characters/{id}/state?chapter=N      → spoiler-free state at chapter N
GET    /characters/{id}/relationships?ch=N   → relationships at chapter N

# Intelligence (Phase 3)
POST   /intelligence/{book_id}/predict       → prediction engine
POST   /intelligence/{book_id}/chat/{char_id} → character chat turn
GET    /intelligence/cross-book              → cross-book character comparison

# Admin
GET    /admin/metrics
GET    /admin/queue-depth

# Webhooks
POST   /webhooks/stripe
```

---

## Environment Variables (Revised)

```bash
# App
APP_NAME=LoreVia
DEBUG=false
API_V1_PREFIX=/api/v1

# Database
DATABASE_URL=postgresql://...

# Redis
REDIS_URL=rediss://...

# Storage (PDFs/EPUBs only — much smaller without images)
S3_BUCKET=lorevia-prod
S3_ENDPOINT_URL=https://xxxx.r2.cloudflarestorage.com
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...

# AI (no Replicate, no GPU)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...   # optional fallback

# Auth
JWT_SECRET=...

# Payments + Email
STRIPE_SECRET_KEY=...
STRIPE_WEBHOOK_SECRET=...
RESEND_API_KEY=...

# Monitoring
SENTRY_DSN=...
```

---

## Key Decisions Log

| Decision | Choice | Reason |
|---|---|---|
| Image generation | Dropped | Cost, consistency complexity, wrong moat |
| LLM for summaries | GPT-4o-mini | 10× cheaper, sufficient quality |
| LLM for chat/predictions | GPT-4o | Worth cost for high-value features |
| Semantic search | pgvector over book_chunks | No separate vector DB, works at scale |
| Relationship graph | Extracted per chapter, stored in DB | Queryable, timeline-aware |
| Character chat memory | Last 10 turns + summarised history | Context window management |
| Cross-book | Phase 3, wiki embeddings | Requires sufficient book library first |
| Reading modes | 3 modes (casual/analyst/speed) | Different users want different depths |
| Smart tap | On-demand, not pushed | Never interrupt reading |
