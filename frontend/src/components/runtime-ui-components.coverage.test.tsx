// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const replaceMock = vi.hoisted(() => vi.fn())
const pushMock = vi.hoisted(() => vi.fn())
const useReaderMock = vi.hoisted(() => vi.fn())
const setAppThemeMock = vi.hoisted(() => vi.fn())
const useQueryMock = vi.hoisted(() => vi.fn())
const queryState = vi.hoisted(() => ({ value: null as unknown }))
const readerState = vi.hoisted(() => ({ value: null as unknown }))
const authState = vi.hoisted(() => ({ user: { id: "user-1" }, hydrated: true }))

vi.mock("next/dynamic", () => ({
  default: () => function DynamicPanel(props: Record<string, unknown>) {
    return (
      <aside data-testid="dynamic-panel">
        <p>{String(props.selectedQuote ?? props.result ?? "dynamic-panel")}</p>
        {"onClose" in props ? <button type="button" onClick={() => (props.onClose as () => void)()}>Close panel</button> : null}
      </aside>
    )
  },
}))

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock, push: pushMock }),
}))

vi.mock("@tanstack/react-query", () => ({ useQuery: useQueryMock }))
vi.mock("@/lib/api/books", () => ({ booksApi: { list: vi.fn() } }))
vi.mock("@/lib/query/cacheKeys", () => ({
  asQueryKey: (value: unknown) => value,
  booksListCacheKey: () => "books:list",
}))
vi.mock("@/lib/hooks/useReader", () => ({ useReader: useReaderMock }))
vi.mock("@/lib/stores/authStore", () => ({
  useAuthStore: (selector: (state: typeof authState) => unknown) => selector(authState),
}))
vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: () => ({ setTheme: setAppThemeMock }),
}))
vi.mock("@/components/ui/Skeleton", () => ({
  Skeleton: ({ className = "" }: { className?: string }) => <div className={className}>Skeleton</div>,
}))
vi.mock("@/components/ui/MobileActionBar", () => ({
  MobileActionBar: ({ actions }: { actions: Array<{ id: string; label: string; onSelect?: () => void; href?: string }> }) => (
    <nav>
      {actions.map((action) => (
        <button key={action.id} type="button" onClick={action.onSelect}>
          {action.label}
          {action.href ? ` ${action.href}` : ""}
        </button>
      ))}
    </nav>
  ),
}))
vi.mock("@/components/reader/ReaderToolbar", () => ({
  ReaderToolbar: ({
    chapterTitle,
    onSummary,
    onToggleTheme,
    onSetFontSize,
    onSetFontFamily,
    onSetDisplayStyle,
    onToggleQuoteMode,
  }: {
    chapterTitle?: string | null
    onSummary: () => void
    onToggleTheme: () => void
    onSetFontSize: (value: number) => void
    onSetFontFamily: (value: "serif") => void
    onSetDisplayStyle: (value: "relaxed") => void
    onToggleQuoteMode: () => void
  }) => (
    <header>
      <p>{chapterTitle}</p>
      <button type="button" onClick={onSummary}>Summary toolbar</button>
      <button type="button" onClick={onToggleTheme}>Toggle theme</button>
      <button type="button" onClick={() => onSetFontSize(22)}>Bigger font</button>
      <button type="button" onClick={() => onSetFontFamily("serif")}>Serif font</button>
      <button type="button" onClick={() => onSetDisplayStyle("relaxed")}>Relax display</button>
      <button type="button" onClick={onToggleQuoteMode}>Quote mode</button>
    </header>
  ),
}))
vi.mock("@/components/reader/ChapterText", () => ({
  ChapterText: ({ textContent, onTap, onQuoteSelect }: { textContent?: string | null; onTap: () => void; onQuoteSelect: (text: string) => void }) => (
    <article>
      <p>{textContent}</p>
      <button type="button" onClick={onTap}>Tap passage</button>
      <button type="button" onClick={() => onQuoteSelect("Selected quote")}>Select quote</button>
    </article>
  ),
}))
vi.mock("@/components/reader/ReaderQuickRail", () => ({
  ReaderQuickRail: ({ onSummary }: { onSummary: () => void }) => <button type="button" onClick={onSummary}>Rail summary</button>,
}))
vi.mock("@/components/reader/ReadingProgressRail", () => ({
  ReadingProgressRail: ({ progressPercent }: { progressPercent: number | null }) => <p>Progress {progressPercent ?? 0}</p>,
}))
vi.mock("@/lib/utils/richText", () => ({
  sanitizeRichTextHtml: (value: string) => value,
}))

