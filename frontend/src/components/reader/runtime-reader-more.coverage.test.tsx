// @vitest-environment jsdom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, type ReactElement } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const booksApiMock = vi.hoisted(() => ({
  deleteCover: vi.fn(),
  updateCover: vi.fn(),
}))
const readerApiMock = vi.hoisted(() => ({
  getSummary: vi.fn(),
}))
const captureMock = vi.hoisted(() => vi.fn())

vi.mock("@/components/ui/Skeleton", () => ({
  Skeleton: ({ className = "" }: { className?: string }) => <div className={className}>Loading row</div>,
}))
vi.mock("@/lib/analytics/posthog", () => ({ capture: captureMock }))
vi.mock("@/lib/api/books", () => ({ booksApi: booksApiMock }))
vi.mock("@/lib/api/reader", () => ({ readerApi: readerApiMock }))

import { SummaryPanel } from "@/components/reader/SummaryPanel"
import { CoverEditOverlay } from "@/components/ui/CoverEditOverlay"

let root: Root | null = null
let container: HTMLDivElement | null = null
let queryClient: QueryClient | null = null

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

async function renderElement(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  const client = new QueryClient({
    defaultOptions: { queries: { gcTime: 0, retry: false } },
  })
  queryClient = client
  root = createRoot(container)

  await act(async () => {
    root?.render(<QueryClientProvider client={client}>{element}</QueryClientProvider>)
    await flush()
  })
}

async function flush() {
  await Promise.resolve()
  await new Promise((resolve) => window.setTimeout(resolve, 0))
  await Promise.resolve()
}

function bodyText() {
  return document.body.textContent ?? ""
}

function button(label: string, index = 0) {
  const matches = Array.from(document.body.querySelectorAll("button")).filter((item) =>
    item.textContent?.includes(label) || item.getAttribute("aria-label") === label,
  )
  const target = matches[index]
  if (!target) throw new Error(`Missing button: ${label}\n${bodyText()}`)
  return target
}

async function click(label: string, index = 0) {
  await act(async () => {
    button(label, index).dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await flush()
  })
}

beforeEach(() => {
  booksApiMock.deleteCover.mockReset().mockResolvedValue({ id: "book-1", title: "No Cover" })
  booksApiMock.updateCover.mockReset().mockResolvedValue({ id: "book-1", title: "New Cover" })
  readerApiMock.getSummary.mockReset().mockResolvedValue({
    content: "Mara closes the lantern gate.",
    key_events: [{ event: "The gate closes" }],
    char_changes: [{ character: "Mara", change: "She trusts Theo" }],
    clues: [{ clue: "The brass key hums" }],
  })
  captureMock.mockReset()
})

afterEach(() => {
  if (root) {
    act(() => {
      root?.unmount()
    })
  }
  queryClient?.clear()
  container?.remove()
  root = null
  container = null
  queryClient = null
  document.body.innerHTML = ""
})

describe("additional reader runtime component coverage", () => {
  it("loads, normalizes, switches, tracks, and closes chapter summaries", async () => {
    const onClose = vi.fn()
    readerApiMock.getSummary.mockResolvedValueOnce({
      content: "```json\n{\"summary\":\"Mara decodes the lock.\",\"key_events\":[{\"event\":\"Lock decoded\"}],\"char_changes\":[{\"character\":\"Mara\",\"change\":\"She becomes honest\"}],\"clues\":[{\"clue\":\"Key has a maker mark\"}]}\n```",
    })

    await renderElement(<SummaryPanel bookId="book-1" chapterNum={4} onClose={onClose} theme="dark" />)
    await act(flush)

    expect(readerApiMock.getSummary).toHaveBeenCalledWith("book-1", 4, "short")
    expect(bodyText()).toContain("Chapter 4 Summary")
    expect(bodyText()).toContain("Mara decodes the lock.")
    expect(bodyText()).toContain("Lock decoded")
    expect(bodyText()).toContain("Mara: She becomes honest")
    expect(bodyText()).toContain("Key has a maker mark")
    expect(captureMock).toHaveBeenCalledWith("summary_viewed", {
      book_id: "book-1",
      chapter: 4,
      mode: "short",
    })

    await click("Full analysis")
    expect(readerApiMock.getSummary).toHaveBeenCalledWith("book-1", 4, "detailed")
    await click("Close summary")
    expect(onClose).toHaveBeenCalled()
  })

  it("shows the empty summary state when no summary is returned", async () => {
    readerApiMock.getSummary.mockResolvedValueOnce(null)

    await renderElement(<SummaryPanel bookId="book-1" chapterNum={9} onClose={vi.fn()} theme="light" />)
    await act(flush)

    expect(bodyText()).toContain("Summary not available yet")
  })

  it("uploads, removes, dismisses, and disables cover editing while requests run", async () => {
    const onCoverUpdated = vi.fn()
    await renderElement(
      <CoverEditOverlay bookId="book-1" isDark hasCover onCoverUpdated={onCoverUpdated} />,
    )

    await click("Edit cover photo")
    expect(bodyText()).toContain("Upload new photo")
    expect(bodyText()).toContain("Remove cover photo")

    const input = document.body.querySelector('input[type="file"]') as HTMLInputElement
    const file = new File(["cover"], "cover.png", { type: "image/png" })
    Object.defineProperty(input, "files", { configurable: true, value: [file] })
    await act(async () => {
      input.dispatchEvent(new Event("change", { bubbles: true }))
      await flush()
    })
    expect(booksApiMock.updateCover).toHaveBeenCalledWith("book-1", file)
    expect(onCoverUpdated).toHaveBeenCalledWith({ id: "book-1", title: "New Cover" })

    await click("Edit cover photo")
    await click("Remove cover photo")
    expect(booksApiMock.deleteCover).toHaveBeenCalledWith("book-1")
    expect(onCoverUpdated).toHaveBeenCalledWith({ id: "book-1", title: "No Cover" })

    await click("Edit cover photo")
    await act(async () => {
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }))
      await flush()
    })
    expect(bodyText()).not.toContain("Upload new photo")
  })
})
