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
  const originalFetch = globalThis.fetch

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
    Object.defineProperty(globalThis, "fetch", {
      configurable: true,
      value: originalFetch,
    })
  })

  function defaultProps(overrides: Partial<React.ComponentProps<typeof ChapterText>> = {}) {
    return {
      bookId: "book-1",
      chapterNum: 2,
      chapterTitle: "The Ember Gate",
      totalChapters: 3,
      textUrl: null,
      textContent: "Mara crossed the bridge with Theo.\n\nThe lantern hummed.",
      htmlContent: null,
      media: [],
      characters: [{ id: "char-1", name: "Mara", aliases: ["Keeper"], role: "mc", first_chapter: 1, personality_tags: [] }],
      onTap: vi.fn(),
      onQuoteSelect: vi.fn(),
      theme: "light",
      fontSize: 20,
      fontFamily: "serif",
      displayStyle: "relaxed",
      quoteModeEnabled: false,
      canUseQuoteMode: false,
      canCopyManuscript: true,
      ...overrides,
    } satisfies React.ComponentProps<typeof ChapterText>
  }

  function renderChapter(overrides: Partial<React.ComponentProps<typeof ChapterText>> = {}) {
    container = document.createElement("div")
    document.body.appendChild(container)
    root = createRoot(container)

    act(() => {
      root?.render(<ChapterText {...defaultProps(overrides)} />)
    })
  }

  async function flush() {
    await act(async () => {
      await Promise.resolve()
      await new Promise((resolve) => window.setTimeout(resolve, 0))
      await Promise.resolve()
    })
  }

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

  it("resolves relative chapter media urls against the current origin", () => {
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
          textContent={"[[IMAGE:1]]"}
          htmlContent={null}
          media={[{
            marker: "[[IMAGE:1]]",
            asset_type: "image",
            url: "/api/v1/reader/media/demo",
            content_base64: null,
            content_type: "image/png",
            sort_order: 0,
            caption: "Demo media",
          }]}
          characters={[]}
          onTap={() => {}}
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

    const image = container.querySelector("img")
    expect(image?.getAttribute("src")).toBe(new URL("/api/v1/reader/media/demo", window.location.origin).toString())
  })

  it("renders base64 media when url is unavailable", () => {
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
          textContent={"[[IMAGE:1]]"}
          htmlContent={null}
          media={[{
            marker: "[[IMAGE:1]]",
            asset_type: "image",
            url: null,
            content_base64: "YWJj",
            content_type: "image/png",
            sort_order: 0,
            caption: "Fallback media",
          }]}
          characters={[]}
          onTap={() => {}}
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

    const image = container.querySelector("img")
    expect(image?.getAttribute("src")).toBe("data:image/png;base64,YWJj")
  })

  it("fetches remote chapter text and annotates character aliases in relaxed layout", async () => {
    const onTap = vi.fn()
    Object.defineProperty(globalThis, "fetch", {
      configurable: true,
      value: vi.fn().mockResolvedValue({
        text: () => Promise.resolve("Keeper stood beside the lantern."),
      }),
    })

    renderChapter({ textContent: null, textUrl: "/chapter.txt", onTap })
    expect(container?.textContent).toContain("Loading chapter text")
    await flush()

    expect(globalThis.fetch).toHaveBeenCalledWith("/chapter.txt")
    expect(container?.textContent).toContain("Keeper stood beside the lantern.")
    expect(container?.textContent).toContain("5 words in this chapter")

    const mention = container?.querySelector('[title="Tap for context: Keeper"]')
    expect(mention).not.toBeNull()
    act(() => {
      mention?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    })
    expect(onTap).toHaveBeenCalledWith("Keeper")
  })

  it("captures quote selections and shows the private-copy protection notice", () => {
    const onQuoteSelect = vi.fn()
    Object.defineProperty(window, "getSelection", {
      configurable: true,
      value: vi.fn(() => ({ toString: () => "Mara crossed the bridge" })),
    })

    renderChapter({
      canCopyManuscript: false,
      canUseQuoteMode: true,
      onQuoteSelect,
      quoteModeEnabled: true,
      theme: "dark",
    })

    const shell = container?.querySelector(".reader-display-relaxed")
    act(() => {
      shell?.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }))
    })
    expect(onQuoteSelect).toHaveBeenCalledWith("Mara crossed the bridge")

    const copyEvent = new Event("copy", { bubbles: true, cancelable: true })
    const preventDefault = vi.spyOn(copyEvent, "preventDefault")
    act(() => {
      shell?.dispatchEvent(copyEvent)
    })
    expect(preventDefault).toHaveBeenCalled()
    expect(container?.textContent).toContain("Private share: copying disabled")
    expect(container?.textContent).toContain("Copy is disabled")
  })
})
