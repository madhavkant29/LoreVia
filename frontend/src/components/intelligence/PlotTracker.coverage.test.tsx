// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const useQueryMock = vi.hoisted(() => vi.fn())
const readerApiMock = vi.hoisted(() => ({
  getPlotThreads: vi.fn(),
  getPlotThreadsPage: vi.fn(),
  getPlotThread: vi.fn(),
  getChapterList: vi.fn(),
  updatePlotThread: vi.fn(),
}))
const booksApiMock = vi.hoisted(() => ({
  listVaultNotes: vi.fn(),
}))
const saveContextualVaultNoteMock = vi.hoisted(() => vi.fn())

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a>,
}))
vi.mock("@tanstack/react-query", () => ({ useQuery: useQueryMock, useQueryClient: () => ({ setQueryData: vi.fn() }) }))
vi.mock("@/lib/api/books", () => ({ booksApi: booksApiMock }))
vi.mock("@/lib/api/reader", () => ({ readerApi: readerApiMock }))
vi.mock("@/lib/query/cacheKeys", () => ({
  asQueryKey: (value: unknown) => value,
  readerCacheKey: (...parts: string[]) => parts.join(":"),
}))
vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: () => ({ theme: "dark" }),
}))
vi.mock("@/lib/utils/notes", () => ({ saveContextualVaultNote: saveContextualVaultNoteMock }))

import { PlotTracker } from "@/components/intelligence/PlotTracker"

let root: Root | null = null
let container: HTMLDivElement | null = null

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

beforeEach(() => {
  readerApiMock.getPlotThreads.mockResolvedValue(plotThreads())
  readerApiMock.updatePlotThread.mockImplementation(async (_book, id, payload) => ({ ...plotThreads().find((thread) => thread.id === id), ...payload }))
  booksApiMock.listVaultNotes.mockResolvedValue([])
  saveContextualVaultNoteMock.mockResolvedValue({})
  useQueryMock.mockImplementation(({ queryKey }: { queryKey: string }) => ({
    data: String(queryKey).includes(":chapters") ? { chapters: [{ number: 1 }, { number: 4 }] } : String(queryKey).includes(":detail:") ? plotThreads()[0] : plotThreads(),
    isLoading: false,
    refetch: vi.fn().mockResolvedValue({}),
  }))
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

describe("PlotTracker", () => {
  it("renders compact, dashboard, save note, status, and vault flows", async () => {
    await render(<PlotTracker bookId="book-1" chapter={2} mode="compact" />)
    expect(text()).toContain("Missing gate oath")
    expect(text()).toContain("View all plot threads")

    await rerender(<PlotTracker bookId="book-1" mode="dashboard" />)
    expect(text()).toContain("Needs attention")
    await click("Missing gate oath")
    expect(text()).toContain("Thread details")
    await click("Save to notes")
    expect(saveContextualVaultNoteMock).toHaveBeenCalled()
    setSelectValue("select", "resolved")
    setTextareaValue("textarea", "Resolve this in the finale.")
    await click("Save changes")
    expect(readerApiMock.updatePlotThread).toHaveBeenCalledWith("book-1", "thread-1", {
      note: "Resolve this in the finale.",
      status: "resolved",
    })

    useQueryMock.mockReturnValue({ data: [], isLoading: false, refetch: vi.fn() })
    await rerender(<PlotTracker key="empty" bookId="book-1" />)
    expect(text()).toContain("No plot threads yet")

    useQueryMock.mockReturnValue({ data: [], isLoading: true, refetch: vi.fn() })
    await rerender(<PlotTracker key="loading" bookId="book-1" />)
    expect(text()).toContain("Loading plot threads")
  })

  it("retains failed edits and blocks navigation or closing until discarded", async () => {
    readerApiMock.updatePlotThread.mockRejectedValueOnce(new Error("offline"))
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false)
    await render(<PlotTracker bookId="book-1" mode="dashboard" />)
    await click("Missing gate oath")
    await act(async () => { setTextareaValue("textarea", "Keep this draft"); await flush() })
    await click("Save changes")
    expect(text()).toContain("Changes could not be saved")
    await click("Close")
    expect(confirm).toHaveBeenCalled()
    expect(container?.querySelector("textarea")?.value).toBe("Keep this draft")
    const unload = new Event("beforeunload", { cancelable: true })
    window.dispatchEvent(unload)
    expect(unload.defaultPrevented).toBe(true)
    const link = container?.querySelector('a[href="/book-1/notes"]')
    const navigate = new MouseEvent("click", { bubbles: true, cancelable: true })
    link?.dispatchEvent(navigate)
    expect(navigate.defaultPrevented).toBe(true)
    await click("Discard changes")
    expect(container?.querySelector("textarea")?.value).toBe("Track the oath.")
    await click("Close")
    expect(container?.querySelector("textarea")).toBeNull()
    confirm.mockRestore()
  })

  it("preserves edits during a refreshed detail snapshot and handles copy failures", async () => {
    await render(<PlotTracker bookId="book-1" mode="dashboard" />)
    await click("Missing gate oath")
    await act(async () => { setTextareaValue("textarea", "Unsaved reminder"); await flush() })
    await rerender(<PlotTracker bookId="book-1" mode="dashboard" />)
    expect(container?.querySelector("textarea")?.value).toBe("Unsaved reminder")
    saveContextualVaultNoteMock.mockRejectedValueOnce(new Error("offline"))
    await click("Save to notes")
    expect(text()).toContain("The copy could not be saved")
    await click("Save to notes")
    expect(text()).toContain("Copied to Notes")
    expect(saveContextualVaultNoteMock).toHaveBeenLastCalledWith(expect.objectContaining({ content: expect.stringContaining("Unsaved reminder") }))
    expect(container?.querySelector("textarea")?.value).toBe("Unsaved reminder")
  })

  it("distinguishes loading failures from empty results and retries", async () => {
    const refetch = vi.fn()
    useQueryMock.mockReturnValue({ data: undefined, isError: true, isLoading: false, refetch })
    await render(<PlotTracker bookId="book-1" mode="dashboard" />)
    expect(text()).toContain("Plot threads could not be loaded")
    expect(text()).not.toContain("No plot threads yet")
    await click("Retry plot threads")
    expect(refetch).toHaveBeenCalled()
  })

  it("locks concurrent saves until the current request finishes", async () => {
    let finish: ((value: unknown) => void) | undefined
    readerApiMock.updatePlotThread.mockImplementationOnce(() => new Promise((resolve) => { finish = resolve }))
    await render(<PlotTracker bookId="book-1" mode="dashboard" />)
    await click("Missing gate oath")
    await act(async () => { setTextareaValue("textarea", "One correction"); await flush() })
    const save = Array.from(container?.querySelectorAll("button") ?? []).find((button) => button.textContent === "Save changes")
    await act(async () => { save?.click(); save?.click(); await flush() })
    expect(readerApiMock.updatePlotThread).toHaveBeenCalledTimes(1)
    expect(container?.querySelector("fieldset")?.disabled).toBe(true)
    await act(async () => { finish?.({ ...plotThreads()[0], note: "One correction" }); await flush() })
    expect(text()).toContain("Thread changes saved.")
  })
})

async function render(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root?.render(element)
    await flush()
  })
}

