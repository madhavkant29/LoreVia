# Narration script

## Manuscript intelligence, end to end (30s)

LoreVia is an AI-powered manuscript intelligence platform for fiction authors. The engineering problem is maintaining character, plot, and continuity context across long drafts. The product combines a Next.js author workspace, a FastAPI application, PostgreSQL with pgvector, object storage, and Celery workers. This walkthrough follows a manuscript from upload to evidence-backed analysis, then examines recovery and deployment.

## The author workspace (22s)

The Next.js App Router hosts the author workspace and interactive demo. React components own the editing interface; TanStack Query manages server state, while Zustand stores selected client state. Axios sends credentialed API requests through a same-origin rewrite. These screenshots use the repository's synthetic demo content, not customer manuscripts.

## API and persistence boundaries (23s)

FastAPI validates endpoint input with Pydantic schemas and resolves authenticated users before service calls. LoreVia issues access and refresh JWTs in HttpOnly cookies, with CSRF checks on unsafe requests. SQLAlchemy uses async sessions against PostgreSQL. Services own multi-step transactions; Alembic revisions evolve the schema.

## Upload becomes durable work (30s)

On upload, the API bounds and validates the file, previews structure, checks allowances, and rejects a duplicate active upload for the same user. The upload service writes the source to S3-compatible storage, commits the Book, processing run, and task execution, then dispatches after commit. The response reports processing while the long job continues.

## Five specialized worker roles (30s)

Redis carries Celery messages. Five worker roles isolate extraction, analysis, embedding, intelligence, and maintenance. Extraction and analysis also consume priority queues. The launcher registers only the modules each role needs; Beat schedules maintenance. Late acknowledgments, one-message prefetch, task timeouts, and child recycling bound failure and memory behavior, but redelivery requires replay-safe tasks.

## From chapters to story structure (25s)

An extraction worker reads the stored manuscript, parses chapters, and creates chapter work. Chapter processing builds chunks, character candidates, identities, and relationship data. Analysis tasks derive summaries and narrative signals; embedding tasks create vectors. The UI reports stored processing state, not a prediction from a browser timer.

## Retrieval with chapter boundaries (25s)

Book chunks and character embeddings use 1,536-dimensional pgvector columns. Search embeds the question, queries book-scoped chunks, filters by chapter to respect spoiler boundaries, and can combine vector and lexical candidates. Advisor prompts use retrieved passages, and grounded answer schemas carry citations. Retrieval narrows context; it does not make model output automatically reliable.

## Recovery is a database concern (30s)

Long-running work can fail after a database commit or during a broker publish. LoreVia records executions and an outbox in PostgreSQL, then a maintenance task reconciles stalled dispatch. Workers claim rows under a lock and use stable execution identities; terminal results are guarded. The tradeoff is more control-plane code, but it makes retries auditable.

## Worker memory and health probes (30s)

One operational issue was memory spent importing every task module in every worker and in health probes. Role-specific loading reduced idle imports. The health check now creates a minimal Celery client and pings the exact worker identity without loading SQLAlchemy or tasks. Local Docker tests covered registration and failure states; VPS memory gains remain unmeasured.

## Deployment and engineering lessons (30s)

The tracked deployment places the Next.js frontend on Vercel and routes API traffic through Cloudflare to Nginx and FastAPI on a Hetzner VPS. Compose runs Redis and the five worker roles. Supabase supports OAuth, R2-compatible storage holds files, Sentry captures backend failures, and GitHub Actions defines test and image gates. The hosted product may be retired; the repository preserves the engineering design and verification history.
