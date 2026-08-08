// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const useQueryMock = vi.hoisted(() => vi.fn())
const useParamsMock = vi.hoisted(() => vi.fn(() => ({ bookId: "book-1" })))
const setTimelineCollapsedSectionMock = vi.hoisted(() => vi.fn())
const patchBookPreferencesMock = vi.hoisted(() => vi.fn())
const hydrateBookPreferencesMock = vi.hoisted(() => vi.fn())
const captureMock = vi.hoisted(() => vi.fn())
const preferencesState = vi.hoisted(() => ({
  theme: "light" as "light" | "dark",
  timelineCollapsedSections: {} as Record<string, boolean>,
}))

vi.mock("next/navigation", () => ({
  useParams: useParamsMock,
}))

vi.mock("@tanstack/react-query", () => ({
  useQuery: useQueryMock,
}))

vi.mock("@/components/reader/WorkspaceFamilyHeader", () => ({
  WorkspaceFamilyHeader: ({
    title,
    description,
    actions,
  }: {
    title: string
    description: string
    actions?: ReactNode
  }) => (
    <header>
      <h1>{title}</h1>
      <p>{description}</p>
      {actions}
    </header>
  ),
}))

vi.mock("@/components/ui/Workspace", () => ({
  WorkspaceEmptyState: ({ title, body, className = "" }: { title: string; body: string; className?: string }) => (
    <section className={className}>
      <h2>{title}</h2>
      <p>{body}</p>
    </section>
  ),
  WorkspaceMetric: ({ label, value, className = "" }: { label: string; value: string; className?: string }) => (
    <section className={className}>
      <p>{label}</p>
      <strong>{value}</strong>
    </section>
  ),
  WorkspacePage: ({ children, className = "" }: { children: ReactNode; className?: string }) => (
    <main className={className}>{children}</main>
  ),
  WorkspacePanel: ({ children, className = "" }: { children: ReactNode; className?: string }) => (
    <section className={className}>{children}</section>
  ),
}))

vi.mock("@/lib/api/books", () => ({ booksApi: { get: vi.fn() } }))
vi.mock("@/lib/api/reader", () => ({ readerApi: { getTimeline: vi.fn() } }))
vi.mock("@/lib/query/cacheKeys", () => ({
  asQueryKey: (value: unknown) => value,
  bookCacheKey: (...parts: string[]) => parts.join(":"),
  readerCacheKey: (...parts: string[]) => parts.join(":"),
}))
vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: () => ({
    theme: preferencesState.theme,
  }),
}))
vi.mock("@/lib/stores/uiPreferencesStore", () => ({
  defaultBookUiPreference: (bookId: string) => ({
    book_id: bookId,
    timeline_collapsed_sections: preferencesState.timelineCollapsedSections,
  }),
  useUiPreferencesStore: (selector: (state: Record<string, unknown>) => unknown) => selector({
    preferences: { complexity_mode: "standard" },
    bookPreferences: {
      "book-1": {
        book_id: "book-1",
        timeline_collapsed_sections: preferencesState.timelineCollapsedSections,
      },
    },
    hydrateBook: hydrateBookPreferencesMock,
    patchBook: patchBookPreferencesMock,
    setTimelineCollapsedSection: setTimelineCollapsedSectionMock,
  }),
}))
vi.mock("@/lib/analytics/posthog", () => ({ capture: captureMock }))

import TimelinePage from "@/app/(reader)/[bookId]/timeline/page"

let root: Root | null = null
let container: HTMLDivElement | null = null

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const bookFixture = {
  id: "book-1",
  title: "The Lantern Gate",
  mode: "author",
}

const timelineFixture = {
  chapters: [
    { number: 1 },
    { number: 2 },
    { number: 3 },
  ],
  character_tracks: [
    {
      id: "character-1",
      name: "Mara",
      role: "keeper",
      detail: "Carries the lantern through the gate.",
      start_chapter: 1,
      end_chapter: 3,
    },
  ],
  thread_tracks: [
    {
      id: "thread-1",
      title: "The brass key",
      status: "resolved",
      note: "The key changes hands.",
      detail: null,
      start_chapter: 1,
      end_chapter: 2,
    },
    {
      id: "thread-2",
      title: "The hidden gate",
      status: "open",
      note: null,
      detail: "The gate is still active.",
      start_chapter: 2,
      end_chapter: 3,
    },
  ],
  relationship_markers: [
    {
      id: "relationship-1",
      title: "Mara and Theo trust shift",
      detail: "Theo reveals the lock rule.",
      chapter_number: 2,
    },
  ],
}

