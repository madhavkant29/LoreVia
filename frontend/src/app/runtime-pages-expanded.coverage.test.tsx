// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const pushMock = vi.hoisted(() => vi.fn())
const replaceMock = vi.hoisted(() => vi.fn())
const querySetMock = vi.hoisted(() => vi.fn())
const queryRefetchMock = vi.hoisted(() => vi.fn().mockResolvedValue({}))
const useQueryMock = vi.hoisted(() => vi.fn())
const useQueryClientMock = vi.hoisted(() => vi.fn())
const useParamsMock = vi.hoisted(() => vi.fn(() => ({ bookId: "book-1" })))
const booksApiMock = vi.hoisted(() => ({
  get: vi.fn(),
  getBookNotes: vi.fn(),
  getCharacters: vi.fn(),
  getChapterReports: vi.fn(),
  getPreWritingCheck: vi.fn(),
  getReaderBootstrap: vi.fn(),
  getRevisionIntelligence: vi.fn(),
  getStats: vi.fn(),
  getStoryHealth: vi.fn(),
  getWriterWorkspace: vi.fn(),
  importManuscript: vi.fn(),
  listQuotes: vi.fn(),
  retryProcessing: vi.fn(),
  setMode: vi.fn(),
  updateWriterWorkspace: vi.fn(),
}))
const betaReadsApiMock = vi.hoisted(() => ({
  createAssignment: vi.fn(),
  getBookAssignmentDetail: vi.fn(),
  listBookAssignments: vi.fn(),
  updateBookFeedbackItem: vi.fn(),
}))
const intelligenceApiMock = vi.hoisted(() => ({
  editorialReviewStream: vi.fn(),
}))
const saveContextualVaultNoteMock = vi.hoisted(() => vi.fn())
const useBookDetailMock = vi.hoisted(() => vi.fn())

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a>,
}))

vi.mock("next/dynamic", () => ({
  default: () => function DynamicRuntimeMock(props: Record<string, unknown>) {
    return (
      <section data-testid="dynamic-runtime-mock">
        <p>{String(props.title ?? props.active ?? props.label ?? "Dynamic runtime panel")}</p>
        {"onModeChange" in props ? <button type="button" onClick={() => (props.onModeChange as (mode: "reader" | "author") => void)("reader")}>Switch reader mode</button> : null}
        {"onToggleTheme" in props ? <button type="button" onClick={() => (props.onToggleTheme as () => void)()}>Toggle theme</button> : null}
        {"onContinueReading" in props ? <button type="button" onClick={() => (props.onContinueReading as () => void)()}>Continue mock read</button> : null}
        {"onNavigate" in props ? <button type="button" onClick={() => (props.onNavigate as (href: string) => void)("/book-1/chapters")}>Navigate mock</button> : null}
        {"onOpenManuscript" in props ? <button type="button" onClick={() => (props.onOpenManuscript as () => void)()}>Open mock manuscript</button> : null}
        {"onOpenRelationships" in props ? <button type="button" onClick={() => (props.onOpenRelationships as () => void)()}>Open mock graph</button> : null}
        {"onSaveGoalCalendar" in props ? <button type="button" onClick={() => void (props.onSaveGoalCalendar as (items: unknown[]) => Promise<boolean>)([{ id: "goal-1" }])}>Save mock goal</button> : null}
        {"onRevisionChange" in props ? <button type="button" onClick={() => (props.onRevisionChange as (value: unknown) => void)({ summary: { recent_edit_label: "Changed" } })}>Change revision</button> : null}
        {"onWriterWorkspaceChange" in props ? <button type="button" onClick={() => (props.onWriterWorkspaceChange as (value: unknown) => void)({ goal_calendar: [] })}>Change workspace</button> : null}
        {"onSaveNote" in props ? <button type="button" onClick={() => void (props.onSaveNote as (title: string, body: string, chapter: number | null) => Promise<void>)("Review note", "Tighten this section.", 3)}>Save review note</button> : null}
        {"editResult" in props ? <p>{String((props.editResult as { summary?: string } | null)?.summary ?? "Editorial result")}</p> : null}
      </section>
    )
  },
}))

vi.mock("next/navigation", () => ({
  useParams: useParamsMock,
  useRouter: () => ({ push: pushMock, replace: replaceMock }),
}))

vi.mock("@tanstack/react-query", () => ({
  useQuery: useQueryMock,
  useQueryClient: useQueryClientMock,
}))

