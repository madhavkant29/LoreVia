// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const booksApiMock = vi.hoisted(() => ({
  deleteScene: vi.fn(),
  getWorkspaceTree: vi.fn(),
  saveScene: vi.fn(),
}))
const useBookDetailMock = vi.hoisted(() => vi.fn())
const paramsMock = vi.hoisted(() => ({ bookId: "book-1" }))
const promptMock = vi.hoisted(() => vi.fn())
const confirmMock = vi.hoisted(() => vi.fn())
const routerMock = vi.hoisted(() => ({ push: vi.fn() }))

vi.mock("next/navigation", () => ({ useParams: () => paramsMock, useRouter: () => routerMock }))
vi.mock("next/link", () => ({
  default: ({ children, href, prefetch: _prefetch, ...props }: { children: ReactNode; href: string; prefetch?: boolean | null }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))
vi.mock("next/dynamic", () => ({
  default: (loader: () => Promise<unknown>) => {
    const source = String(loader)
    if (source.includes("SharedRichTextEditor") && source.includes("EditorToolbar")) {
      return function EditorToolbarStub() {
        return <div data-testid="editor-toolbar">Toolbar</div>
      }
    }
    if (source.includes("SharedRichTextEditor")) {
      return function RichTextEditorStub({ html, onChange }: { html: string; onChange: (html: string, text: string) => void }) {
        return (
          <div data-editor-key="scene-workspace-editor">
            <div data-testid="rich-text-html">{html}</div>
            <button type="button" onClick={() => onChange("<p>New scene body with more words.</p>", "New scene body with more words.")}>
              Write body
            </button>
          </div>
        )
      }
    }
    return function WhatsTheWordPanelStub() {
      return <div data-testid="word-finder">Word finder ready</div>
    }
  },
}))
vi.mock("@/components/characters/AddCharacterFromSelection", () => ({
  AddCharacterFromSelection: ({ open, selectedText }: { open: boolean; selectedText: string }) =>
    open ? <div data-testid="add-character-selection">{selectedText}</div> : null,
}))
vi.mock("@/lib/api/books", () => ({ booksApi: booksApiMock }))
vi.mock("@/lib/hooks/useBookDetail", () => ({
  useBookDetail: useBookDetailMock,
  useCachedBookDetail: useBookDetailMock,
}))
vi.mock("@/lib/stores/preferencesStore", () => ({ usePreferencesStore: () => ({ theme: "dark" }) }))
vi.mock("@/components/ui/PromptDialog", () => ({ usePromptDialog: () => promptMock }))
vi.mock("@/components/ui/ConfirmDialog", () => ({ useConfirmDialog: () => confirmMock }))

import ScenesPage from "@/app/(reader)/[bookId]/scenes/page"

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

const baseTree = {
  chapters: [
    { chapter_number: 1, title: "Ash Market" },
    { chapter_number: 2, title: "Gate Law" },
  ],
  scene_groups: [
    {
      chapter_number: 1,
      scenes: [
        {
          id: "scene-1",
          title: "Opening Gate",
          description: "Mira notices ash marks.",
          body: "Mira opens the gate.",
          html_body: "<p>Mira opens the gate.</p>",
          path: "scenes/chapter-01/opening-gate.md",
          chapter_number: 1,
          status: "assigned",
          sort_order: 1,
          metadata: {
            pov: "Mira",
            timeline: "Day 1",
            location: "Gatehouse",
            tags: ["gate", "ash"],
            mood: ["tense"],
            status_note: "draft",
            summary: "The first gate scene.",
          },
        },
      ],
    },
    {
      chapter_number: null,
      scenes: [
        {
          id: "scene-2",
          title: "Unassigned Note",
          description: "",
          body: "Loose beat.",
          html_body: "<p>Loose beat.</p>",
          path: "scenes/unassigned/unassigned-note.md",
          chapter_number: null,
          status: "unassigned",
          sort_order: 2,
          metadata: {},
        },
      ],
    },
  ],
  structure_tree: [
    {
      id: "chapter-1",
      label: "Chapter 1",
      kind: "chapter",
      chapter_number: 1,
      children: [
        {
          id: "scene-1",
          label: "Opening Gate",
          kind: "scene",
          chapter_number: 1,
          scene_id: "scene-1",
          children: [],
        },
      ],
    },
  ],
}

async function renderPage(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  queryClient = client
  await act(async () => {
    root?.render(<QueryClientProvider client={client}>{element}</QueryClientProvider>)
    await Promise.resolve()
  })
}

async function waitForText(expected: string) {
  for (let index = 0; index < 30; index += 1) {
    if ((container?.textContent ?? "").includes(expected)) return
    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 0))
    })
  }
  throw new Error(`Expected text not found: ${expected}. Saw: ${container?.textContent}`)
}