function defaultQueryResult(data: unknown) {
  return {
    data,
    isLoading: false,
    isError: false,
  }
}

async function renderPage(element: ReactElement = <TimelinePage />) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  await act(async () => {
    root?.render(element)
    await Promise.resolve()
    await Promise.resolve()
  })
}

function text() {
  return container?.textContent ?? ""
}

async function clickButton(label: string) {
  const button = Array.from(container?.querySelectorAll("button") ?? []).find((node) =>
    node.textContent?.includes(label),
  )
  if (!button) throw new Error(`Missing button: ${label}\n${text()}`)

  await act(async () => {
    button.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await Promise.resolve()
  })
}

beforeEach(() => {
  useParamsMock.mockReturnValue({ bookId: "book-1" })
  preferencesState.theme = "light"
  preferencesState.timelineCollapsedSections = {}
  setTimelineCollapsedSectionMock.mockReset()
  patchBookPreferencesMock.mockReset()
  hydrateBookPreferencesMock.mockReset()
  captureMock.mockReset()
  useQueryMock.mockImplementation(({ queryKey }: { queryKey: unknown }) => {
    const key = Array.isArray(queryKey) ? queryKey.join(":") : String(queryKey)
    if (key === "book-1:detail") return defaultQueryResult(bookFixture)
    if (key === "book-1:timeline") return defaultQueryResult(timelineFixture)
    return defaultQueryResult(null)
  })
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
})

describe("timeline runtime page", () => {
  it("renders populated author timeline lanes and collapse handlers", async () => {
    await renderPage()

    expect(captureMock).toHaveBeenCalledWith("major_events_opened", { book_id: "book-1" })
    expect(text()).toContain("Arc timeline")
    expect(text()).toContain("Chapters mapped")
    expect(text()).toContain("Mara")
    expect(text()).toContain("KEEPER")
    expect(text()).toContain("The brass key")
    expect(text()).toContain("The hidden gate")
    expect(text()).toContain("Mara and Theo trust shift")

    await clickButton("Characters")
    await clickButton("Plot Threads")
    await clickButton("Relationship Shifts")

    expect(setTimelineCollapsedSectionMock).toHaveBeenCalledWith("book-1", "characters", true)
    expect(setTimelineCollapsedSectionMock).toHaveBeenCalledWith("book-1", "plotThreads", true)
    expect(setTimelineCollapsedSectionMock).toHaveBeenCalledWith("book-1", "relationships", true)
    expect(patchBookPreferencesMock).toHaveBeenCalled()
  })

  it("renders reader, dark, loading, empty, and error timeline states", async () => {
    preferencesState.theme = "dark"
    useQueryMock.mockImplementation(({ queryKey }: { queryKey: unknown }) => {
      const key = Array.isArray(queryKey) ? queryKey.join(":") : String(queryKey)
      if (key === "book-1:detail") return defaultQueryResult({ ...bookFixture, mode: "reader" })
      if (key === "book-1:timeline") return { data: null, isLoading: true, isError: false }
      return defaultQueryResult(null)
    })
    await renderPage()
    expect(text()).toContain("Major events")
    expect(text()).toContain("Building your timeline...")
    expect(container?.querySelector("main")?.className).toContain("text-slate-100")

    ;(root as Root | null)?.unmount()
    ;(container as HTMLDivElement | null)?.remove()
    root = null
    container = null

    useQueryMock.mockImplementation(({ queryKey }: { queryKey: unknown }) => {
      const key = Array.isArray(queryKey) ? queryKey.join(":") : String(queryKey)
      if (key === "book-1:detail") return defaultQueryResult(bookFixture)
      if (key === "book-1:timeline") return defaultQueryResult({
        chapters: [],
        character_tracks: [],
        thread_tracks: [],
        relationship_markers: [],
      })
      return defaultQueryResult(null)
    })
    await renderPage()
    expect(text()).toContain("No major-event data yet")

    ;(root as Root | null)?.unmount()
    ;(container as HTMLDivElement | null)?.remove()
    root = null
    container = null

    useQueryMock.mockImplementation(({ queryKey }: { queryKey: unknown }) => {
      const key = Array.isArray(queryKey) ? queryKey.join(":") : String(queryKey)
      if (key === "book-1:detail") return defaultQueryResult(bookFixture)
      if (key === "book-1:timeline") return { data: null, isLoading: false, isError: true }
      return defaultQueryResult(null)
    })
    await renderPage()
    expect(text()).toContain("Major events unavailable")
  })
})
