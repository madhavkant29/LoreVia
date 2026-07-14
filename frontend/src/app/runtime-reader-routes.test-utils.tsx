// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const routerMock = vi.hoisted(() => ({ back: vi.fn(), push: vi.fn() }))
const searchParamsState = vi.hoisted(() => ({ value: new URLSearchParams() }))
const themeState = vi.hoisted(() => ({ value: "light" }))
const authState = vi.hoisted(() => ({ user: { id: "user-1", tier: "pro" } as { id: string; tier: string } | null }))
const useQueryMock = vi.hoisted(() => vi.fn())
const booksApiMock = vi.hoisted(() => ({
  deleteChapter: vi.fn(),
  get: vi.fn(),
  getBookNotes: vi.fn(),
  getVaultGraph: vi.fn(),
  list: vi.fn(),
  listNotes: vi.fn(),
  listQuotes: vi.fn(),
  listSeries: vi.fn(),
  listVaultNotes: vi.fn(),
}))
const readerApiMock = vi.hoisted(() => ({
  getChapterList: vi.fn(),
  getProgress: vi.fn(),
  markBookRead: vi.fn(),
  search: vi.fn(),
  thematicSearch: vi.fn(),
  updateChapterReadStatus: vi.fn(),
}))
const intelligenceApiMock = vi.hoisted(() => ({
  answerStream: vi.fn(),
  getCrossBookIntelligence: vi.fn(),
  seriesAdvisorMessageStream: vi.fn(),
}))

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a>,
}))

vi.mock("next/dynamic", () => ({
  default: () => function DynamicMock(props: Record<string, unknown>) {
    return <section data-testid="dynamic-route-section">{String(props.title ?? props.bookTitle ?? "Dynamic route section")}</section>
  },
}))

vi.mock("next/navigation", () => ({
  useParams: () => ({ bookId: "book-1", seriesId: "series-1" }),
  useRouter: () => routerMock,
  useSearchParams: () => searchParamsState.value,
}))

