import { booksApi } from "@/lib/api/books"
import type { ObsidianVaultNoteSaveResult } from "@/types/book"

export type VaultNoteContext =
  | "characters"
  | "plot_threads"
  | "story_advisor"
  | "manuscript"
  | "manual_editor"
  | "custom"

type SaveContextualVaultNoteInput = {
  bookId: string
  title: string
  content: string
  context: VaultNoteContext
  folderSegments?: string[]
  explicitFolder?: string | null
}

const CONTEXT_ROOT_FOLDERS: Record<Exclude<VaultNoteContext, "custom">, string> = {
  characters: "Characters",
  plot_threads: "Plot Threads",
  story_advisor: "Story Advisor",
  manuscript: "Manuscript",
  manual_editor: "Manual Editor",
}

export function sanitizeNotePathSegment(value: string) {
  return value
    .replace(/[<>:"|?*]+/g, "")
    .replace(/[\\/]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
}

export function joinNoteFolderSegments(...segments: Array<string | null | undefined>) {
  return segments
    .flatMap((segment) => (segment ?? "").split("/"))
    .map((segment) => sanitizeNotePathSegment(segment))
    .filter(Boolean)
    .join("/")
}

export function buildContextualNoteFolder(context: VaultNoteContext, options?: { folderSegments?: string[]; explicitFolder?: string | null }) {
  if (context === "custom") {
    return joinNoteFolderSegments(options?.explicitFolder ?? "", ...(options?.folderSegments ?? []))
  }
  return joinNoteFolderSegments(CONTEXT_ROOT_FOLDERS[context], ...(options?.folderSegments ?? []))
}

export function buildContextualNotePath(
  title: string,
  context: VaultNoteContext,
  options?: { folderSegments?: string[]; explicitFolder?: string | null }
) {
  const folder = buildContextualNoteFolder(context, options)
  const safeTitle = sanitizeNotePathSegment(title) || "Untitled note"
  const filename = `${safeTitle}.md`
  return folder ? `${folder}/${filename}` : filename
}

export async function saveContextualVaultNote({
  bookId,
  title,
  content,
  context,
  folderSegments,
  explicitFolder,
}: SaveContextualVaultNoteInput): Promise<ObsidianVaultNoteSaveResult> {
  const normalizedTitle = sanitizeNotePathSegment(title) || "Untitled note"
  const normalizedContent = content.replace(/\r\n/g, "\n").trim()
  const existing = await booksApi.listObsidianNotes(bookId)
  const existingPaths = new Set(existing.map((note) => note.path.toLowerCase()))
  const folder = buildContextualNoteFolder(context, { folderSegments, explicitFolder })

  let path = buildContextualNotePath(normalizedTitle, context, { folderSegments, explicitFolder })
  if (existingPaths.has(path.toLowerCase())) {
    let suffix = 2
    while (existingPaths.has(path.toLowerCase())) {
      const filename = `${normalizedTitle} ${suffix}.md`
      path = folder ? `${folder}/${filename}` : filename
      suffix += 1
    }
  }

  return booksApi.saveObsidianNote(bookId, {
    path,
    content: normalizedContent.startsWith("# ") ? normalizedContent : `# ${normalizedTitle}\n\n${normalizedContent}`,
  })
}
