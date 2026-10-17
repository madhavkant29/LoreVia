import React from "react"
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { ActivationExperience } from "./ActivationExperience"
import type { RevisionIntelligence } from "@/types/book"

const decideMock = vi.fn()
const getContinuityFindingsMock = vi.fn()
const createContinuityScanMock = vi.fn()
const updateWriterWorkspaceMock = vi.fn()
const getFirstImpressionMock = vi.fn()
const retryFirstImpressionMock = vi.fn()
const captureMock = vi.fn()

vi.mock("@/lib/api/books", () => ({
  booksApi: {
    decideRevisionFinding: (...args: unknown[]) => decideMock(...args),
    getContinuityFindings: (...args: unknown[]) => getContinuityFindingsMock(...args),
    createContinuityScan: (...args: unknown[]) => createContinuityScanMock(...args),
    updateWriterWorkspace: (...args: unknown[]) => updateWriterWorkspaceMock(...args),
  },
}))

vi.mock("@/lib/api/intelligence", () => ({
  intelligenceApi: {
    getFirstImpression: (...args: unknown[]) => getFirstImpressionMock(...args),
    retryFirstImpression: (...args: unknown[]) => retryFirstImpressionMock(...args),
  },
}))

vi.mock("@/lib/analytics/posthog", () => ({ capture: (...args: unknown[]) => captureMock(...args) }))

function revision(overrides: Partial<RevisionIntelligence> = {}): RevisionIntelligence {
  return {
    tagline: "Know what changed",
    summary: { hero_message: "Review this", active_item_count: 1, high_severity_count: 1, task_ready_count: 1 },
    change_impacts: [],
    genre_checks: [],
    revision_plan: [],
    knowledge_matrix: [],
    knowledge_timeline: [],
    scene_advice: [],
    confusion_map: [],
    voice_alerts: [],
    priority_findings: [{
      id: "rev-1",
      category: "impact",
      title: "The key disappears",
      description: "The key is present before this chapter but missing afterward.",
      severity: "high",
      chapter_ref: 4,
      source_label: "Chapter Four",
      recommendation: "Restore the handoff or revise the later assumption.",
      status: "pending",
      why_flagged: "The object state changes without a recorded handoff.",
      evidence_strength: "strong",
      evidence: [{ chapter_ref: 4, source_label: "Chapter Four", excerpt: "The silver key was gone.", source_content_version: 2 }],
      is_stale: false,
    }],
    activation: { eligible: true, completed: false },
    analysis_complete: true,
    analysis_limitations: [],
    ...overrides,
  }
}

function firstImpression(overrides: Record<string, unknown> = {}) {
  return {
    status: "complete",
    task_id: "first-read-1",
    progress: null,
    error: null,
    can_retry: false,
    report: {
      report_id: "report-1",
      scope: "full_book",
      request_hash: "request-1",
      source_fingerprint: "source-1",
      created_at: "2026-08-31T00:05:00Z",
      is_stale: false,
      checks: ["reader_feedback"],
      coverage: {
        requested_chapters: [1, 2, 3],
        analyzed_chapters: [1, 2, 3],
        missing_chapters: [],
        word_count: 3200,
        character_count: 4,
      },
      overall_impression: "The opening establishes a tense sibling relationship and sustains it through the turn in chapter three.",
      reader_vibe: "Intimate speculative mystery with a restrained, uneasy voice.",
      story_understanding: "Mara is trying to protect her brother while learning that his memories may be manufactured.",
      strengths: ["Mara and Theo's chapter-two argument carries clear emotional history."],
      reader_questions: [],
      prioritized_revisions: ["Clarify what Mara believes before the chapter-three reveal."],
      overused_terms: [],
      character_voices: [],
      findings: [],
      revision_candidates: [],
      warnings: [],
    },
    ...overrides,
  }
}

