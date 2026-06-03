import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"

import { RevisionIntelligencePanel } from "./RevisionIntelligencePanel"
import type { RevisionActionItem, RevisionIntelligence } from "@/types/book"

vi.mock("@/lib/api/books", () => ({
  booksApi: {
    createChapterSnapshot: vi.fn(),
    getChapterVersions: vi.fn(),
    updateWriterWorkspace: vi.fn(),
  },
}))

let container: HTMLDivElement | null = null
let root: Root | null = null

describe("RevisionIntelligencePanel", () => {
  beforeAll(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  })

  afterEach(() => {
    act(() => root?.unmount())
    container?.remove()
    container = null
    root = null
  })

  it("keeps timeline matrices collapsed until requested", () => {
    const view = renderPanel()

    expect(view.textContent).toContain("Show timeline matrices (1)")
    expect(view.textContent).not.toContain("Hidden fact timeline")

    const button = Array.from(view.querySelectorAll("button")).find((candidate) => candidate.textContent === "Show timeline matrices (1)")
    act(() => {
      button?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    })

    expect(view.textContent).toContain("Hidden fact timeline")
    expect(view.textContent).toContain("Ch 1")
  })

  it("uses compact summaries in the overview preview", () => {
    const view = renderPanel("preview")

    expect(view.textContent).toContain("Top continuity issue")
    expect(view.textContent).not.toContain("Mark as fixed")
    expect(view.textContent).not.toContain("Convert to task")
  })
})

function renderPanel(variant: "full" | "preview" | "story-map" = "full") {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => {
    root?.render(
      <RevisionIntelligencePanel
        bookId="book-1"
        revision={buildRevision()}
        writerWorkspace={null}
        isDark={false}
        onRevisionChange={vi.fn()}
        onWriterWorkspaceChange={vi.fn()}
        variant={variant}
      />
    )
  })
  return container
}

function buildRevision(): RevisionIntelligence {
  const topItem: RevisionActionItem = {
    category: "continuity",
    id: "issue-1",
    title: "Top continuity issue",
    description: "The handoff needs a clearer on-page setup.",
    severity: "high",
    chapter_ref: 4,
    recommendation: "Add a direct knowledge transfer before the later reveal.",
    status: "pending",
  }

  return {
    tagline: "Revision intelligence",
    summary: {
      active_item_count: 1,
      hero_message: "One revision issue needs attention.",
      high_severity_count: 1,
      task_ready_count: 1,
    },
    change_impacts: [topItem],
    confusion_map: [],
    genre_checks: [],
    knowledge_matrix: [
      {
        fact: "Hidden fact",
        entries: [
          { character_name: "Mira", chapter_learned: 2, source: "Tracked through manuscript evidence" },
          { character_name: "Kael", chapter_learned: null, source: "No earlier evidence surfaced yet" },
        ],
        warning: "LoreVia has no clear evidence yet that Kael learned this.",
      },
    ],
    knowledge_timeline: [
      {
        fact: "Hidden fact",
        rows: [
          {
            character_name: "Mira",
            chapter_learned: 2,
            source: "Tracked through manuscript evidence",
            cells: [
              { chapter_number: 1, state: "unknown" },
              { chapter_number: 2, state: "learned" },
            ],
          },
        ],
        warning: null,
      },
    ],
    revision_plan: [{ title: "Pass 1", summary: "Fix continuity.", items: [topItem] }],
    scene_advice: [],
    voice_alerts: [],
  }
}
