import React, { act, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"

import { ChapterText } from "./ChapterText"

vi.mock("next/link", () => ({
  default: ({ href, children, prefetch: _prefetch, ...props }: { href: string; children: ReactNode; prefetch?: boolean }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

describe("ChapterText", () => {
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

  it("opens character context when an html mention token is clicked", () => {
    const onTap = vi.fn()
    container = document.createElement("div")
    document.body.appendChild(container)
    root = createRoot(container)

    act(() => {
      root?.render(
        <ChapterText
          bookId="book-1"
          chapterNum={2}
          chapterTitle="The Ember Gate"
          totalChapters={3}
          textUrl={null}
          textContent={null}
          htmlContent={'<p><span class="mention-token" data-mention="Nora">Nora</span> crossed the bridge.</p>'}
          media={[]}
          characters={[]}
          onTap={onTap}
          onQuoteSelect={() => {}}
          theme="light"
          fontSize={20}
          fontFamily="serif"
          displayStyle="published"
          quoteModeEnabled={false}
          canUseQuoteMode={false}
          canCopyManuscript
        />
      )
    })

    const mention = container.querySelector('[data-mention="Nora"]')
    expect(mention).not.toBeNull()

    act(() => {
      mention?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    })

    expect(onTap).toHaveBeenCalledWith("Nora")
  })
})
