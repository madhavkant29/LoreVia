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

  it("drives goals, template editing, corkboard movement, readability, and emotional arc actions", async () => {
    const workspace = buildWorkspace()
    workspace.corkboard_cards = [
      { id: "card-1", title: "Open on the gate", description: "Opening beat", status: "planned", lane: "ideas", chapter_number: 2 },
      { id: "card-2", title: "Pressure the witness", description: "Middle beat", status: "drafting", lane: "drafting", chapter_number: null },
      { id: "card-3", title: "Resolve the key", description: "Closing beat", status: "revised", lane: "revised", chapter_number: 8 },
    ]
    workspace.templates?.push({
      id: "template-2",
      kind: "custom-kind",
      title: "Custom Turn",
      description: "A custom beat.",
      content: "Turn the scene.",
    })
    const onTightenSelectedText = vi.fn()
    const onWordCountGoalChange = vi.fn()
    const onSaveGoals = vi.fn()
    const onApplyTemplate = vi.fn().mockResolvedValue(undefined)
    const onSaveTemplates = vi.fn().mockResolvedValue(undefined)
    const onNewCorkboardTitleChange = vi.fn()
    const onAddCorkboardCard = vi.fn()
    const onUpdateCardLane = vi.fn()

    container = document.createElement("div")
    document.body.appendChild(container)
    root = createRoot(container)
    await act(async () => {
      root?.render(
        <ManuscriptPlanWorkspace
          isDark={false}
          editorMode="book"
          writerWorkspace={workspace}
          tighteningSelection={false}
          onTightenSelectedText={onTightenSelectedText}
          chapterWordCount={1250}
          fullBookWordCount={42000}
          chapterGoalProgress={50}
          bookGoalProgress={52}
          readabilityLoading={false}
          readability={{ reading_ease: 71.4, average_sentence_length: 13.2, grade_level: 7.1, label: "Easy", words: 1250, sentences: 95, paragraphs: 18 }}
          chapterApproxPages={1}
          fullBookApproxPages={120}
          chapterVersionsCount={3}
          workspaceSaving={false}
          onWordCountGoalChange={onWordCountGoalChange}
          onSaveGoals={onSaveGoals}
          onApplyTemplate={onApplyTemplate}
          onSaveTemplates={onSaveTemplates}
          newCorkboardTitle="A new reversal"
          onNewCorkboardTitleChange={onNewCorkboardTitleChange}
          onAddCorkboardCard={onAddCorkboardCard}
          onUpdateCardLane={onUpdateCardLane}
          emotionalArc={{
            focus_character_count: 1,
            latest_turning_points: [],
            characters: [{
              character_id: "char-1",
              character_name: "Mara",
              trajectory_score: 2,
              points: [
                { chapter_number: 1, label: "Doubt", sentiment: -3, impact_score: 2, growth_direction: "negative" },
                { chapter_number: 4, label: "Trust", sentiment: 4, impact_score: 4, growth_direction: "positive" },
              ],
            }],
          }}
        />
      )
    })

    const rendered = container

    expect(container.textContent).toContain("Easy (71)")
    expect(container.textContent).toContain("Switch to chapter view")
    expect(container.querySelector('[aria-label="Mara emotional arc"]')).not.toBeNull()

    clickButton(container, "Tighten selected text")
    clickButton(container, "Save goals")
    clickButton(container, "Add")
    clickCardButton(container, "Open on the gate", "Drafting")
    expect(onTightenSelectedText).toHaveBeenCalled()
    expect(onSaveGoals).toHaveBeenCalled()
    expect(onAddCorkboardCard).toHaveBeenCalled()
    expect(onUpdateCardLane).toHaveBeenCalledWith("card-1", "drafting")

    const goalInput = container.querySelector<HTMLInputElement>('input[aria-label="Chapter target words"]')
    act(() => changeValue(goalInput, "3200"))
    expect(onWordCountGoalChange).toHaveBeenCalledWith("chapter_target", 3200)

    act(() => clickButton(rendered, "Use template", 1))
    expect(container.textContent).toContain("Use or customize template")
    const titleInput = Array.from(container.querySelectorAll<HTMLInputElement>('input')).find((input) => input.value === "Custom Turn")
    act(() => changeValue(titleInput ?? null, "Revised Turn"))
    const destination = container.querySelector<HTMLInputElement>('input[value="corkboard"]')
    act(() => destination?.click())
    await act(async () => {
      clickButton(rendered, "Save template changes")
      await Promise.resolve()
    })
    expect(onSaveTemplates).toHaveBeenCalledWith(expect.arrayContaining([expect.objectContaining({ id: "template-2", title: "Revised Turn" })]))
    await act(async () => {
      clickButton(rendered, "Use in selected destination")
      await Promise.resolve()
    })
    expect(onApplyTemplate).toHaveBeenCalledWith(expect.objectContaining({ title: "Revised Turn" }), "corkboard")

    act(() => clickButton(rendered, "New custom template"))
    expect(container.textContent).toContain("Add scaffold content to preview it here.")
    act(() => clickButton(rendered, "Close"))
    expect(container.textContent).not.toContain("Use or customize template")
  })
})

function clickButton(container: HTMLElement, label: string, index = 0) {
  const button = Array.from(container.querySelectorAll("button")).filter((candidate) => candidate.textContent?.trim() === label)[index]
  if (!button) throw new Error(`Missing button: ${label}`)
  button.dispatchEvent(new MouseEvent("click", { bubbles: true }))
}

function clickCardButton(container: HTMLElement, cardTitle: string, label: string) {
  const card = Array.from(container.querySelectorAll("article")).find((candidate) => candidate.textContent?.includes(cardTitle))
  if (!card) throw new Error(`Missing card: ${cardTitle}`)
  clickButton(card, label)
}

function changeValue(input: HTMLInputElement | null, value: string) {
  if (!input) throw new Error("Missing input")
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(input, value)
  input.dispatchEvent(new Event("input", { bubbles: true }))
}

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
    novel_preface: "",
    revision_board: {
      items: [],
    },
  } as WriterWorkspace
}
