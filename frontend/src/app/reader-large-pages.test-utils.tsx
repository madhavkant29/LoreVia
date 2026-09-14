// @vitest-environment jsdom

import { act, type ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, expect, vi } from "vitest"
import type { Book, ManuscriptBootstrapPayload, WriterWorkspace } from "@/types/book"
import type { ChapterData, ChapterListResponse } from "@/types/reader"

const replaceMock = vi.hoisted(() => vi.fn())
const pushMock = vi.hoisted(() => vi.fn())
const routerMock = vi.hoisted(() => ({ push: pushMock, replace: replaceMock }))
const searchParamsMock = vi.hoisted(() => new URLSearchParams())
const booksApiMock = vi.hoisted(() => ({
  createChapterSnapshot: vi.fn(),
  createSceneSnapshot: vi.fn(),
  deleteBookNote: vi.fn(),
  deleteChapter: vi.fn(),
  deleteManuscriptAnnotation: vi.fn(),
  deleteScene: vi.fn(),
  exportManuscript: vi.fn(),
  get: vi.fn(),
  getBookNotes: vi.fn(),
  getChapterVersionDetail: vi.fn(),
  getChapterVersions: vi.fn(),
  getCharacters: vi.fn(),
  getEmotionalArc: vi.fn(),
  getManuscriptAnnotations: vi.fn(),
  getManuscriptBootstrap: vi.fn(),
  getPreWritingCheck: vi.fn(),
  getReadability: vi.fn(),
  getRestoreStatus: vi.fn(),
  getSceneInsertion: vi.fn(),
  getSceneVersionDetail: vi.fn(),
  getSceneVersions: vi.fn(),
  getWorkspaceTree: vi.fn(),
  getWriterWorkspace: vi.fn(),
  importManuscript: vi.fn(),
  listVaultNotes: vi.fn(),
  reorderChapterScenes: vi.fn(),
  reprocessChapter: vi.fn(),
  reprocessManuscript: vi.fn(),
  restoreChapterVersion: vi.fn(),
  restoreSceneVersion: vi.fn(),
  retryProcessing: vi.fn(),
  saveChapterContent: vi.fn(),
  saveBookNote: vi.fn(),
  saveManuscriptAnnotation: vi.fn(),
  saveScene: vi.fn(),
  updateCharacter: vi.fn(),
  updateWriterWorkspace: vi.fn(),
}))
const readerApiMock = vi.hoisted(() => ({
  getChapter: vi.fn(),
  getChapterList: vi.fn(),
  getPlotThreads: vi.fn(),
  getTimeline: vi.fn(),
  search: vi.fn(),
}))
const intelligenceApiMock = vi.hoisted(() => ({
  advisorSuggestions: vi.fn(),
  continuityReport: vi.fn(),
  editorialReview: vi.fn(),
  inlineContinuity: vi.fn(),
  proseTightenStream: vi.fn(),
  synopsis: vi.fn(),
}))

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

