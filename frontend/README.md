# LoreVia Frontend

Next.js 15 + TypeScript + Tailwind

## Setup

```bash
cp .env.local.example .env.local   # fill in API URL
npm install
npm run dev
```

## Testing

### Frontend unit tests

```powershell
cd frontend
npm.cmd test
```

This runs the Vitest suite for frontend utilities, stores, config, API wrappers, and other client-side logic.

### Frontend E2E smoke tests

```powershell
cd frontend
npm.cmd run test:e2e
```

Notes:

- The smoke suite boots the local Next.js dev server automatically.
- API calls are mocked in the browser for the smoke flows, so the suite does not require a live backend.
- The Playwright config uses Playwright-managed Chromium so local and CI runs use the same browser engine.

### Will these fail in non-production environments?

Not by default.

- Unit tests are designed to run locally and in CI-style non-production environments.
- E2E smoke tests are also designed for non-production use because they exercise the local app with mocked API responses instead of production services.
- The main CI pipeline installs Chromium and runs the same frontend unit and E2E smoke suites that you run locally.

They may still fail if the machine is missing prerequisites such as installed dependencies or a supported browser runtime.

## Key pages

| Route | Description |
|---|---|
| / | Landing page |
| /login, /register | Auth |
| /library | Book list + upload |
| /settings | Reading mode, account |
| /[bookId] | Book overview + recall card |
| /[bookId]/chapter/[n] | Reader with Smart Tap |
| /[bookId]/characters | All extracted characters |
| /[bookId]/graph | Relationship graph |
| /[bookId]/search | Semantic search |

## Smart Tap

Select any text in the reader → context panel slides in automatically.
Character name → full profile + relationships.
Any other text → semantic search results.
