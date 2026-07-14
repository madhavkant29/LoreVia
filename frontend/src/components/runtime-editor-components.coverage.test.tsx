// @vitest-environment jsdom

import { act, type ReactElement } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const intelligenceApiMock = vi.hoisted(() => ({
  continuityReport: vi.fn(),
}))

vi.mock("@/components/editor/SharedRichTextEditor", () => ({
  EditorToolbar: ({ editorKey }: { editorKey: string }) => <div>Toolbar {editorKey}</div>,
  RichTextEditor: ({ html, onChange }: { html: string; onChange: (html: string, text: string) => void }) => (
    <button type="button" onClick={() => onChange("<p>Updated scene</p>", "Updated scene")}>
      Rich editor {html}
    </button>
  ),
}))
vi.mock("@/lib/api/intelligence", () => ({ intelligenceApi: intelligenceApiMock }))

import { ImportStructureEditor } from "@/components/modals/ImportStructureEditor"
import { EditorialReviewResults } from "@/components/reader/EditorialReviewResults"
import { ManuscriptOverlayDialogs } from "@/components/reader/ManuscriptOverlayDialogs"

let root: Root | null = null
let container: HTMLDivElement | null = null

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

beforeEach(() => {
  intelligenceApiMock.continuityReport.mockResolvedValue(new Blob(["report"], { type: "application/pdf" }))
  Object.defineProperty(URL, "createObjectURL", { configurable: true, value: vi.fn(() => "blob:report") })
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: vi.fn() })
  Object.defineProperty(HTMLAnchorElement.prototype, "click", { configurable: true, value: vi.fn() })
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

