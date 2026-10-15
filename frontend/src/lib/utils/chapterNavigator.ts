import type { Book } from "@/types/book"
import type { ChapterListItem } from "@/types/reader"

export type ChapterStatusFilter = "all" | "unread" | "read" | "queued"

export function filterChapterList(chapters: ChapterListItem[], search: string, status: ChapterStatusFilter) {
  const query = search.trim().toLocaleLowerCase()
  return chapters.filter((chapter) => {
    const matchesStatus = status === "all" || (status === "queued" ? !chapter.processed : status === "read" ? chapter.read : !chapter.read)
    const searchable = `${chapter.number} ${chapter.title ?? ""} ${(chapter.tags ?? []).join(" ")}`.toLocaleLowerCase()
    return matchesStatus && (!query || searchable.includes(query))
  })
}

export function canRemoveChapter(book: Book | null, chapter: number) {
  if (book?.mode !== "author") return false
  if (!book.collaboration_role) return true
  if (!book.collaboration_permissions?.can_edit_manuscript) return false
  const scope = book.collaboration_scope
  return (scope?.chapter_start == null || chapter >= scope.chapter_start)
    && (scope?.chapter_end == null || chapter <= scope.chapter_end)
}