async function rerender(element: ReactElement) {
  await act(async () => {
    root?.render(element)
    await flush()
  })
}

async function flush() {
  await Promise.resolve()
  await new Promise((resolve) => window.setTimeout(resolve, 0))
  await Promise.resolve()
}

function text() {
  return container?.textContent ?? ""
}

async function click(label: string, index = 0) {
  const button = Array.from(container?.querySelectorAll("button") ?? []).filter((node) => node.textContent?.includes(label))[index]
  if (!button) throw new Error(`Missing button ${label}\n${text()}`)
  await act(async () => {
    button.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await flush()
  })
}

function setTextareaValue(selector: string, value: string) {
  const input = container?.querySelector(selector) as HTMLTextAreaElement | null
  if (!input) throw new Error(`Missing textarea ${selector}`)
  const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set
  setter?.call(input, value)
  input.dispatchEvent(new Event("input", { bubbles: true }))
}

function setSelectValue(selector: string, value: string) {
  const input = container?.querySelector(selector) as HTMLSelectElement | null
  if (!input) throw new Error(`Missing select ${selector}`)
  input.value = value
  input.dispatchEvent(new Event("change", { bubbles: true }))
}

function plotThreads() {
  return [
    {
      id: "thread-1",
      title: "Missing gate oath",
      type: "continuity",
      status: "developing",
      description: "The oath is introduced but not paid off.",
      first_mentioned: 1,
      last_mentioned: 4,
      resolved_at: null,
      related_characters: ["Mara", "Joren"],
      mention_count: 5,
      risk: "May feel abandoned.",
      suggested_action: "Resolve before the finale.",
      note: "Track the oath.",
    },
    {
      id: "thread-2",
      title: "Ash prophecy",
      type: "prophecy",
      status: "resolved",
      description: "Prophecy thread closes.",
      first_mentioned: 2,
      last_mentioned: 7,
      resolved_at: 8,
      related_characters: [],
      mention_count: 2,
      risk: "",
      suggested_action: "",
      note: "",
    },
  ]
}