vi.mock("next/dynamic", () => ({
  default: () => function DynamicRuntimePanel(props: Record<string, unknown>) {
    const callbacks = props as Record<string, unknown>
    const call = (name: string, ...args: unknown[]) => {
      const fn = callbacks[name]
      if (typeof fn === "function") {
        ;(fn as (...values: unknown[]) => unknown)(...args)
      }
    }
    return (
      <div data-testid="dynamic-runtime-panel" data-editor-key={typeof props.editorKey === "string" ? props.editorKey : undefined}>
        {String(props.label ?? "runtime panel")}
        {"onChange" in callbacks ? <button type="button" onClick={() => call("onChange", "<p>Runtime note body.</p>", "Runtime note body.")}>Change rich text</button> : null}
        {"onToggleLeftRail" in callbacks ? <button type="button" onClick={() => call("onToggleLeftRail")}>Toggle left rail</button> : null}
        {"onTogglePageSetup" in callbacks ? <button type="button" onClick={() => call("onTogglePageSetup")}>Toggle page setup</button> : null}
        {"onToggleSearchTools" in callbacks ? <button type="button" onClick={() => call("onToggleSearchTools")}>Toggle search tools</button> : null}
        {"onReplaceQueryChange" in callbacks ? <button type="button" onClick={() => { call("onReplaceQueryChange", "amber"); call("onReplaceValueChange", "silver"); call("onReplaceInCurrentChapter") }}>Replace chapter text</button> : null}
        {"onAddCorkboardCard" in callbacks ? <button type="button" onClick={() => { call("onNewCorkboardTitleChange", "New pressure beat"); call("onAddCorkboardCard") }}>Add corkboard card</button> : null}
        {"onSaveGoals" in callbacks ? <button type="button" onClick={() => { call("onWordCountGoalChange", "session_target", 1200); call("onSaveGoals") }}>Save goals</button> : null}
        {"onApplyTemplate" in callbacks ? (
          <button
            type="button"
            onClick={() => call("onApplyTemplate", { id: "template-2", title: "Reversal beat", description: "Force a turn.", content: "Turn the scene." }, "chapter_note")}
          >
            Apply chapter template
          </button>
        ) : null}
        {"onSaveTemplates" in callbacks ? <button type="button" onClick={() => call("onSaveTemplates", [{ id: "template-3", title: "Saved template", description: "Desc", content: "Body" }])}>Save templates</button> : null}
        {"onOpenRightPane" in callbacks ? <button type="button" onClick={() => call("onOpenRightPane", "notes")}>Open notes pane</button> : null}
        {"onOpenCharCard" in callbacks ? (
          <button
            type="button"
            onClick={() => call("onOpenCharCard", {
              id: "char-1",
              name: "Mara",
              role: "mc",
              aliases: ["Gatekeeper"],
              first_chapter: 1,
              last_seen_chapter: 2,
              description: "Mara guards the gate.",
              arc_summary: "She learns to trust.",
              personality_tags: ["guarded"],
              motivations: ["protect the gate"],
              fears: ["betrayal"],
              growth_events: [],
            })}
          >
            Open character card
          </button>
        ) : null}
        {"onBookNoteSaved" in callbacks ? (
          <button
            type="button"
            onClick={() => call("onBookNoteSaved", {
              id: "note-dynamic",
              title: "Injected note",
              body: "Runtime note",
              chapter_number: null,
              updated_at: "2026-01-01T00:00:00Z",
            })}
          >
            Inject note
          </button>
        ) : null}
        {"onSceneDraftChange" in callbacks ? <button type="button" onClick={() => call("onSceneDraftChange", "<p>Changed scene.</p>", "Changed scene.")}>Change scene draft</button> : null}
        {"onSaveScene" in callbacks ? <button type="button" onClick={() => call("onSaveScene")}>Save scene dialog</button> : null}
        {"onCreateSceneSnapshot" in callbacks ? (
          <>
            <button type="button" onClick={() => call("onSceneVersionNameDraftChange", "Scene milestone")}>Name scene version</button>
            <button type="button" onClick={() => call("onCreateSceneSnapshot")}>Snapshot scene dialog</button>
          </>
        ) : null}
        {"onCompareSceneVersion" in callbacks ? <button type="button" onClick={() => call("onCompareSceneVersion", "scene-version-1")}>Compare scene version</button> : null}
        {"onRestoreSceneSnapshot" in callbacks ? <button type="button" onClick={() => call("onRestoreSceneSnapshot", "scene-version-1")}>Restore scene version</button> : null}
        {"onCloseSceneEditor" in callbacks ? <button type="button" onClick={() => call("onCloseSceneEditor")}>Close scene dialog</button> : null}
        {"onCompileManuscript" in callbacks ? <button type="button" onClick={() => call("onCompileManuscript")}>Compile manuscript dialog</button> : null}
        {"onCloseCompileDialog" in callbacks ? <button type="button" onClick={() => call("onCloseCompileDialog")}>Close compile dialog</button> : null}
      </div>
    )
  },
}))

