// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const booksApiMock = vi.hoisted(() => ({
  addBookToSeries: vi.fn(),
  createSeries: vi.fn(),
  getSeriesBible: vi.fn(),
  list: vi.fn(),
  listSeries: vi.fn(),
  removeBookFromSeries: vi.fn(),
  setSeriesBookStatus: vi.fn(),
}))
const intelligenceApiMock = vi.hoisted(() => ({
  seriesAdvisorMessageStream: vi.fn(),
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
  useAuthStore: (selector: (state: { user: { tier: string | null } | null }) => unknown) =>
    selector({ user: userTier ? { tier: userTier } : null }),
}))
vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: () => ({ theme }),
}))
vi.mock("@/lib/utils/richText", () => ({ renderMarkdownHtml: (value: string) => `<p>${value}</p>` }))

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
    if ((container?.textContent ?? "").includes(expected)) return
    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 0))
    })
  }
  throw new Error(`Expected text not found: ${expected}. Saw: ${container?.textContent}`)
}

function text() {
  return container?.textContent ?? ""
}

function button(label: string, index = 0) {
  const matches = Array.from(container?.querySelectorAll("button") ?? []).filter((item) =>
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
  userTier = "architect"
  theme = "dark"
  booksApiMock.listSeries.mockResolvedValue(seriesRows)
  booksApiMock.list.mockResolvedValue(bookRows)
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
  intelligenceApiMock.seriesAdvisorMessageStream.mockImplementation(async (_seriesId, _messages, callbacks) => {
    callbacks?.onDelta?.("Draft ")
    return {
      reply: "Draft the oath payoff.",
      intent: "direction",
      response_type: "standard",
      retrieved_passages: [],
      cached: true,
    }
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
})

describe("SeriesPage", () => {
  it("renders the paid gate for guests and free users", async () => {
    userTier = null
    await renderPage(<SeriesPage />)
    expect(text()).toContain("Series workspace")
    expect(text()).toContain("reserved for paid plans")
    expect(booksApiMock.listSeries).not.toHaveBeenCalled()
  })

  it("drives series creation, bible, world analysis, advisor, continuity, and book actions", async () => {
    await renderPage(<SeriesPage />)
    await waitForText("Gate Saga")

    expect(text()).toContain("Track sagas")
    expect(text()).toContain("Gate One")
    expect(text()).toContain("Gate Two")

    const inputs = Array.from(container?.querySelectorAll("input") ?? []) as HTMLInputElement[]
    await act(async () => {
      setFieldValue(inputs[0], "Moon Saga")
      setFieldValue(inputs[1], "A second continuity lane.")
      await Promise.resolve()
    })
    await click("Create series")
    expect(booksApiMock.createSeries).toHaveBeenCalledWith({
      name: "Moon Saga",
      description: "A second continuity lane.",
    })

    await click("View Series Bible")
    await waitForText("Gate law changes between episodes.")
    expect(booksApiMock.getSeriesBible).toHaveBeenCalledWith("series-1")
    expect(text()).toContain("Recurring characters")
    expect(text()).toContain("Pilot")

    await click("World analysis")
    await waitForText("Ash Gate")
    expect(worldBuildingApiMock.getSeriesAnalysis).toHaveBeenCalledWith("series-1")

    await click("Ask")
    await waitForText("Series intelligence")
    const askInput = container?.querySelector('input[aria-label="Ask series question"]') as HTMLInputElement
    await act(async () => {
      setFieldValue(askInput, "How should the oath pay off?")
      await Promise.resolve()
    })
    await click("Ask", 2)
    await waitForText("Draft the oath payoff.")
    expect(intelligenceApiMock.seriesAdvisorMessageStream).toHaveBeenCalled()
    expect(text()).toContain("Cached response")

    await click("Series continuity check")
    const select = container?.querySelector("select") as HTMLSelectElement
    const chapterInput = container?.querySelector('input[aria-label="Scene number"]') as HTMLInputElement
    const passage = container?.querySelector('textarea[aria-label="Passage to cross-check"]') as HTMLTextAreaElement
    await act(async () => {
      setFieldValue(select, "book-1")
      setFieldValue(chapterInput, "4")
      setFieldValue(passage, "Mira repeats the old oath.")
      await Promise.resolve()
    })
    await click("Run series continuity check")
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

    await click("Close")
    await click("Mark read")
    expect(booksApiMock.setSeriesBookStatus).toHaveBeenCalledWith("series-1", "book-1", true)

    await click("Remove")
    expect(booksApiMock.removeBookFromSeries).toHaveBeenCalledWith("series-1", "book-1")

    const volumeInput = container?.querySelector('input[aria-label="Volume number"]') as HTMLInputElement
    await act(async () => {
      setFieldValue(volumeInput, "2")
      await Promise.resolve()
    })
    await click("Add")
    expect(booksApiMock.addBookToSeries).toHaveBeenCalledWith("series-1", "book-2", { position: 2 })
  })
})
