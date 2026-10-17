import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"

import { RevisionIntelligencePanel } from "./RevisionIntelligencePanel"
import { booksApi } from "@/lib/api/books"
import type { RevisionActionItem, RevisionIntelligence, WriterWorkspace } from "@/types/book"

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

  it("expands genre-specific findings when a genre card is clicked", () => {
    const view = renderPanel()

    const button = Array.from(view.querySelectorAll("button")).find((candidate) => candidate.textContent?.includes("Fantasy"))
    act(() => {
      button?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    })

    expect(view.textContent).toContain("Lore pressure around the archive terms.")
  })

  it("opens timeline matrices from the story-map timeline summary and expands hidden threads", () => {
    const view = renderPanel("story-map", buildRevisionWithTimelineThreads())

    const hiddenButton = Array.from(view.querySelectorAll("button")).find((candidate) => candidate.textContent?.includes("1 more timeline thread hidden"))
    act(() => {
      hiddenButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    })

    expect(view.textContent).toContain("Show fewer timeline threads.")
    expect(view.textContent).toContain("Family obligation")

    const timelineButton = Array.from(view.querySelectorAll("button")).find((candidate) => candidate.textContent?.includes("Gregor's transformation into a vermin"))
    act(() => {
      timelineButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    })

    expect(view.textContent).toContain("Gregor's transformation into a vermin timeline")
    expect(view.textContent).toContain("Grete")
    expect(view.textContent).toContain("Ch 3")
  })
  it("keeps checklist creation disabled until existing planning data is available", () => {
    const view = renderPanel("preview")
    expect(Array.from(view.querySelectorAll("button")).find((button) => button.textContent === "Create checklist")?.disabled).toBe(true)
    expect(view.textContent).toContain("once project planning data loads")
  })

  it("prevents repeat checklist submission and reports a failed save", async () => {
    let rejectSave: (reason: Error) => void = () => {}
    vi.mocked(booksApi.updateWriterWorkspace).mockImplementation(() => new Promise((_, reject) => { rejectSave = reject }))
    const workspace = { goal_calendar: [], revision_board: { items: [], last_generated_at: null } } as unknown as WriterWorkspace
    const view = renderPanel("preview", buildRevision(), workspace)
    const button = Array.from(view.querySelectorAll("button")).find((candidate) => candidate.textContent === "Create checklist")!
    await act(async () => { button.click() })
    expect(button.disabled).toBe(true)
    expect(button.textContent).toBe("Creating checklist...")
    await act(async () => { rejectSave(new Error("offline")); await Promise.resolve() })
    expect(button.disabled).toBe(false)
    expect(view.textContent).toContain("could not create the revision checklist")
  })

  it("reports the number of persisted tasks after checklist creation", async () => {
    const onTaskCreated = vi.fn()
    const workspace = { goal_calendar: [], revision_board: { items: [], last_generated_at: null } } as unknown as WriterWorkspace
    vi.mocked(booksApi.updateWriterWorkspace).mockResolvedValue(workspace)
    const view = renderPanel("preview", buildRevision(), workspace, onTaskCreated)
    const button = Array.from(view.querySelectorAll("button")).find((candidate) => candidate.textContent === "Create checklist")!

    await act(async () => {
      button.click()
      await Promise.resolve()
    })

    expect(onTaskCreated).toHaveBeenCalledWith(1)
    expect(view.textContent).toContain("Created 1 revision checklist item.")
    expect(view.querySelector('a[href="/book-1#author-project-tasks"]')?.textContent).toBe("View tasks")
  })

  it("saves a Story Map task and reports the save to the overview", async () => {
    const onTaskCreated = vi.fn()
    const workspace = { goal_calendar: [], revision_board: { items: [], last_generated_at: null } } as unknown as WriterWorkspace
    vi.mocked(booksApi.updateWriterWorkspace).mockResolvedValue(workspace)
    const view = renderPanel("story-map", buildRevision(), workspace, onTaskCreated)
    const button = Array.from(view.querySelectorAll("button")).find((candidate) => candidate.textContent === "Convert to task")!

    await act(async () => { button.click(); await Promise.resolve() })

    expect(booksApi.updateWriterWorkspace).toHaveBeenCalledWith("book-1", expect.objectContaining({
      goal_calendar: [expect.objectContaining({ id: "revision-task:issue-1", title: "Top continuity issue", quota_unit: "tasks" })],
    }))
    expect(onTaskCreated).toHaveBeenCalledWith(1)
  })

  it("shows a dismissible error beside Story Map when task saving fails", async () => {
    vi.mocked(booksApi.updateWriterWorkspace).mockRejectedValue(new Error("offline"))
    const workspace = { goal_calendar: [], revision_board: { items: [], last_generated_at: null } } as unknown as WriterWorkspace
    const view = renderPanel("story-map", buildRevision(), workspace)
    const button = Array.from(view.querySelectorAll("button")).find((candidate) => candidate.textContent === "Convert to task")!

    await act(async () => { button.click(); await Promise.resolve() })

    expect(view.querySelector('[role="status"]')?.textContent).toContain("could not save")
    await act(async () => { view.querySelector<HTMLButtonElement>('[aria-label="Dismiss revision notice"]')?.click() })
    expect(view.querySelector('[role="status"]')).toBeNull()
  })

  it("shows the API reason when task creation is forbidden", async () => {
    const forbidden = Object.assign(new Error("Request failed"), {
      isAxiosError: true,
      response: { data: { detail: "This authoring feature requires an Author or Architect plan." } },
    })
    vi.mocked(booksApi.updateWriterWorkspace).mockRejectedValue(forbidden)
    const workspace = { goal_calendar: [], revision_board: { items: [], last_generated_at: null } } as unknown as WriterWorkspace
    const view = renderPanel("story-map", buildRevision(), workspace)
    const button = Array.from(view.querySelectorAll("button")).find((candidate) => candidate.textContent === "Convert to task")!

    await act(async () => { button.click(); await Promise.resolve() })

    expect(view.querySelector('[role="status"]')?.textContent).toContain("requires an Author or Architect plan")
  })

  it("disables conversion until project planning data is available", () => {
    const view = renderPanel("story-map")
    expect(Array.from(view.querySelectorAll("button")).find((button) => button.textContent === "Convert to task")?.disabled).toBe(true)
  })

})

