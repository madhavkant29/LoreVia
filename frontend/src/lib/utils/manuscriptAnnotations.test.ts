import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import {
  applyAnnotationHighlights,
  buildAnnotationSelectionAnchor,
  cleanAnnotationText,
  clearAnnotationHighlights,
  resolveAnnotationRange,
  scrollAnnotationRangeIntoView,
} from "./manuscriptAnnotations"

beforeEach(() => {
  Object.defineProperty(globalThis, "CSS", { configurable: true, value: {} })
})

afterEach(() => {
  document.body.innerHTML = ""
  window.getSelection()?.removeAllRanges()
  vi.restoreAllMocks()
  Reflect.deleteProperty(globalThis, "Highlight")
  Reflect.deleteProperty(globalThis, "CSS")
})

describe("manuscript annotation utilities", () => {
  it("normalizes annotation text safely", () => {
    expect(cleanAnnotationText("  Nora   crossed \n the gate ")).toBe("Nora crossed the gate")
  })

  it("resolves ranges from exact offsets when the manuscript has not moved", () => {
    document.body.innerHTML = "<div id='editor'>Nora crossed the ember gate before dawn.</div>"
    const editor = document.getElementById("editor") as HTMLElement

    const range = resolveAnnotationRange(editor, {
      quote: "crossed the ember gate",
      anchor_context_before: "Nora",
      anchor_context_after: "before dawn",
      start_offset: 5,
      end_offset: 27,
    })

    expect(range?.toString()).toBe("crossed the ember gate")
  })

  it("falls back to context matching when offsets drift", () => {
    document.body.innerHTML = "<div id='editor'>The guard hesitated. Nora crossed the ember gate before dawn. Later, Nora crossed the ember gate again.</div>"
    const editor = document.getElementById("editor") as HTMLElement

    const range = resolveAnnotationRange(editor, {
      quote: "Nora crossed the ember gate",
      anchor_context_before: "guard hesitated",
      anchor_context_after: "before dawn",
      start_offset: 0,
      end_offset: 0,
    })

    expect(range?.toString()).toBe("Nora crossed the ember gate")
  })

  it("builds a normalized selection anchor with surrounding context", () => {
    document.body.innerHTML = "<div id='editor'>Before the gate, <span>Nora   crossed</span> after dawn.</div>"
    const editor = document.getElementById("editor") as HTMLElement
    const text = editor.querySelector("span")?.firstChild as Text
    const range = document.createRange()
    range.setStart(text, 0)
    range.setEnd(text, text.length)
    const selection = window.getSelection()
    selection?.removeAllRanges()
    selection?.addRange(range)

    expect(buildAnnotationSelectionAnchor(editor)).toEqual({
      quote: "Nora crossed",
      anchorContextBefore: "Before the gate,",
      anchorContextAfter: "after dawn.",
      startOffset: 17,
      endOffset: 31,
    })
  })

  it("rejects missing, collapsed, outside, and whitespace-only selections", () => {
    document.body.innerHTML = "<div id='editor'>Inside</div><div id='outside'>Outside</div>"
    const editor = document.getElementById("editor") as HTMLElement
    const outside = document.getElementById("outside")?.firstChild as Text
    const selection = window.getSelection()
    selection?.removeAllRanges()
    expect(buildAnnotationSelectionAnchor(editor)).toBeNull()

    const collapsed = document.createRange()
    collapsed.setStart(editor.firstChild as Text, 1)
    collapsed.collapse(true)
    selection?.addRange(collapsed)
    expect(buildAnnotationSelectionAnchor(editor)).toBeNull()

    selection?.removeAllRanges()
    const outsideRange = document.createRange()
    outsideRange.selectNodeContents(outside)
    selection?.addRange(outsideRange)
    expect(buildAnnotationSelectionAnchor(editor)).toBeNull()

    editor.textContent = "   "
    selection?.removeAllRanges()
    const whitespaceRange = document.createRange()
    whitespaceRange.selectNodeContents(editor)
    selection?.addRange(whitespaceRange)
    expect(buildAnnotationSelectionAnchor(editor)).toBeNull()
  })

  it("registers open, resolved, and active CSS highlights and returns their ranges", () => {
    document.body.innerHTML = "<div id='editor'>Nora entered. Ilya followed.</div>"
    const editor = document.getElementById("editor") as HTMLElement
    const highlights = { delete: vi.fn(), set: vi.fn() }
    class HighlightMock {
      ranges: Range[]
      constructor(...ranges: Range[]) {
        this.ranges = ranges
      }
    }
    Object.defineProperty(globalThis.CSS, "highlights", { configurable: true, value: highlights })
    Object.defineProperty(globalThis, "Highlight", { configurable: true, value: HighlightMock })

    const ranges = applyAnnotationHighlights(editor, [
      {
        id: "open",
        quote: "Nora entered",
        status: "open",
        anchor_context_before: null,
        anchor_context_after: null,
        start_offset: 0,
        end_offset: 12,
      },
      {
        id: "resolved",
        quote: "Ilya followed",
        status: "resolved",
        anchor_context_before: null,
        anchor_context_after: null,
        start_offset: 14,
        end_offset: 27,
      },
      {
        id: "missing",
        quote: "Not present",
        status: "open",
        anchor_context_before: null,
        anchor_context_after: null,
        start_offset: null,
        end_offset: null,
      },
    ] as never, "resolved")

    expect([...ranges.keys()]).toEqual(["open", "resolved"])
    expect(highlights.delete).toHaveBeenCalledTimes(3)
    expect(highlights.set.mock.calls.map(([name]) => name)).toEqual([
      "lorevia-annotation-open",
      "lorevia-annotation-resolved",
      "lorevia-annotation-active",
    ])
  })

  it("clears highlights and handles unavailable browser APIs", () => {
    const highlights = { delete: vi.fn(), set: vi.fn() }
    clearAnnotationHighlights(highlights)
    expect(highlights.delete).toHaveBeenCalledTimes(3)

    expect(applyAnnotationHighlights(null, [], null)).toEqual(new Map())
    clearAnnotationHighlights(null as never)

    document.body.innerHTML = "<div id='editor'>Nora entered.</div>"
    const editor = document.getElementById("editor") as HTMLElement
    Object.defineProperty(globalThis.CSS, "highlights", { configurable: true, value: highlights })
    expect(applyAnnotationHighlights(editor, [{
      id: "open",
      quote: "Nora",
      status: "open",
      anchor_context_before: null,
      anchor_context_after: null,
      start_offset: 0,
      end_offset: 4,
    }] as never, null).has("open")).toBe(true)
    expect(highlights.set).not.toHaveBeenCalled()
  })

  it("scrolls visible ranges with a fixed header offset and ignores empty rectangles", () => {
    const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => undefined)
    const visibleRange = { getBoundingClientRect: () => ({ top: 250, width: 20, height: 10 }) } as Range
    scrollAnnotationRangeIntoView(visibleRange)
    expect(scrollTo).toHaveBeenCalledWith({ top: 90, behavior: "smooth" })

    scrollTo.mockClear()
    const emptyRange = { getBoundingClientRect: () => ({ top: 250, width: 0, height: 0 }) } as Range
    scrollAnnotationRangeIntoView(emptyRange)
    expect(scrollTo).not.toHaveBeenCalled()
  })

  it("returns null for empty text, invalid offsets, and unmatched quotes", () => {
    const editor = document.createElement("div")
    expect(resolveAnnotationRange(editor, {
      quote: "Nora",
      anchor_context_before: null,
      anchor_context_after: null,
      start_offset: 0,
      end_offset: 4,
    })).toBeNull()

    editor.textContent = "Nora entered."
    expect(resolveAnnotationRange(editor, {
      quote: "Nora",
      anchor_context_before: null,
      anchor_context_after: null,
      start_offset: -1,
      end_offset: 4,
    })?.toString()).toBe("Nora")
    expect(resolveAnnotationRange(editor, {
      quote: "Missing",
      anchor_context_before: null,
      anchor_context_after: null,
      start_offset: 0,
      end_offset: 7,
    })).toBeNull()
  })
})
