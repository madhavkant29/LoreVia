import type { Book } from "@/types/book"
import type { ChapterListItem, ReadingProgress } from "@/types/reader"

const READER_WORDS_PER_MINUTE = 230

export function estimateReaderBookWords(
  book: Pick<Book, "total_words" | "total_tokens" | "total_chapters" | "work_type">,
  progress?: Pick<ReadingProgress, "percent_complete" | "chapters_left" | "chapters_read_count"> | null,
) {
  if (typeof book.total_words === "number" && book.total_words > 0) return Math.round(book.total_words)
  if (typeof book.total_tokens === "number" && book.total_tokens > 0) return Math.round(book.total_tokens * 0.75)

  const defaultUnits = Math.max(
    book.total_chapters ?? 0,
    (progress?.chapters_left ?? 0) + (progress?.chapters_read_count ?? 0),
    1,
  )
  const unitWords = book.work_type === "screenplay" ? 900 : 3200

  return defaultUnits * unitWords
}

export function estimateRemainingReadingMinutes(
  book: Pick<Book, "total_words" | "total_tokens" | "total_chapters" | "work_type">,
  progress?: Pick<ReadingProgress, "percent_complete" | "chapters_left" | "chapters_read_count"> | null,
) {
  const totalWords = estimateReaderBookWords(book, progress)
  if (!totalWords) return null

  const percent = Math.max(0, Math.min(100, progress?.percent_complete ?? 0))
  const remainingWords = percent > 0 ? totalWords * (1 - percent / 100) : totalWords

  return Math.max(1, Math.ceil(remainingWords / READER_WORDS_PER_MINUTE))
}

export function formatReadingDuration(minutes?: number | null) {
  if (typeof minutes !== "number" || Number.isNaN(minutes) || minutes <= 0) return "Syncing"
  if (minutes < 60) return `${minutes} min`

  const hours = Math.floor(minutes / 60)
  const remainder = minutes % 60
  return remainder > 0 ? `${hours}h ${remainder}m` : `${hours}h`
}

export function formatBookFormatLabel(format?: Book["format"]) {
  switch (format) {
    case "epub":
      return "ePub"
    case "docx":
      return "DOCX"
    case "pdf":
      return "PDF"
    case "txt":
      return "TXT"
    case "md":
      return "Markdown"
    case "doc":
      return "DOC"
    case "fountain":
      return "Fountain"
    case "manual":
      return "Manual"
    default:
      return "Digital"
  }
}

export function buildReaderChapterPreview(chapters: ChapterListItem[], currentChapter: number, windowSize = 8) {
  if (chapters.length <= windowSize) return chapters

  const currentIndex = Math.max(0, chapters.findIndex((chapter) => chapter.number === currentChapter))
  const maxStart = Math.max(0, chapters.length - windowSize)
  const start = Math.min(maxStart, Math.max(0, currentIndex - 2))

  return chapters.slice(start, start + windowSize)
}