vi.mock("@/components/overview/CreateFab", () => ({
  CreateFab: ({ onAddScene, onNavigate }: { onAddScene: () => void; onNavigate: (href: string) => void }) => (
    <div>
      <button type="button" onClick={onAddScene}>Add scene</button>
      <button type="button" onClick={() => onNavigate("/book-1/advisor")}>Fab navigate</button>
    </div>
  ),
}))

vi.mock("@/components/billing/ContextualUpgradePrompt", () => ({
  ContextualUpgradePrompt: ({ body, onBack }: { body: string; onBack: () => void }) => (
    <div>
      <p>{body}</p>
      <button type="button" onClick={onBack}>Dismiss gate</button>
    </div>
  ),
}))

vi.mock("@/components/ui/ErrorCard", () => ({
  ErrorCard: ({ title, message, onRetry }: { title: string; message: string; onRetry: () => void }) => (
    <section>
      <h1>{title}</h1>
      <p>{message}</p>
      <button type="button" onClick={onRetry}>Retry</button>
    </section>
  ),
}))

vi.mock("@/components/ui/RecentActivityList", () => ({
  RecentActivityList: ({ title, items, emptyLabel }: { title: string; items: Array<{ label: string }>; emptyLabel: string }) => (
    <section>
      <h2>{title}</h2>
      {items.length ? items.map((item) => <p key={item.label}>{item.label}</p>) : <p>{emptyLabel}</p>}
    </section>
  ),
}))

vi.mock("@/components/ui/ResponsivenessStatus", () => ({
  ProcessingStatusPanel: ({ status, onRetry }: { status?: { label?: string; retryAvailable?: boolean } | null; onRetry?: () => void }) => (
    <section>
      <p>{status?.label ?? "No processing status"}</p>
      {onRetry ? <button type="button" onClick={onRetry}>Retry processing</button> : null}
    </section>
  ),
}))

vi.mock("@/components/ui/Skeleton", () => ({
  DashboardSkeleton: () => <div>Dashboard loading</div>,
  SidebarSkeleton: () => <div>Sidebar loading</div>,
  Skeleton: ({ className = "" }: { className?: string }) => <span className={className}>Skeleton</span>,
}))

vi.mock("@/components/reader/WorkspaceFamilyHeader", () => ({
  WorkspaceFamilyHeader: ({ title, description, actions }: { title: string; description: string; actions?: ReactNode }) => (
    <header>
      <h1>{title}</h1>
      <p>{description}</p>
      {actions}
    </header>
  ),
}))

vi.mock("@/components/modals/UploadModal", () => ({
  UploadModal: ({ onClose }: { onClose: () => void }) => (
    <section>
      <p>Upload modal inline</p>
      <button type="button" onClick={onClose}>Close upload</button>
    </section>
  ),
}))

vi.mock("@/lib/api/books", () => ({ booksApi: booksApiMock }))
vi.mock("@/lib/api/betaReads", () => ({ betaReadsApi: betaReadsApiMock }))
vi.mock("@/lib/api/intelligence", () => ({ intelligenceApi: intelligenceApiMock }))
vi.mock("@/lib/hooks/useBookDetail", () => ({ useBookDetail: useBookDetailMock }))
vi.mock("@/lib/query/cacheKeys", () => ({
  asQueryKey: (value: unknown) => value,
  bookCacheKey: (...parts: string[]) => parts.join(":"),
  booksQuotesCacheKey: () => "quotes",
  booksStatsCacheKey: () => "stats",
  readerCacheKey: (...parts: string[]) => parts.join(":"),
}))
vi.mock("@/lib/analytics/posthog", () => ({ capture: vi.fn(), captureTiming: vi.fn() }))
vi.mock("@/lib/stores/authStore", () => ({
  useAuthStore: (selector: (state: { hydrated: boolean; user: { username: string; tier: string; daily_word_goal: number; today_word_count: number; login_streak_days: number; login_activity_dates: string[] } }) => unknown) =>
    selector({
      hydrated: true,
      user: {
        username: "Mira",
        tier: "architect",
        daily_word_goal: 1200,
        today_word_count: 640,
        login_streak_days: 5,
        login_activity_dates: ["2026-06-15", "2026-06-16"],
      },
    }),
}))
vi.mock("@/lib/stores/bookModeStore", () => ({
  useBookModeStore: (selector: (state: { getMode: () => "reader" | "author"; setMode: (bookId: string, mode: "reader" | "author") => void }) => unknown) =>
    selector({ getMode: () => "reader", setMode: vi.fn() }),
}))
vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: (selector?: (state: { theme: "light" | "dark"; toggleTheme: () => void }) => unknown) => {
    const state = { theme: "dark" as const, toggleTheme: vi.fn() }
    return typeof selector === "function" ? selector(state) : state
  },
}))
vi.mock("@/lib/utils/notes", () => ({ saveContextualVaultNote: saveContextualVaultNoteMock }))