vi.mock("@tanstack/react-query", () => ({ useQuery: useQueryMock }))
vi.mock("@/lib/api/books", () => ({ booksApi: booksApiMock }))
vi.mock("@/lib/api/reader", () => ({ readerApi: readerApiMock }))
vi.mock("@/lib/api/intelligence", () => ({ intelligenceApi: intelligenceApiMock }))
vi.mock("@/lib/analytics/posthog", () => ({ capture: vi.fn() }))
vi.mock("@/lib/billing/plans", () => ({
  canUseAuthorFeatures: (tier?: string | null) => tier !== "free",
  isPaidTier: (tier?: string | null) => tier === "pro" || tier === "architect",
}))
vi.mock("@/lib/hooks/useBookDetail", () => ({
  useBookDetail: () => ({ data: { id: "book-1", title: "The Lantern Gate", mode: "author" }, isLoading: false }),
}))
vi.mock("@/lib/limits/dailyCap", () => ({ buildDailyCapEventDetail: () => null }))
vi.mock("@/lib/query/cacheKeys", () => ({
  asQueryKey: (value: unknown) => value,
  bookCacheKey: (...parts: string[]) => parts.join(":"),
  booksListCacheKey: () => "books:list",
  booksNotesCacheKey: () => "dashboard:notes",
  booksQuotesCacheKey: () => "dashboard:quotes",
  booksSeriesCacheKey: () => "dashboard:series",
  readerCacheKey: (...parts: string[]) => parts.join(":"),
}))
vi.mock("@/lib/stores/authStore", () => ({
  useAuthStore: (selector: (state: typeof authState) => unknown) => selector(authState),
}))
vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: () => ({ theme: themeState.value }),
}))
vi.mock("@/lib/utils/richText", () => ({
  renderMarkdownHtml: (value: string) => `<p>${value}</p>`,
  renderRichTextHtml: (value: string) => `<p>${value}</p>`,
}))
vi.mock("@/components/reader/AskLoreViaWorkspace", () => ({
  AskLoreViaWorkspace: ({
    error,
    history,
    input,
    loading,
    onInputChange,
    onKeyDown,
    onSubmit,
    quickPrompts,
    scopeLabel,
  }: {
    error: string | null
    history: Array<{ question: string; answer: string }>
    input: string
    loading: boolean
    onInputChange: (value: string) => void
    onKeyDown: (event: React.KeyboardEvent<HTMLTextAreaElement>) => void
    onSubmit: (value: string) => void
    quickPrompts: string[]
    scopeLabel: string
  }) => (
    <main>
      <p>{scopeLabel}</p>
      <textarea
        aria-label="Ask input"
        value={input}
        onChange={(event) => onInputChange(event.target.value)}
        onKeyDown={onKeyDown}
      />
      <button type="button" onClick={() => onSubmit(input)}>Ask LoreVia</button>
      {quickPrompts.map((prompt) => <button key={prompt} type="button" onClick={() => onSubmit(prompt)}>{prompt}</button>)}
      {loading ? <p>Asking...</p> : null}
      {error ? <p>{error}</p> : null}
      {history.map((entry) => <article key={entry.question}>{entry.question} {entry.answer}</article>)}
    </main>
  ),
}))
vi.mock("@/components/reader/ChapterList", () => ({
  ChapterList: ({
    chapters,
    onDeleteChapter,
    onOpenChapter,
    onToggleChapterRead,
    readBusyKey,
    unitLabel,
  }: {
    chapters: Array<{ number: number; title?: string; read?: boolean }>
    onDeleteChapter?: (chapter: number) => void
    onOpenChapter: (chapter: number) => void
    onToggleChapterRead: (chapter: number, read: boolean) => void
    readBusyKey?: string | null
    unitLabel: string
  }) => (
    <section>
      <p>{unitLabel} list mock {readBusyKey ?? "idle"}</p>
      {chapters.map((chapter) => (
        <article key={chapter.number}>
          <h2>{chapter.title}</h2>
          <button type="button" onClick={() => onOpenChapter(chapter.number)}>Open {chapter.number}</button>
          <button type="button" onClick={() => onToggleChapterRead(chapter.number, !chapter.read)}>Toggle read {chapter.number}</button>
          {onDeleteChapter ? <button type="button" onClick={() => onDeleteChapter(chapter.number)}>Remove {chapter.number}</button> : null}
        </article>
      ))}
    </section>
  ),
}))
vi.mock("@/components/reader/ChaptersPageHeader", () => ({
  ChaptersPageHeader: ({
    backLabel,
    onBack,
    onPrimaryAction,
    primaryActionBusy,
    title,
  }: {
    backLabel: string
    onBack: () => void
    onPrimaryAction: () => void
    primaryActionBusy: boolean
    title: string
  }) => (
    <header>
      <h1>{title}</h1>
      <button type="button" onClick={onBack}>{backLabel}</button>
      <button type="button" onClick={onPrimaryAction}>{primaryActionBusy ? "Marking..." : "Mark book as read"}</button>
    </header>
  ),
}))
vi.mock("@/components/ui/ConfirmDialog", () => ({ useConfirmDialog: () => vi.fn().mockResolvedValue(true) }))
vi.mock("@/components/ui/Skeleton", () => ({ Skeleton: ({ className = "" }: { className?: string }) => <span className={className}>Skeleton</span> }))
vi.mock("@/components/ui/Workspace", () => ({
  WorkspaceEmptyState: ({ body, title }: { body: string; title: string }) => <section><h2>{title}</h2><p>{body}</p></section>,
  WorkspaceHeader: ({ description, eyebrow, meta, title }: { description: string; eyebrow: string; meta?: ReactNode; title: string }) => (
    <header><p>{eyebrow}</p><h1>{title}</h1><p>{description}</p>{meta}</header>
  ),
  WorkspaceMetric: ({ label, note, value }: { label: string; note?: string; value: string }) => <div>{label}: {value} {note}</div>,
  WorkspacePage: ({ children }: { children: ReactNode }) => <main>{children}</main>,
  WorkspacePanel: ({ children }: { children: ReactNode }) => <section>{children}</section>,
}))


let root: Root | null = null
let container: HTMLDivElement | null = null
const storage: Record<string, string> = {}

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

