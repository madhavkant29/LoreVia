import React, { act, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"

import { ReaderToolbar } from "./ReaderToolbar"

vi.mock("next/link", () => ({
  default: ({ href, children, prefetch: _prefetch, ...props }: { href: string; children: ReactNode; prefetch?: boolean }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

describe("ReaderToolbar", () => {
  let container: HTMLDivElement | null = null
  let root: Root | null = null

  beforeAll(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  })

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

  it("renders required reader actions and selected toolbar controls", () => {
    const onSummary = vi.fn()
    const onToggleTheme = vi.fn()
    const onSetFontSize = vi.fn()
    const onSetFontFamily = vi.fn()
    const onSetDisplayStyle = vi.fn()
    const onToggleQuoteMode = vi.fn()

    container = document.createElement("div")
    document.body.appendChild(container)
    root = createRoot(container)

    act(() => {
      root?.render(
        <ReaderToolbar
          bookId="book-1"
          chapterNum={3}
          chapterTitle="The Lantern Room"
          totalChapters={5}
          wordsRead={1200}
          totalWords={3600}
          progressPercent={33}
          onSummary={onSummary}
          theme="dark"
          onToggleTheme={onToggleTheme}
          fontSize={20}
          onSetFontSize={onSetFontSize}
          fontFamily="serif"
          onSetFontFamily={onSetFontFamily}
          displayStyle="published"
          onSetDisplayStyle={onSetDisplayStyle}
          quoteModeEnabled={false}
          canUseQuoteMode
          onToggleQuoteMode={onToggleQuoteMode}
        />
      )
    })

    expect(container.textContent).toContain("Back to book")
    expect(container.textContent).toContain("Summary")
    expect(container.textContent).toContain("Graph")
    expect(container.textContent).toContain("Ask with citations")
    expect(container.textContent).toContain("Search passages")
    expect(container.textContent).toContain("The Lantern Room")
    expect(container.textContent).toContain("33%")

    const publishedButton = Array.from(container.querySelectorAll("button")).find((button) => button.textContent === "Published")
    const serifButton = Array.from(container.querySelectorAll("button")).find((button) => button.textContent === "serif")
    expect(publishedButton?.getAttribute("aria-pressed")).toBe("true")
    expect(serifButton?.getAttribute("aria-pressed")).toBe("true")
  })
})
