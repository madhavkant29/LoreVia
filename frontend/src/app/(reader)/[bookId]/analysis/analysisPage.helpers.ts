import type { ChapterConsistencyReport, ContinuityFinding, StoryHealth } from "@/types/book"

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

export function summarizeEditorialReview({
  health,
  findings,
  reports,
  failed = false,
}: {
  health: StoryHealth | null
  findings: ContinuityFinding[] | null
  reports: ChapterConsistencyReport[] | null
  failed?: boolean
}) {
  const current = (findings ?? []).filter((finding) => !finding.is_stale && !finding.decision && finding.status !== "resolved")
  const ranked = [...current].sort((a, b) => (severityRank[a.severity] ?? 99) - (severityRank[b.severity] ?? 99))
  const lead = ranked[0]
  const reportFlags = (reports ?? []).flatMap((report) => report.continuity_flags.map((flag) => ({ chapter: report.chapter_number, flag })))
  const editorialNote = reports?.find((report) => (report.editorial_concerns?.length ?? 0) > 0)
  const revisionQuestionReport = reports?.find((report) => report.revision_question && (report.editorial_concerns?.length ?? 0) === 0)
  const editorialConcernCount = (reports ?? []).reduce((total, report) => total + (report.editorial_concerns?.length ?? 0), 0)
  const revisionQuestionCount = (reports ?? []).filter((report) => report.revision_question).length
  const reportedChapters = reports?.length ?? 0
  const flaggedChapters = reports?.filter((report) => report.continuity_flags.length > 0).length ?? 0
  const unreviewedChapters = reports?.filter((report) => report.editorial_concerns == null).length ?? 0
  const availableMetrics = (health?.metrics ?? []).filter((metric) => metric.available !== false)
  const weakestMetric = [...availableMetrics].sort((a, b) => a.score - b.score)[0]
  const newNames = [...new Set((reports ?? []).flatMap((report) => report.new_characters.map((character) => character.name)))].filter(Boolean)
  const openedThreads = [...new Set((reports ?? []).flatMap((report) => report.plot_threads_opened))].filter(Boolean)
  const relationshipShifts = (reports ?? []).reduce((total, report) => total + report.relationship_changes.length, 0)

  const leadSentence = failed && !findings && !reports
    ? "Review evidence could not load. Retry the report before drawing a conclusion."
    : lead
    ? `Start with “${lead.title}”${findingChapter(lead) ? ` in Chapter ${findingChapter(lead)}` : ""}. Read the cited passage before deciding what, if anything, to revise.`
    : reportFlags.length > 0
      ? `Chapter ${reportFlags[0].chapter} raises a continuity question: ${reportFlags[0].flag}`
      : editorialNote
        ? `Chapter ${editorialNote.chapter_number} deserves another pass: ${editorialNote.editorial_concerns?.[0]?.issue}`
      : revisionQuestionReport
        ? `Chapter ${revisionQuestionReport.chapter_number} leaves a useful revision question: ${revisionQuestionReport.revision_question?.question}`
      : reports && reports.length === 0
        ? "There are no chapter reports to review yet."
      : reports
        ? unreviewedChapters > 0
          ? "No supported issue stands out yet. Some chapters still need an editorial pass."
          : "This pass found no chapter-specific problem it could support with the text. That is not a clean bill of health."
        : findings
          ? "Chapter reports are still loading or unavailable. No chapter-level conclusion can be made yet."
        : "The manuscript review is still loading."

  const contextSentence = weakestMetric
    ? `${weakestMetric.label} is the lowest measured area (${weakestMetric.score}%). Use it to decide where to read closely, not as a grade on the writing.`
    : health?.available === false
      ? "A story-health measure is not available yet; this review should not be read as a quality score."
      : null

  const storySentence = newNames.length || openedThreads.length || relationshipShifts
    ? [
        newNames.length ? `${newNames.length > 2 ? `${newNames.slice(0, 2).join(", ")}, and ${newNames.length - 2} others` : newNames.join(" and ")} ${newNames.length === 1 ? "enters" : "enter"} the cast` : null,
        relationshipShifts ? `${relationshipShifts} relationship ${relationshipShifts === 1 ? "shift" : "shifts"} ${relationshipShifts === 1 ? "is" : "are"} recorded` : null,
        openedThreads.length ? `“${openedThreads[0]}” ${openedThreads.length === 1 ? "is marked as a newly opened thread" : `and ${openedThreads.length - 1} other plot threads open`}` : null,
      ].filter(Boolean).join("; ") + "."
    : null

  const scopeSentence = reports
    ? reportedChapters === 0
      ? "Chapter coverage will appear here after the manuscript has been processed."
      : `This view covers ${reportedChapters} recent chapter report${reportedChapters === 1 ? "" : "s"}. ${flaggedChapters} ${flaggedChapters === 1 ? "has" : "have"} a continuity flag; ${editorialConcernCount} passage-backed editorial concern${editorialConcernCount === 1 ? "" : "s"} ${editorialConcernCount === 1 ? "is" : "are"} recorded.${revisionQuestionCount ? ` ${revisionQuestionCount} chapter${revisionQuestionCount === 1 ? " has" : "s have"} a passage-backed revision question.` : ""} ${current.length} current finding${current.length === 1 ? "" : "s"} ${current.length === 1 ? "awaits" : "await"} your decision.${unreviewedChapters ? ` ${unreviewedChapters} chapter${unreviewedChapters === 1 ? " has" : "s have"} no editorial note yet.` : ""} A quiet report does not prove a chapter is problem-free.`
    : findings
      ? `${current.length} current finding${current.length === 1 ? "" : "s"} ${current.length === 1 ? "awaits" : "await"} review. Chapter coverage is not available yet.`
      : "Chapter coverage and findings are still loading."

  return { leadSentence, contextSentence, storySentence, scopeSentence }
}