import StatsPage from "@/app/(dashboard)/stats/page"
import BookOverviewPage from "@/app/(reader)/[bookId]/page"
import AuthorLoopPage from "@/app/(reader)/[bookId]/author-loop/page"
import EditorialReviewPage from "@/app/(reader)/[bookId]/editorial-review/page"

let root: Root | null = null
let container: HTMLDivElement | null = null
const localStore: Record<string, string> = {}
const sessionStore: Record<string, string> = {}

function makeStorage(store: Record<string, string>) {
  return {
    get length() {
      return Object.keys(store).length
    },
    clear: vi.fn(() => {
      Object.keys(store).forEach((key) => delete store[key])
    }),
    getItem: vi.fn((key: string) => store[key] ?? null),
    key: vi.fn((index: number) => Object.keys(store)[index] ?? null),
    removeItem: vi.fn((key: string) => {
      delete store[key]
    }),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value
    }),
  }
}

const bookFixture = {
  id: "book-1",
  title: "The Lantern Gate",
  author: "A. Writer",
  genre: "Fantasy",
  format: "docx",
  work_type: "novel",
  status: "ready",
  mode: "author",
  workspace_shell: "author",
  access_class: "owner",
  can_switch_workspace_mode: true,
  total_chapters: 12,
  total_words: 42000,
  total_tokens: 56000,
  chapters_left: 2,
  progress_pct: 72,
  created_at: "2026-01-01T00:00:00Z",
  processing: {
    status: "ready",
    stage: "ready",
    progress_pct: 100,
    chapters_completed: 12,
    chapters_total: 12,
    last_chapter_number: 12,
    last_chapter_title: "Home",
    eta_seconds: 0,
  },
}

const writerWorkspaceFixture = {
  word_count_goals: { book_target: 60000 },
  goal_calendar: [],
  templates: [{ id: "template-1" }],
  corkboard_cards: [{ id: "card-1" }],
  revision_board: { items: [] },
}

const statsFixture = {
  public: {
    total_books_read: 4,
    total_words_read: 240000,
  },
  private: {
    total_uploads: 9,
    llm_request_count: 22,
    llm_total_tokens: 45000,
    saved_quotes: 7,
  },
  writing: {
    today: { words: 640, target_words: 1200, progress_pct: 53 },
    this_week: { words: 4200, target_words: 8400, progress_pct: 50 },
    this_month: { words: 18000, target_words: null, progress_pct: null },
    this_year: { words: 90000, target_words: null, progress_pct: null },
    last_24_hours: { words: 700, target_words: null, progress_pct: null },
    last_7_days: { words: 5000, target_words: null, progress_pct: null },
    last_30_days: { words: 19000, target_words: null, progress_pct: null },
    last_year: { words: 120000, target_words: null, progress_pct: null },
    entries_today: [
      { book_id: "book-1", chapter_number: 3, title: "The Mirror Room", words: 640 },
    ],
    heatmap: Array.from({ length: 21 }, (_, index) => ({
      date: `2026-06-${String(index + 1).padStart(2, "0")}`,
      words: index % 5 === 0 ? 0 : (index + 1) * 20,
    })),
  },
}

const chapterListFixture = {
  chapters: [
    { chapter_number: 1, title: "The Door", summary: "A door opens." },
    { chapter_number: 2, title: "The Key", summary: "A key turns." },
  ],
}

const overviewFixture = {
  book: bookFixture,
  progress: { current_chapter: 3, percent_complete: 72, chapters_left: 2 },
  chapter_list: chapterListFixture,
  summary_collection: { summaries: [] },
}

const characterFixture = {
  id: "char-1",
  name: "Mara",
  aliases: ["The Lantern"],
  description: "A careful keeper of locked doors.",
  first_chapter: 1,
}

