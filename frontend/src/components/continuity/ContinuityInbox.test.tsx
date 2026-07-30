import React from "react"
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { ContinuityInbox } from "./ContinuityInbox"
import type { ContinuityFinding, RevisionIntelligence } from "@/types/book"

const getFindingsMock = vi.fn()
const createScanMock = vi.fn()
const decideMock = vi.fn()
const recheckMock = vi.fn()
const captureMock = vi.fn()

vi.mock("@/lib/api/books", () => ({
  booksApi: {
    getContinuityFindings: (...args: unknown[]) => getFindingsMock(...args),
    createContinuityScan: (...args: unknown[]) => createScanMock(...args),
    decideContinuityFinding: (...args: unknown[]) => decideMock(...args),
    recheckContinuityFinding: (...args: unknown[]) => recheckMock(...args),
  },
}))

vi.mock("@/lib/analytics/posthog", () => ({
  capture: (...args: unknown[]) => captureMock(...args),
}))

const finding: ContinuityFinding = {
  id: "finding-1",
  scan_id: "scan-1",
  book_id: "book-1",
  category: "character_state",
  severity: "high",
  confidence: 0.94,
  status: "pending",
  title: "Ilya's eyes change",
  explanation: "The passages disagree.",
  recommendation: "Confirm the intended canon.",
  subject_type: "character",
  subject_id: "char-1",
  subject_label: "Ilya",
  detector_version: "v1",
  content_versions: { "1": 1, "3": 2 },
  coverage: {},
  is_stale: false,
  evidence: [
    {
      observation_id: "obs-1",
      role: "earlier_state",
      evidence_order: 1,
      subject_type: "character",
      subject_id: "char-1",
      subject_label: "Ilya",
      predicate: "character.eyes",
      display_value: "blue",
      chapter_number: 1,
      content_version: 1,
      excerpt: "Ilya's eyes were blue.",
      confidence: 0.95,
    },
    {
      observation_id: "obs-2",
      role: "conflicting_state",
      evidence_order: 2,
      subject_type: "character",
      subject_id: "char-1",
      subject_label: "Ilya",
      predicate: "character.eyes",
      display_value: "green",
      chapter_number: 3,
      content_version: 2,
      excerpt: "Ilya's eyes were green.",
      confidence: 0.94,
    },
  ],
}

function revision(overrides: Partial<RevisionIntelligence> = {}): RevisionIntelligence {
  return {
    tagline: "Continuity",
    summary: { hero_message: "Ready", active_item_count: 0, high_severity_count: 0, task_ready_count: 0 },
    change_impacts: [],
    genre_checks: [],
    revision_plan: [],
    knowledge_matrix: [],
    knowledge_timeline: [],
    scene_advice: [],
    confusion_map: [],
    voice_alerts: [],
    analysis_complete: true,
    continuity_status: "issues_found",
    ...overrides,
  }
}