beforeEach(() => {
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: {
      getItem: vi.fn((key: string) => storage[key] ?? null),
      setItem: vi.fn((key: string, value: string) => { storage[key] = value }),
      removeItem: vi.fn((key: string) => { delete storage[key] }),
      clear: vi.fn(() => Object.keys(storage).forEach((key) => delete storage[key])),
    },
  })
  Object.defineProperty(window, "requestIdleCallback", {
    configurable: true,
    value: (callback: IdleRequestCallback) => window.setTimeout(() => callback({ didTimeout: false, timeRemaining: () => 50 } as IdleDeadline), 0),
  })
  Object.defineProperty(window, "cancelIdleCallback", {
    configurable: true,
    value: (id: number) => window.clearTimeout(id),
  })
  Element.prototype.scrollIntoView = vi.fn()
  routerMock.back.mockReset()
  routerMock.push.mockReset()
  themeState.value = "light"
  authState.user = { id: "user-1", tier: "pro" }
  searchParamsState.value = new URLSearchParams()
  Object.values(booksApiMock).forEach((mock) => mock.mockReset())
  Object.values(readerApiMock).forEach((mock) => mock.mockReset())
  Object.values(intelligenceApiMock).forEach((mock) => mock.mockReset())

  booksApiMock.get.mockResolvedValue({ id: "book-1", title: "The Lantern Gate", mode: "author", work_type: "novel", total_chapters: 3 })
  booksApiMock.list.mockResolvedValue([
    { id: "book-1", title: "The Lantern Gate", mode: "author", work_type: "novel", total_chapters: 3 },
    { id: "book-2", title: "The Ash Door", mode: "author", work_type: "novel", total_chapters: 4 },
  ])
  booksApiMock.listNotes.mockResolvedValue([])
  booksApiMock.listQuotes.mockResolvedValue([])
  booksApiMock.getBookNotes.mockResolvedValue([])
  booksApiMock.listVaultNotes.mockResolvedValue([])
  booksApiMock.getVaultGraph.mockResolvedValue({ nodes: [], edges: [] })
  booksApiMock.deleteChapter.mockResolvedValue({})
  booksApiMock.listSeries.mockResolvedValue({ items: [{ id: "series-1", name: "Gate Cycle", description: "Linked gate novels.", books: [{ id: "book-1" }] }] })
  readerApiMock.getChapterList.mockResolvedValue({ chapters: [] })
  readerApiMock.getProgress.mockResolvedValue({ current_chapter: 2, progress_pct: 50 })
  readerApiMock.markBookRead.mockResolvedValue({})
  readerApiMock.search.mockResolvedValue([])
  readerApiMock.thematicSearch.mockResolvedValue({ results: [] })
  readerApiMock.updateChapterReadStatus.mockResolvedValue({})
  intelligenceApiMock.answerStream.mockResolvedValue({ answer: "The answer cites chapter two.", citations: [{ chapter_number: 2 }] })
  intelligenceApiMock.getCrossBookIntelligence.mockResolvedValue({
    series_id: "series-1",
    series_name: "Gate Cycle",
    comparison_book_ids: ["book-1", "book-2"],
    character_matches: [
      {
        left_book_id: "book-1",
        right_book_id: "book-2",
        left_name: "Mara Vale",
        right_name: "Mara Vail",
        similarity: 0.82,
      },
    ],
    wiki_matches: [
      {
        left_book_id: "book-1",
        right_book_id: "book-2",
        left_name: "Moon Gate",
        right_name: "Lunar Gate",
        entry_type: "place",
        similarity: 0.55,
      },
    ],
  })
  intelligenceApiMock.seriesAdvisorMessageStream.mockResolvedValue({ reply: "Series answer", intent: "plot", response_type: "standard", retrieved_passages: [], cached: false })
  useQueryMock.mockImplementation(({ queryKey }: { queryKey: string }) => {
    const key = String(queryKey)
    if (key.includes("cross-book-wiki")) {
      return {
        data: {
          series_id: "series-1",
          series_name: "Gate Cycle",
          comparison_book_ids: ["book-1", "book-2"],
          character_matches: [
            {
              left_book_id: "book-1",
              right_book_id: "book-2",
              left_name: "Mara Vale",
              right_name: "Mara Vail",
              similarity: 0.82,
            },
          ],
          wiki_matches: [
            {
              left_book_id: "book-1",
              right_book_id: "book-2",
              left_name: "Moon Gate",
              right_name: "Lunar Gate",
              entry_type: "place",
              similarity: 0.55,
            },
          ],
        },
        isLoading: false,
      }
    }
    if (key === "books:list") {
      return {
        data: [
          { id: "book-1", title: "The Lantern Gate", mode: "author", work_type: "novel", total_chapters: 3 },
          { id: "book-2", title: "The Ash Door", mode: "author", work_type: "novel", total_chapters: 4 },
        ],
        isLoading: false,
      }
    }
    if (key === "dashboard:notes") return { data: notesFixture(), isLoading: false }
    if (key === "dashboard:quotes") return { data: quotesFixture(), isLoading: false }
    if (key === "dashboard:series") return { data: { items: [{ id: "series-1", name: "Gate Cycle", description: "Linked gate novels.", books: [{ id: "book-1" }, { id: "book-2" }] }] }, isLoading: false }
    if (key.includes("chapters")) return { data: chapterListFixture(), isLoading: false, isError: false, refetch: vi.fn().mockResolvedValue({}) }
    if (key.includes("progress")) return { data: { current_chapter: 2, progress_pct: 50 }, isLoading: false, refetch: vi.fn().mockResolvedValue({}) }
    if (key.includes("notes")) return { data: bookNotesFixture(), isLoading: false, refetch: vi.fn().mockResolvedValue({}) }
    if (key.includes("vault-notes")) return { data: [{ path: "Characters/Mara.md", content: "Mara keeps the gate." }], isLoading: false, refetch: vi.fn().mockResolvedValue({}) }
    if (key.includes("vault-graph")) return { data: { nodes: [{ id: "mara" }], edges: [] }, isLoading: false, refetch: vi.fn().mockResolvedValue({}) }
    return { data: { id: "book-1", title: "The Lantern Gate", mode: "author", work_type: "novel", total_chapters: 3 }, isLoading: false, isError: false, refetch: vi.fn().mockResolvedValue({}) }
  })
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
  vi.clearAllMocks()
})


