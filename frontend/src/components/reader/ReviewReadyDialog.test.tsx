// @vitest-environment jsdom

import { act } from "react"
import type { ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import type { Book } from "@/types/book"

vi.mock("next/link", () => ({
  default: ({ children, href, onClick }: { children: ReactNode; href: string; onClick: () => void }) =>
    <a href={href} onClick={(event) => { event.preventDefault(); onClick() }}>{children}</a>,
}))

vi.mock("@/components/ui/Dialog", () => ({
  Dialog: ({ open, title, footer, onClose }: { open: boolean; title: ReactNode; footer: ReactNode; onClose: () => void }) =>
    open ? <div role="dialog">{title}{footer}<button onClick={onClose}>Close</button></div> : null,
}))

import { ReviewReadyDialog, reviewReadyPromptKey } from "./ReviewReadyDialog"

let root: Root | null = null
let container: HTMLDivElement | null = null

function makeBook(status = "ready", isFullyReady = true): Book {
  return { id: "book-1", status, processing: { processing_run_id: "run-1", is_fully_ready: isFullyReady } } as Book
}

function renderDialog(book: Book | null, enabled = true, hasReviewMaterial = true) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => root?.render(<ReviewReadyDialog book={book} bookId="book-1" enabled={enabled} hasReviewMaterial={hasReviewMaterial} />))
}

beforeEach(() => window.localStorage.clear())
afterEach(() => {
  act(() => root?.unmount())
  container?.remove()
  root = null
  container = null
  vi.restoreAllMocks()
})

describe("ReviewReadyDialog", () => {
  it("waits for the entire manuscript to be ready, not only extraction", () => {
    expect(reviewReadyPromptKey(makeBook("processing"), true)).toBeNull()
    expect(reviewReadyPromptKey(makeBook("ready", false), true)).toBeNull()
    expect(reviewReadyPromptKey(null, true)).toBeNull()
    expect(reviewReadyPromptKey(makeBook(), false)).toBeNull()
    renderDialog(makeBook("processing"))
    expect(container?.querySelector('[role="dialog"]')).toBeNull()
  })

  it("waits until at least one chapter report is available", () => {
    const book = makeBook()
    renderDialog(book, true, false)
    expect(container?.querySelector('[role="dialog"]')).toBeNull()
    act(() => root?.render(<ReviewReadyDialog book={book} bookId="book-1" enabled hasReviewMaterial />))
    expect(container?.querySelector('[role="dialog"]')).toBeTruthy()
  })

  it("shows both review destinations once per completed run", () => {
    const book = makeBook()
    renderDialog(book)

    expect(container?.querySelector('[role="dialog"]')).toBeTruthy()
    expect(container?.querySelector('a[href="/book-1/advisor?tab=scan"]')).toBeTruthy()
    expect(container?.querySelector('a[href="/book-1/analysis?view=chapters"]')).toBeTruthy()

    act(() => (container?.querySelector("button") as HTMLButtonElement).click())
    expect(window.localStorage.getItem(reviewReadyPromptKey(book, true)!)).toBe("dismissed")
    expect(container?.querySelector('[role="dialog"]')).toBeNull()
  })

  it("does not open for a reader without author access or a dismissed run", () => {
    const book = makeBook()
    window.localStorage.setItem(reviewReadyPromptKey(book, true)!, "dismissed")
    renderDialog(book)
    expect(container?.querySelector('[role="dialog"]')).toBeNull()
    act(() => root?.render(<ReviewReadyDialog book={book} bookId="book-1" enabled={false} hasReviewMaterial />))
    expect(container?.querySelector('[role="dialog"]')).toBeNull()
  })

  it("keeps the destination link mounted until navigation can complete", () => {
    const book = makeBook()
    renderDialog(book)

    act(() => {
      container?.querySelector<HTMLAnchorElement>('a[href="/book-1/advisor?tab=scan"]')?.click()
    })

    expect(window.localStorage.getItem(reviewReadyPromptKey(book, true)!)).toBe("dismissed")
    expect(container?.querySelector('a[href="/book-1/advisor?tab=scan"]')).toBeTruthy()
  })

  it("still opens and can be dismissed when review prompt storage is blocked", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new DOMException("Blocked", "SecurityError") })
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new DOMException("Blocked", "SecurityError") })

    renderDialog(makeBook())
    expect(container?.querySelector('[role="dialog"]')).toBeTruthy()

    act(() => (container?.querySelector("button") as HTMLButtonElement).click())
    expect(container?.querySelector('[role="dialog"]')).toBeNull()
  })
})
