import {
  buildUniqueWorkspacePath,
  buildWorkspaceFolderTree,
  normalizeWorkspaceFolderPath,
  workspaceFileTitle,
  workspaceFolderFromPath,
  type WorkspaceFolderNode,
} from "@/lib/utils/workspacePaths"
import type { VaultGraphEdge, VaultNote, VaultNoteRelations } from "@/types/book"

export const FAVORITES_STORAGE_KEY = "vault-note-favorites:v1"
export const FOLDERS_STORAGE_KEY_PREFIX = "vault-note-folders:v1:"
export const CORE_NOTE_FOLDERS = [
  "Characters",
  "Plot Threads",
  "Story Advisor",
  "Manual Editor",
  "Worldbuilding",
  "Timeline",
  "Themes",
  "Templates",
  "Custom",
]

export type FolderNode = WorkspaceFolderNode
export type NotesDragItem = { kind: "note"; path: string }

export const TOOLBAR_BUTTON_DEFS = [
  { key: "bold", label: "B", title: "Bold", kind: "wrap" as const, open: "**", close: "**", fallbackText: "bold text" },
  { key: "italic", label: "I", title: "Italic", className: "italic", kind: "wrap" as const, open: "*", close: "*", fallbackText: "italic text" },
  { key: "strike", label: "S", title: "Strikethrough", className: "line-through", kind: "wrap" as const, open: "~~", close: "~~", fallbackText: "crossed text" },
  { key: "underline", label: "U", title: "Underline helper", className: "underline", kind: "wrap" as const, open: "<u>", close: "</u>", fallbackText: "underlined text" },
  { key: "h1", label: "H1", title: "Heading 1", kind: "prefix" as const, prefix: "# ", fallbackText: "Heading" },
  { key: "h2", label: "H2", title: "Heading 2", kind: "prefix" as const, prefix: "## ", fallbackText: "Section heading" },
  { key: "h3", label: "H3", title: "Heading 3", kind: "prefix" as const, prefix: "### ", fallbackText: "Subsection" },
  { key: "bullets", label: "-", title: "Bullet list", kind: "prefix" as const, prefix: "- ", fallbackText: "List item" },
  { key: "numbers", label: "1.", title: "Numbered list", kind: "prefix" as const, prefix: "1. ", fallbackText: "Numbered item" },
  { key: "check", label: "[ ]", title: "Checklist", kind: "prefix" as const, prefix: "- [ ] ", fallbackText: "Checklist item" },
  { key: "quote", label: '"', title: "Blockquote", kind: "prefix" as const, prefix: "> ", fallbackText: "Quoted note" },
  { key: "code", label: "</>", title: "Code", kind: "wrap" as const, open: "`", close: "`", fallbackText: "code" },
  { key: "link", label: "[[]]", title: "Wiki link", kind: "wrap" as const, open: "[[", close: "]]", fallbackText: "Linked note" },
  { key: "divider", label: "---", title: "Divider", kind: "snippet" as const, snippet: "\n---\n" },
  { key: "scene-break", label: "***", title: "Scene break", kind: "snippet" as const, snippet: "\n***\n" },
  { key: "bookmark", label: "#", title: "Bookmark / anchor", kind: "snippet" as const, snippet: "\n^anchor-name\n" },
  { key: "template", label: "Tpl", title: "Scene note template", kind: "snippet" as const, snippet: "\n## Scene note\n- POV:\n- Location:\n- Timeline:\n- Tags:\n- Continuity risk:\n\n" },
  { key: "table", label: "tbl", title: "Table", kind: "snippet" as const, snippet: "\n| Column | Detail |\n| --- | --- |\n| Item | Note |\n" },
] as const

export function noteTitle(path: string) {
  return workspaceFileTitle(path)
}

export function noteFolder(path: string) {
  return workspaceFolderFromPath(path)
}

export function matchesReference(path: string, reference: string) {
  const cleanedReference = reference.replace(/\.md$/i, "").trim().toLowerCase()
  const cleanedPath = path.toLowerCase()
  return cleanedPath === reference.toLowerCase() || noteTitle(path).toLowerCase() === cleanedReference
}