vi.mock("next/navigation", () => ({
  useParams: () => ({ bookId: "book-1" }),
  useRouter: () => routerMock,
  useSearchParams: () => searchParamsMock,
}))

vi.mock("@/components/characters/AddCharacterFromSelection", () => ({
  AddCharacterFromSelection: () => <div data-testid="add-character-selection" />,
}))

vi.mock("@/components/ui/ConfirmDialog", () => ({
  useConfirmDialog: () => vi.fn().mockResolvedValue(true),
}))

vi.mock("@/components/ui/ResponsivenessStatus", () => ({
  LastSavedLabel: ({ updatedAt }: { updatedAt?: string | null }) => <span>Saved {updatedAt ?? "now"}</span>,
  ProcessingStatusStrip: ({ title }: { title?: string }) => <div>{title ?? "Processing status"}</div>,
  RecoverableInlineError: ({ message }: { message?: string }) => <div>{message ?? "Recoverable issue"}</div>,
  SaveStatePill: ({ state }: { state?: string }) => <span>{state ?? "idle"}</span>,
}))

vi.mock("@/components/ui/Skeleton", () => ({
  CardSkeleton: ({ className = "" }: { className?: string }) => <div className={className}>Card loading</div>,
  RowSkeleton: ({ className = "" }: { className?: string }) => <div className={className}>Row loading</div>,
  SidebarSkeleton: ({ className = "" }: { className?: string }) => <div className={className}>Sidebar loading</div>,
  Skeleton: ({ className = "" }: { className?: string }) => <div className={className} />,
}))

vi.mock("@/components/reader/ManuscriptExportMenu", () => ({
  ManuscriptExportMenu: ({
    onCompile,
    onIncludeTableOfContentsChange,
    onPresetChange,
    onPrint,
  }: {
    onCompile?: (format: "pdf" | "docx" | "epub" | "vault") => void
    onIncludeTableOfContentsChange?: (value: boolean) => void
    onPresetChange?: (value: string) => void
    onPrint?: () => void
  }) => (
    <div>
      <button type="button" onClick={() => onCompile?.("pdf")}>Export manuscript</button>
      <button type="button" onClick={() => onPrint?.()}>Print manuscript</button>
      <button type="button" onClick={() => onPresetChange?.("submission_packet")}>Submission preset</button>
      <button type="button" onClick={() => onIncludeTableOfContentsChange?.(true)}>Include TOC</button>
    </div>
  ),
}))

vi.mock("@/components/reader/ManuscriptModeSwitch", () => ({
  ManuscriptModeSwitch: <T extends string>({
    options,
    selected,
    onSelect,
    renderLabel,
  }: {
    options: readonly T[]
    selected: T
    onSelect: (value: T) => void
    renderLabel: (value: T) => ReactNode
  }) => (
    <div>
      {options.map((option) => (
        <button
          key={option}
          type="button"
          aria-pressed={selected === option}
          onClick={() => onSelect(option)}
        >
          {renderLabel(option)}
        </button>
      ))}
    </div>
  ),
}))

vi.mock("@/components/reader/ManuscriptSceneOrderStatus", () => ({
  ManuscriptSceneOrderStatus: ({ state }: { state: string }) => <span>{state}</span>,
}))

vi.mock("@/components/reader/ManuscriptVersionHistory", () => ({
  ManuscriptVersionHistory: ({
    onCreateSnapshot,
    onPreviewSnapshot,
    onRestoreSnapshot,
    onVersionNameChange,
  }: {
    onCreateSnapshot?: () => void
    onPreviewSnapshot?: (versionId: string) => void
    onRestoreSnapshot?: (versionId: string) => void
    onVersionNameChange?: (value: string) => void
  }) => (
    <div>
      Version history
      <button type="button" onClick={() => { onVersionNameChange?.("Milestone"); onCreateSnapshot?.() }}>Create chapter snapshot</button>
      <button type="button" onClick={() => onPreviewSnapshot?.("version-1")}>Preview chapter snapshot</button>
      <button type="button" onClick={() => onRestoreSnapshot?.("version-1")}>Restore chapter snapshot</button>
    </div>
  ),
}))

