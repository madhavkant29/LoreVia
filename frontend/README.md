# LoreVia Frontend

Next.js 15 + TypeScript + Tailwind

## Setup

```bash
cp .env.local.example .env.local   # fill in API URL
npm install
npm run dev
```

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