import { CommandPalette } from "@/components/ui/CommandPalette"
import { MarkdownPreview } from "@/components/reader/MarkdownPreview"
import { ReaderView } from "@/components/reader/ReaderView"

let root: Root | null = null
let container: HTMLDivElement | null = null
const localStore: Record<string, string> = {}

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

function makeStorage() {
  return {
    clear: vi.fn(() => {
      Object.keys(localStore).forEach((key) => delete localStore[key])
    }),
    getItem: vi.fn((key: string) => localStore[key] ?? null),
    removeItem: vi.fn((key: string) => {
      delete localStore[key]
    }),
    setItem: vi.fn((key: string, value: string) => {
      localStore[key] = value
    }),
  }
}

async function renderElement(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root?.render(element)
    await flush()
  })
}

async function flush() {
  await Promise.resolve()
  await new Promise((resolve) => window.setTimeout(resolve, 0))
  await Promise.resolve()
}

function text() {
  return container?.textContent ?? ""
}

async function click(label: string) {
  const button = Array.from(container?.querySelectorAll("button") ?? []).find((node) =>
    node.textContent?.includes(label),
  )
  if (!button) throw new Error(`Missing button ${label}\n${text()}`)
  await act(async () => {
    button.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await flush()
  })
}

function setInputValue(selector: string, value: string) {
  const input = container?.querySelector(selector) as HTMLInputElement | null
  if (!input) throw new Error(`Missing input ${selector}`)
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set
  setter?.call(input, value)
  input.dispatchEvent(new Event("input", { bubbles: true }))
}

function makeLoadedReaderState() {
  return {
    data: {
      chapter_title: "The Door",
      total_chapters: 4,
      text_content: "Mara opens the gate. [[IMAGE:one]] Theo waits.",
      html_content: null,
      text_url: null,
      media: [],
      characters: [],
      can_copy_manuscript: true,
      beta_feedback: [{ id: "feedback-1" }],
    },
    loading: false,
    error: null,
    tap: vi.fn(),
    contextResult: "Context answer",
    contextLoading: false,
    clearContext: vi.fn(),
    saveProgress: vi.fn(),
  }
}

function makeLoadedBooksState() {
  return {
    data: [
      {
        id: "book-1",
        title: "The Lantern Gate",
        author: "A Writer",
        genre: "Fantasy",
        mode: "author",
        status: "ready",
      },
    ],
    isLoading: false,
  }
}

