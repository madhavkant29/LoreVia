# LoreVia — Agent & AI Coding Instructions

> **Read this file in full before making any changes to the codebase.**
> These rules apply to every agent, AI assistant, and automated tool that touches this repo.

---

## Project Layout (quick reference)

```
LoreVia2/
├── backend/               ← FastAPI + SQLAlchemy backend
│   ├── app/
│   │   ├── api/v1/routes/ ← Endpoint handlers ONLY — no business logic here
│   │   ├── engine/        ← Core NLP / extraction / character engine
│   │   ├── models/        ← SQLAlchemy ORM models
│   │   ├── schemas/       ← Pydantic request / response schemas
│   │   ├── services/      ← Service-layer orchestration
│   │   ├── utils/         ← Helper / utility functions
│   │   └── workers/       ← Celery tasks and consumers
│   └── requirements.txt   ← Single requirements file (no requirements-dev.txt)
└── frontend/              ← React / Next.js frontend
```

## Deployment Note

- Treat the current deployment target as a **VPS** unless the user explicitly says this has changed.
- Do not assume Render-specific infrastructure, `onrender.com` hostnames, or Render-managed env behavior.
- When discussing production incidents, do not claim env overrides or platform-level settings exist unless they have been verified from the VPS deployment configuration or explicitly confirmed by the user.

---

## Rules — follow every one of these

### 1. Models and Schemas

- **SQLAlchemy ORM models** go in `backend/app/models/`.
  - Add to an existing file if the model belongs to an existing domain
    (e.g., a new intelligence-related model → `models/intelligence.py`).
  - Create a new file only for a genuinely new domain.
- **Pydantic schemas** (request bodies, response shapes) go in `backend/app/schemas/`.
  - Same rule: extend existing schema files before creating new ones.
- **Never** define models or schemas inline inside route files.

### 2. Helper / Utility Functions

- Pure helpers live in `backend/app/utils/`; multi-step workflows and transactional
  orchestration live in `backend/app/services/`.
- Large domains may use packages such as `utils/books/`, `services/characters/`,
  or `services/public/`. Prefer focused modules near 500 lines over expanding a
  domain-level `*_utils.py` god module.
  - `character_utils.py` — character display, status, relationship text, text cleaning
  - `book_utils.py`      — DB query wrappers, cover, progress, chapter numbers, manuscript parsing
  - `export_utils.py`    — Character card and bible renderers (Markdown / PDF / DOCX)
  - `reader_utils.py`    — Timeline/graph filters, media serialization, summary normalization
  - `advisor_utils.py`   — LLM prompts, intent classification, story context, report builders
  - Existing files remain valid homes for small changes. When a file is already
    oversized, add to or create the matching domain package instead.
- Route files **import and call** these helpers — they do not redefine them.
- **No `as _name` import aliases.** Import with the public name directly.
- **No shim/wrapper functions** that do nothing but call the real function.

### 3. Route Files (`app/api/v1/routes/`)

- Contain **endpoint handlers only**.
- Business logic, data transformation, and filtering belong in `utils/` or `services/`.
- Keep each route file under ~500 lines. Extract to utils when it grows beyond that.

### 4. Requirements

- There is **one** requirements file: `backend/requirements.txt`.
- `requirements-dev.txt` has been deleted — do not recreate it.
- Add all new dependencies (prod and dev) to `requirements.txt`.
- Pin to an exact version (e.g., `spacy==3.8.14`).

### 5. NER / Character Filtering

- Character visibility logic lives in `backend/app/engine/character/entity_filters.py`.
- Use `character_visibility_score()` + `VISIBILITY_THRESHOLD` instead of hard boolean stopword checks.
- Stopwords are soft penalties, not hard gates — NER and profile evidence can override them.
- Never add new hard `if name in STOPWORDS: return False` gates; add to the scoring system instead.

### 6. Code Style

- Python: follow the existing patterns (async/await, SQLAlchemy 2.x `select()` style, type hints).
- No commented-out code left in PRs.
- Preserve all existing docstrings and comments unrelated to your change.

### 6a. Frontend Branding

- Always use the real LoreVia logo assets from `frontend/public/`.
- Use `frontend/public/logoandtext.png` for full logo lockups and `frontend/public/image.png` only for icon-only marks.
- Do not recreate the LoreVia logo with inline SVG, text-only approximations, generated artwork, or hand-drawn substitutes.

### 7. Testing

