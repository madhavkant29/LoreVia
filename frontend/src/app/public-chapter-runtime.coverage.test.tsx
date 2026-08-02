// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const publicApiMock = vi.hoisted(() => ({
  getChapter: vi.fn(),
  trackView: vi.fn(),
}))

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
    prefetch: _prefetch,
    replace: _replace,
    scroll: _scroll,
    shallow: _shallow,
    locale: _locale,
    ...props
  }: {
    children: ReactNode
    href: string
    prefetch?: boolean | null
    replace?: boolean
    scroll?: boolean
    shallow?: boolean
    locale?: string | false
  }) => <a href={href} {...props}>{children}</a>,
}))

vi.mock("@/lib/api/public", () => ({ publicApi: publicApiMock }))

import { PublicChapterPageClient } from "@/components/public/PublicChapterPageClient"

let root: Root | null = null
let container: HTMLDivElement | null = null
let queryClient: QueryClient | null = null

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

beforeEach(() => {
  Object.values(publicApiMock).forEach((mock) => mock.mockReset())
  publicApiMock.trackView.mockResolvedValue({})
})

afterEach(() => {
  cleanupRenderedTree()
})

describe("PublicChapterPageClient runtime behavior", () => {
  it("renders chapter content, navigation, tracking, and unavailable states", async () => {
    const chapter = {
      book_id: "book-1",
      chapter_number: 2,
      chapter_title: "The Gate",
      chapter_description: "Mara reaches the sealed gate.",
      html_content: "<p>The brass key turned.</p>",
      text_content: null,
      text_url: null,
      total_chapters: 4,
    }
    publicApiMock.getChapter.mockResolvedValue(chapter)

    await renderElement(
      <PublicChapterPageClient bookId="book-1" chapterId="2" initialChapter={chapter as never} />,
    )
    await flushAsync()

    expect(container?.textContent).toContain("The Gate")
    expect(container?.textContent).toContain("The brass key turned")
    expect(container?.textContent).toContain("Previous chapter")
    expect(container?.textContent).toContain("Next chapter")
    expect(publicApiMock.trackView).toHaveBeenCalledWith("book-1", {
      eventType: "chapter_view",
      chapterNumber: 2,
    })

    cleanupRenderedTree()
    await renderElement(<PublicChapterPageClient bookId="book-1" chapterId="bad" />)
    await flushAsync()
    expect(container?.textContent).toContain("This chapter is not available")
  })
})

async function renderElement(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  queryClient = client
  await act(async () => {
    root?.render(<QueryClientProvider client={client}>{element}</QueryClientProvider>)
    await Promise.resolve()
  })
}

function cleanupRenderedTree() {
  if (root) {
    act(() => {
      root?.unmount()
    })
  }
  queryClient?.clear()
  container?.remove()
  document.body.innerHTML = ""
  root = null
  container = null
  queryClient = null
}

async function flushAsync() {
  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
    await new Promise((resolve) => window.setTimeout(resolve, 0))
  })
}