describe("runtime editor components", () => {
  it("edits import structure with quick marks, merge, delete, cancel, and save", async () => {
    const onSave = vi.fn()
    const onCancel = vi.fn()
    await render(
      <ImportStructureEditor
        sections={[
          { id: "s1", type: "preface", title: "Opening", number: 1, confidence: 0.8, include_in_analysis: true },
          { id: "s2", type: "chapter", title: "Chapter One", number: 2, confidence: 0.7, include_in_analysis: true },
          { id: "s3", type: "toc", title: "Contents", number: 3, confidence: 0.4, include_in_analysis: false },
        ] as never}
        onCancel={onCancel}
        onSave={onSave}
      />,
    )

    expect(text()).toContain("Edit section structure")
    setInputValue('input[aria-label="Section 1 title"]', "Updated Opening")
    await click("All chapters")
    await click("Merge")
    await click("Merge with #2")
    await click("Delete")
    await click("Cancel")
    await click("Save changes")

    expect(onCancel).toHaveBeenCalled()
    expect(onSave).toHaveBeenCalled()
    expect(onSave.mock.calls[0][0]).toHaveLength(1)
  })

  it("renders editorial review results and drives save and continuity report actions", async () => {
    const onSaveNote = vi.fn().mockResolvedValue(undefined)
    await render(
      <EditorialReviewResults
        bookId="book-1"
        chapterNumber={4}
        editText="Mara breaks the gate rule."
        editPassages={[{ chapter_num: 2, chapter_title: "The Rule", excerpt: "The rule was sworn.", relevance: 0.9 }]}
        editResult={{
          overall_verdict: "Strong scene with continuity risks.",
          thematic_fit: { score: "weak", notes: "Theme needs a clearer echo." },
          continuity_issues: [
            {
              title: "Gate oath contradiction",
              severity: "critical",
              type: "timeline",
              description: "Mara breaks a rule she has not learned yet.",
              suggestion: "Move the oath earlier.",
            },
          ],
          grammar_issues: [
            { issue: "Comma splice", original: "The gate opens, Mara runs", fix: "The gate opens, and Mara runs." },
          ],
          formatting_notes: ["Scene break needs spacing."],
        } as never}
        isDark={false}
        onSaveNote={onSaveNote}
      />,
    )

    expect(text()).toContain("Overall verdict")
    await click("Save summary note")
    await click("Download continuity report")
    await click("Save note (Ch. 4)")
    await click("Save note", 1)
    await click("Save note", 2)

    expect(onSaveNote).toHaveBeenCalled()
    expect(intelligenceApiMock.continuityReport).toHaveBeenCalledWith("book-1", "Mara breaks the gate rule.", "pdf", 4)
    expect(URL.createObjectURL).toHaveBeenCalled()

    await rerender(
      <EditorialReviewResults
        bookId="book-1"
        chapterNumber={null}
        editText=""
        editPassages={[]}
        editResult={{
          overall_verdict: "Clean.",
          thematic_fit: { score: "strong", notes: "Theme lands." },
          continuity_issues: [],
          grammar_issues: [],
          formatting_notes: [],
        } as never}
        isDark
        onSaveNote={onSaveNote}
      />,
    )
    expect(text()).toContain("No continuity or grammar issues found")
  })

  it("renders manuscript overlay scene and compile dialogs with callbacks", async () => {
    const handlers = {
      onCloseSceneEditor: vi.fn(),
      onSceneTitleDraftChange: vi.fn(),
      onSceneChapterDraftChange: vi.fn(),
      onSceneDescriptionDraftChange: vi.fn(),
      onSceneDraftChange: vi.fn(),
      onSceneVersionNameDraftChange: vi.fn(),
      onCreateSceneSnapshot: vi.fn(),
      onCompareSceneVersion: vi.fn(),
      onRestoreSceneSnapshot: vi.fn(),
      onSaveScene: vi.fn(),
      onCloseCompileDialog: vi.fn(),
      onIncludeSceneMetadataOnExportChange: vi.fn(),
      onIncludeTableOfContentsOnExportChange: vi.fn(),
      onUpdateFrontMatter: vi.fn(),
      onCompileManuscript: vi.fn(),
    }

    await render(<ManuscriptOverlayDialogs {...overlayProps(handlers)} />)

    expect(text()).toContain("Edit chapter scene")
    expect(text()).toContain("Compile manuscript")
    setInputValue("input", "Gate revised")
    await click("Rich editor")
    await click("Save named version")
    await click("Compare")
    await click("Restore")
    await click("Save scene")
    await clickCheckbox(0)
    await clickCheckbox(1)
    await click("Compile PDF")
    await click("Close")

    expect(handlers.onSceneTitleDraftChange).toHaveBeenCalledWith("Gate revised")
    expect(handlers.onSceneDraftChange).toHaveBeenCalledWith("<p>Updated scene</p>", "Updated scene")
    expect(handlers.onCompareSceneVersion).toHaveBeenCalledWith("version-1")
    expect(handlers.onRestoreSceneSnapshot).toHaveBeenCalledWith("version-1")
    expect(handlers.onCompileManuscript).toHaveBeenCalled()
  })
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

async function click(label: string, index = 0) {
  const button = Array.from(container?.querySelectorAll("button") ?? []).filter((node) => node.textContent?.includes(label))[index]
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

async function clickCheckbox(index: number) {
  const input = Array.from(container?.querySelectorAll('input[type="checkbox"]') ?? [])[index] as HTMLInputElement | undefined
  if (!input) throw new Error(`Missing checkbox ${index}`)
  await act(async () => {
    input.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await flush()
  })
}

function overlayProps(handlers: Record<string, ReturnType<typeof vi.fn>>) {
  return {
    isDark: false,
    sceneEditorOpen: true,
    editingScene: { id: "scene-1", title: "Gate opens" },
    sceneTitleDraft: "Gate opens",
    sceneChapterDraft: 1,
    workspaceTree: { chapters: [{ chapter_number: 1 }] },
    sceneDescriptionDraft: "Mara reaches the gate.",
    characters: [{ id: "char-1", name: "Mara" }],
    sceneHtmlDraft: "<p>Gate opens</p>",
    sceneVersions: [{ id: "version-1", note: "First pass", scene_title: "Gate opens", created_at: "2026-01-01T00:00:00Z", word_count: 120, snapshot_kind: "manual" }],
    sceneVersionNameDraft: "Milestone",
    sceneVersionDetail: { id: "version-1", body: "Saved text" },
    restoringSceneVersionId: null,
    sceneBodyDraft: "Current text",
    sceneSaving: false,
    showCompileDialog: true,
    writerWorkspace: { publishing: { active_preset: "standard_manuscript" } },
    manuscriptFrontMatter: {
      author_name: "Ada Rivers",
      pen_name: "A. Rivers",
      contact_email: "ada@example.com",
      contact_phone: "555",
      contact_address: "1 Gate Road",
      title: "The Lantern Gate",
      subtitle: "A Novel",
      header_last_name: "Rivers",
      header_title: "Lantern",
      dedication: "For readers",
      acknowledgments: "Thanks",
      epigraph: "Open",
      prologue: "Before",
      include_dedication: false,
      include_acknowledgments: false,
      include_epigraph: false,
      include_prologue: false,
    },
    compileFormat: "pdf" as const,
    fullBookWordCount: 82000,
    includeSceneMetadataOnExport: true,
    includeTableOfContentsOnExport: false,
    exporting: null,
    workspaceSaving: false,
    ...handlers,
  } as React.ComponentProps<typeof ManuscriptOverlayDialogs>
}
