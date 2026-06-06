import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"

import { ManuscriptPlanWorkspace } from "./ManuscriptPlanWorkspace"
import type { WriterWorkspace } from "@/types/book"

describe("ManuscriptPlanWorkspace", () => {
  let container: HTMLDivElement | null = null
  let root: Root | null = null

  beforeAll(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  })

  afterEach(() => {
    if (root) {
      act(() => {
        root?.unmount()
      })
    }
    container?.remove()
    container = null
    root = null
  })

  it("labels word-count goal fields and explains template insertion", () => {
    container = document.createElement("div")
    document.body.appendChild(container)
    root = createRoot(container)

    act(() => {
      root?.render(
        <ManuscriptPlanWorkspace
          isDark
          editorMode="chapter"
          writerWorkspace={buildWorkspace()}
          tighteningSelection={false}
          onTightenSelectedText={vi.fn()}
          chapterWordCount={6310}
          fullBookWordCount={13767}
          chapterGoalProgress={100}
          bookGoalProgress={17}
          readabilityLoading={false}
          readability={null}
          chapterApproxPages={13}
          fullBookApproxPages={28}
          chapterVersionsCount={0}
          workspaceSaving={false}
          onWordCountGoalChange={vi.fn()}
          onSaveGoals={vi.fn()}
          onApplyTemplate={vi.fn()}
          onSaveTemplates={vi.fn()}
          newCorkboardTitle=""
          onNewCorkboardTitleChange={vi.fn()}
          onAddCorkboardCard={vi.fn()}
          onUpdateCardLane={vi.fn()}
          emotionalArc={null}
        />
      )
    })

    expect(container.textContent).toContain("Chapter target")
    expect(container.textContent).toContain("Book target")
    expect(container.textContent).toContain("Session target")
    expect(container.textContent).toContain("No manual chapter snapshots yet.")
    expect(container.textContent).toContain("Templates insert reusable structure into the draft.")

    expect(container.querySelector<HTMLInputElement>('input[aria-label="Chapter target words"]')?.value).toBe("2500")
    expect(container.querySelector<HTMLInputElement>('input[aria-label="Book target words"]')?.value).toBe("80000")
    expect(container.querySelector<HTMLInputElement>('input[aria-label="Session target words"]')?.value).toBe("1000")
  })
})

function buildWorkspace(): WriterWorkspace {
  return {
    word_count_goals: {
      chapter_target: 2500,
      book_target: 80000,
      session_target: 1000,
    },
    goal_calendar: [],
    corkboard_cards: [],
    templates: [
      {
        id: "template-1",
        kind: "chapter",
        title: "Chapter Three-Beat",
        description: "Open with pressure, pivot in the middle, end on a story-moving turn.",
        content: "Pressure\nPivot\nTurn",
      },
    ],
    publishing: {
      active_preset: "standard_manuscript",
      trim_size: "8.5x11",
      include_title_page: true,
      mirror_margins: false,
    },
    manuscript_front_matter: {
      author_name: "Author",
      pen_name: "",
      contact_email: "",
      contact_phone: "",
      contact_address: "",
      title: "Meta",
      subtitle: "",
      header_last_name: "",
      header_title: "",
      dedication: "",
      acknowledgments: "",
      epigraph: "",
      prologue: "",
      include_dedication: false,
      include_acknowledgments: false,
      include_epigraph: false,
      include_prologue: false,
    },
    revision_board: {
      items: [],
    },
  } as WriterWorkspace
}
