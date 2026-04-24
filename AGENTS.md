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

- Every helper function must live in `backend/app/utils/`.
  - `character_utils.py` — character display, status, relationship text, text cleaning
  - `book_utils.py`      — DB query wrappers, cover, progress, chapter numbers, manuscript parsing
  - `export_utils.py`    — Character card and bible renderers (Markdown / PDF / DOCX)
  - `reader_utils.py`    — Timeline/graph filters, media serialization, summary normalization
  - `advisor_utils.py`   — LLM prompts, intent classification, story context, report builders
  - Add to the matching file above; create a new `*_utils.py` only for a new, distinct domain.
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

### 7. Testing

- **Write tests for all new functions** in `backend/tests/unit/` for utility functions and `backend/tests/integration/` for API endpoints.
- **Consider edge cases** when writing tests: empty inputs, null values, boundary conditions, malformed data, and error scenarios.
- Test both happy paths and error paths.
- Use descriptive test names that clearly indicate what is being tested.
- Maintain test coverage for critical paths.

---

## Before you write any code

1. Identify which existing file the change belongs to (model, schema, util, route, service).
2. Check `app/utils/` — the helper may already exist.
3. Check `app/models/` — the model may already exist.
4. Only then write new code, always in the right layer.
