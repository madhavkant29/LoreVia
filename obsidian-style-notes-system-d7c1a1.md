# Obsidian-Style Notes System

Transform the notes experience into a full Obsidian-like editor with folder structure, graph viewer, markdown preview/edit modes, and ZIP import/export for per-book notes.

## Current State

- **BookNote**: Chapter-linked notes from manuscript workspace, shown in `/dashboard/notes`
- **ObsidianVaultNote**: Stores exported character bible vault overrides
- **ObsidianVaultPreview**: Component for previewing/editing exported vaults (currently only for character bible)

## Proposed Changes

### Database Schema
- Add `source` column to `ObsidianVaultNote` table (enum: `character_bible`, `user_notes`)
- Create migration to add this column with default value `character_bible`
- Update unique constraint to include `source` field

### Backend API

**New Endpoints:**
- `GET /books/{book_id}/notes/obsidian` - List user notes for a book
- `PUT /books/{book_id}/notes/obsidian` - Save/update a user note
- `DELETE /books/{book_id}/notes/obsidian/{path}` - Delete a user note
- `POST /books/{book_id}/notes/obsidian/import` - Import Obsidian vault ZIP
- `GET /books/{book_id}/notes/obsidian/export` - Export notes as Obsidian vault ZIP
- `GET /books/{book_id}/notes/obsidian/graph` - Get graph data (nodes/edges from [[wiki-links]])

**Backend Utils:**
- Parse markdown to extract [[wiki-link]] references
- Build graph structure (nodes = notes, edges = wiki-link connections)
- ZIP parsing/writing for vault import/export
- Folder structure utilities

### Frontend Components

**New Page:**
- `/[bookId]/notes` - Dedicated page for per-book Obsidian-style notes

**New Components:**
- `ObsidianNotesEditor` - Main editor component (fork of ObsidianVaultPreview)
  - Folder tree navigation sidebar
  - File list with folder grouping
  - Markdown editor with live preview toggle
  - Edit/Preview mode switch (button to toggle between raw markdown and rendered view)
  - Graph viewer panel
  - Import/Export ZIP buttons
- `GraphViewer` - Visual graph component showing note connections
  - Force-directed layout
  - Click node to open note
  - Hover to show connections
- `FolderTree` - Collapsible folder structure component
- `MarkdownPreview` - Rendered markdown view (using existing rich text utils)

**Integration Points:**
- Add "Open Notes" button to book overview page (`/[bookId]/page.tsx`)
- Add per-book notes links to dashboard notes page (`/dashboard/notes/page.tsx`)
- Keep existing BookNote system intact, show in both places

### Key Features

1. **Folder Structure**: Notes organized in folders (e.g., `Characters/`, `Plot/`, `World/`)
2. **File Navigation**: Browse notes by folder, search across all notes
3. **Edit/Preview Modes**: 
   - Edit mode: Raw markdown textarea
   - Preview mode: Rendered markdown (bold, italic, links, etc. rendered)
   - Toggle button to switch between modes
4. **Graph Viewer**: Visual representation of note connections via [[wiki-links]]
5. **Wiki-Link Navigation**: Click [[Note Name]] to open that note
6. **ZIP Import/Export**: 
   - Import existing Obsidian vaults
   - Export notes as vault for use in Obsidian app
7. **Auto-save**: Debounced save on edit (like current ObsidianVaultPreview)

### Implementation Order

1. Database migration for `source` column
2. Backend API endpoints for user notes (separate from character bible)
3. Backend utils for graph data and ZIP handling
4. Frontend API client methods
5. GraphViewer component
6. FolderTree component
7. ObsidianNotesEditor component
8. New `/[bookId]/notes` page
9. Integration links in book overview and dashboard notes
10. Testing and refinement

### Notes

- Existing BookNote system remains unchanged
- Character bible export notes use `source=character_bible`
- User notes use `source=user_notes`
- Both systems can coexist per book
- Graph viewer parses [[wiki-links]] in markdown content
- ZIP import creates notes with paths matching vault structure