function renderPanel(
  variant: "full" | "preview" | "story-map" = "full",
  revision: RevisionIntelligence = buildRevision(),
  writerWorkspace: WriterWorkspace | null = null,
  onTaskCreated: (count: number) => void = vi.fn(),
) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => {
    root?.render(
      <RevisionIntelligencePanel
        bookId="book-1"
        revision={revision}
        writerWorkspace={writerWorkspace}
        isDark={false}
        onRevisionChange={vi.fn()}
        onWriterWorkspaceChange={vi.fn()}
        onTaskCreated={onTaskCreated}
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
    genre_checks: [
      {
        genre: "fantasy",
        label: "Fantasy",
        checks: ["magic system consistency"],
        rationale: "LoreVia is weighting fantasy-specific checks.",
        findings: [
          {
            id: "genre-1",
            category: "confusion",
            title: "Lore pressure around the archive terms.",
            description: "Readers get multiple invented terms at once.",
            severity: "medium",
            chapter_ref: 3,
            status: "pending",
          },
        ],
      },
    ],
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

function buildRevisionWithTimelineThreads(): RevisionIntelligence {
  const revision = buildRevision()

  return {
    ...revision,
    knowledge_timeline: [
      {
        fact: "Gregor's transformation into a vermin",
        rows: [
          {
            character_name: "Gregor",
            chapter_learned: 1,
            source: "Immediate lived experience",
            cells: [
              { chapter_number: 1, state: "learned" },
              { chapter_number: 2, state: "known" },
              { chapter_number: 3, state: "known" },
            ],
          },
          {
            character_name: "Grete",
            chapter_learned: null,
            source: "No earlier evidence surfaced yet",
            cells: [
              { chapter_number: 1, state: "unknown" },
              { chapter_number: 2, state: "unknown" },
              { chapter_number: 3, state: "unknown" },
            ],
          },
        ],
        warning: "Grete still lacks an explicit handoff before later scenes depend on this fact.",
      },
      {
        fact: "Gregor's struggle for survival",
        rows: [
          {
            character_name: "Gregor",
            chapter_learned: 1,
            source: "Tracked through manuscript evidence",
            cells: [
              { chapter_number: 1, state: "learned" },
              { chapter_number: 2, state: "known" },
            ],
          },
        ],
        warning: null,
      },
      {
        fact: "Gregor's obligation to his family",
        rows: [
          {
            character_name: "Gregor",
            chapter_learned: 1,
            source: "Tracked through manuscript evidence",
            cells: [
              { chapter_number: 1, state: "learned" },
              { chapter_number: 2, state: "known" },
            ],
          },
        ],
        warning: null,
      },
      {
        fact: "Concern for family obligations",
        rows: [
          {
            character_name: "Mr. Samsa",
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
      {
        fact: "Family obligation",
        rows: [
          {
            character_name: "Mrs. Samsa",
            chapter_learned: null,
            source: "No earlier evidence surfaced yet",
            cells: [
              { chapter_number: 1, state: "unknown" },
              { chapter_number: 2, state: "unknown" },
            ],
          },
        ],
        warning: null,
      },
    ],
  }
}