- **Write tests for all new functions** in `backend/tests/unit/` for utility functions and `backend/tests/integration/` for API endpoints.
- **Write frontend tests** for new frontend logic in `frontend/src/**/*.test.ts(x)` and add/update E2E smoke coverage in `frontend/e2e/` when the change affects a user flow.
- **Consider edge cases** when writing tests: empty inputs, null values, boundary conditions, malformed data, and error scenarios.
- Test both happy paths and error paths.
- Use descriptive test names that clearly indicate what is being tested.
- Maintain test coverage for critical paths.
- When running backend tests locally, always use Docker Compose Local instead of the host venv so the repo's pinned app, database, Redis, and extension setup are consistent.
- Preferred backend test command:
  `docker compose -f docker-compose-local.yml exec -T api pytest tests -v`
- Treat local `docker compose -f docker-compose-local.yml` test commands and required local service startup as pre-approved for this repo; do not pause to ask for confirmation before running them when they are needed to verify backend changes.
- When running frontend unit tests locally, prefer `cd frontend && npm.cmd test`.
- When running frontend E2E smoke tests locally, prefer `cd frontend && npm.cmd run test:e2e`.
- Frontend E2E smoke tests are designed for non-production environments: they boot the local Next dev server and mock API responses at the browser/network layer instead of requiring a live backend.
- If tests need app settings, seed safe local dummy env vars instead of changing production config.
- For DB-backed tests, confirm the local test database and required extensions are available before running the suite.

### 8. Environment Files

- **Do not modify, delete, replace, rename, or rewrite any `.env`, `.env.*`, production env file, or local secret file unless the user explicitly asks for that exact change.**
- This includes `backend/.env`, `backend/.env.local`, root `.env`, deploy env files, and any secret-bearing config file.
- If env values need to be discussed, explain the required changes in the response instead of editing the file directly unless the user clearly told you to edit it.
- For tests, use temporary in-process dummy values, monkeypatching, or documented commands rather than changing tracked or local env files.

### 9. Operational Authorization Boundaries

- **Agents must never create, edit, generate, apply, test, run, or trigger database migrations.** When a code change would require a migration, document the required schema change and leave all migration work to the user.
- Agents may make code changes and run local Docker and Node commands.
- Agents may create or update feature branches and pull requests.
- **Agents must never merge a pull request, push to `main`, deploy to any environment, or trigger a production workflow unless the user gives explicit authorization for that exact action in the current conversation.** A general implementation plan or a request to continue is not merge or deployment authorization.

---

## Before you write any code

1. Identify which existing file the change belongs to (model, schema, util, route, service).
2. Check `app/utils/` — the helper may already exist.
3. Check `app/models/` — the model may already exist.
4. Only then write new code, always in the right layer.

## Schema Changes (Human-Maintainer Reference Only)

The following section documents repository requirements for human-maintainer migration work. It does not authorize an agent to perform migration work and does not override Rule 9.

When adding a new table or changing schema:

1. Update the SQLAlchemy model in `backend/app/models/...`.
2. Create a new Alembic revision.
3. Fill in the migration’s `upgrade()` and `downgrade()` functions.
4. Push the branch after verifying the migration locally.

### Migration Best Practices

- **Never edit an existing migration after it has been pushed to Git, shared with anyone else, or applied to any non-local database.**
- If a shipped migration needs correction, **create a new follow-up Alembic revision** that repairs the schema or data state instead of rewriting the old migration file.
- Treat previously pushed migration files as **immutable history** unless the user explicitly asks for a one-off local-only reset and confirms the migration has never left the machine.

**Always handle edge cases and prevent duplication:**

- **Check if tables exist before creating them:**
  ```python
  bind = op.get_bind()
  inspector = sa.inspect(bind)
  tables = set(inspector.get_table_names())
  if "table_name" not in tables:
      op.create_table("table_name", ...)
  ```

- **Check if columns exist before adding them:**
  ```python
  columns = {col["name"] for col in inspector.get_columns("table_name")}
  if "column_name" not in columns:
      op.add_column("table_name", sa.Column("column_name", ...))
  ```

- **Check if indexes exist before creating them:**
  ```python
  indexes = {idx["name"] for idx in inspector.get_indexes("table_name")}
  if "index_name" not in indexes:
      op.create_index("index_name", "table_name", ["column_name"])
  ```

- **Make migrations idempotent** — they should be safe to run multiple times without errors.

### Supabase Data API Exposure