beforeEach(() => {
  Object.defineProperty(window, "localStorage", { configurable: true, value: makeStorage() })
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn((query: string) => ({
      matches: query.includes("max-width") || query.includes("pointer"),
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  })
  Object.defineProperty(window, "requestIdleCallback", {
    configurable: true,
    value: (callback: IdleRequestCallback) => window.setTimeout(() => callback({ didTimeout: false, timeRemaining: () => 0 } as IdleDeadline), 0),
  })
  Object.defineProperty(window, "cancelIdleCallback", {
    configurable: true,
    value: (id: number) => window.clearTimeout(id),
  })
  Object.defineProperty(HTMLElement.prototype, "scrollHeight", { configurable: true, value: 900 })
  Object.defineProperty(HTMLElement.prototype, "clientHeight", { configurable: true, value: 300 })
  replaceMock.mockReset()
  pushMock.mockReset()
  setAppThemeMock.mockReset()
  queryState.value = makeLoadedBooksState()
  useQueryMock.mockReset().mockImplementation(() => queryState.value)
  readerState.value = makeLoadedReaderState()
  useReaderMock.mockReset().mockImplementation(() => readerState.value)
  window.localStorage.clear()
})

afterEach(() => {
  if (root) {
    act(() => {
      root?.unmount()
    })
  }
  container?.remove()
  root = null
  container = null
  document.body.innerHTML = ""
})

describe("runtime UI components", () => {
  it("renders ReaderView loading, error, and loaded interaction states", async () => {
    readerState.value = {
      data: null,
      loading: true,
      error: null,
      tap: vi.fn(),
      contextResult: null,
      contextLoading: false,
      clearContext: vi.fn(),
      saveProgress: vi.fn(),
    }
    await renderElement(<ReaderView bookId="book-1" chapterNum={2} />)
    expect(text()).toContain("Loading chapter")

    root?.unmount()
    container?.remove()
    root = null
    container = null
    readerState.value = {
      data: null,
      loading: false,
      error: "Chapter unavailable",
      tap: vi.fn(),
      contextResult: null,
      contextLoading: false,
      clearContext: vi.fn(),
      saveProgress: vi.fn(),
    }
    await renderElement(<ReaderView bookId="book-1" chapterNum={2} />)
    await act(flush)
    expect(replaceMock).toHaveBeenCalledWith("/library")
    expect(text()).toContain("Chapter unavailable")

    root?.unmount()
    container?.remove()
    root = null
    container = null
    readerState.value = makeLoadedReaderState()
    await renderElement(<ReaderView bookId="book-1" chapterNum={2} />)
    expect(text()).toContain("The Door")
    expect(text()).toContain("Mara opens the gate")
    expect(text()).toContain("Context answer")

    await click("Summary toolbar")
    expect(text()).toContain("dynamic-panel")
    await click("Toggle theme")
    await click("Bigger font")
    await click("Relax display")
    await click("Quote mode")
    await click("Select quote")
    expect(text()).toContain("Selected quote")
    await click("Close panel")
    expect(text()).not.toContain("Selected quote")
  })

  it("renders MarkdownPreview headings, code, links, embeds, cycles, and note clicks", async () => {
    const onOpenNote = vi.fn()
    await renderElement(
      <MarkdownPreview
        content={"# Heading\n\n**Bold** and *italic* with `code`.\n- Item\n[Site](https://example.com)\n[[Mara|Mara]]\n![[Gate]]\n![[Mara]]"}
        isDark={false}
        currentPath="Characters/Mara.md"
        notes={[
          { path: "Places/Gate.md", content: "Gate links back to [[Mara]]." },
          { path: "Characters/Mara.md", content: "Mara note." },
        ] as never}
        onOpenNote={onOpenNote}
      />,
    )

    expect(container?.querySelector("h1")?.textContent).toBe("Heading")
    expect(container?.querySelector("strong")?.textContent).toBe("Bold")
    expect(container?.querySelector("code")?.textContent).toBe("code")
    expect(text()).toContain("Embedded note")
    const vaultLink = Array.from(container?.querySelectorAll("a") ?? []).find((node) => node.getAttribute("href")?.startsWith("#vault-note=Mara"))
    expect(vaultLink).toBeTruthy()
    await act(async () => {
      vaultLink?.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true }))
      await flush()
    })
    expect(onOpenNote).toHaveBeenCalledWith("Mara")
  })

  it("opens CommandPalette with keyboard, filters actions, navigates, and shows loading and empty states", async () => {
    await renderElement(<CommandPalette />)
    expect(text()).toBe("")

    await act(async () => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true, bubbles: true }))
      await flush()
    })
    expect(text()).toContain("Command palette")
    expect(text()).toContain("Open Library")
    expect(text()).toContain("The Lantern Gate")

    setInputValue('input[aria-label="Search commands"]', "manuscript")
    expect(text()).toContain("Open manuscript: The Lantern Gate")
    await act(async () => {
      container?.querySelector("input")?.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }))
      await flush()
    })
    expect(pushMock).toHaveBeenCalledWith("/the-lantern-gate--book-1/manuscript")

    root?.unmount()
    container?.remove()
    root = null
    container = null
    queryState.value = { data: [], isLoading: true }
    await renderElement(<CommandPalette />)
    await act(async () => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true }))
      await flush()
    })
    expect(text()).toContain("Loading project actions")

    queryState.value = { data: [], isLoading: false }
    setInputValue('input[aria-label="Search commands"]', "zz-no-match")
    await act(flush)
    expect(text()).toContain("No matching commands")
    await act(async () => {
      window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }))
      await flush()
    })
    expect(text()).toBe("")
  })
})