vi.mock("@/components/reader/ManuscriptWorkspaceSidebarHeader", () => ({
  ManuscriptWorkspaceSidebarHeader: ({ bookTitle, onCreateChapter }: { bookTitle?: string; onCreateChapter: () => void }) => (
    <div>
      <span>{bookTitle}</span>
      <button type="button" onClick={onCreateChapter}>New chapter</button>
    </div>
  ),
}))

vi.mock("@/lib/api/books", () => ({ booksApi: booksApiMock }))
vi.mock("@/lib/api/reader", () => ({
  MANUSCRIPT_CHAPTER_INCLUDE: ["media", "text_content", "html_content"],
  readerApi: readerApiMock,
}))
vi.mock("@/lib/api/intelligence", () => ({ intelligenceApi: intelligenceApiMock }))
vi.mock("@/lib/utils/manuscriptAnnotations", () => ({
  applyAnnotationHighlights: vi.fn(() => new Map()),
  buildAnnotationSelectionAnchor: vi.fn(() => ({
    quote: "amber light",
    anchorContextBefore: "patient",
    anchorContextAfter: "filled",
    startOffset: 12,
    endOffset: 23,
  })),
  clearAnnotationHighlights: vi.fn(),
  MANUSCRIPT_ANNOTATION_CATEGORIES: ["continuity", "clarity"],
  MANUSCRIPT_ANNOTATION_CATEGORY_LABELS: {
    continuity: "Continuity",
    clarity: "Clarity",
  },
  scrollAnnotationRangeIntoView: vi.fn(),
}))
vi.mock("@/lib/analytics/posthog", () => ({ capture: vi.fn(), captureTiming: vi.fn() }))
vi.mock("@/lib/billing/plans", () => ({ canUseAuthorFeatures: () => true }))
vi.mock("@/lib/stores/authStore", () => ({
  useAuthStore: (selector: (state: { hydrated: boolean; user: { tier: string } }) => unknown) =>
    selector({ hydrated: true, user: { tier: "pro" } }),
}))
vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: (selector?: (state: { theme: "dark" }) => unknown) => {
    const state = { theme: "dark" as const }
    return typeof selector === "function" ? selector(state) : state
  },
}))

import ManuscriptPage from "@/app/(reader)/[bookId]/manuscript/page"

let root: Root | null = null
let container: HTMLDivElement | null = null
let queryClient: QueryClient | null = null
const localStorageStore: Record<string, string> = {}
const localStorageMock = {
  getItem: vi.fn((key: string) => localStorageStore[key] ?? null),
  setItem: vi.fn((key: string, value: string) => {
    localStorageStore[key] = value
  }),
  removeItem: vi.fn((key: string) => {
    delete localStorageStore[key]
  }),
  clear: vi.fn(() => {
    Object.keys(localStorageStore).forEach((key) => delete localStorageStore[key])
  }),
}

