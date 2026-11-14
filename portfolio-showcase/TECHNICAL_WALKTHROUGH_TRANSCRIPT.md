# LoreVia technical walkthrough — full transcript

This is the complete spoken narration of the 4:35 technical architecture video. Timestamps mark the start and end of each chapter. The pipeline animation illustrates the implementation; it is not live telemetry. The application screenshots use synthetic demo content.

## 00:00–00:30 · Manuscript intelligence, end to end

LoreVia is an AI-powered manuscript intelligence platform for fiction authors. The engineering problem is maintaining character, plot, and continuity context across long drafts. The product combines a Next.js author workspace, a FastAPI application, PostgreSQL with pgvector, object storage, and Celery workers. This walkthrough follows a manuscript from upload to evidence-backed analysis, then examines recovery and deployment.

## 00:30–00:52 · The author workspace

The Next.js App Router hosts the author workspace and interactive demo. React components own the editing interface; TanStack Query manages server state, while Zustand stores selected client state. Axios sends credentialed API requests through a same-origin rewrite. These screenshots use the repository's synthetic demo content, not customer manuscripts.

## 00:52–01:15 · API and persistence boundaries

FastAPI validates endpoint input with Pydantic schemas and resolves authenticated users before service calls. LoreVia issues access and refresh JWTs in HttpOnly cookies, with CSRF checks on unsafe requests. SQLAlchemy uses async sessions against PostgreSQL. Services own multi-step transactions; Alembic revisions evolve the schema.

## 01:15–01:45 · Upload becomes durable work

On upload, the API bounds and validates the file, previews structure, checks allowances, and rejects a duplicate active upload for the same user. The upload service writes the source to S3-compatible storage, commits the Book, processing run, and task execution, then dispatches after commit. The response reports processing while the long job continues.

## 01:45–02:15 · Five specialized worker roles

Redis carries Celery messages. Five worker roles isolate extraction, analysis, embedding, intelligence, and maintenance. Extraction and analysis also consume priority queues. The launcher registers only the modules each role needs; Beat schedules maintenance. Late acknowledgments, one-message prefetch, task timeouts, and child recycling bound failure and memory behavior, but redelivery requires replay-safe tasks.

## 02:15–02:40 · From chapters to story structure

An extraction worker reads the stored manuscript, parses chapters, and creates chapter work. Chapter processing builds chunks, character candidates, identities, and relationship data. Analysis tasks derive summaries and narrative signals; embedding tasks create vectors. The UI reports stored processing state, not a prediction from a browser timer.

## 02:40–03:05 · Retrieval with chapter boundaries

Book chunks and character embeddings use 1,536-dimensional pgvector columns. Search embeds the question, queries book-scoped chunks, filters by chapter to respect spoiler boundaries, and can combine vector and lexical candidates. Advisor prompts use retrieved passages, and grounded answer schemas carry citations. Retrieval narrows context; it does not make model output automatically reliable.

## 03:05–03:35 · Recovery is a database concern

Long-running work can fail after a database commit or during a broker publish. LoreVia records executions and an outbox in PostgreSQL, then a maintenance task reconciles stalled dispatch. Workers claim rows under a lock and use stable execution identities; terminal results are guarded. The tradeoff is more control-plane code, but it makes retries auditable.

## 03:35–04:05 · Worker memory and health probes

One operational issue was memory spent importing every task module in every worker and in health probes. Role-specific loading reduced idle imports. The health check now creates a minimal Celery client and pings the exact worker identity without loading SQLAlchemy or tasks. Local Docker tests covered registration and failure states; VPS memory gains remain unmeasured.

## 04:05–04:35 · Deployment and engineering lessons

The tracked deployment places the Next.js frontend on Vercel and routes API traffic through Cloudflare to Nginx and FastAPI on a Hetzner VPS. Compose runs Redis and the five worker roles. Supabase supports OAuth, R2-compatible storage holds files, Sentry captures backend failures, and GitHub Actions defines test and image gates. The hosted product may be retired; the repository preserves the engineering design and verification history.
