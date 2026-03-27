# 01 — Project Overview & Vision

## What This Is

**LoreVia** is an AI-powered reading companion for novels. Users upload their own PDF/EPUB books. The platform deeply understands the book — extracting characters, relationships, plot threads, and meaning — then surfaces that intelligence while the user reads, so they never lose context, never forget who a character is, and never feel lost in a complex story.

**Core promise:** "Your books, deeply understood."

## The Pivot (Why We Dropped Image Generation)

Image generation was the original direction. We dropped it for three compounding reasons:

1. **Cost** — SDXL via Replicate costs $0.02–0.20 per character. At 20 characters per book × 1,000 users, that's $400–$4,000 in GPU costs before a single dollar of revenue.
2. **Consistency** — diffusion models have inherent variance. Keeping a character visually identical across 100 chapters requires architectural complexity (LoRA training, seed locking, img2img pipelines) that delays shipping.
3. **Wrong moat** — anyone with a GPU can generate images. Nobody has a deeply structured, spoiler-aware character intelligence engine that understands the *meaning* of a book. That's the defensible position.

The intelligence layer we built (confidence-weighted trait extraction, pgvector deduplication, spoiler-free state evolution) was the right foundation. We're keeping all of it and building on top — just replacing the image output with textual intelligence output.

---

## Product Features

### Phase 1 — MVP (Weeks 1–6)
**Core reading loop. Prove the intelligence is useful.**

| Feature | Description |
|---|---|
| Smart Tap | Tap any character name, place, or event mid-read → instant inline context card |
| Character Profiles | Auto-extracted: name, aliases, traits, personality, role, first appearance |
| Chapter Summaries | Per-chapter: key events, character changes, important clues (not generic) |
| Memory Recall | Return after days → "Here's what you need to remember" before resuming |

### Phase 2 — Retention (Weeks 7–12)
**Make users depend on LoreVia for every book.**

| Feature | Description |
|---|---|
| Relationship Graph | Interactive node graph — characters as nodes, relationships as edges, evolves per chapter |
| Semantic Search | Natural language search inside the book: "when did X betray Y", "all scenes with the sword" |
| Plot Tracker | Tracks major arcs, subplots, unresolved threads with status (ongoing/resolved/unknown) |
| Reading Modes | Casual (summaries), Analyst (deep breakdown), Speed (key points only) |

### Phase 3 — Differentiation (Weeks 13–20)
**Features nobody else has.**

| Feature | Description |
|---|---|
| Prediction Engine | "Who is likely the traitor?" — multiple theories, confidence scores, reasoning from text |
| Character Chat | Talk to characters, grounded in story context and timeline (not generic chatbot) |
| Auto Wiki | Auto-generated wiki: characters, locations, factions, items, events |
| Cross-Book Intelligence | Compare characters across books, detect archetypes, theme-based recommendations |

---

## UX Philosophy

1. **Enhance reading, never interrupt it** — intelligence surfaces on demand (tap), not pushed
2. **Spoiler-free always** — every feature is gated to what the user has read so far
3. **User controls depth** — Casual / Analyst / Speed modes for every feature
4. **Novel first** — reader is fullscreen text; intelligence lives in a slide-in panel

---

## Target Users

- Light novel / web novel readers with large casts (50+ characters)
- Fantasy / sci-fi readers in complex multi-book series
- Readers who take breaks and lose context between sessions
- Analysts and students doing close reading

---

## Monetization

| Tier | Price | What They Get |
|---|---|---|
| Free | $0 | 2 books, basic character profiles, chapter summaries |
| Pro | ₹299–₹799/mo ($4–$10) | Unlimited books, relationship graph, semantic search, memory recall |
| Power | ₹1,499/mo ($18) | All Pro + prediction engine, character chat, cross-book intelligence |

**Key shift from old model:** No per-use credits. Intelligence features are subscription-only. This gives predictable revenue and aligns incentives — we want users reading more, not worrying about burning credits.

---

## Profitability (Revised — No GPU Costs)

| Scale | Revenue | AI Cost | Infra | Profit | Margin |
|---|---|---|---|---|---|
| 1k users | $5,400 | $400 | $300 | $4,700 | **87%** |
| 10k users | $54,000 | $3,000 | $2,000 | $49,000 | **91%** |
| 100k users | $540,000 | $20,000 | $15,000 | $505,000 | **93%** |

AI costs are now purely LLM extraction + embeddings + inference for summaries/chat. No GPU. Margins are dramatically better.

---

## Competitive Moat (Build Order)

1. **Character Intelligence Graph** — structured, confidence-weighted, spoiler-aware character knowledge. Proprietary dataset that gets richer with every book processed.
2. **Semantic Memory** — pgvector embeddings over the full book. Enables search, predictions, and chat that no keyword-based system can match.
3. **Reading History** — users' annotations, highlights, reading patterns. Personalisation layer that improves the longer they use LoreVia.
4. **Cross-Book Graph** — when users have read 10+ books, LoreVia understands their taste and the archetypes they enjoy. Nobody else has this.

---

## What Stays from the Old Architecture

Everything except image generation:
- PDF/EPUB parsing (PyMuPDF, ebooklib)
- Token chunking (tiktoken)
- LLM character extraction with confidence + trait types
- pgvector deduplication (cosine similarity > 0.88)
- Spoiler-free character state evolution per chapter
- Redis caching layer
- Celery async workers
- FastAPI backend + Next.js frontend
- PostgreSQL + pgvector (still needed for semantic search)

## What Gets Removed

- SDXL / Replicate image generation
- LoRA registry and style router
- CLIP scorer, face checker, aesthetic scorer
- Image selection pipeline
- `character_images` table
- `creator_art` table (community art tab)
- All image-related workers and tasks
- Cloudflare CDN for image delivery (still use Cloudflare WAF)
