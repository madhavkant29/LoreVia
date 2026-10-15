import type { ChapterSummary, SummaryCollectionResponse } from "@/types/reader"

export function normalizeChapterSummary(summary: ChapterSummary): ChapterSummary {
  const content = typeof summary.content === "string" ? summary.content.trim() : ""
  let source: Record<string, unknown> = summary as unknown as Record<string, unknown>
  if (content.startsWith("{") || content.startsWith("```")) {
    try {
      const parsed: unknown = JSON.parse(content.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, ""))
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) source = { ...source, ...parsed }
    } catch { /* Preserve plain text if a generated structured recap is malformed. */ }
  }
  return {
    content: typeof source.summary === "string" ? source.summary : content,
    key_events: Array.isArray(source.key_events) ? source.key_events.filter((item) => item && typeof item.event === "string") : [],
    char_changes: Array.isArray(source.char_changes) ? source.char_changes.filter((item) => item && typeof item.character === "string" && typeof item.change === "string") : [],
    clues: Array.isArray(source.clues) ? source.clues.filter((item) => item && typeof item.clue === "string") : [],
  }
}

export type ManuscriptRecap = {
  chapterCount: number
  content: string
}

export function buildManuscriptRecap(
  collection: SummaryCollectionResponse | null | undefined,
  maxLength = 560,
): ManuscriptRecap | null {
  const available = (collection?.summaries ?? [])
    .filter((summary) => summary.available && summary.content?.trim())
    .sort((left, right) => left.chapter_number - right.chapter_number)
  if (!available.length) return null

  const combined = available
    .map((summary) => summary.content?.trim().replace(/\s+/g, " ") ?? "")
    .join(" ")
  if (combined.length <= maxLength) return { chapterCount: available.length, content: combined }

  const clipped = combined.slice(0, Math.max(1, maxLength - 1))
  const lastBoundary = Math.max(clipped.lastIndexOf(". "), clipped.lastIndexOf("! "), clipped.lastIndexOf("? "))
  const content = lastBoundary >= Math.floor(maxLength * 0.55)
    ? clipped.slice(0, lastBoundary + 1)
    : `${clipped.replace(/\s+\S*$/, "").trim()}…`
  return { chapterCount: available.length, content }
}
