import type { BookNote, ChapterVersion, ManuscriptAnnotation } from "@/types/book"
import type { Character } from "@/types/character"

export type WorkspaceTab = "write" | "plan" | "analysis"
export type RightPane = "context" | "advisor" | "notes" | "arcs" | "insights" | "character"
export type EditorMode = "chapter" | "book"
export type DraftSurfaceMode = "edit" | "paged"
export type SaveTarget = "book_note" | "vault_note" | "workspace" | "corkboard" | "chapter_title" | "annotation"

export const WORKSPACE_TABS: Array<{ id: WorkspaceTab; label: string; title: string }> = [
  { id: "write", label: "Write", title: "Write manuscript" },
  { id: "plan", label: "Plan", title: "Plan story structure" },
  { id: "analysis", label: "Analysis", title: "Review manuscript and characters" },
]

export const EMPTY_CHARACTERS: Character[] = []
export const EMPTY_ANNOTATIONS: ManuscriptAnnotation[] = []
export const EMPTY_NOTES: BookNote[] = []
export const EMPTY_CHAPTER_VERSIONS: ChapterVersion[] = []
export const SCENE_DRAG_SCENE_ID_MIME = "application/x-lorevia-scene-id"
export const SCENE_DRAG_CHAPTER_MIME = "application/x-lorevia-chapter-number"
export const MANUSCRIPT_PROCESSING_POLL_INTERVAL_MS = 5_000
