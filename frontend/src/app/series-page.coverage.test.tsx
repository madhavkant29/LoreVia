// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const booksApiMock = vi.hoisted(() => ({
  addBookToSeries: vi.fn(),
  createSeries: vi.fn(),
  getSeriesBible: vi.fn(),
  list: vi.fn(),
  listPage: vi.fn(),
  listSelector: vi.fn(),
  listSeries: vi.fn(),
  removeBookFromSeries: vi.fn(),
  setSeriesBookStatus: vi.fn(),
}))
const intelligenceApiMock = vi.hoisted(() => ({
  seriesContinuityCheckStream: vi.fn(),
}))
const worldBuildingApiMock = vi.hoisted(() => ({
  getSeriesAnalysis: vi.fn(),
}))

let userTier: string | null = "architect"
let theme = "dark"

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))
vi.mock("@/components/ui/Workspace", () => ({
  WorkspaceEmptyState: ({ body, title }: { body: string; title: string }) => (
    <div>
      <h2>{title}</h2>
      <p>{body}</p>
    </div>
  ),
  WorkspaceHeader: ({ description, eyebrow, title }: { description: string; eyebrow: string; title: string }) => (
    <header>
      <p>{eyebrow}</p>
      <h1>{title}</h1>
      <p>{description}</p>
    </header>
  ),
  WorkspacePage: ({ children, className }: { children: ReactNode; className?: string }) => (
    <main className={className}>{children}</main>
  ),
}))
vi.mock("@/lib/api/books", () => ({ booksApi: booksApiMock }))
vi.mock("@/lib/api/intelligence", () => ({ intelligenceApi: intelligenceApiMock }))
vi.mock("@/lib/api/worldBuilding", () => ({ worldBuildingApi: worldBuildingApiMock }))
vi.mock("@/lib/billing/plans", () => ({ isPaidTier: (tier?: string | null) => tier === "author" || tier === "architect" }))
vi.mock("@/lib/stores/authStore", () => ({
  useAuthStore: (selector: (state: { hydrated: boolean; user: { tier: string | null } | null }) => unknown) =>
    selector({ hydrated: true, user: userTier ? { tier: userTier } : null }),
}))
vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: () => ({ theme }),
}))
import SeriesPage from "@/app/(dashboard)/series/page"

let root: Root | null = null
let container: HTMLDivElement | null = null

const seriesRows = {
  items: [
    {
      id: "series-1",
      name: "Gate Saga",
      description: "A connected gate fantasy.",
      books: [
        {
          id: "book-1",
          title: "Gate One",
          author: "A. Writer",
          progress_pct: 75,
          chapters_read_count: 8,
          chapters_left: 4,
          series_order: 1,
          work_type: "screenplay",
          public_slug: null,
          mode: "author",
        },
      ],
    },
  ],
}
const bookRows = [
  seriesRows.items[0].books[0],
  {
    id: "book-2",
    title: "Gate Two",
    author: "A. Writer",
    progress_pct: 10,
    chapters_read_count: 1,
    chapters_left: 11,
    series_order: null,
    primary_series_id: null,
    series_name: null,
    work_type: "novel",
    mode: "author",
  },
]

async function renderPage(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root?.render(element)
    await Promise.resolve()
  })
}

async function waitForText(expected: string) {
  for (let index = 0; index < 30; index += 1) {
    if ((document.body.textContent ?? "").includes(expected)) return
    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 0))
    })
  }
  throw new Error(`Expected text not found: ${expected}. Saw: ${document.body.textContent}`)
}

function text() {
  return document.body.textContent ?? ""
}

function button(label: string, index = 0) {
  const matches = Array.from(document.body.querySelectorAll("button")).filter((item) =>
    item.textContent?.includes(label)
  )
  const match = matches[index]
  if (!match) throw new Error(`Missing button: ${label}`)
  return match
}

async function click(label: string, index = 0) {
  await act(async () => {
    button(label, index).dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await Promise.resolve()
    await Promise.resolve()
  })
}

function setFieldValue(field: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement, value: string) {
  const prototype =
    field instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : field instanceof HTMLInputElement
        ? HTMLInputElement.prototype
        : HTMLSelectElement.prototype
  const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set
  setter?.call(field, value)
  field.dispatchEvent(new Event(field instanceof HTMLSelectElement ? "change" : "input", { bubbles: true }))
}