function text() {
  return container?.textContent ?? ""
}

async function clickByText(label: string) {
  const match = Array.from(container?.querySelectorAll("button") ?? []).find((button) =>
    button.textContent?.includes(label) || button.getAttribute("aria-label") === label
  )
  if (!match) throw new Error(`Missing button: ${label}`)
  await act(async () => {
    match.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await Promise.resolve()
  })
}

function setFieldValue(field: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement, value: string) {
  const prototype =
    field instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : field instanceof HTMLInputElement
        ? HTMLInputElement.prototype
        : HTMLSelectElement.prototype
  const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set
  setter?.call(field, value)
  field.dispatchEvent(new Event(field instanceof HTMLSelectElement ? "change" : "input", { bubbles: true }))
}

beforeEach(() => {
  vi.stubGlobal("matchMedia", () => ({ matches: true, addEventListener: vi.fn(), removeEventListener: vi.fn() }))
  confirmMock.mockResolvedValue(true)
  Object.defineProperty(window, "localStorage", { configurable: true, value: localStorageMock })
  window.localStorage.clear()
  promptMock.mockResolvedValue("scenes/chapter-02/new arc")
  useBookDetailMock.mockReturnValue({
    data: { id: "book-1", title: "The Ember Gate", work_type: "novel" },
  })
  booksApiMock.getWorkspaceTree.mockResolvedValue(baseTree)
  booksApiMock.saveScene.mockResolvedValue({ id: "scene-1" })
  booksApiMock.deleteScene.mockResolvedValue({})
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
  queryClient?.clear()
  queryClient = null
  document.body.innerHTML = ""
  vi.clearAllMocks()
  vi.unstubAllGlobals()
})

