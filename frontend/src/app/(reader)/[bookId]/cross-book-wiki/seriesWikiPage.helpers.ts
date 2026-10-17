import type { BookSelector } from "@/types/book"
import type { CrossBookIntelligence, CrossBookMatch } from "@/types/intelligence"
import { normalizeBookRouteId } from "@/lib/utils/bookRoutes"

export type ReferenceType = "characters" | "wiki"
export type SeriesReference = {
  key: string; source: ReferenceType; entryType: string | null; similarity: number
  firstName: string; firstBookId: string; firstBookTitle: string
  secondName: string; secondBookId: string; secondBookTitle: string; involvesCurrentBook: boolean
}

export function seriesComparisonIds(data: CrossBookIntelligence | null | undefined): string[] {
  return Array.from(new Set((Array.isArray(data?.comparison_book_ids) ? data.comparison_book_ids : []).filter(id => typeof id === "string" && id.trim()).map(normalizeBookRouteId)))
}

export function seriesReferences(data: CrossBookIntelligence | null | undefined, books: Pick<BookSelector, "id" | "title">[], currentId: string) {
  const current = normalizeBookRouteId(currentId)
  const titles = new Map(books.map(book => [normalizeBookRouteId(book.id), book.title]))
  const comparisonIds = new Set(seriesComparisonIds(data))
  const unique = new Map<string, SeriesReference>()
  let omitted = 0
  for (const source of ["characters", "wiki"] as const) {
    const rows = source === "characters" ? data?.character_matches : data?.wiki_matches
    for (const row of Array.isArray(rows) ? rows : []) {
      const match: CrossBookMatch | null = row
      if (!match || typeof match.left_book_id !== "string" || typeof match.right_book_id !== "string" || typeof match.left_name !== "string" || !match.left_name.trim() || typeof match.right_name !== "string" || !match.right_name.trim() || typeof match.similarity !== "number" || !Number.isFinite(match.similarity) || match.similarity < 0 || match.similarity > 1) { omitted++; continue }
      const left = normalizeBookRouteId(match.left_book_id), right = normalizeBookRouteId(match.right_book_id)
      if (!left || !right || left === right || !comparisonIds.has(left) || !comparisonIds.has(right)) { omitted++; continue }
      const entryType = typeof match.entry_type === "string" && match.entry_type.trim() ? match.entry_type.trim() : null
      const endpoints = [[left, match.left_name.trim()], [right, match.right_name.trim()]].sort((a, b) => a[0].localeCompare(b[0]) || a[1].localeCompare(b[1]))
      const key = JSON.stringify([source, entryType, endpoints])
      const flip = right === current
      const firstBookId = flip ? right : left, secondBookId = flip ? left : right
      const reference: SeriesReference = { key, source, entryType, similarity: match.similarity, firstName: (flip ? match.right_name : match.left_name).trim(), firstBookId, firstBookTitle: titles.get(firstBookId) || `Book ${firstBookId}`, secondName: (flip ? match.left_name : match.right_name).trim(), secondBookId, secondBookTitle: titles.get(secondBookId) || `Book ${secondBookId}`, involvesCurrentBook: left === current || right === current }
      if (!unique.has(key) || unique.get(key)!.similarity < reference.similarity) unique.set(key, reference)
    }
  }
  return { references: [...unique.values()].sort((a, b) => b.similarity - a.similarity || a.key.localeCompare(b.key)), omitted }
}

export function filterSeriesReferences(references: SeriesReference[], options: { mode: "all" | ReferenceType; scope: "current" | "series"; threshold: number; query: string }) {
  const query = options.query.trim().toLowerCase()
  return references.filter(item => (options.scope === "series" || item.involvesCurrentBook) && (options.mode === "all" || item.source === options.mode) && item.similarity * 100 >= options.threshold && [item.firstName, item.secondName, item.firstBookTitle, item.secondBookTitle, item.entryType ?? ""].some(value => value.toLowerCase().includes(query)))
}

export function seriesSimilarityLabel(score: number): string {
  return `${Number((score * 100).toFixed(1))}%`
}
