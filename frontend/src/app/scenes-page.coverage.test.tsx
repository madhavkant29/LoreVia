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

vi.mock("next/navigation", () => ({ useParams: () => paramsMock }))
vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
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
vi.mock("@/lib/hooks/useBookDetail", () => ({ useBookDetail: useBookDetailMock }))
vi.mock("@/lib/stores/preferencesStore", () => ({ usePreferencesStore: () => ({ theme: "dark" }) }))

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

function clickByText(label: string) {
  const match = Array.from(container?.querySelectorAll("button") ?? []).find((button) =>
    button.textContent?.includes(label) || button.getAttribute("aria-label") === label
  )
  if (!match) throw new Error(`Missing button: ${label}`)
  act(() => {
    match.dispatchEvent(new MouseEvent("click", { bubbles: true }))
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
  Object.defineProperty(window, "localStorage", { configurable: true, value: localStorageMock })
  window.localStorage.clear()
  window.prompt = vi.fn(() => "scenes/chapter-02/new arc")
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
})

describe("ScenesPage", () => {
  it("renders scene workspace and drives folder, search, edit, save, and delete flows", async () => {
    await renderPage(<ScenesPage />)
    await waitForText("Opening Gate")

    expect(text()).toContain("The Ember Gate scenes")
    expect(text()).toContain("Mira notices ash marks.")
    expect(text()).toContain("The first gate scene.")
    expect(text()).toContain("scenes/chapter-01/opening-gate.md")

    clickByText("Open word finder")
    expect(text()).toContain("Word finder ready")

    clickByText("Scenes")
    const searchInput = container?.querySelector("aside input") as HTMLInputElement
    act(() => {
      setFieldValue(searchInput, "missing")
    })
    expect(text()).toContain("No scenes match this view.")
    act(() => {
      setFieldValue(searchInput, "Opening")
    })
    expect(text()).toContain("Opening Gate")

    clickByText("New folder")
    expect(window.prompt).toHaveBeenCalled()
    expect(text()).toContain("Created folder scenes/chapter-02/new arc")

    clickByText("New scene")
    const fields = Array.from(container?.querySelectorAll("input, textarea, select") ?? []) as Array<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
    const titleInput = fields.find((field) => field instanceof HTMLInputElement && field.value === "") as HTMLInputElement
    const descriptionInput = Array.from(container?.querySelectorAll("textarea") ?? [])[0] as HTMLTextAreaElement
    act(() => {
      setFieldValue(titleInput, "Market Ambush")
      setFieldValue(descriptionInput, "Mira is ambushed at the ash market.")
      clickByText("Write body")
    })
    await act(async () => {
      clickByText("Save scene")
      await Promise.resolve()
      await Promise.resolve()
    })

    expect(booksApiMock.saveScene).toHaveBeenCalledWith("book-1", expect.objectContaining({
      title: "Market Ambush",
      description: "Mira is ambushed at the ash market.",
      body: "New scene body with more words.",
      path: expect.stringContaining("market-ambush.md"),
    }))

    clickByText("Delete")
    expect(booksApiMock.deleteScene).toHaveBeenCalledWith("book-1", "scene-1")
  })

  it("shows retry state when the scene tree query fails", async () => {
    booksApiMock.getWorkspaceTree.mockRejectedValueOnce(new Error("offline"))

    await renderPage(<ScenesPage />)
    await waitForText("Scene workspace unavailable")

    expect(text()).toContain("Try again to refresh the folder tree")
    await act(async () => {
      clickByText("Retry")
      await Promise.resolve()
    })
    expect(booksApiMock.getWorkspaceTree).toHaveBeenCalled()
  })
})