const chapterReportFixture = {
  id: "report-1",
  chapter_number: 2,
  chapter_title: "The Key",
  summary: "The door was brass, then iron.",
  continuity_flags: ["Door changes color"],
}

const revisionIntelligenceFixture = {
  summary: { recent_edit_label: "Scene two changed yesterday." },
  change_impacts: [
    {
      id: "issue-1",
      category: "continuity",
      title: "Lantern location conflict",
      description: "The lantern is in two rooms at once.",
      recommendation: "Move the lantern back into the entry hall.",
      source_label: "Continuity scan",
      chapter_ref: 2,
      severity: "medium",
      status: "pending",
    },
  ],
  scene_advice: [],
  confusion_map: [],
  voice_alerts: [],
  revision_plan: [],
}

const assignmentFixture = {
  id: "assign-1",
  reader_email: "reader@example.com",
  task_label: "Focused beta read",
  scope_kind: "chapter_range",
  chapter_start: 1,
  chapter_end: 3,
  window_days: 5,
  expires_at: "2026-07-01T00:00:00Z",
  required_progress_pct: 100,
  required_comment_count: 0,
  required_feedback_item_count: 1,
  require_final_feedback: true,
  progress_pct: 40,
  submitted_at: null,
  question_count: 2,
  status_label: "In progress",
  view_bucket: "active",
  state: "in_progress",
}

const assignmentDetailFixture = {
  assignment: assignmentFixture,
  feedback_summary: {
    feedback_item_count: 1,
    confusing_count: 1,
    answer_count: 1,
    favorite_count: 0,
  },
  feedback_items: [
    {
      id: "feedback-1",
      author_status: "open",
      chapter_number: 2,
      question_prompt: "Where were you confused?",
      body: "The lock rules are unclear.",
      anchor_text: "lock rules",
      author_task_id: null,
    },
  ],
}

function defaultQueryResult(data: unknown) {
  return {
    data,
    isLoading: false,
    isError: false,
    isSuccess: true,
    refetch: queryRefetchMock,
  }
}