beforeEach(() => {
  vi.spyOn(window, "confirm").mockReturnValue(true)
  userTier = "architect"
  theme = "dark"
  booksApiMock.listSeries.mockResolvedValue(seriesRows)
  booksApiMock.list.mockResolvedValue(bookRows)
  booksApiMock.listPage.mockResolvedValue({ items: bookRows, next_cursor: null, has_more: false })
  booksApiMock.listSelector.mockResolvedValue(bookRows)
  booksApiMock.createSeries.mockResolvedValue({ id: "series-2" })
  booksApiMock.getSeriesBible.mockResolvedValue({
    episode_count: 1,
    episodes: [{ episode_number: 1, title: "Pilot", total_scenes: 12, total_dialogue_lines: 90 }],
    recurring_characters: [{ name: "Mira", episode_count: 1, total_mentions: 30 }],
    recurring_relationships: [{ name: "Mira/Joren" }],
    unresolved_plot_threads: [{ title: "Ash gate", status: "open", episode_count: 1 }],
    continuity_risks: ["Gate law changes between episodes."],
  })
  worldBuildingApiMock.getSeriesAnalysis.mockResolvedValue({
    book_count: 2,
    analysis_count: 3,
    world_context: [{ name: "Ash Gate" }, "Moon Road"],
  })
  intelligenceApiMock.seriesContinuityCheckStream.mockImplementation(async (_seriesId, _bookId, _text, _chapter, callbacks) => {
    callbacks?.onStage?.("Reading earlier volumes")
    return {
      cached: true,
      retrieved_passages: [{ book_title: "Gate One", chapter_num: 3, excerpt: "The oath is binding." }],
      review: {
        overall_verdict: "Fits the earlier oath.",
        thematic_fit: { score: "strong", notes: "The vow motif aligns." },
        continuity_issues: [{ title: "Oath timing", description: "Clarify when it was sworn.", severity: "minor", suggestion: "Name the scene." }],
        cross_book_opportunities: [{ title: "Echo the gate law", description: "Repeat the earlier rule." }],
      },
    }
  })
  booksApiMock.setSeriesBookStatus.mockResolvedValue({})
  booksApiMock.removeBookFromSeries.mockResolvedValue({})
  booksApiMock.addBookToSeries.mockResolvedValue({})
})

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
  vi.clearAllMocks()
  vi.restoreAllMocks()
})

