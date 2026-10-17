import { describe, expect, it, vi } from "vitest"

import type { BetaReaderReport } from "@/types/intelligence"
import {
  betaReaderScopeLabel,
  buildBetaReaderFindingNote,
  buildBetaReaderReportNote,
  matchesBetaReaderFilters,
  matchesBetaReaderTermFilters,
} from "./aiBetaReader"

const report: BetaReaderReport = {
  report_id: "report-1",
  scope: "chapter_range",
  request_hash: "request",
  source_fingerprint: "source",
  created_at: "2026-08-30T10:00:00Z",
  is_stale: false,
  checks: ["reader_feedback"],
  coverage: {
    requested_chapters: [2, 3, 4],
    analyzed_chapters: [2, 3, 4],
    missing_chapters: [],
    word_count: 2400,
    character_count: 2,
  },
  overall_impression: "The middle builds pressure well.",
  strengths: ["Clear stakes"],
  reader_questions: ["Who holds the key?"],
  prioritized_revisions: ["Clarify the time jump."],
  overused_terms: [],
  character_voices: [],
  findings: [],
  revision_candidates: [],
  warnings: [],
}

describe("AI beta reader helpers", () => {
  it("builds human-readable scope labels", () => {
    expect(betaReaderScopeLabel("passage")).toBe("Passage")
    expect(betaReaderScopeLabel("chapter", [7])).toBe("Chapter 7")
    expect(betaReaderScopeLabel("chapter_range", [2, 3, 4])).toBe("Chapters 2–4")
    expect(betaReaderScopeLabel("full_book")).toBe("Full manuscript")
  })

  it("builds report and finding notes with traceable evidence", () => {
    vi.spyOn(Date.prototype, "toLocaleString").mockReturnValue("30 Aug 2026")
    expect(buildBetaReaderReportNote(report)).toContain("# AI Beta Reader report")
    expect(buildBetaReaderReportNote(report)).toContain("Chapters 2–4")
    expect(buildBetaReaderReportNote(report)).toContain("Clarify the time jump")

    const note = buildBetaReaderFindingNote({
      id: "finding-1",
      category: "clarity",
      severity: "high",
      title: "Clarify the turn",
      description: "The motivation is unclear.",
      chapter_number: 3,
      evidence: [{ chapter_number: 3, excerpt: "She turned away." }],
      recommendation: "Add the missing reaction.",
      reader_question: null,
    })
    expect(note).toContain("**Chapter:** 3")
    expect(note).toContain("Chapter 3: > She turned away.")
    vi.restoreAllMocks()
  })

  it("filters by chapter, severity, and type", () => {
    const item = { chapter_number: 3, severity: "high", category: "clarity" }
    expect(matchesBetaReaderFilters(item, {
      chapter: "3",
      severity: "high",
      findingType: "clarity",
    })).toBe(true)
    expect(matchesBetaReaderFilters(item, {
      chapter: "2",
      severity: "all",
      findingType: "all",
    })).toBe(false)
  })

  it("filters repeated terms by their chapter distribution and term kind", () => {
    const term = {
      id: "term-1",
      term: "silver moon",
      kind: "phrase" as const,
      count: 4,
      rate_per_1000: 2,
      narration_count: 4,
      dialogue_count: 0,
      burst_detected: false,
      chapter_counts: { "2": 4 },
      evidence: [],
    }
    expect(matchesBetaReaderTermFilters(term, {
      chapter: "2",
      findingType: "phrase",
    })).toBe(true)
    expect(matchesBetaReaderTermFilters(term, {
      chapter: "3",
      findingType: "phrase",
    })).toBe(false)
    expect(matchesBetaReaderTermFilters(term, {
      chapter: "2",
      findingType: "word",
    })).toBe(false)
  })
})