export function fileWordCount(value: string) {
  const trimmed = value.trim()
  return trimmed ? trimmed.split(/\s+/).length : 0
}

export function fileCharacterCount(value: string) {
  return value.trim().length
}

export function countMarkdownHeadings(value: string) {
  return value.match(/^#{1,6}\s+/gm)?.length ?? 0
}

export function countWikiLinks(value: string) {
  return value.match(/\[\[[^\]]+\]\]/g)?.length ?? 0
}

export function buildFolderTree(paths: string[], seededFolders: string[] = []) {
  const root = buildWorkspaceFolderTree(paths, seededFolders)
  root.name = "All notes"
  return root
}

export function buildUniqueNotePath(notes: VaultNote[], folder: string | null, baseTitle: string) {
  return buildUniqueWorkspacePath(notes.map((note) => note.path), folder, baseTitle)
}

export function buildNoteMap(notes: VaultNote[]) {
  return new Map(notes.map((note) => [note.path, note]))
}

export function getSelectedVaultNote(noteMap: Map<string, VaultNote>, selectedPath: string | null) {
  return selectedPath ? noteMap.get(selectedPath) ?? null : null
}

export function getSelectedNoteContent(selectedNote: VaultNote | null, drafts: Record<string, string>) {
  return selectedNote ? drafts[selectedNote.path] ?? selectedNote.content : ""
}

export function getSelectedOutgoingLinks(edges: VaultGraphEdge[], selectedPath: string | null) {
  return edges.filter((edge) => edge.source === selectedPath)
}

export function getRecentVaultMentions(relations: VaultNoteRelations | null) {
  return [...(relations?.backlinks ?? [])]
    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
    .slice(0, 3)
}

export function getVaultPreviewNodes(
  selectedOutgoingLinks: Pick<VaultGraphEdge, "target">[],
  recentMentions: Pick<VaultNoteRelations["backlinks"][number], "source_note_path">[],
) {
  const unique = new Map<string, { id: string; label: string }>()
  for (const link of selectedOutgoingLinks.slice(0, 2)) {
    unique.set(link.target, { id: link.target, label: noteTitle(link.target) })
  }
  for (const link of recentMentions.slice(0, 2)) {
    if (!unique.has(link.source_note_path)) {
      unique.set(link.source_note_path, { id: link.source_note_path, label: noteTitle(link.source_note_path) })
    }
  }
  return [...unique.values()].slice(0, 4)
}

export function filterVaultNotes(
  notes: VaultNote[],
  drafts: Record<string, string>,
  selectedFolder: string | null,
  query: string
) {
  const term = query.trim().toLowerCase()
  return [...notes]
    .filter((note) => {
      const draft = drafts[note.path] ?? note.content
      const folder = noteFolder(note.path)
      const folderMatches = !selectedFolder || folder === selectedFolder || folder.startsWith(`${selectedFolder}/`)
      if (!folderMatches) return false
      if (!term) return true
      return (
        note.path.toLowerCase().includes(term) ||
        folder.toLowerCase().includes(term) ||
        noteTitle(note.path).toLowerCase().includes(term) ||
        draft.toLowerCase().includes(term)
      )
    })
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())
}

export function getFavoriteVaultNotes(notes: VaultNote[], favorites: Record<string, boolean>) {
  return notes.filter((note) => favorites[note.path])
}

export function getDisplayedVaultNotes(notesView: "recent" | "favorites", filteredNotes: VaultNote[], favoriteNotes: VaultNote[]) {
  return notesView === "favorites" ? favoriteNotes : filteredNotes
}

export function getAvailableNotePaths(notes: VaultNote[]) {
  return notes.map((note) => note.path)
}

export interface TextSelectionRange {
  start: number
  end: number
}

export interface TextEditResult extends TextSelectionRange {
  value: string
}

