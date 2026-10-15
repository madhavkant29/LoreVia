import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { useManuscriptChapterLoading } from "./manuscriptPage.chapterLoading"

const api = vi.hoisted(() => ({ bootstrap: vi.fn(), chapters: vi.fn(), chapter: vi.fn() }))
vi.mock("@/lib/api/books", () => ({ booksApi: { getManuscriptBootstrap: api.bootstrap } }))
vi.mock("@/lib/api/reader", () => ({ MANUSCRIPT_CHAPTER_INCLUDE: [], readerApi: { getChapterList: api.chapters, getChapter: api.chapter } }))
vi.mock("@/lib/analytics/posthog", () => ({ captureTiming: vi.fn() }))

let root: Root | undefined
let result: ReturnType<typeof useManuscriptChapterLoading>
const chapter = { chapter_number: 1, chapter_title: "The harbour", text_content: "The keeper returned before dawn.", html_content: "<p>The keeper returned before dawn.</p>", content_version: 1, media: [] }

beforeEach(() => {
  vi.stubGlobal("localStorage", { getItem: () => null, removeItem: vi.fn() })
  api.bootstrap.mockReset().mockResolvedValue({ profile: "critical", book: { mode: "author", access_class: "owner" }, characters: [], writer_workspace: null, workspace_tree: null })
  api.chapters.mockReset().mockResolvedValue({ chapters: [{ number: 1, title: "The harbour" }] })
  api.chapter.mockReset().mockResolvedValue(chapter)
})
afterEach(() => { act(() => root?.unmount()); document.body.innerHTML = ""; vi.unstubAllGlobals() })

async function mount() {
  const setters = Object.fromEntries([
    "AutosaveState", "Book", "BookDrafts", "ChapterList", "ChapterTitle", "Characters", "CollapsedSceneGroups", "ContentVersionByChapter", "DirtyDrafts", "DraftChapterNumber", "FullBookLoading", "Html", "Loading", "Review", "ReviewPassages", "SelectedChapter", "StatusMessage", "Text", "WorkspaceTree", "WriterWorkspace",
  ].map((name) => [`set${name}`, vi.fn()]))
  const args = {
    ...setters, authHydrated: true, bookDrafts: {}, bookId: "book-1", chapterList: null,
    editorMode: "chapter", nextChapterNumber: 1, selectedChapter: null, userTier: "author",
    queryClient: { setQueryData: vi.fn() }, router: { replace: vi.fn() },
    deferredChecksSeedRef: { current: null }, firstChapterLoadedCapturedRef: { current: false },
    initialChapterLoadedRef: { current: null }, manuscriptLoadStartedAtRef: { current: 0 }, refetchWorkspaceTree: vi.fn(),
  } as unknown as Parameters<typeof useManuscriptChapterLoading>[0]
  function Harness() { result = useManuscriptChapterLoading(args); return null }
  const host = document.createElement("div")
  document.body.appendChild(host)
  root = createRoot(host)
  await act(async () => root?.render(<Harness />))
  return setters
}

describe("manuscript loading recovery", () => {
  it("handles a failed bootstrap and recovers through the retry action", async () => {
    api.bootstrap.mockRejectedValueOnce(new Error("offline"))
    const setters = await mount()
    expect(result.loadError).toContain("Your manuscript could not be loaded")
    await act(async () => result.retryLoad())
    expect(result.loadError).toBeNull()
    expect(setters.setText).toHaveBeenLastCalledWith(chapter.text_content)
    expect(setters.setLoading).toHaveBeenLastCalledWith(false)
  })

  it("reports a failed chapter without presenting it as successfully loaded", async () => {
    api.chapter.mockRejectedValueOnce(new Error("offline"))
    const setters = await mount()
    expect(result.loadError).toContain("Chapter 1 could not be loaded")
    expect(setters.setBookDrafts).not.toHaveBeenCalled()
    await act(async () => result.retryLoad())
    expect(result.loadError).toBeNull()
    expect(setters.setText).toHaveBeenLastCalledWith(chapter.text_content)
  })
})