describe("SeriesPage", () => {
  it("keeps a failed creation draft and honors discard cancellation", async () => {
    booksApiMock.createSeries.mockRejectedValueOnce(new Error("offline"))
    await renderPage(<SeriesPage />)
    await click("New series")
    const name = document.querySelector('input[aria-label="Series name"]') as HTMLInputElement
    await act(async () => { setFieldValue(name, "Draft cycle") })
    await click("Create series")
    await waitForText("Creation could not be confirmed")
    expect(name.value).toBe("Draft cycle")
    vi.mocked(window.confirm).mockReturnValueOnce(false)
    await click("Cancel new series")
    expect(name.isConnected).toBe(true)
    await click("Cancel new series")
    expect(name.isConnected).toBe(false)
  })

  it("retries failed world context and renders the backend's string response intact", async () => {
    worldBuildingApiMock.getSeriesAnalysis.mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce({ book_count: 1, analysis_count: 1, world_context: "The first rule.\nThe last rule." })
    await renderPage(<SeriesPage />)
    await click("World analysis")
    await waitForText("This series context could not be loaded.")
    await click("Retry series context")
    await waitForText("The first rule.\nThe last rule.")
  })

  it("protects unsaved series forms when navigating or unloading", async () => {
    await renderPage(<SeriesPage />)
    await click("New series")
    const name = document.querySelector('input[aria-label="Series name"]') as HTMLInputElement
    await act(async () => { setFieldValue(name, "Keep this draft") })
    const unload = new Event("beforeunload", { cancelable: true })
    window.dispatchEvent(unload)
    expect(unload.defaultPrevented).toBe(true)
    vi.mocked(window.confirm).mockReturnValueOnce(false)
    const navigation = new MouseEvent("click", { bubbles: true, cancelable: true })
    document.querySelector('a[href="/series/series-1/ask"]')?.dispatchEvent(navigation)
    expect(navigation.defaultPrevented).toBe(true)
    expect(name.value).toBe("Keep this draft")
    await click("Cancel new series")
    const cleanUnload = new Event("beforeunload", { cancelable: true })
    window.dispatchEvent(cleanUnload)
    expect(cleanUnload.defaultPrevented).toBe(false)
  })

  it("does not silently coerce invalid chapter numbers or truncate continuity passages", async () => {
    await renderPage(<SeriesPage />)
    await click("Continuity check")
    const project = document.querySelector('select[aria-label="Project to check"]') as HTMLSelectElement
    const chapter = document.querySelector('input[aria-label="Chapter or scene number"]') as HTMLInputElement
    const passage = document.querySelector('textarea[aria-label="Passage to cross-check"]') as HTMLTextAreaElement
    await act(async () => { setFieldValue(project, "book-1"); setFieldValue(chapter, "-2"); setFieldValue(passage, "Keep the whole passage.") })
    expect(button("Run continuity check").disabled).toBe(true)
    expect(chapter.value).toBe("-2")
    await act(async () => { setFieldValue(chapter, "2"); setFieldValue(passage, "x".repeat(4001)) })
    expect(button("Run continuity check").disabled).toBe(true)
    expect(passage.value).toHaveLength(4001)
    expect(intelligenceApiMock.seriesContinuityCheckStream).not.toHaveBeenCalled()
  })

  it("renders the paid gate for guests and free users", async () => {
    userTier = null
    await renderPage(<SeriesPage />)
    expect(text()).toContain("Series workspace")
    expect(text()).toContain("reserved for paid plans")
    expect(booksApiMock.listSeries).not.toHaveBeenCalled()
  })

  it("uses one selected-series workspace and defers secondary analysis until requested", async () => {
    await renderPage(<SeriesPage />)
    await waitForText("Gate Saga")

    expect(text()).toContain("Series management")
    expect(text()).toContain("Gate One")
    expect(text()).not.toContain("Gate Two")
    expect(booksApiMock.getSeriesBible).not.toHaveBeenCalled()
    expect(worldBuildingApiMock.getSeriesAnalysis).not.toHaveBeenCalled()

    const askLink = document.body.querySelector('a[href="/series/series-1/ask"]')
    expect(askLink?.textContent).toContain("Ask about this series")

    await click("New series")
    const nameInput = document.body.querySelector('input') as HTMLInputElement
    const descriptionInput = document.body.querySelector('textarea') as HTMLTextAreaElement
    await act(async () => {
      setFieldValue(nameInput, "Moon Saga")
      setFieldValue(descriptionInput, "A second continuity lane.")
      await Promise.resolve()
    })
    await click("Create series")
    expect(booksApiMock.createSeries).toHaveBeenCalledWith({
      name: "Moon Saga",
      description: "A second continuity lane.",
    })

    await click("Series bible")
    await waitForText("Gate law changes between episodes.")
    expect(booksApiMock.getSeriesBible).toHaveBeenCalledWith("series-1")
    expect(text()).toContain("Recurring characters")
    expect(text()).toContain("Pilot")

    await click("World analysis")
    await waitForText("Ash Gate")
    expect(worldBuildingApiMock.getSeriesAnalysis).toHaveBeenCalledWith("series-1")

    await click("Continuity check")
    const select = document.body.querySelector('select[aria-label="Project to check"]') as HTMLSelectElement
    const chapterInput = document.body.querySelector('input[aria-label="Chapter or scene number"]') as HTMLInputElement
    const passage = document.body.querySelector('textarea[aria-label="Passage to cross-check"]') as HTMLTextAreaElement
    await act(async () => {
      setFieldValue(select, "book-1")
      setFieldValue(chapterInput, "4")
      setFieldValue(passage, "Mira repeats the old oath.")
      await Promise.resolve()
    })
    await click("Run continuity check")
    await waitForText("Fits the earlier oath.")
    expect(intelligenceApiMock.seriesContinuityCheckStream).toHaveBeenCalledWith(
      "series-1",
      "book-1",
      "Mira repeats the old oath.",
      4,
      expect.any(Object),
    )
    expect(text()).toContain("Oath timing")
    expect(text()).toContain("Echo the gate law")

    await click("Mark complete")
    expect(booksApiMock.setSeriesBookStatus).toHaveBeenCalledWith("series-1", "book-1", true)

    await click("Remove")
    expect(booksApiMock.removeBookFromSeries).toHaveBeenCalledWith("series-1", "book-1")

    await click("Add project")
    expect(text()).toContain("Gate Two")
    const projectSelect = container?.querySelector('select[aria-label="Project to add"]') as HTMLSelectElement
    const volumeInput = container?.querySelector('input[aria-label="Series position"]') as HTMLInputElement
    await act(async () => {
      setFieldValue(projectSelect, "book-2")
      setFieldValue(volumeInput, "2")
      await Promise.resolve()
    })
    await click("Add")
    expect(booksApiMock.addBookToSeries).toHaveBeenCalledWith("series-1", "book-2", { position: 2 })
  })
})