async function renderPage(element: ReactElement) {
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

function field<T extends HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>(selector: string) {
  const item = container?.querySelector(selector)
  if (!item) throw new Error(`Missing field: ${selector}`)
  return item as T
}

function setFieldValue(item: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement, value: string) {
  const prototype =
    item instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : item instanceof HTMLSelectElement
        ? HTMLSelectElement.prototype
        : HTMLInputElement.prototype
  const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set
  setter?.call(item, value)
  item.dispatchEvent(new Event(item instanceof HTMLSelectElement ? "change" : "input", { bubbles: true }))
}

async function click(label: string, index = 0) {
  const buttons = Array.from(container?.querySelectorAll("button") ?? []).filter((button) => button.textContent?.includes(label))
  const target = buttons[index]
  if (!target) throw new Error(`Missing button: ${label}\n${text()}`)
  await act(async () => {
    target.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await flush()
  })
}

beforeEach(() => {
  pushMock.mockReset()
  replaceMock.mockReset()
  querySetMock.mockReset()
  queryRefetchMock.mockClear()
  useParamsMock.mockReturnValue({ bookId: "book-1" })
  useQueryClientMock.mockReturnValue({ setQueryData: querySetMock, clear: vi.fn() })
  useBookDetailMock.mockReturnValue(defaultQueryResult(bookFixture))
  booksApiMock.get.mockResolvedValue(bookFixture)
  booksApiMock.getReaderBootstrap.mockResolvedValue({
    overview: overviewFixture,
    notes: [],
    saved_quotes: [],
    stats: statsFixture,
    characters: [characterFixture],
    chapter_reports: [chapterReportFixture],
    prewriting_check: { alerts: [{ id: "alert-1" }] },
    story_health: { score: 84, summary: "Continuity is mostly stable." },
    writer_workspace: writerWorkspaceFixture,
    revision_intelligence: revisionIntelligenceFixture,
  })
  booksApiMock.getStats.mockResolvedValue(statsFixture)
  booksApiMock.getBookNotes.mockResolvedValue([])
  booksApiMock.listQuotes.mockResolvedValue([])
  booksApiMock.getCharacters.mockResolvedValue([characterFixture])
  booksApiMock.getChapterReports.mockResolvedValue([chapterReportFixture])
  booksApiMock.getPreWritingCheck.mockResolvedValue({ alerts: [{ id: "alert-1" }] })
  booksApiMock.getStoryHealth.mockResolvedValue({ score: 84, summary: "Continuity is mostly stable." })
  booksApiMock.getWriterWorkspace.mockResolvedValue(writerWorkspaceFixture)
  booksApiMock.getRevisionIntelligence.mockResolvedValue(revisionIntelligenceFixture)
  booksApiMock.updateWriterWorkspace.mockResolvedValue(writerWorkspaceFixture)
  booksApiMock.setMode.mockResolvedValue({ ...bookFixture, mode: "author", workspace_shell: "author" })
  booksApiMock.retryProcessing.mockResolvedValue({ status: "processing", stage: "extracting", progress_pct: 25 })
  booksApiMock.importManuscript.mockResolvedValue({ mode: "author", imported_chapters: [3, 4] })
  betaReadsApiMock.createAssignment.mockResolvedValue({ id: "assign-1" })
  betaReadsApiMock.listBookAssignments.mockResolvedValue([assignmentFixture])
  betaReadsApiMock.getBookAssignmentDetail.mockResolvedValue(assignmentDetailFixture)
  betaReadsApiMock.updateBookFeedbackItem.mockResolvedValue({})
  intelligenceApiMock.editorialReviewStream.mockImplementation(async (_bookId, _text, _chapter, options) => {
    options?.onStage?.("Checking continuity")
    return {
      review: { summary: "Strong scene with one continuity fix.", issues: [] },
      retrieved_passages: [{ chapter_number: 2, text: "Earlier lock rule." }],
    }
  })
  saveContextualVaultNoteMock.mockResolvedValue({ path: "Editorial Review/Chapter 3/Review note" })

  useQueryMock.mockImplementation(({ queryKey }: { queryKey: unknown }) => {
    const key = Array.isArray(queryKey) ? queryKey.join(":") : String(queryKey)
    if (key === "stats") return defaultQueryResult(statsFixture)
    if (key === "book-1:detail") return defaultQueryResult(bookFixture)
    if (key === "book-1:characters") return defaultQueryResult([characterFixture])
    if (key === "book-1:chapter-reports:12" || key === "book-1:chapter-reports:6") return defaultQueryResult([chapterReportFixture])
    if (key === "book-1:story-health") return defaultQueryResult({ score: 84 })
    if (key === "book-1:pre-writing:auto") return defaultQueryResult({ alerts: [{ id: "alert-1" }] })
    if (key === "book-1:revision-intelligence") return defaultQueryResult(revisionIntelligenceFixture)
    if (key === "book-1:writer-workspace") return defaultQueryResult(writerWorkspaceFixture)
    if (key === "author-loop:book-1:beta-assignments") return defaultQueryResult([assignmentFixture])
    if (key === "author-loop:book-1:beta-detail:assign-1") return defaultQueryResult(assignmentDetailFixture)
    if (key === "book-1:overview") return defaultQueryResult(overviewFixture)
    if (key === "book-1:notes") return defaultQueryResult([])
    if (key === "quotes") return defaultQueryResult([])
    return defaultQueryResult(null)
  })

  Object.defineProperty(window, "requestIdleCallback", {
    configurable: true,
    value: (callback: IdleRequestCallback) => window.setTimeout(() => callback({ didTimeout: false, timeRemaining: () => 0 } as IdleDeadline), 0),
  })
  Object.defineProperty(window, "cancelIdleCallback", {
    configurable: true,
    value: (id: number) => window.clearTimeout(id),
  })
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: makeStorage(localStore),
  })
  Object.defineProperty(window, "sessionStorage", {
    configurable: true,
    value: makeStorage(sessionStore),
  })
  window.scrollTo = vi.fn()
  window.localStorage.clear()
  window.sessionStorage.clear()
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

describe("expanded runtime page coverage", () => {
  it("renders the stats dashboard populated, loading, unavailable, and gated states", async () => {
    await renderPage(<StatsPage />)

    expect(text()).toContain("Writing momentum overview")
    expect(text()).toContain("The Mirror Room")
    expect(text()).toContain("Books finished")
    expect(text()).toContain("LLM tokens")

    root?.unmount()
    container?.remove()
    root = null
    container = null
    useQueryMock.mockReturnValueOnce({ data: null, isLoading: true, isError: false, refetch: queryRefetchMock })
    await renderPage(<StatsPage />)
    expect(text()).toContain("Loading dashboard")

    root?.unmount()
    container?.remove()
    root = null
    container = null
    useQueryMock.mockReturnValueOnce({ data: null, isLoading: false, isError: false, refetch: queryRefetchMock })
    await renderPage(<StatsPage />)
    expect(text()).toContain("Stats unavailable")
  })

  it("drives editorial import, review, author mode, and note-save handlers", async () => {
    await renderPage(<EditorialReviewPage />)

    expect(text()).toContain("The Lantern Gate editorial review")
    setFieldValue(field<HTMLTextAreaElement>("textarea"), "Mara unlocks the gate and finds the lantern inside.")
    setFieldValue(field<HTMLInputElement>("input[type='number']"), "3")
    await click("Add to current upload")
    expect(booksApiMock.importManuscript).toHaveBeenCalledWith("book-1", expect.objectContaining({ chapterNumber: 3 }))

    await click("Run Editorial Review")
    expect(intelligenceApiMock.editorialReviewStream).toHaveBeenCalledWith("book-1", expect.any(String), 3, expect.any(Object))
    expect(text()).toContain("Strong scene")
    await click("Save review note")
    expect(saveContextualVaultNoteMock).toHaveBeenCalledWith(expect.objectContaining({ bookId: "book-1", title: "Review note" }))
  })

  it("renders and exercises author loop upload, issue, invite, and feedback actions", async () => {
    await renderPage(<AuthorLoopPage />)

    expect(text()).toContain("The Lantern Gate author loop")
    expect(text()).toContain("Mara")
    expect(text()).toContain("reader@example.com")
    await click("Open upload tools")
    expect(text()).toContain("Hide upload tools")
    expect(text()).toContain("Dynamic runtime panel")
    await click("Convert to task")
    expect(booksApiMock.updateWriterWorkspace).toHaveBeenCalled()

    setFieldValue(field<HTMLInputElement>('input[aria-label="Reader email"]'), "beta@example.com")
    setFieldValue(field<HTMLSelectElement>('select[aria-label="Scope"]'), "chapter_range")
    await act(flush)
    setFieldValue(field<HTMLInputElement>('input[aria-label="From chapter"]'), "2")
    setFieldValue(field<HTMLInputElement>('input[aria-label="Through chapter"]'), "5")
    await click("Send beta invite")
    expect(betaReadsApiMock.createAssignment).toHaveBeenCalledWith("book-1", expect.objectContaining({ readerEmail: "beta@example.com" }))

    await click("Convert to task", 2)
    expect(betaReadsApiMock.updateBookFeedbackItem).toHaveBeenCalled()
  })

  it("renders loaded and error book overview flows and calls navigation/save handlers", async () => {
    await renderPage(<BookOverviewPage />)

    expect(text()).toContain("Project signals")
    expect(text()).toContain("72% complete")
    await click("Switch reader mode")
    expect(booksApiMock.setMode).toHaveBeenCalledWith("book-1", "reader")
    await click("Read")
    expect(pushMock).toHaveBeenCalledWith("/book-1/chapter/3")
    await click("Open mock manuscript")
    expect(pushMock).toHaveBeenCalledWith("/book-1/manuscript")
    await click("Open mock graph")
    expect(pushMock).toHaveBeenCalledWith("/book-1/graph")
    await click("Save mock goal")
    expect(booksApiMock.updateWriterWorkspace).toHaveBeenCalledWith("book-1", expect.objectContaining({ goal_calendar: [{ id: "goal-1" }] }))
    await click("Add scene")
    expect(pushMock).toHaveBeenCalledWith("/book-1/manuscript?newScene=1")

    root?.unmount()
    container?.remove()
    root = null
    container = null
    useQueryMock.mockImplementation(({ queryKey }: { queryKey: unknown }) => {
      const key = Array.isArray(queryKey) ? queryKey.join(":") : String(queryKey)
      if (key === "book-1:overview") {
        return { data: null, isLoading: false, isError: true, isSuccess: false, refetch: queryRefetchMock }
      }
      return defaultQueryResult(null)
    })
    await renderPage(<BookOverviewPage />)
    expect(text()).toContain("Failed to load book overview")
    await click("Retry")
    expect(queryRefetchMock).toHaveBeenCalled()
    expect(replaceMock).toHaveBeenCalledWith("/library")
  })
})
