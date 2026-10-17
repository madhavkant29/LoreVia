// @vitest-environment jsdom

import { act } from "react"
import { describe, expect, it, vi } from "vitest"

import {
  GoalCalendarCard,
  clickByText,
  clickByTextAsync,
  getContainer,
  renderElement,
  setFieldValue,
} from "./overviewCards.test-utils"

describe("overview goal calendar", () => {
  it("adds, toggles, removes, and navigates goal calendar items", async () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date("2026-06-15T12:00:00Z"))
    const saveGoalCalendar = vi.fn(async () => true)
    const openManuscript = vi.fn()

    await renderElement(
      <GoalCalendarCard
        isDark={false}
        writerWorkspace={{
          word_count_goals: {
            book_target: 90000,
            chapter_target: 4500,
            session_target: 1500,
          },
          goal_calendar: [
            {
              id: "outline",
              title: "Outline midpoint",
              due_date: "2026-06-15",
              quota_value: 1200,
              quota_unit: "words",
              completed: false,
            },
            {
              id: "revise",
              title: "Revise opening",
              due_date: "2026-06-14",
              quota_value: null,
              quota_unit: null,
              completed: true,
            },
          ],
          corkboard_cards: [],
          templates: [],
          publishing: {
            active_preset: "standard_manuscript",
            trim_size: "6x9",
            include_title_page: true,
            mirror_margins: false,
          },
          manuscript_front_matter: {
            author_name: "",
            pen_name: "",
            contact_email: "",
            contact_phone: "",
            contact_address: "",
            title: "",
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
          revision_board: { items: [] },
        }}
        saveState="saved"
        saveMessage="Planner saved"
        onSaveGoalCalendar={saveGoalCalendar}
        onOpenManuscript={openManuscript}
      />,
    )

    expect(getContainer().textContent).toContain("Goal Calendar")
    expect(getContainer().textContent).toContain("Outline midpoint")
    expect(getContainer().textContent).toContain("1,200 words")
    expect(getContainer().textContent).toContain("Planner saved")

    const nextMonth = getContainer().querySelector('button[aria-label="Show next month"]')!
    act(() => nextMonth.dispatchEvent(new MouseEvent("click", { bubbles: true })))
    expect(getContainer().textContent).toContain("July 2026")
    const previousMonth = getContainer().querySelector('button[aria-label="Show previous month"]')!
    act(() => previousMonth.dispatchEvent(new MouseEvent("click", { bubbles: true })))
    expect(getContainer().textContent).toContain("June 2026")
    expect(getContainer().querySelector('input[aria-label="Planning date"]')).not.toBeNull()
    expect(getContainer().querySelector('select[aria-label="Quota unit"]')).not.toBeNull()

    const titleInput = getContainer().querySelector("input[aria-label='Planning item']") as HTMLInputElement
    const quotaInput = getContainer().querySelector("input[aria-label='Planning quota']") as HTMLInputElement
    const unitSelect = getContainer().querySelector("select") as HTMLSelectElement
    act(() => {
      setFieldValue(titleInput, "Draft reveal scene")
      setFieldValue(quotaInput, "875.4")
      setFieldValue(unitSelect, "scenes")
    })

    await clickByTextAsync("Add item")
    expect(saveGoalCalendar).toHaveBeenCalledWith(expect.arrayContaining([
      expect.objectContaining({
        title: "Draft reveal scene",
        due_date: "2026-06-15",
        quota_value: 875,
        quota_unit: "scenes",
        completed: false,
      }),
    ]))

    const checkbox = getContainer().querySelector("input[type='checkbox']") as HTMLInputElement
    act(() => {
      checkbox.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    })
    clickByText("Remove")
    clickByText("Adjust word goals")

    expect(saveGoalCalendar).toHaveBeenCalledWith(expect.arrayContaining([
      expect.objectContaining({ id: "outline", completed: true }),
    ]))
    expect(saveGoalCalendar).toHaveBeenCalledWith([
      expect.objectContaining({ id: "revise" }),
    ])
    expect(openManuscript).toHaveBeenCalledTimes(1)
  })
})
