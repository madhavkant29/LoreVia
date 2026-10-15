import type { ChapterConsistencyReport, ContinuityFinding } from "@/types/book"

export type FindingGroup = "pending" | "reviewed" | "stale"
const severityRank: Record<string, number> = { critical: 0, high: 1, warning: 2, medium: 3, low: 4, info: 5 }

export function partitionFindings(findings: ContinuityFinding[]) {
  const groups: Record<FindingGroup, ContinuityFinding[]> = { pending: [], reviewed: [], stale: [] }
  for (const finding of findings) {
    const group = finding.is_stale ? "stale" : finding.decision || finding.status === "resolved" ? "reviewed" : "pending"
    groups[group].push(finding)
  }
  for (const entries of Object.values(groups)) entries.sort((a, b) => (severityRank[a.severity] ?? 99) - (severityRank[b.severity] ?? 99))
  return groups
}

export function filterFindings(findings: ContinuityFinding[], query: string) {
  const search = query.trim().toLowerCase()
  if (!search) return findings
  return findings.filter((finding) => [finding.title, finding.explanation, finding.subject_label, finding.category, finding.severity].some((value) => value?.toLowerCase().includes(search)))
}

export function findingChapter(finding: ContinuityFinding) {
  return finding.evidence.find((item) => Number.isInteger(item.chapter_number) && item.chapter_number > 0)?.chapter_number ?? null
}

export function summarizeReports(reports: ChapterConsistencyReport[]) {
  return reports.reduce((summary, report) => ({
    chapters: summary.chapters + 1,
    changes: summary.changes + report.new_characters.length + report.relationship_changes.length + report.plot_threads_opened.length + report.plot_threads_resolved.length,
    flags: summary.flags + report.continuity_flags.length,
  }), { chapters: 0, changes: 0, flags: 0 })
}