beforeEach(() => {
  vi.stubGlobal("localStorage", localStorageMock)
  localStorageMock.clear()
  Object.defineProperty(window, "print", { configurable: true, value: vi.fn() })
  Object.defineProperty(window.URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:manuscript") })
  Object.defineProperty(window.URL, "revokeObjectURL", { configurable: true, value: vi.fn() })
  HTMLAnchorElement.prototype.click = vi.fn()
  replaceMock.mockReset()
  pushMock.mockReset()
  Object.values(booksApiMock).forEach((mock) => mock.mockReset())
  Object.values(readerApiMock).forEach((mock) => mock.mockReset())
  Object.values(intelligenceApiMock).forEach((mock) => mock.mockReset())

  const book = buildBook()
  const workspace = buildWorkspace()
  const chapters = buildChapterList()
  const chapter = buildChapter()

  booksApiMock.get.mockResolvedValue(book)
  booksApiMock.createChapterSnapshot.mockResolvedValue({ id: "version-2" })
  booksApiMock.createSceneSnapshot.mockResolvedValue({ id: "scene-version-2" })
  booksApiMock.deleteBookNote.mockResolvedValue({})
  booksApiMock.deleteChapter.mockResolvedValue({})
  booksApiMock.deleteManuscriptAnnotation.mockResolvedValue({})
  booksApiMock.deleteScene.mockResolvedValue({})
  booksApiMock.exportManuscript.mockResolvedValue(new Blob(["manuscript"], { type: "application/pdf" }))
  booksApiMock.getBookNotes.mockResolvedValue([])
  booksApiMock.getChapterVersionDetail.mockResolvedValue({ id: "version-1", text: "Earlier text", title: "Earlier title" })
  booksApiMock.getChapterVersions.mockResolvedValue([])
  booksApiMock.getCharacters.mockResolvedValue([buildRuntimeCharacter()])
  booksApiMock.getEmotionalArc.mockResolvedValue(null)
  booksApiMock.getManuscriptAnnotations.mockResolvedValue([
    {
      id: "annotation-1",
      chapter_number: 2,
      quote: "amber light",
      comment: "Check color.",
      category: "continuity",
      status: "open",
      visibility: "shared",
      can_edit: true,
      created_by_label: "Ada",
      updated_at: "2026-01-01T00:00:00Z",
    },
  ])
  booksApiMock.getManuscriptBootstrap.mockResolvedValue(buildBootstrap(book, workspace))
  booksApiMock.getPreWritingCheck.mockResolvedValue(null)
  booksApiMock.getReadability.mockResolvedValue(null)
  booksApiMock.getRestoreStatus.mockResolvedValue({ restore_status: "done" })
  booksApiMock.getSceneInsertion.mockResolvedValue({ text: "Inserted scene text.", html: "<p>Inserted scene text.</p>" })
  booksApiMock.getSceneVersionDetail.mockResolvedValue({ id: "scene-version-1", body: "Earlier scene", title: "Earlier scene" })
  booksApiMock.getSceneVersions.mockResolvedValue([])
  booksApiMock.getWorkspaceTree.mockResolvedValue(buildWorkspaceTree())
  booksApiMock.getWriterWorkspace.mockResolvedValue(workspace)
  booksApiMock.importManuscript.mockResolvedValue({ imported_chapters: [2], chapter_content_versions: { 2: 4 } })
  booksApiMock.saveChapterContent.mockImplementation((_bookId: string, chapterNumber: number) =>
    Promise.resolve({
      status: "updated",
      book_id: "book-1",
      chapter_number: chapterNumber,
      content_version: 4,
      client_mutation_id: "mutation-1",
      saved_at: "2026-01-01T00:00:00Z",
      story_memory_status: "queued",
    }),
  )
  booksApiMock.listVaultNotes.mockResolvedValue([])
  booksApiMock.reorderChapterScenes.mockResolvedValue({ scene_ids: ["scene-1"], structure_version: 2 })
  booksApiMock.reprocessChapter.mockResolvedValue({})
  booksApiMock.reprocessManuscript.mockResolvedValue({ chapters_queued: 2 })
  booksApiMock.restoreChapterVersion.mockResolvedValue({
    chapter_number: 2,
    title: "The Key",
    text: "Restored chapter text.",
    html: "<p>Restored chapter text.</p>",
    versions: [{ id: "version-1", name: "Draft one", created_at: "2026-01-01T00:00:00Z" }],
  })
  booksApiMock.restoreSceneVersion.mockResolvedValue({ scene: { id: "scene-1", title: "Gate opens", body: "Restored scene.", html: "<p>Restored scene.</p>" } })
  booksApiMock.retryProcessing.mockResolvedValue({ stage: "queued", ready: false })
  booksApiMock.saveBookNote.mockImplementation((_bookId, payload) =>
    Promise.resolve({
      id: payload.noteId ?? "note-saved",
      title: payload.title,
      body: payload.body,
      chapter_number: payload.chapterNumber ?? null,
      updated_at: "2026-01-01T00:00:00Z",
    }),
  )
  booksApiMock.saveManuscriptAnnotation.mockImplementation((_bookId, payload) =>
    Promise.resolve({
      id: payload.annotationId ?? "annotation-new",
      chapter_number: payload.chapterNumber ?? 2,
      quote: payload.quote ?? "amber light",
      comment: payload.comment ?? "Saved annotation.",
      category: payload.category ?? "continuity",
      status: payload.status ?? "open",
      visibility: payload.visibility ?? "shared",
      can_edit: true,
      created_by_label: "Ada",
      updated_at: "2026-01-01T00:00:00Z",
    }),
  )
  booksApiMock.saveScene.mockResolvedValue({ id: "scene-1", title: "Gate opens", body: "Changed scene.", chapter_number: 1 })
  booksApiMock.updateCharacter.mockImplementation((_bookId, _characterId, payload) =>
    Promise.resolve({
      ...buildRuntimeCharacter(),
      description: payload.description,
      arc_summary: payload.arcSummary,
      personality_tags: payload.personalityTags,
      motivations: payload.motivations,
      fears: payload.fears,
    }),
  )
  booksApiMock.updateWriterWorkspace.mockResolvedValue(workspace)

  readerApiMock.getChapter.mockImplementation((_bookId: string, chapterNumber: number) =>
    Promise.resolve({ ...chapter, chapter_number: chapterNumber, chapter_title: chapterNumber === 1 ? "The Door" : "The Key" }),
  )
  readerApiMock.getChapterList.mockResolvedValue(chapters)
  readerApiMock.getPlotThreads.mockResolvedValue([{ id: "thread-1", title: "Gate law", status: "open", introduced_at: 1 }])
  readerApiMock.getTimeline.mockResolvedValue({ events: [] })
  readerApiMock.search.mockResolvedValue([{ chapter_num: 1, chapter_title: "The Door", summary: "Mara opens the gate.", text: "Mara opens the gate.", score: 0.9 }])

  intelligenceApiMock.advisorSuggestions.mockResolvedValue({ suggestions: [{ id: "suggestion-1", chapter_ref: 2, title: "Clarify the key", body: "Tie the key to Mara." }], total: 1, meta: {} })
  intelligenceApiMock.continuityReport.mockResolvedValue(new Blob(["report"], { type: "application/pdf" }))
  intelligenceApiMock.editorialReview.mockResolvedValue({
    review: {
      overall_verdict: "The chapter works with one continuity fix.",
      continuity_issues: [{ severity: "warning", type: "object", title: "Key changes color", description: "The key was brass.", suggestion: "Keep it brass." }],
      insertion_opportunities: [{ title: "Add gate law", target_chapter: 1, target_chapter_title: "The Door", problem: "Rule unclear", what_to_add: "Define the lock rule.", why_here: "It is introduced here.", anchor_excerpt: "The gate opened." }],
    },
    retrieved_passages: [{ chapter_num: 1, chapter_title: "The Door", excerpt: "The gate opened.", chunk_index: 0 }],
  })
  intelligenceApiMock.inlineContinuity.mockResolvedValue({ issues: [] })
  intelligenceApiMock.proseTightenStream.mockResolvedValue({ tightened_text: "Tighter prose.", rationale: ["Tightened the line."] })
  intelligenceApiMock.synopsis.mockResolvedValue({ synopsis: "Mara opens a dangerous gate.", focus_points: ["gate", "key"] })
})

afterEach(() => {
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
})

function renderWithQueryClient(node: ReactNode) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })
  queryClient = client

  act(() => {
    root?.render(<QueryClientProvider client={client}>{node}</QueryClientProvider>)
  })
}