describe("ActivationExperience", () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    container = document.createElement("div")
    document.body.appendChild(container)
    root = createRoot(container)
    decideMock.mockReset()
    getContinuityFindingsMock.mockReset()
    getContinuityFindingsMock.mockResolvedValue([])
    createContinuityScanMock.mockReset()
    createContinuityScanMock.mockResolvedValue({
      id: "scan-1",
      book_id: "book-1",
      scope: "full_book",
      status: "ready",
      continuity_status: "clean",
      detector_version: "v1",
      chapter_versions: {},
      coverage: { chapters_analyzed: 24 },
      metrics: {},
      word_count: 1000,
      finding_count: 0,
      stale_finding_count: 0,
      findings: [],
    })
    updateWriterWorkspaceMock.mockReset()
    updateWriterWorkspaceMock.mockResolvedValue({})
    getFirstImpressionMock.mockReset()
    getFirstImpressionMock.mockResolvedValue(firstImpression())
    retryFirstImpressionMock.mockReset()
    captureMock.mockReset()
  })

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
  })

  it("shows evidence and completes activation when a finding is accepted", async () => {
    const completed = revision({ activation: { eligible: false, completed: true, completion_action: "added_to_revision_plan" } })
    decideMock.mockResolvedValue(completed)
    const onChange = vi.fn()

    await act(async () => {
      root.render(<ActivationExperience bookId="book-1" bookTitle="Atlas" chapterCount={24} isDark={false} revision={revision()} onRevisionChange={onChange} onNavigate={vi.fn()} />)
    })
    const findingButton = Array.from(container.querySelectorAll("button")).find((button) => button.textContent?.includes("The key disappears"))
    await act(async () => findingButton?.dispatchEvent(new MouseEvent("click", { bubbles: true })))
    expect(container.textContent).toContain("The silver key was gone")

    const acceptButton = Array.from(container.querySelectorAll("button")).find((button) => button.textContent?.includes("Add to revision plan"))
    await act(async () => acceptButton?.dispatchEvent(new MouseEvent("click", { bubbles: true })))

    expect(decideMock).toHaveBeenCalledWith("book-1", "rev-1", { decision: "accepted", action: "added_to_revision_plan" })
    expect(onChange).toHaveBeenCalledWith(completed)
    expect(captureMock).toHaveBeenCalledWith("activation_completed", expect.objectContaining({ book_id: "book-1" }))
    expect(captureMock.mock.calls.filter(([event]) => event === "activation_experience_viewed")).toHaveLength(1)
  })

  it("renders a transparent incomplete-analysis state", () => {
    act(() => {
      root.render(<ActivationExperience bookId="book-1" bookTitle="Atlas" chapterCount={24} isDark revision={revision({ analysis_complete: false, priority_findings: [], analysis_limitations: ["Story intelligence is still processing."] })} onRevisionChange={vi.fn()} onNavigate={vi.fn()} />)
    })

    expect(container.querySelector('[data-testid="activation-incomplete"]')).not.toBeNull()
    expect(container.textContent).toContain("will not manufacture continuity findings")
    expect(container.textContent).toContain("Story intelligence is still processing")
  })

  it("orders grounded validation and understanding before critique and improvement", async () => {
    getFirstImpressionMock.mockResolvedValue(firstImpression({
      report: {
        ...firstImpression().report,
        coverage: {
          requested_chapters: [1, 2, 3],
          analyzed_chapters: [1, 2],
          missing_chapters: [3],
          word_count: 2200,
          character_count: 4,
        },
      },
    }))

    await act(async () => {
      root.render(<ActivationExperience enableFirstImpression bookId="book-1" bookCreatedAt="2026-08-31T00:00:00Z" bookTitle="Atlas" chapterCount={3} isDark={false} revision={revision()} onRevisionChange={vi.fn()} onNavigate={vi.fn()} />)
    })

    const validate = container.querySelector('[data-testid="whats-working-section"]') as HTMLElement
    const understand = container.querySelector('[data-testid="story-understanding-section"]') as HTMLElement
    const critique = container.querySelector('[data-testid="existing-analysis"]') as HTMLElement
    const improve = container.querySelector('[data-testid="improve-section"]') as HTMLElement
    expect(validate).not.toBeNull()
    expect(understand).not.toBeNull()
    expect(critique).not.toBeNull()
    expect(improve).not.toBeNull()
    expect(validate.compareDocumentPosition(understand) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(understand.compareDocumentPosition(critique) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(critique.compareDocumentPosition(improve) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(container.textContent).toContain("Mara and Theo's chapter-two argument")
    expect(container.textContent).toContain("Partial coverage: 2 of 3 requested chapters")
    expect(container.textContent).toContain("Missing chapters: 3")
  })

  it("uses transparent copy when no grounded strengths are available and marks stale snapshots", async () => {
    getFirstImpressionMock.mockResolvedValue(firstImpression({
      report: { ...firstImpression().report, strengths: [], is_stale: true },
    }))

    await act(async () => {
      root.render(<ActivationExperience enableFirstImpression bookId="book-1" bookTitle="Atlas" chapterCount={3} isDark={false} revision={revision()} onRevisionChange={vi.fn()} onNavigate={vi.fn()} />)
    })

    expect(container.textContent).toContain("rather than inventing praise")
    expect(container.textContent).toContain("Uploaded-draft snapshot")
    expect(container.textContent).toContain("Run a new read in AI Beta Reader")
  })

  it("shows non-blocking progress with screenplay language", async () => {
    getFirstImpressionMock.mockResolvedValue({
      status: "running",
      task_id: "first-read-1",
      progress: { stage: "reading", completed: 2, total: 5, message: "Reading for what makes this manuscript itself." },
      report: null,
      error: null,
      can_retry: false,
    })

    await act(async () => {
      root.render(<ActivationExperience enableFirstImpression bookId="book-1" bookTitle="Atlas" bookWorkType="screenplay" chapterCount={5} isDark={false} revision={revision()} onRevisionChange={vi.fn()} onNavigate={vi.fn()} />)
    })

    expect(container.textContent).toContain("all 5 scenes together")
    expect(container.textContent).toContain("Continue to existing analysis")
    expect(container.querySelector('[data-testid="existing-analysis"]')).toBeNull()
  })

  it("falls back to existing analysis when no automatic first read exists", async () => {
    getFirstImpressionMock.mockResolvedValue({
      status: "not_started",
      task_id: null,
      progress: null,
      report: null,
      error: null,
      can_retry: false,
    })

    await act(async () => {
      root.render(<ActivationExperience enableFirstImpression bookId="book-1" bookTitle="Atlas" chapterCount={3} isDark={false} revision={revision()} onRevisionChange={vi.fn()} onNavigate={vi.fn()} />)
    })

    expect(container.querySelector('[data-testid="first-read-not-started"]')).not.toBeNull()
    expect(container.querySelector('[data-testid="first-read-progress"]')).toBeNull()
    expect(container.querySelector('[data-testid="existing-analysis"]')).not.toBeNull()
    expect(container.textContent).toContain("does not have an automatic first read saved yet")
  })

  it("persists activation without forcing a finding decision", async () => {
    const onChange = vi.fn()
    await act(async () => {
      root.render(<ActivationExperience enableFirstImpression bookId="book-1" bookTitle="Atlas" chapterCount={3} isDark={false} revision={revision()} onRevisionChange={onChange} onNavigate={vi.fn()} />)
    })
    const continueButton = Array.from(container.querySelectorAll("button")).find((button) => button.textContent?.includes("Continue to workspace"))
    await act(async () => continueButton?.dispatchEvent(new MouseEvent("click", { bubbles: true })))

    expect(updateWriterWorkspaceMock).toHaveBeenCalledWith("book-1", {
      activation: expect.objectContaining({ completion_action: "reviewed_first_read", completed_finding_id: null }),
    })
    expect(decideMock).not.toHaveBeenCalled()
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ activation: expect.objectContaining({ completed: true }) }))
  })

  it("offers an explicit retry and a skip path after failure", async () => {
    getFirstImpressionMock.mockResolvedValue({ status: "failed", task_id: "first-read-1", progress: null, report: null, error: "generation_failed", can_retry: true })
    retryFirstImpressionMock.mockResolvedValue({ status: "queued", task_id: "first-read-2", progress: null, report: null, error: null, can_retry: false })

    await act(async () => {
      root.render(<ActivationExperience enableFirstImpression bookId="book-1" bookTitle="Atlas" chapterCount={3} isDark={false} revision={revision()} onRevisionChange={vi.fn()} onNavigate={vi.fn()} />)
    })
    expect(container.textContent).toContain("Retry first read")
    expect(container.textContent).toContain("Continue to existing analysis")
    const retry = Array.from(container.querySelectorAll("button")).find((button) => button.textContent?.includes("Retry first read"))
    await act(async () => retry?.dispatchEvent(new MouseEvent("click", { bubbles: true })))
    expect(retryFirstImpressionMock).toHaveBeenCalledWith("book-1")
  })
})