describe("ScenesPage", () => {
  it("protects dirty navigation and page unload while allowing explicit discard", async () => {
    await renderPage(<ScenesPage />)
    await waitForText("Mira opens the gate.")
    act(() => setFieldValue(container!.querySelector<HTMLInputElement>("#scene-title")!, "Unsaved title"))
    const unload = new Event("beforeunload", { cancelable: true })
    window.dispatchEvent(unload)
    expect(unload.defaultPrevented).toBe(true)
    const link = document.createElement("a")
    link.href = "/book-1/chapters"
    document.body.appendChild(link)
    confirmMock.mockResolvedValueOnce(false)
    await act(async () => { link.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true })); await Promise.resolve() })
    expect(routerMock.push).not.toHaveBeenCalled()
    await act(async () => { link.dispatchEvent(new MouseEvent("click", { bubbles: true, cancelable: true })); await Promise.resolve() })
    expect(routerMock.push).toHaveBeenCalledWith("/book-1/chapters")
  })

  it("treats angle brackets in plain scene text as text when HTML is absent", async () => {
    booksApiMock.getWorkspaceTree.mockResolvedValue({ ...baseTree, scene_groups: [{ chapter_number: 1, scenes: [{ ...baseTree.scene_groups[0].scenes[0], body: "<gate> & rain", html_body: null }] }] })
    await renderPage(<ScenesPage />)
    await waitForText("&lt;gate&gt; &amp; rain")
  })

  it("preserves edits during refresh and when starting a new scene is cancelled", async () => {
    await renderPage(<ScenesPage />)
    await waitForText("Mira opens the gate.")
    const title = container!.querySelector<HTMLInputElement>("#scene-title")!
    act(() => setFieldValue(title, "Unsaved revision"))
    const refreshed = structuredClone(baseTree)
    refreshed.scene_groups[0].scenes[0].title = "Server revision"
    booksApiMock.getWorkspaceTree.mockResolvedValue(refreshed)
    await act(async () => { await queryClient!.refetchQueries() })
    expect(title.value).toBe("Unsaved revision")
    confirmMock.mockResolvedValueOnce(false)
    await clickByText("New scene")
    expect(title.value).toBe("Unsaved revision")
    expect(confirmMock).toHaveBeenCalledWith(expect.objectContaining({ title: "Discard unsaved scene changes?" }))
    await clickByText("New scene")
    expect(title.value).toBe("")
    await act(async () => { await queryClient!.refetchQueries() })
    expect(title.value).toBe("")
  })

  it("keeps a failed save editable and retries without losing the submitted draft", async () => {
    await renderPage(<ScenesPage />)
    await waitForText("Mira opens the gate.")
    const title = container!.querySelector<HTMLInputElement>("#scene-title")!
    act(() => setFieldValue(title, "Revised gate"))
    booksApiMock.saveScene.mockRejectedValueOnce(new Error("Offline"))
    await clickByText("Save scene")
    await waitForText("Could not save this scene")
    expect(title.value).toBe("Revised gate")
    await clickByText("Save scene")
    expect(booksApiMock.saveScene).toHaveBeenLastCalledWith("book-1", expect.objectContaining({ id: "scene-1", title: "Revised gate" }))
    await waitForText("Scene saved.")
  })

  it("confirms deletion and keeps the scene after a failed delete", async () => {
    await renderPage(<ScenesPage />)
    await waitForText("Mira opens the gate.")
    confirmMock.mockResolvedValueOnce(false)
    await clickByText("Delete")
    expect(booksApiMock.deleteScene).not.toHaveBeenCalled()
    booksApiMock.deleteScene.mockRejectedValueOnce(new Error("Offline"))
    await clickByText("Delete")
    await waitForText("Could not delete this scene")
    expect(container!.querySelector<HTMLInputElement>("#scene-title")!.value).toBe("Opening Gate")
  })

  it("keeps the editor available when refreshing an existing tree fails", async () => {
    await renderPage(<ScenesPage />)
    await waitForText("Mira opens the gate.")
    booksApiMock.getWorkspaceTree.mockRejectedValueOnce(new Error("Offline"))
    await act(async () => { await queryClient!.refetchQueries() })
    await waitForText("Could not refresh the scene list")
    expect(text()).toContain("Mira opens the gate.")
    expect(text()).not.toContain("Scene workspace unavailable")
  })

  it("renders scene workspace and drives folder, search, edit, save, and delete flows", async () => {
    await renderPage(<ScenesPage />)
    await waitForText("Mira opens the gate.")

    expect(text()).toContain("Scenes")
    expect(text()).toContain("The Ember Gate · Draft and organize scene files.")
    await clickByText("Outline")
    await waitForText("Opening Gate")
    expect(text()).toContain("Mira notices ash marks.")
    await clickByText("Details")
    expect(text()).toContain("scenes/chapter-01/opening-gate.md")

    await clickByText("Open word finder")
    expect(text()).toContain("Word finder ready")

    await clickByText("Scenes")
    const searchInput = container?.querySelector("aside input") as HTMLInputElement
    act(() => {
      setFieldValue(searchInput, "missing")
    })
    expect(text()).toContain("No scenes match this view.")
    act(() => {
      setFieldValue(searchInput, "Opening")
    })
    expect(text()).toContain("Opening Gate")

    await clickByText("New folder")
    expect(promptMock).toHaveBeenCalled()
    expect(text()).toContain("Created folder scenes/chapter-02/new arc")

    await clickByText("New scene")
    const fields = Array.from(container?.querySelectorAll("input, textarea, select") ?? []) as Array<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
    const titleInput = fields.find((field) => field instanceof HTMLInputElement && field.value === "") as HTMLInputElement
    const descriptionInput = Array.from(container?.querySelectorAll("textarea") ?? [])[0] as HTMLTextAreaElement
    await act(async () => {
      setFieldValue(titleInput, "Market Ambush")
      setFieldValue(descriptionInput, "Mira is ambushed at the ash market.")
      await Promise.resolve()
    })
    await clickByText("Write body")
    await clickByText("Save scene")
    await act(async () => {
      await Promise.resolve()
      await Promise.resolve()
    })

    expect(booksApiMock.saveScene).toHaveBeenCalledWith("book-1", expect.objectContaining({
      title: "Market Ambush",
      description: "Mira is ambushed at the ash market.",
      body: "New scene body with more words.",
      path: expect.stringContaining("market-ambush.md"),
    }))

    await clickByText("Delete")
    expect(booksApiMock.deleteScene).toHaveBeenCalledWith("book-1", "scene-1")
  })

  it("shows retry state when the scene tree query fails", async () => {
    booksApiMock.getWorkspaceTree.mockRejectedValueOnce(new Error("offline"))

    await renderPage(<ScenesPage />)
    await waitForText("Scene workspace unavailable")

    expect(text()).toContain("Try again to refresh the folder tree")
    await clickByText("Retry")
    expect(booksApiMock.getWorkspaceTree).toHaveBeenCalled()
  })
})