export function renderManuscriptPage() {
  renderWithQueryClient(<ManuscriptPage />)
}

export function getReaderLargePagesContainer() {
  return container
}

export { booksApiMock, intelligenceApiMock, readerApiMock }
export async function flushUi() {
  await act(async () => {
    await Promise.resolve()
    await Promise.resolve()
    await Promise.resolve()
    await new Promise((resolve) => setTimeout(resolve, 0))
  })
}

export async function clickText(text: string) {
  const button = Array.from(container?.querySelectorAll("button") ?? []).find((node) =>
    node.textContent?.includes(text) || node.getAttribute("aria-label") === text,
  )
  expect(button, `button containing ${text}`).toBeTruthy()
  await act(async () => {
    button?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await flushUi()
  })
}

export async function clickTextIfExists(text: string) {
  const button = Array.from(container?.querySelectorAll("button") ?? []).find((node) =>
    node.textContent?.includes(text) || node.getAttribute("aria-label") === text,
  )
  if (!button) return
  await act(async () => {
    button.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await flushUi()
  })
}

export async function clickButtonWithSibling(text: string, siblingText: string) {
  const button = Array.from(container?.querySelectorAll("button") ?? []).find((node) => {
    if (node.textContent?.trim() !== text) return false
    const siblingLabels = Array.from(node.parentElement?.querySelectorAll("button") ?? []).map((sibling) =>
      sibling.textContent?.trim(),
    )
    return siblingLabels.includes(siblingText)
  })
  expect(button, `button ${text} with sibling ${siblingText}`).toBeTruthy()
  await act(async () => {
    button?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await flushUi()
  })
}

