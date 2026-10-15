import { act, useRef } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { useReaderPosition } from "./useReaderPosition"

describe("useReaderPosition", () => {
  let root: Root
  let host: HTMLDivElement
  let surface: HTMLDivElement
  const save = vi.fn()
  let value: ReturnType<typeof useReaderPosition>
  beforeEach(() => { vi.useFakeTimers(); localStorage.clear(); save.mockReset(); host = document.createElement("div"); document.body.append(host); root = createRoot(host) })
  afterEach(() => { act(() => root.unmount()); host.remove(); vi.restoreAllMocks(); vi.useRealTimers() })
  function Reader() {
    const scrollRef = useRef<HTMLDivElement>(null)
    value = useReaderPosition({ bookId: "sky--book-1", chapterNum: 2, chapterTitle: "Gate", ready: true, scrollRef, saveProgress: save })
    return <div ref={(element) => {
      scrollRef.current = element
      if (!element) return
      surface = element
      Object.defineProperty(element, "clientHeight", { configurable: true, value: 500 })
      element.getBoundingClientRect = () => ({ top: 0 }) as DOMRect
      element.querySelector<HTMLElement>("[data-chapter-content]")!.getBoundingClientRect = () => ({ bottom: 2000 - element.scrollTop }) as DOMRect
    }}><article data-chapter-content>Chapter</article><div>Comments do not count as reading text</div></div>
  }
  it("restores a bookmark without a zero write and saves actual scrolling", () => {
    localStorage.setItem("reader-bookmark:book-1", JSON.stringify({ bookId: "book-1", chapter: 2, scrollPct: 0.5 }))
    act(() => root.render(<Reader />))
    expect(surface.scrollTop).toBe(750); expect(value.scrollPct).toBe(0.5); expect(save).not.toHaveBeenCalled()
    act(() => { surface.dispatchEvent(new Event("wheel")); surface.scrollTop = 900; surface.dispatchEvent(new Event("scroll")); vi.advanceTimersByTime(350) })
    expect(save).toHaveBeenCalledWith(0.6)
    expect(JSON.parse(localStorage.getItem("reader-bookmark:book-1")!).scrollPct).toBe(0.6)
  })
  it("keeps reading operable when browser storage throws", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("Blocked") })
    act(() => root.render(<Reader />))
    expect(value.storageError).toBe(true)
    expect(value.scrollPct).toBe(0)
  })
})