async function render(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  await act(async () => {
    root?.render(element)
    await flush()
  })
}

async function rerender(element: ReactElement) {
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
  const button = Array.from(container?.querySelectorAll("button") ?? []).find((node) => node.textContent?.includes(label))
  if (!button) throw new Error(`Missing button ${label}\n${text()}`)
  await act(async () => {
    button.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await flush()
  })
}

async function waitForText(expected: string) {
  for (let index = 0; index < 40; index += 1) {
    if (text().includes(expected)) return
    await act(flush)
  }
  throw new Error(`Missing text ${expected}\n${text()}`)
}

function setInputValue(selector: string, value: string) {
  const input = container?.querySelector(selector) as HTMLInputElement | null
  if (!input) throw new Error(`Missing input ${selector}`)
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set
  setter?.call(input, value)
  input.dispatchEvent(new Event("input", { bubbles: true }))
}

function setTextareaValue(value: string) {
  const input = container?.querySelector("textarea") as HTMLTextAreaElement | null
  if (!input) throw new Error("Missing textarea")
  const setter = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, "value")?.set
  setter?.call(input, value)
  input.dispatchEvent(new Event("input", { bubbles: true }))
}

async function pressTextareaEnter() {
  const input = container?.querySelector("textarea")
  if (!input) throw new Error("Missing textarea")
  await act(async () => {
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }))
    await flush()
  })
}

function notesFixture() {
  return [
    {
      id: "note-1",
      book_id: "book-1",
      book_title: "The Lantern Gate",
      chapter_number: 2,
      chapter_title: "The Key",
      title: "Continuity note",
      body: "Mara carries the silver key.",
      updated_at: "2026-01-02T00:00:00Z",
    },
  ]
}

function quotesFixture() {
  return [
    {
      id: "quote-1",
      book_id: "book-1",
      book_title: "The Lantern Gate",
      chapter_number: 2,
      chapter_title: "The Key",
      character_name: "Mara",
      quote_text: "The gate remembers every oath.",
      note: "Important oath clue.",
      created_at: "2026-01-02T00:00:00Z",
    },
  ]
}

function bookNotesFixture() {
  return [
    {
      id: "book-note-1",
      title: "Continuity note",
      body: "Gate rules stay consistent.",
      chapter_number: 2,
      chapter_title: "The Key",
      updated_at: "2026-01-02T00:00:00Z",
    },
  ]
}

function chapterListFixture() {
  return {
    chapters: [
      { number: 1, title: "The Door", processed: true, read: false },
      { number: 2, title: "The Key", processed: true, read: true },
    ],
  }
}

function getContainer() {
  return container
}

export {
  authState,
  booksApiMock,
  click,
  flush,
  getContainer,
  intelligenceApiMock,
  readerApiMock,
  render,
  rerender,
  routerMock,
  searchParamsState,
  setInputValue,
  setTextareaValue,
  pressTextareaEnter,
  text,
  waitForText,
}
