import React from "react"
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { ActivationExperience } from "./ActivationExperience"
import type { RevisionIntelligence } from "@/types/book"

const decideMock = vi.fn()
const captureMock = vi.fn()

vi.mock("@/lib/api/books", () => ({
  booksApi: { decideRevisionFinding: (...args: unknown[]) => decideMock(...args) },
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

describe("ActivationExperience", () => {
  let container: HTMLDivElement
  let root: Root

  beforeEach(() => {
    container = document.createElement("div")
    document.body.appendChild(container)
    root = createRoot(container)
    decideMock.mockReset()
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
})
