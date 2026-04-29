See AGENTS.md at the repo root for the full coding rules that apply to this project.

Key non-negotiables (repeated here for quick reference):

- SQLAlchemy models → `backend/app/models/` (add to existing file or create new only for new domain)
- Pydantic schemas → `backend/app/schemas/` (same rule)
- Helper / utility functions → `backend/app/utils/` (character_utils, book_utils, export_utils, reader_utils, advisor_utils)
- Route files (`app/api/v1/routes/`) contain endpoint handlers ONLY — no business logic
- Import helpers with public names — no `as _name` aliases, no shim wrapper functions
- One requirements file: `backend/requirements.txt` — pin exact versions, never recreate requirements-dev.txt
- Character filtering: use `character_visibility_score()` + `VISIBILITY_THRESHOLD` — stopwords are soft penalties, not hard gates
- No commented-out code; preserve unrelated docstrings and comments
- **Write tests for all new functions** in `backend/tests/unit/` for utility functions and `backend/tests/integration/` for API endpoints
- **Consider edge cases** when writing tests: empty inputs, null values, boundary conditions, malformed data, and error scenarios

**Migration Best Practices (see AGENTS.md for full details):**
- Always check if tables, columns, and indexes exist before creating them to prevent duplication
- Make migrations idempotent — safe to run multiple times without errors
- Always write both `upgrade()` and `downgrade()` — migrations must be reversible
- Use nullable=True for new columns on existing tables
- Add server_default for new non-nullable columns to avoid blocking writes
- Batch large data migrations with LIMIT/OFFSET to avoid long locks
- Test migrations locally on a fresh database before pushing
