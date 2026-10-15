import { describe, expect, it } from "vitest"
import type { ChapterConsistencyReport, ContinuityFinding } from "@/types/book"
import { filterFindings, findingChapter, partitionFindings, summarizeReports } from "./analysisPage.helpers"

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
})
