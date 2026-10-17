import { describe, expect, it } from "vitest"
import type { ChapterConsistencyReport, ContinuityFinding, StoryHealth } from "@/types/book"
import { filterFindings, findingChapter, partitionFindings, summarizeEditorialReview, summarizeReports } from "./analysisPage.helpers"

function finding(overrides: Partial<ContinuityFinding> = {}) {
  return { id: "one", severity: "high", title: "The gate oath", explanation: "Mira knows the answer", category: "knowledge", subject_label: "Mira", status: "pending", is_stale: false, decision: null, evidence: [], ...overrides } as ContinuityFinding
}
describe("analysis evidence helpers", () => {
  it("returns empty groups without manufacturing findings", () => {
    expect(partitionFindings([])).toEqual({ pending: [], reviewed: [], stale: [] })
  })
  it("counts a stale reviewed finding once and preserves its decision", () => {
    const record = finding({ is_stale: true, decision: "accepted" })
    const groups = partitionFindings([record])
    expect(groups.stale).toEqual([record]); expect(groups.reviewed).toEqual([])
  })
  it("groups resolved and decided findings separately from pending findings", () => {
    const records = [finding(), finding({ id: "resolved", status: "resolved" }), finding({ id: "intentional", decision: "intentional" })]
    const groups = partitionFindings(records)
    expect(groups.pending.map((item) => item.id)).toEqual(["one"])
    expect(groups.reviewed.map((item) => item.id)).toEqual(["resolved", "intentional"])
  })
  it("sorts severity without mutating the original list and leaves unknown severity last", () => {
    const records = [finding({ severity: "unknown" }), finding({ severity: "low" }), finding({ severity: "critical" })]
    expect(partitionFindings(records).pending.map((item) => item.severity)).toEqual(["critical", "low", "unknown"])
    expect(records[0].severity).toBe("unknown")
  })
  it.each(["  MIRA ", "oath", "KNOWLEDGE", "high", "answer"])("searches available finding context: %s", (query) => {
    expect(filterFindings([finding()], query)).toHaveLength(1)
  })
  it("handles blank and unmatched searches", () => {
    const records = [finding()]
    expect(filterFindings(records, " ")).toEqual(records)
    expect(filterFindings(records, "unmatched")).toEqual([])
  })
  it("does not fail when optional subject text is absent", () => {
    expect(filterFindings([finding({ subject_label: undefined })], "missing")).toEqual([])
  })
  it("links only positive integer chapters and skips invalid earlier evidence", () => {
    const evidence = [0, -1, Number.NaN, 1.2, 3].map((chapter_number) => ({ chapter_number })) as ContinuityFinding["evidence"]
    expect(findingChapter(finding({ evidence }))).toBe(3)
    expect(findingChapter(finding())).toBeNull()
  })
  it("summarizes only the supplied reports", () => {
    const report = { chapter_number: 1, chapter_title: "One", summary: "", new_characters: [{ id: "mira", name: "Mira", role: null, first_chapter: 1, arc_summary: null }], relationship_changes: ["Trust"], plot_threads_opened: ["Oath"], plot_threads_resolved: [], continuity_flags: ["Knowledge"] } as ChapterConsistencyReport
    expect(summarizeReports([report])).toEqual({ chapters: 1, changes: 3, flags: 1 })
    expect(summarizeReports([])).toEqual({ chapters: 0, changes: 0, flags: 0 })
  })
  it("writes a grounded review lead from the strongest current finding and states report coverage", () => {
    const report = { chapter_number: 3, chapter_title: "The gate", summary: "", new_characters: [], relationship_changes: [], plot_threads_opened: [], plot_threads_resolved: [], continuity_flags: ["The gate changes hands without a handoff."] } as ChapterConsistencyReport
    const health = { score: 71, status: "Needs review", summary: "", metrics: [{ label: "Continuity", score: 62, detail: "" }, { label: "Characters", score: 82, detail: "" }] } as StoryHealth
    const review = summarizeEditorialReview({ health, findings: [finding({ evidence: [{ chapter_number: 3 }] as ContinuityFinding["evidence"] })], reports: [report] })
    expect(review.leadSentence).toContain("The gate oath” in Chapter 3")
    expect(review.contextSentence).toContain("Continuity is the lowest measured area (62%)")
    expect(review.scopeSentence).toContain("1 recent chapter report. 1 has a continuity flag")
  })
  it("does not invent a chapter problem when findings are absent or stale", () => {
    const report: ChapterConsistencyReport = { chapter_number: 1, chapter_title: "Opening", summary: "", new_characters: [], relationship_changes: [], plot_threads_opened: [], plot_threads_resolved: [], continuity_flags: [] }
    const review = summarizeEditorialReview({ health: null, findings: [finding({ is_stale: true })], reports: [report] })
    expect(review.leadSentence).toContain("Some chapters still need an editorial pass")
    expect(review.scopeSentence).toContain("1 chapter has no editorial note yet")
    expect(review.scopeSentence).toContain("does not prove a chapter is problem-free")
    expect(summarizeEditorialReview({ health: null, findings: null, reports: null }).leadSentence).toContain("still loading")
  })
  it("distinguishes a completed empty review from a chapter that has not been reviewed", () => {
    const report: ChapterConsistencyReport = { chapter_number: 1, chapter_title: "Opening", summary: "", new_characters: [], relationship_changes: [], plot_threads_opened: [], plot_threads_resolved: [], continuity_flags: [], editorial_concerns: [] }
    const review = summarizeEditorialReview({ health: null, findings: [], reports: [report] })
    expect(review.leadSentence).toContain("could support with the text")
    expect(review.scopeSentence).not.toContain("no editorial note yet")
  })
  it("uses a grounded revision question without counting it as an editorial problem", () => {
    const report: ChapterConsistencyReport = { chapter_number: 2, chapter_title: "Departure", summary: "", new_characters: [], relationship_changes: [], plot_threads_opened: [], plot_threads_resolved: [], continuity_flags: [], editorial_concerns: [], revision_question: { question: "What does Mara hope to change by leaving?", evidence: "Mara left at dawn." } }
    const review = summarizeEditorialReview({ health: null, findings: [], reports: [report] })
    expect(review.leadSentence).toContain("What does Mara hope to change by leaving?")
    expect(review.scopeSentence).toContain("1 chapter has a passage-backed revision question")
    expect(review.scopeSentence).toContain("0 passage-backed editorial concerns")
  })
  it("does not present unavailable or empty chapter reports as a clean review", () => {
    expect(summarizeEditorialReview({ health: null, findings: [], reports: null }).leadSentence).toContain("No chapter-level conclusion")
    expect(summarizeEditorialReview({ health: null, findings: [], reports: [] }).leadSentence).toContain("no chapter reports")
    expect(summarizeEditorialReview({ health: null, findings: null, reports: null, failed: true }).leadSentence).toContain("could not load")
  })
  it("grounds the brief review in cast, relationship, and thread changes", () => {
    const report: ChapterConsistencyReport = { chapter_number: 2, chapter_title: "The Gate", summary: "", new_characters: [{ id: "mara", name: "Mara", role: null, first_chapter: 2, arc_summary: null }], relationship_changes: ["Mara and Jon: uneasy allies"], plot_threads_opened: ["The sealed gate"], plot_threads_resolved: [], continuity_flags: [], editorial_concerns: [] }
    const review = summarizeEditorialReview({ health: null, findings: [], reports: [report] })
    expect(review.storySentence).toContain("Mara enters the cast")
    expect(review.storySentence).toContain("1 relationship shift is recorded")
    expect(review.storySentence).toContain("“The sealed gate” is marked as a newly opened thread")
  })
})
