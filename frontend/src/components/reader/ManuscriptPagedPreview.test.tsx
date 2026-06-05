// @vitest-environment jsdom

import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest"

import { getManuscriptPreviewLayout, getManuscriptPreviewPageExtentPx, millimetersToPixels } from "@/lib/utils/manuscriptPreview"

import { ManuscriptPagedPreview } from "./ManuscriptPagedPreview"

class ResizeObserverMock {
  callback: ResizeObserverCallback

  constructor(callback: ResizeObserverCallback) {
    this.callback = callback
  }

  observe() {}

  unobserve() {}

  disconnect() {}

  trigger() {
    this.callback([], this as unknown as ResizeObserver)
  }
}

describe("ManuscriptPagedPreview", () => {
  let container: HTMLDivElement | null = null
  let root: Root | null = null
  let observers: ResizeObserverMock[] = []

  beforeAll(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    globalThis.PointerEvent = MouseEvent as typeof PointerEvent
  })

  beforeEach(() => {
    observers = []
    globalThis.ResizeObserver = class {
      private observer: ResizeObserverMock

      constructor(callback: ResizeObserverCallback) {
        this.observer = new ResizeObserverMock(callback)
        observers.push(this.observer)
      }

      observe() {
        this.observer.observe()
      }

      unobserve() {
        this.observer.unobserve()
      }

      disconnect() {
        this.observer.disconnect()
      }
    } as unknown as typeof ResizeObserver
  })

  afterEach(() => {
    if (root) {
      act(() => {
        root?.unmount()
      })
    }
    container?.remove()
    container = null
    root = null
  })

  it("lets the preview shell drag horizontally between pages", () => {
    container = document.createElement("div")
    document.body.appendChild(container)
    root = createRoot(container)

    act(() => {
      root?.render(
        <ManuscriptPagedPreview
          sections={[
            { id: "section-1", title: "Chapter 1", html: "<p>Nora crossed the ember gate with ash on her sleeves.</p>" },
            { id: "section-2", title: "Chapter 2", html: "<p>Morning came with a hard white sun and the smell of metal in the rain.</p>" },
          ]}
          preset="standard_manuscript"
          firstLineIndent={false}
          lineHeight={2}
          isDark={false}
        />
      )
    })

    const shell = container.querySelector('[data-testid="manuscript-paged-preview-shell"]') as HTMLDivElement | null
    expect(shell).not.toBeNull()
    if (!shell) return

    const layout = getManuscriptPreviewLayout("standard_manuscript")
    const pageExtent = getManuscriptPreviewPageExtentPx(layout)
    const pageWidth = millimetersToPixels(layout.pageWidthMm)
    const scrollTo = vi.fn(({ left }: { left: number }) => {
      shell.scrollLeft = left
    })

    Object.defineProperty(shell, "clientWidth", { configurable: true, get: () => pageWidth })
    Object.defineProperty(shell, "scrollWidth", { configurable: true, get: () => pageExtent * 2 - layout.pageGapPx - 1 })
    Object.defineProperty(shell, "scrollLeft", { configurable: true, writable: true, value: 0 })
    Object.defineProperty(shell, "setPointerCapture", { configurable: true, value: vi.fn() })
    Object.defineProperty(shell, "releasePointerCapture", { configurable: true, value: vi.fn() })
    Object.defineProperty(shell, "scrollTo", { configurable: true, value: scrollTo })

    act(() => {
      observers.forEach((observer) => observer.trigger())
    })

    expect(container.textContent).toContain("Page 1 of 2")

    act(() => {
      shell.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, button: 0, clientX: pageExtent }))
      shell.dispatchEvent(new PointerEvent("pointermove", { bubbles: true, button: 0, clientX: 0 }))
      shell.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, button: 0, clientX: 0 }))
    })

    expect(scrollTo).toHaveBeenCalledWith({ left: pageExtent, behavior: "smooth" })
    expect(container.textContent).toContain("Page 2 of 2")
  })
})