export async function changeFieldValue(field: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement, value: string) {
  await act(async () => {
    setFieldValue(field, value)
    await flushUi()
  })
}

function setFieldValue(field: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement, value: string) {
  const prototype =
    field instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : field instanceof HTMLSelectElement
        ? HTMLSelectElement.prototype
        : HTMLInputElement.prototype
  Object.getOwnPropertyDescriptor(prototype, "value")?.set?.call(field, value)
  field.dispatchEvent(new Event(field instanceof HTMLSelectElement ? "change" : "input", { bubbles: true }))
}

function buildBook(): Book {
  return {
    id: "book-1",
    title: "The Ember Gate",
    author: "Ada Rivers",
    genre: "Fantasy",
    format: "docx",
    work_type: "novel",
    status: "ready",
    mode: "author",
    workspace_shell: "author",
    access_class: "owner",
    can_switch_workspace_mode: true,
    total_chapters: 2,
    created_at: "2026-01-01T00:00:00Z",
  } as Book
}

function buildChapterList(): ChapterListResponse {
  return {
    book_id: "book-1",
    total_chapters: 2,
    read_upto: 0,
    chapters: [
      { number: 1, title: "The Door", processed: true, read: true, word_count: 5 },
      { number: 2, title: "The Key", processed: true, read: false, word_count: 7 },
    ],
  } as ChapterListResponse
}

function buildChapter(): ChapterData {
  return {
    chapter_number: 2,
    chapter_title: "The Key",
    text_url: null,
    characters: [],
    text_content: "The opening chamber glowed with a patient amber light.",
    html_content: "<p>The opening chamber glowed with a patient amber light.</p>",
    content_version: 3,
    media: [
      {
        id: "media-1",
        marker: "[image:gate]",
        content_type: "image/png",
        content_base64: "ZmFrZQ==",
        sort_order: 1,
      },
    ],
  } as unknown as ChapterData
}

function buildBootstrap(book: Book, workspace: WriterWorkspace): ManuscriptBootstrapPayload {
  return {
    book,
    characters: [buildRuntimeCharacter() as ManuscriptBootstrapPayload["characters"][number]],
    writer_workspace: workspace,
    emotional_arc: null,
    synopsis: { synopsis: "Mara opens a dangerous gate.", focus_points: ["gate", "key"] } as ManuscriptBootstrapPayload["synopsis"],
    workspace_tree: buildWorkspaceTree() as unknown as ManuscriptBootstrapPayload["workspace_tree"],
    annotations: [{ id: "annotation-1", chapter_number: 2, quote: "amber light", comment: "Check color.", category: "continuity", status: "open", visibility: "shared", can_edit: true }] as ManuscriptBootstrapPayload["annotations"],
    notes: [
      { id: "note-1", title: "Chapter note", body: "Remember the key.", chapter_number: 2, updated_at: "2026-01-01T00:00:00Z" },
      { id: "note-2", title: "Book note", body: "Overall theme.", chapter_number: null, updated_at: "2026-01-01T00:00:00Z" },
    ] as ManuscriptBootstrapPayload["notes"],
    vault_notes: [{ id: "vault-1", title: "Gate lore", content: "The gate needs a brass key.", path: "World/Gate.md", updated_at: "2026-01-01T00:00:00Z" }] as unknown as ManuscriptBootstrapPayload["vault_notes"],
    chapter_versions: [{ id: "version-1", name: "Draft one", created_at: "2026-01-01T00:00:00Z" }] as unknown as ManuscriptBootstrapPayload["chapter_versions"],
    prewriting_check: null,
  }
}

