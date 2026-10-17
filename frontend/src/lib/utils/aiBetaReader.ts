import type {
  BetaReaderFinding,
  BetaReaderOverusedTerm,
  BetaReaderReport,
  BetaReaderRevisionCandidate,
  BetaReaderScope,
} from "@/types/intelligence"

export function betaReaderScopeLabel(scope: BetaReaderScope, chapters: number[] = []) {
  if (scope === "passage") return "Passage"
  if (scope === "full_book") return "Full manuscript"
  if (scope === "chapter") return chapters[0] ? `Chapter ${chapters[0]}` : "Chapter"
  if (chapters.length > 1) return `Chapters ${chapters[0]}–${chapters.at(-1)}`
  return "Chapter range"
}

function evidenceMarkdown(evidence: Array<{ chapter_number: number | null; excerpt: string }>) {
  return evidence.map((item) => (
    `- ${item.chapter_number ? `Chapter ${item.chapter_number}: ` : ""}> ${item.excerpt}`
  )).join("\n")
}

export function buildBetaReaderFindingNote(
  item: BetaReaderFinding | BetaReaderRevisionCandidate,
) {
  return [
    `# ${item.title}`,
    "",
    `**Severity:** ${item.severity}`,
    `**Type:** ${item.category}`,
    item.chapter_number ? `**Chapter:** ${item.chapter_number}` : null,
    "",
    item.description,
    "",
    "## Revision direction",
    "",
    item.recommendation,
    item.evidence.length ? "\n## Evidence\n" : null,
    item.evidence.length ? evidenceMarkdown(item.evidence) : null,
  ].filter((value): value is string => value !== null).join("\n")
}

export function buildBetaReaderReportNote(report: BetaReaderReport) {
  const sections = [
    "# AI Beta Reader report",
    "",
    `**Scope:** ${betaReaderScopeLabel(report.scope, report.coverage.requested_chapters)}`,
    `**Created:** ${new Date(report.created_at).toLocaleString()}`,
    `**Coverage:** ${report.coverage.word_count.toLocaleString()} words`,
    "",
    "## Overall impression",
    "",
    report.overall_impression,
  ]
  if (report.strengths.length) {
    sections.push("", "## Strengths", "", ...report.strengths.map((item) => `- ${item}`))
  }
  if (report.reader_questions.length) {
    sections.push("", "## Reader questions", "", ...report.reader_questions.map((item) => `- ${item}`))
  }
  if (report.prioritized_revisions.length) {
    sections.push("", "## Revision priorities", "", ...report.prioritized_revisions.map((item) => `- ${item}`))
  }
  return sections.join("\n")
}

export function matchesBetaReaderFilters(
  item: { chapter_number?: number | null; severity?: string; category?: string },
  filters: { chapter: string; severity: string; findingType: string },
) {
  if (filters.chapter !== "all" && item.chapter_number !== Number(filters.chapter)) return false
  if (filters.severity !== "all" && item.severity !== filters.severity) return false
  if (filters.findingType !== "all" && item.category !== filters.findingType) return false
  return true
}

export function matchesBetaReaderTermFilters(
  item: BetaReaderOverusedTerm,
  filters: { chapter: string; findingType: string },
) {
  if (filters.chapter !== "all" && !item.chapter_counts[filters.chapter]) return false
  if (filters.findingType !== "all" && item.kind !== filters.findingType) return false
  return true
}