describe("ContinuityInbox", () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    container = document.createElement("div")
    document.body.appendChild(container)
    root = createRoot(container)
    getFindingsMock.mockReset()
    createScanMock.mockReset()
    decideMock.mockReset()
    recheckMock.mockReset()
    captureMock.mockReset()
  })

  afterEach(() => {
    act(() => root.unmount())
    container.remove()
  })

  it("shows side-by-side versioned evidence and marks intentional changes", async () => {
    getFindingsMock.mockResolvedValue([finding])
    decideMock.mockResolvedValue({ ...finding, status: "intentional", decision: "intentional" })
    const navigate = vi.fn()
    const bookCreatedAt = "2026-06-19T08:59:55.000Z"

    await act(async () => {
      root.render(
        <ContinuityInbox
          bookId="book-1"
          bookCreatedAt={bookCreatedAt}
          chapterCount={3}
          isDark={false}
          revision={revision({
            continuity_scan_id: "scan-1",
            continuity_completed_at: "2026-06-19T09:00:00.000Z",
            continuity_duration_ms: 900,
          })}
          onNavigate={navigate}
        />,
      )
    })

    expect(container.textContent).toContain("Ilya's eyes were blue")
    expect(container.textContent).toContain("Ilya's eyes were green")
    expect(container.textContent).toContain("Chapter 1 · v1")
    expect(container.textContent).toContain("Chapter 3 · v2")
    expect(getFindingsMock).toHaveBeenCalledWith("book-1", { includeStale: true })
    expect(captureMock).toHaveBeenCalledWith(
      "first_usable_result_latency",
      expect.objectContaining({
        $insert_id: "first-usable-result:book-1",
        book_id: "book-1",
        result_type: "continuity_findings",
        latency_ms: 5_000,
        scan_id: "scan-1",
        scan_duration_ms: 900,
      }),
    )

    const evidenceButton = Array.from(container.querySelectorAll("button"))
      .find((item) => item.textContent?.includes("Chapter 1"))
    await act(async () => {
      evidenceButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    })
    expect(navigate).toHaveBeenCalledWith(
      "/book-1/manuscript?chapter=1&continuity_finding=finding-1",
    )

    const button = Array.from(container.querySelectorAll("button"))
      .find((item) => item.textContent === "Mark intentional")
    await act(async () => button?.dispatchEvent(new MouseEvent("click", { bubbles: true })))

    expect(decideMock).toHaveBeenCalledWith("book-1", "finding-1", {
      decision: "intentional",
      action: null,
      reason: "intentional",
    })
    expect(captureMock).toHaveBeenCalledWith(
      "continuity_finding_intentional",
      expect.objectContaining({ finding_id: "finding-1" }),
    )
  })

  it("creates a revision task only when the author asks for one", async () => {
    getFindingsMock.mockResolvedValue([finding])
    decideMock.mockResolvedValue({
      ...finding,
      status: "accepted",
      decision: "accepted",
      action: "added_to_revision_plan",
    })

    await act(async () => {
      root.render(
        <ContinuityInbox
          bookId="book-1"
          chapterCount={3}
          isDark={false}
          revision={revision()}
          onNavigate={vi.fn()}
        />,
      )
    })

    const button = Array.from(container.querySelectorAll("button"))
      .find((item) => item.textContent === "Create task")
    await act(async () => button?.dispatchEvent(new MouseEvent("click", { bubbles: true })))

    expect(decideMock).toHaveBeenCalledWith("book-1", "finding-1", {
      decision: "accepted",
      action: "added_to_revision_plan",
      reason: null,
    })
    expect(captureMock).toHaveBeenCalledWith(
      "continuity_revision_task_created",
      expect.objectContaining({ finding_id: "finding-1" }),
    )
  })

  it("treats a verified clean scan as a successful activation result", async () => {
    getFindingsMock.mockResolvedValue([])
    const bookCreatedAt = "2026-06-19T08:59:55.000Z"

    await act(async () => {
      root.render(
        <ContinuityInbox
          bookId="book-1"
          bookCreatedAt={bookCreatedAt}
          chapterCount={8}
          isDark
          revision={revision({
            continuity_status: "clean",
            continuity_scan_id: "scan-clean",
            continuity_completed_at: "2026-06-19T09:00:00.000Z",
            continuity_duration_ms: 700,
            coverage: { chapters_analyzed: 8 },
          })}
          onNavigate={vi.fn()}
        />,
      )
    })

    expect(container.querySelector('[data-testid="continuity-inbox-clean"]')).not.toBeNull()
    expect(container.textContent).toContain("successful result")
    expect(createScanMock).not.toHaveBeenCalled()
    expect(captureMock).toHaveBeenCalledWith(
      "activation_completed",
      expect.objectContaining({ action: "verified_clean_scan" }),
    )
    expect(captureMock).toHaveBeenCalledWith(
      "first_usable_result_latency",
      expect.objectContaining({
        result_type: "verified_clean",
        latency_ms: 5_000,
        scan_id: "scan-clean",
        scan_duration_ms: 700,
      }),
    )
  })

  it("reports a persisted failed scan instead of treating it as a usable result", async () => {
    getFindingsMock.mockResolvedValue([])
    createScanMock.mockResolvedValue({
      id: "scan-failed",
      book_id: "book-1",
      scope: "full_book",
      status: "failed",
      continuity_status: "insufficient_evidence",
      detector_version: "v1",
      chapter_versions: {},
      coverage: {},
      metrics: {},
      word_count: 0,
      error_detail: "detector unavailable",
      finding_count: 0,
      stale_finding_count: 0,
      findings: [],
    })

    await act(async () => {
      root.render(
        <ContinuityInbox
          bookId="book-1"
          chapterCount={3}
          isDark={false}
          revision={revision({ continuity_status: "insufficient_evidence" })}
          onNavigate={vi.fn()}
        />,
      )
    })

    expect(container.textContent).toContain("detector unavailable")
    expect(captureMock).toHaveBeenCalledWith(
      "continuity_scan_failed",
      expect.objectContaining({ scan_id: "scan-failed" }),
    )
    expect(captureMock).not.toHaveBeenCalledWith(
      "continuity_scan_completed",
      expect.anything(),
    )
  })
})