export function wrapSelectedText(
  currentValue: string,
  selectionRange: TextSelectionRange,
  before: string,
  after = before,
  fallback = ""
): TextEditResult {
  const selection = currentValue.slice(selectionRange.start, selectionRange.end)
  const body = selection || fallback
  const value = `${currentValue.slice(0, selectionRange.start)}${before}${body}${after}${currentValue.slice(selectionRange.end)}`
  const start = selectionRange.start + before.length
  return {
    value,
    start,
    end: start + body.length,
  }
}

export function prefixSelectedTextLines(currentValue: string, selectionRange: TextSelectionRange, prefix: string, fallback: string): TextEditResult {
  const selection = currentValue.slice(selectionRange.start, selectionRange.end)
  const source = selection || fallback
  const nextChunk = source
    .split("\n")
    .map((line) => `${prefix}${line}`)
    .join("\n")
  return {
    value: `${currentValue.slice(0, selectionRange.start)}${nextChunk}${currentValue.slice(selectionRange.end)}`,
    start: selectionRange.start,
    end: selectionRange.start + nextChunk.length,
  }
}

export function insertTextSnippet(currentValue: string, selectionRange: TextSelectionRange, snippet: string): TextEditResult {
  const cursor = selectionRange.start + snippet.length
  return {
    value: `${currentValue.slice(0, selectionRange.start)}${snippet}${currentValue.slice(selectionRange.end)}`,
    start: cursor,
    end: cursor,
  }
}

export function loadFavoriteMap() {
  if (typeof window === "undefined") return {}
  try {
    return JSON.parse(window.localStorage.getItem(FAVORITES_STORAGE_KEY) || "{}") as Record<string, boolean>
  } catch {
    return {}
  }
}

export function loadCustomFolders(bookId: string) {
  if (typeof window === "undefined") return [] as string[]
  try {
    const raw = window.localStorage.getItem(`${FOLDERS_STORAGE_KEY_PREFIX}${bookId}`)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed.map((value) => normalizeWorkspaceFolderPath(String(value))).filter(Boolean) : []
  } catch {
    return []
  }
}

export function parseNotesDragItem(event: { dataTransfer?: DataTransfer | null }) {
  const raw = event.dataTransfer?.getData("application/lorevia-note-item")
  if (!raw) return null
  try {
    const value = JSON.parse(raw) as NotesDragItem
    return value.kind === "note" && value.path ? value : null
  } catch {
    return null
  }
}

export function formatRelativeTime(value: string) {
  const timestamp = new Date(value).getTime()
  if (Number.isNaN(timestamp)) return "Unknown"
  const diffMs = timestamp - Date.now()
  const diffMinutes = Math.round(diffMs / 60000)
  if (Math.abs(diffMinutes) < 1) return "just now"
  if (Math.abs(diffMinutes) < 60) return `${Math.abs(diffMinutes)}m ago`
  const diffHours = Math.round(diffMinutes / 60)
  if (Math.abs(diffHours) < 24) return `${Math.abs(diffHours)}h ago`
  const diffDays = Math.round(diffHours / 24)
  if (Math.abs(diffDays) === 1) return "Yesterday"
  if (Math.abs(diffDays) < 7) return `${Math.abs(diffDays)}d ago`
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(new Date(value))
}

export function formatTimestamp(value: string) {
  const timestamp = new Date(value)
  if (Number.isNaN(timestamp.getTime())) return "Unknown"
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(timestamp)
}

export function inferNoteType(path: string) {
  const lower = path.toLowerCase()
  if (lower.includes("character")) return "Character"
  if (lower.includes("plot")) return "Plot"
  if (lower.includes("world")) return "World"
  if (lower.includes("timeline")) return "Timeline"
  if (lower.includes("theme")) return "Theme"
  if (lower.includes("template")) return "Template"
  return "Note"
}

export function markdownButtonClass(isDark: boolean) {
  return `flex h-9 min-w-9 items-center justify-center rounded-xl border px-2 text-sm font-semibold transition ${
    isDark
      ? "border-white/[0.08] bg-white/[0.03] text-slate-300 hover:bg-white/[0.08] hover:text-white"
      : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"
  }`
}
