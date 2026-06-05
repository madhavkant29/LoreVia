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

  it("renders chapter metadata, status chips, and actions from existing chapter data", () => {
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
    expect(view.textContent).toContain("Chapter 3")
    expect(view.textContent).toContain("River of Glass")
    expect(view.textContent).toContain("Processing")
    expect(view.textContent).toContain("Processed")
    expect(view.textContent).toContain("Read status")
    expect(view.textContent).toContain("Marked as read")
    expect(view.textContent).toContain("Intelligence")
    expect(view.textContent).toContain("Indexed and ready")
    expect(view.textContent).toContain("Indexed Summary")
    expect(view.textContent).toContain("Beta Ready")
    expect(view.textContent).toContain("Intel Ready")
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

    expect(view.textContent).toContain("Chapter 8")
    expect(view.textContent).toContain("Queued")
    expect(view.textContent).toContain("Unread")
    expect(view.textContent).toContain("Intel Locked")
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
})

function renderChapterList({
  chapters,
  deleteBusyKey = null,
  onOpenChapter = vi.fn(),
  onToggleChapterRead = vi.fn(),
  onDeleteChapter,
}: {
  chapters: Array<{
    number: number
    title: string | null
    processed: boolean
    read: boolean
    intelligence_available?: boolean
    tags?: string[]
  }>
  deleteBusyKey?: string | null
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
        unitLabel="Chapter"
        isDark={true}
        readBusyKey={null}
        deleteBusyKey={deleteBusyKey}
        onOpenChapter={onOpenChapter}
        onToggleChapterRead={onToggleChapterRead}
        onDeleteChapter={onDeleteChapter}
      />
    )
  })

  return container
}
