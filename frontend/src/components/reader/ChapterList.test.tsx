import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, describe, expect, it, vi } from "vitest"

import { ChapterList } from "./ChapterList"

let container: HTMLDivElement | null = null
let root: Root | null = null

describe("ChapterList", () => {
  afterEach(() => {
    if (root) {
      act(() => {
        root?.unmount()
      })
    }
    if (container) {
      container.remove()
    }
    container = null
    root = null
  })

  it("renders chapter metadata and actions in one compact row", () => {
    const onOpenChapter = vi.fn()
    const onToggleChapterRead = vi.fn()

    const view = renderChapterList({
      chapters: [
        {
          number: 3,
          title: "River of Glass",
          processed: true,
          read: true,
          intelligence_available: true,
          tags: ["indexed_summary", "beta_ready"],
        },
      ],
      onOpenChapter,
      onToggleChapterRead,
    })

    expect(view.textContent).toContain("Chapters")
    expect(view.textContent).toContain("Ch. 3")
    expect(view.textContent).toContain("River of Glass")
    expect(view.textContent).toContain("Processed")
    expect(view.textContent).toContain("Marked as read")
    expect(view.textContent).toContain("Indexed and ready")
    expect(view.textContent).toContain("Indexed Summary")
    expect(view.textContent).toContain("Beta Ready")
    expect(view.querySelectorAll("article")).toHaveLength(1)
    expect(view.textContent).toContain("Mark unread")

    const buttons = Array.from(view.querySelectorAll("button"))
    const openButton = buttons.find((button) => button.textContent?.trim() === "Open")
    const unreadButton = buttons.find((button) => button.textContent?.trim() === "Mark unread")

    act(() => {
      openButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
      unreadButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    })

    expect(onOpenChapter).toHaveBeenCalledWith(3)
    expect(onToggleChapterRead).toHaveBeenCalledWith(3, false)
  })

  it("shows queued and unread states for unprocessed chapters", () => {
    const view = renderChapterList({
      chapters: [
        {
          number: 8,
          title: null,
          processed: false,
          read: false,
          intelligence_available: false,
        },
      ],
    })

    expect(view.textContent).toContain("Ch. 8")
    expect(view.textContent).toContain("Queued")
    expect(view.textContent).toContain("Unread")
    expect(view.textContent).toContain("Not ready yet")
    expect(view.textContent).toContain("Mark read")
  })

  it("renders optional chapter removal actions", () => {
    const onDeleteChapter = vi.fn()

    const view = renderChapterList({
      chapters: [
        {
          number: 4,
          title: "Broken Road",
          processed: true,
          read: true,
          intelligence_available: true,
        },
      ],
      onDeleteChapter,
    })

    const removeButton = Array.from(view.querySelectorAll("button")).find((button) => button.textContent?.trim() === "Remove")
    act(() => {
      removeButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    })

    expect(onDeleteChapter).toHaveBeenCalledWith(4)
  })

  it("disables the chapter removal action while the chapter is being removed", () => {
    const view = renderChapterList({
      chapters: [
        {
          number: 4,
          title: "Broken Road",
          processed: true,
          read: true,
          intelligence_available: true,
        },
      ],
      deleteBusyKey: "chapter:4",
      onDeleteChapter: vi.fn(),
    })

    const removeButton = Array.from(view.querySelectorAll("button")).find((button) => button.textContent?.trim() === "Removing...")
    expect(removeButton).toBeTruthy()
    expect(removeButton?.disabled).toBe(true)
  })

  it("keeps an available chapter recap beside its chapter row", () => {
    const view = renderChapterList({
      chapters: [{ number: 2, title: "The Gate", processed: true, read: true, intelligence_available: true }],
      summaries: [{ chapter_number: 2, chapter_title: "The Gate", read: true, available: true, content: "Nora accepts the gatekeeper's warning.", key_events: [] }],
    })

    expect(view.textContent).toContain("Read chapter recap")
    expect(view.textContent).toContain("Nora accepts the gatekeeper's warning.")
  })

  it("disables competing writes while keeping chapters available to open", () => {
    const view = renderChapterList({
      chapters: [
        { number: 1, title: "First", processed: true, read: true },
        { number: 2, title: "Second", processed: false, read: false },
      ],
      readBusyKey: "chapter:1",
      onDeleteChapter: vi.fn(),
    })
    const second = view.querySelectorAll("article")[1]
    const buttons = Array.from(second.querySelectorAll("button"))
    expect(buttons.find((button) => button.textContent === "Open")?.disabled).toBe(false)
    expect(buttons.find((button) => button.textContent === "Mark read")?.disabled).toBe(true)
    expect(buttons.find((button) => button.textContent === "Remove")?.disabled).toBe(true)
    expect(view.textContent).toContain("Index status unavailable")
  })

  it("does not offer removal outside the allowed chapter scope", () => {
    const view = renderChapterList({
      chapters: [{ number: 1, title: "First", processed: true, read: true }],
      onDeleteChapter: vi.fn(),
      canDeleteChapter: () => false,
    })
    expect(view.textContent).not.toContain("Remove")
    expect(view.querySelector("h3")?.id).toBe("chapter-title-1")
    expect(view.querySelector("article")?.getAttribute("aria-labelledby")).toBe("chapter-title-1")
  })
})

function renderChapterList({
  chapters,
  summaries = [],
  readBusyKey = null,
  deleteBusyKey = null,
  onOpenChapter = vi.fn(),
  onToggleChapterRead = vi.fn(),
  onDeleteChapter,
  canDeleteChapter,
}: {
  chapters: Array<{
    number: number
    title: string | null
    processed: boolean
    read: boolean
    intelligence_available?: boolean
    tags?: string[]
  }>
  summaries?: Array<{
    chapter_number: number
    chapter_title: string | null
    read: boolean
    available: boolean
    content: string | null
    key_events: Array<{ event: string; importance: number }>
  }>
  deleteBusyKey?: string | null
  readBusyKey?: string | null
  canDeleteChapter?: (chapterNumber: number) => boolean
  onOpenChapter?: (chapterNumber: number) => void
  onToggleChapterRead?: (chapterNumber: number, nextRead: boolean) => void
  onDeleteChapter?: (chapterNumber: number) => void
}) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  act(() => {
    root?.render(
      <ChapterList
        chapters={chapters}
        summaries={summaries}
        unitLabel="Chapter"
        isDark={true}
        readBusyKey={readBusyKey}
        deleteBusyKey={deleteBusyKey}
        onOpenChapter={onOpenChapter}
        onToggleChapterRead={onToggleChapterRead}
        onDeleteChapter={onDeleteChapter}
        canDeleteChapter={canDeleteChapter}
      />
    )
  })

  return container
}
