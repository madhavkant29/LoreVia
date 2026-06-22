// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, describe, expect, it, vi } from "vitest"

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a>,
}))

vi.mock("@/components/ui/SmartBookCover", () => ({
  SmartBookCover: ({ title }: { title: string }) => <div data-testid="book-cover">{title}</div>,
}))

import { ManuscriptExportMenu } from "@/components/reader/ManuscriptExportMenu"
import { ManuscriptModeSwitch } from "@/components/reader/ManuscriptModeSwitch"
import { ActiveIssuesCard } from "./ActiveIssuesCard"
import { CreateFab } from "./CreateFab"
import { CurrentProjectCard } from "./CurrentProjectCard"
import { DailyGoalCard } from "./DailyGoalCard"
import { GoalCalendarCard } from "./GoalCalendarCard"
import { ProjectOverviewCard } from "./ProjectOverviewCard"
import { QuickToolsCard } from "./QuickToolsCard"
import { StoryHealthCard } from "./StoryHealthCard"
import { WritingStreakCard } from "./WritingStreakCard"

let root: Root | null = null
let container: HTMLDivElement | null = null

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

async function renderElement(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  await act(async () => {
    root?.render(element)
    await Promise.resolve()
  })
}

function clickByText(text: string) {
  const button = Array.from(container?.querySelectorAll("button") ?? []).find((item) =>
    item.textContent?.includes(text)
  )
  if (!button) throw new Error(`Missing button: ${text}`)
  act(() => {
    button.dispatchEvent(new MouseEvent("click", { bubbles: true }))
  })
}

async function clickByTextAsync(text: string) {
  const button = Array.from(container?.querySelectorAll("button") ?? []).find((item) =>
    item.textContent?.includes(text)
  )
  if (!button) throw new Error(`Missing button: ${text}`)
  await act(async () => {
    button.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await Promise.resolve()
  })
}

function setFieldValue(field: HTMLInputElement | HTMLSelectElement, value: string) {
  const prototype = field instanceof HTMLInputElement ? HTMLInputElement.prototype : HTMLSelectElement.prototype
  const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set
  setter?.call(field, value)
  field.dispatchEvent(new Event(field instanceof HTMLSelectElement ? "change" : "input", { bubbles: true }))
}

afterEach(() => {
  if (root) {
    act(() => {
      root?.unmount()
    })
  }
  container?.remove()
  root = null
  container = null
  document.body.innerHTML = ""
})

