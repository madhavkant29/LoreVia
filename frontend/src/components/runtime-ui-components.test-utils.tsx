import { act, type ReactElement } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, vi } from "vitest"

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
vi.mock("@/lib/api/books", () => ({ booksApi: { listSelector: vi.fn() } }))
vi.mock("@/lib/query/cacheKeys", () => ({
  asQueryKey: (value: unknown) => value,
  booksSelectorCacheKey: () => "books:selector",
}))
vi.mock("@/lib/hooks/useReader", () => ({ useReader: useReaderMock }))
vi.mock("@/lib/hooks/useBookDetail", () => ({ useBookDetail: () => ({ data: { access_class: "owner", mode: "author" } }) }))
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

import { CommandPalette as CommandPaletteComponent } from "@/components/ui/CommandPalette"
import { MarkdownPreview as MarkdownPreviewComponent } from "@/components/reader/MarkdownPreview"
import { ReaderView as ReaderViewComponent } from "@/components/reader/ReaderView"

export const CommandPalette = CommandPaletteComponent
export const MarkdownPreview = MarkdownPreviewComponent
export const ReaderView = ReaderViewComponent
export { pushMock, queryState, readerState, replaceMock, setAppThemeMock, useQueryMock, useReaderMock }

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

export async function renderElement(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root?.render(element)
    await flush()
  })
}

export function cleanupRuntimeUi() {
  if (root) {
    act(() => {
      root?.unmount()
    })
  }
  container?.remove()
  root = null
  container = null
}

export async function flush() {
  await Promise.resolve()
  await new Promise((resolve) => window.setTimeout(resolve, 0))
  await Promise.resolve()
}

export function getContainer() {
  if (!container) throw new Error("Runtime UI test container is not mounted.")
  return container
}

export function text() {
  return document.body.textContent ?? ""
}

export async function click(label: string) {
  const button = Array.from(document.body.querySelectorAll("button") ?? []).find((node) =>
    node.textContent?.includes(label),
  )
  if (!button) throw new Error(`Missing button ${label}\n${text()}`)
  await act(async () => {
    button.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await flush()
  })
}

export function setInputValue(selector: string, value: string) {
  const input = document.body.querySelector(selector) as HTMLInputElement | null
  if (!input) throw new Error(`Missing input ${selector}`)
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set
  setter?.call(input, value)
  input.dispatchEvent(new Event("input", { bubbles: true }))
}

export function makeLoadedReaderState() {
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

export function makeLoadedBooksState() {
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
  cleanupRuntimeUi()
  document.body.innerHTML = ""
})