function buildRuntimeCharacter() {
  return {
    id: "char-1",
    name: "Mara",
    role: "mc",
    aliases: ["Gatekeeper"],
    first_chapter: 1,
    last_seen_chapter: 2,
    description: "Mara guards the gate.",
    arc_summary: "She learns to trust.",
    personality_tags: ["guarded"],
    motivations: ["protect the gate"],
    fears: ["betrayal"],
    growth_events: [{ chapter_number: 2, event_title: "Trusts Theo", impact_score: 7, is_major: true }],
  }
}

function buildWorkspaceTree() {
  return {
    scene_groups: [
      {
        id: "chapter-1",
        label: "Chapter 1",
        chapter_number: 1,
        title: "The Door",
        collapsed_by_default: false,
        scenes: [
          {
            id: "scene-1",
            title: "Gate opens",
            chapter_number: 1,
            scene_index: 0,
            sort_order: 1,
            description: "A discovery opens the route forward.",
            body: "A discovery opens the route forward.",
            html: "<p>A discovery opens the route forward.</p>",
            path: "Chapter 1 / Gate opens",
            pov_character_id: null,
            status: "draft",
            beat_type: "opening",
            word_count: 7,
          },
        ],
      },
    ],
    unassigned_scenes: [],
  }
}

function buildWorkspace(): WriterWorkspace {
  return {
    word_count_goals: {
      chapter_target: 2500,
      book_target: 80000,
      session_target: 1000,
    },
    goal_calendar: [],
    corkboard_cards: [
      {
        id: "card-1",
        lane: "setup",
        title: "Open the gate",
        description: "Establish the locked gate and the protagonist's choice.",
        chapter_number: 1,
        status: "planned",
      },
    ],
    templates: [
      {
        id: "template-1",
        kind: "chapter",
        title: "Scene pressure",
        description: "Start with pressure and finish with a turn.",
        content: "Pressure\nTurn",
      },
    ],
    publishing: {
      active_preset: "standard_manuscript",
      trim_size: "8.5x11",
      include_title_page: true,
      mirror_margins: false,
    },
    manuscript_front_matter: {
      author_name: "Ada Rivers",
      pen_name: "",
      contact_email: "",
      contact_phone: "",
      contact_address: "",
      title: "The Ember Gate",
      subtitle: "",
      header_last_name: "Rivers",
      header_title: "Ember",
      dedication: "",
      acknowledgments: "",
      epigraph: "",
      prologue: "",
      include_dedication: false,
      include_acknowledgments: false,
      include_epigraph: false,
      include_prologue: false,
    },
    novel_preface: "",
    revision_board: {
      items: [],
    },
    editor_preferences: {
      font_family: "georgia",
      font_size: 18,
      line_height: 1.7,
      paragraph_spacing: 0.8,
      focus_mode: false,
    },
    reading_themes: {
      active_theme: "classic",
    },
    typewriter_mode: {
      enabled: false,
      highlight_current_line: false,
    },
    manuscript_layout: {
      page_size: "letter",
      margin: "normal",
      columns: 1,
    },
    structure_tree: [],
    reprocess: {
      auto_reprocess_enabled: true,
      pending_chapters: [2],
    },
    processing: null,
    index_format: "number",
  } as unknown as WriterWorkspace
}