describe("overview and manuscript controls", () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it("renders the current project card and opens the manuscript editor", async () => {
    const onOpenManuscript = vi.fn()

    await renderElement(
      <CurrentProjectCard
        book={{
          id: "book-1",
          title: "The Ember Gate",
          genre: "Fantasy",
          status: "ready",
          created_at: "2026-01-02T00:00:00Z",
          cover_url: null,
          work_type: "novel",
        } as any}
        isDark={false}
        canOpenManuscript
        currentWords={42000}
        targetWords={80000}
        percentComplete={52}
        chapters={[
          { number: 1, title: "Ash", read: true },
          { number: 2, title: "Gate", read: false },
        ] as any}
        unitTitle="Chapter"
        unitPrefix="Ch."
        onOpenManuscript={onOpenManuscript}
      />,
    )

    expect(container?.textContent).toContain("Current Project")
    expect(container?.textContent).toContain("The Ember Gate")
    expect(container?.textContent).toContain("42,000 / 80,000 words")

    clickByText("Open Manuscript Editor")
    expect(onOpenManuscript).toHaveBeenCalledTimes(1)
  })

  it("renders goal, health, issue, and tool cards with callbacks", async () => {
    const navigate = vi.fn()
    const retry = vi.fn()

    await renderElement(
      <div>
        <DailyGoalCard isDark dailyWords={1250} dailyTarget={1000} />
        <StoryHealthCard
          bookId="book-1"
          isDark={false}
          storyHealth={{
            score: 72,
            status: "Stable",
            summary: "Continuity is mostly intact.",
            metrics: [
              { label: "Continuity", score: 80, detail: "Minor drift." },
              { label: "Pacing", score: 60, detail: "Middle slows." },
            ],
          } as any}
          onRetryStoryHealth={retry}
        />
        <ActiveIssuesCard
          isDark={false}
          continuityIssueCount={2}
          worldGapCount={1}
          timelineIssueCount={0}
          onNavigate={navigate}
          bookId="book-1"
        />
        <QuickToolsCard isDark={false} bookId="book-1" onNavigate={navigate} />
      </div>,
    )

    expect(container?.textContent).toContain("Goal reached today.")
    expect(container?.textContent).toContain("Story Health")
    expect(container?.textContent).toContain("Continuity is mostly intact.")
    expect(container?.textContent).toContain("Character Inconsistencies")
    expect(container?.textContent).toContain("Manuscript Editor")

    clickByText("World Gaps")
    clickByText("Story Advisor")
    expect(navigate).toHaveBeenCalledWith("/book-1/world-gap")
    expect(navigate).toHaveBeenCalledWith("/book-1/advisor")
  })

  it("renders project metrics, streaks, and create actions", async () => {
    const addScene = vi.fn()
    const navigate = vi.fn()

    await renderElement(
      <div>
        <ProjectOverviewCard
          isDark={false}
          currentWords={12500}
          chapterCount={8}
          characterCount={14}
          worldArticleCount={6}
        />
        <WritingStreakCard
          isDark
          streakDays={9}
          weekActivity={[true, false, true, true, false, false, true]}
        />
        <CreateFab bookId="book-1" isDark={false} onAddScene={addScene} onNavigate={navigate} />
      </div>,
    )

    expect(container?.textContent).toContain("Project Overview")
    expect(container?.textContent).toContain("12,500")
    expect(container?.textContent).toContain("Writing streak")
    expect(container?.textContent).toContain("9 days")

    clickByText("Add Scene")
    clickByText("Add Note")
    clickByText("Add Character")

    expect(addScene).toHaveBeenCalledTimes(1)
    expect(navigate).toHaveBeenCalledWith("/book-1/notes")
    expect(navigate).toHaveBeenCalledWith("/book-1/characters")
  })

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

    expect(container?.textContent).toContain("Goal Calendar")
    expect(container?.textContent).toContain("Outline midpoint")
    expect(container?.textContent).toContain("1,200 words")
    expect(container?.textContent).toContain("Planner saved")

    const titleInput = container?.querySelector("input[aria-label='Planning item']") as HTMLInputElement
    const quotaInput = container?.querySelector("input[aria-label='Planning quota']") as HTMLInputElement
    const unitSelect = container?.querySelector("select") as HTMLSelectElement
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

    const checkbox = container?.querySelector("input[type='checkbox']") as HTMLInputElement
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

  it("renders story health retry state", async () => {
    const retry = vi.fn()

    await renderElement(
      <StoryHealthCard
        bookId="book-1"
        isDark
        storyHealth={null}
        storyHealthError
        onRetryStoryHealth={retry}
      />,
    )

    expect(container?.textContent).toContain("Failed to load story health")
    clickByText("Retry")
    expect(retry).toHaveBeenCalledTimes(1)
  })

  it("supports manuscript export menu interactions", async () => {
    const onToggle = vi.fn()
    const onPresetChange = vi.fn()
    const onIncludeTableOfContentsChange = vi.fn()
    const onPrint = vi.fn()
    const onCompile = vi.fn()

    await renderElement(
      <ManuscriptExportMenu
        isDark={false}
        open
        activePreset="standard_manuscript"
        exporting={null}
        includeTableOfContents={false}
        onToggle={onToggle}
        onPresetChange={onPresetChange}
        onIncludeTableOfContentsChange={onIncludeTableOfContentsChange}
        onPrint={onPrint}
        onCompile={onCompile}
      />,
    )

    clickByText("Export")
    expect(onToggle).toHaveBeenCalledTimes(1)

    const select = container?.querySelector("select")
    act(() => {
      select!.value = "trade_paperback"
      select!.dispatchEvent(new Event("change", { bubbles: true }))
    })
    const checkbox = container?.querySelector("input[type='checkbox']")
    act(() => {
      checkbox!.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    })
    clickByText("Print")
    clickByText("Compile Word")
    clickByText("Compile submission PDF")

    expect(onPresetChange).toHaveBeenCalledWith("trade_paperback")
    expect(onIncludeTableOfContentsChange).toHaveBeenCalledWith(true)
    expect(onPrint).toHaveBeenCalledTimes(1)
    expect(onCompile).toHaveBeenCalledWith("docx")
    expect(onCompile).toHaveBeenCalledWith("pdf")
  })

  it("supports manuscript mode switching", async () => {
    const onSelect = vi.fn()

    await renderElement(
      <ManuscriptModeSwitch
        isDark={false}
        options={["chapter", "book"] as const}
        selected="chapter"
        onSelect={onSelect}
        renderLabel={(value) => value === "chapter" ? "Chapter" : "Book"}
      />,
    )

    expect(container?.querySelector("[aria-pressed='true']")?.textContent).toBe("Chapter")
    clickByText("Book")
    expect(onSelect).toHaveBeenCalledWith("book")
  })
})