- **Treat Supabase Data API access as explicit opt-in for new `public` tables.**
- **Backend-only tables:** create the table, indexes, and constraints, but do **not** grant `anon` or `authenticated` access.
- **Frontend/Data API tables:** add explicit grants, then enable RLS, then add policies in the same migration.
- Use the shared helpers in `backend/app/utils/migration_utils.py` when a migration needs Supabase Data API exposure:
  - `grant_supabase_data_api_table_access(...)`
  - `grant_supabase_data_api_sequence_access(...)`
  - `enable_row_level_security(...)`
  - `create_policy_if_missing(...)`
- Do not grant `anon` unless the table is intentionally public.
- If a table uses UUID defaults only, sequence grants may be unnecessary. If it uses sequences or identity columns and the client writes through the Data API, grant sequence access explicitly.

Example pattern for a frontend-accessed table:

```python
from app.utils.migration_utils import (
    create_policy_if_missing,
    enable_row_level_security,
    grant_supabase_data_api_table_access,
)

if "beta_reader_assignments" not in tables:
    op.create_table("beta_reader_assignments", ...)

grant_supabase_data_api_table_access("beta_reader_assignments")
enable_row_level_security("beta_reader_assignments")
create_policy_if_missing(
    "beta_reader_assignments",
    "authors can manage assignments",
    command="ALL",
    using="auth.uid() = author_user_id",
    with_check="auth.uid() = author_user_id",
)
```

**Other production migration practices:**

- **Always write both `upgrade()` and `downgrade()`** — migrations must be reversible.
- **Use nullable=True for new columns** on existing tables, then backfill data in a separate migration if needed.
- **Add server_default for new non-nullable columns** to avoid blocking writes during migration.
- **Batch large data migrations** — use `op.execute()` with LIMIT/OFFSET for updates on large tables to avoid long locks.
- **Test migrations locally** on a fresh database before pushing.
- **Always verify a newly generated migration file before applying it.** If you did not explicitly intend to delete something, treat `drop_table`, `drop_column`, `drop_index`, `drop_constraint`, or `cascade` usage as a red flag and remove those lines from the script before running Alembic.
- **Never let Alembic infer a remote database from app settings.** For non-local databases, set `ALEMBIC_DATABASE_URL` explicitly, confirm the target, and refuse to run if an upgrade block contains destructive operations unless you intentionally set the destructive override.
- **Use descriptive revision IDs** — e.g., `20260426_add_character_classification` instead of generic IDs.
- **Document breaking changes** in the migration docstring if the migration cannot be fully reversed.

### Alembic Safety Checklist

Before any `alembic upgrade head` run, follow this exact sequence:

1. Confirm you are using the repo venv and not a global Alembic install.
   ```powershell
   & .\.venv\Scripts\python.exe -m alembic --version
   ```
2. Inspect the target revision and current database state before upgrading.
   ```powershell
   & .\.venv\Scripts\python.exe -m alembic current
   & .\.venv\Scripts\python.exe -m alembic heads
   ```
3. Set the database URL explicitly for the target database.
   ```powershell
   $env:ALEMBIC_DATABASE_URL="postgresql://<user>:<password>@<host>:5432/postgres?sslmode=require"
   ```
4. Confirm you really intend to run against a remote database.
   ```powershell
   $env:ALEMBIC_CONFIRM_REMOTE="YES_I_AM_SURE"
   ```
5. Re-open the migration file and scan for destructive operations before running it.
   - Treat `drop_table`, `drop_column`, `drop_index`, `drop_constraint`, `TRUNCATE`, `CASCADE`, and schema rebuilds as a stop sign unless you explicitly planned them.
   - If the migration changes tables that already contain production data, verify the `upgrade()` and `downgrade()` paths manually before proceeding.
6. Run the upgrade with the repo interpreter.
   ```powershell
   & .\.venv\Scripts\python.exe -m alembic upgrade head
   ```

If there is any doubt about the target database, stop and verify the connection string, revision, and migration diff again before executing the upgrade.

### Database Protection Rules

- Never run CI, local migration scripts, or GitHub-pushed changes against a production database unless the target is explicitly named and confirmed.
- Never let a migration infer production settings from `.env` alone.
- Prefer local or staging verification first, then run production with an explicit `ALEMBIC_DATABASE_URL`.
- After a schema change, verify `alembic current`, `alembic heads`, and the affected table list before considering the migration complete.
- If a migration contains schema recreation, bulk deletes, or `CASCADE`, pause and get a second review before applying it.
