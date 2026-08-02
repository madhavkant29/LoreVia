import type { ChapterConsistencyReport } from "@/types/book"

export function normalizeTag(rawTag: string): string {
  return rawTag.trim().toLowerCase().replace(/\s+/g, " ")
}

function normalizeKeywords(input: string) {
  return input
    .toLowerCase()
    .split(/[^a-z0-9]+/i)
    .map((token) => token.trim())
    .filter((token) => token.length >= 2)
}

export function tagSimilarity(tag: string, query: string) {
  const trimmed = query.trim()
  if (!trimmed) return 0

  const tagLower = tag.toLowerCase()
  const queryLower = trimmed.toLowerCase()
  if (tagLower.includes(queryLower) || queryLower.includes(tagLower)) return 1

  const aTokens = new Set(normalizeKeywords(tag))
  const bTokens = new Set(normalizeKeywords(trimmed))
  if (aTokens.size === 0 || bTokens.size === 0) return 0

  let intersection = 0
  for (const token of aTokens) {
    if (bTokens.has(token)) intersection += 1
  }
  const union = aTokens.size + bTokens.size - intersection
  return union === 0 ? 0 : intersection / union
}

export function buildImportOutcomeCards(reports: ChapterConsistencyReport[]) {
  const totals = reports.reduce(
    (acc, report) => {
      acc.chapters += 1
      acc.characters += report.new_characters.length
      acc.relationships += report.relationship_changes.length
      acc.openThreads += report.plot_threads_opened.length
      acc.continuity += report.continuity_flags.length
      return acc
    },
    { chapters: 0, characters: 0, relationships: 0, openThreads: 0, continuity: 0 },
  )

  return [
    { label: "Chapters processed", value: String(totals.chapters) },
    { label: "New characters found", value: String(totals.characters) },
    { label: "Relationship shifts", value: String(totals.relationships) },
    { label: "Plot threads opened", value: String(totals.openThreads) },
    { label: "Continuity flags surfaced", value: String(totals.continuity) },
  ]
}
