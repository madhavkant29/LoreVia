// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const saveVaultNote = vi.fn()
const deleteVaultNote = vi.fn()
const getVaultGraph = vi.fn()
const exportVaultNotes = vi.fn()
const importVaultNotes = vi.fn()
const listVaultNotes = vi.fn()
const getVaultNoteRelations = vi.fn()
const getWorkspaceTree = vi.fn()
const saveScene = vi.fn()
const confirmDialog = vi.fn()
const promptDialog = vi.fn()

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock("@/components/ui/ShortcutHelp", () => ({ SUPPORT_HELP_EVENT: "lorevia:open-support-help" }))
vi.mock("@/components/ui/WorkspaceSidePanel", () => ({ WorkspaceSidePanel: ({ children, onClose }: { children: ReactNode; onClose: () => void }) => <div><button onClick={onClose}>Close</button>{children}</div> }))
vi.mock("@/components/ui/Dialog", () => ({ Dialog: ({ children }: { children: ReactNode }) => <div>{children}</div> }))

vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a>,
}))

vi.mock("next/dynamic", () => ({
  default: () => (props: Record<string, unknown>) => (
    <div data-testid="dynamic-panel">
      {"content" in props ? String(props.content) : "graph" in props ? "Graph viewer" : "Dynamic panel"}
    </div>
  ),
}))

vi.mock("@/lib/api/books", () => ({
  booksApi: {
    saveVaultNote: (...args: unknown[]) => saveVaultNote(...args),
    deleteVaultNote: (...args: unknown[]) => deleteVaultNote(...args),
    getVaultGraph: (...args: unknown[]) => getVaultGraph(...args),
    exportVaultNotes: (...args: unknown[]) => exportVaultNotes(...args),
    importVaultNotes: (...args: unknown[]) => importVaultNotes(...args),
    listVaultNotes: (...args: unknown[]) => listVaultNotes(...args),
    getVaultNoteRelations: (...args: unknown[]) => getVaultNoteRelations(...args),
    getWorkspaceTree: (...args: unknown[]) => getWorkspaceTree(...args),
    saveScene: (...args: unknown[]) => saveScene(...args),
  },
}))

vi.mock("@/components/characters/AddCharacterFromSelection", () => ({
  AddCharacterFromSelection: ({ open, selectedText }: { open: boolean; selectedText: string }) =>
    open ? <div data-testid="add-character">{selectedText}</div> : null,
}))

vi.mock("@/components/ui/ConfirmDialog", () => ({
  useConfirmDialog: () => (...args: unknown[]) => confirmDialog(...args),
}))
vi.mock("@/components/ui/PromptDialog", () => ({
  usePromptDialog: () => (...args: unknown[]) => promptDialog(...args),
}))

vi.mock("@/components/ui/Tooltip", () => ({
  Tooltip: ({ children }: { children: ReactNode }) => <>{children}</>,
}))

vi.mock("@/lib/utils/vaultStorageMigration", () => ({
  migrateVaultStorage: vi.fn(),
}))

import { VaultNotesEditor } from "./VaultNotesEditor"

let root: Root | null = null
let container: HTMLDivElement | null = null

;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true

const initialNotes = [
  {
    id: "note-1",
    book_id: "book-1",
    path: "Characters/Mira.md",
    source: "user_notes",
    content: "# Mira\n\nMira trusts [[Plot Threads/Ash Gate]].\n\nThe gate opens.",
    created_at: "2026-06-01T00:00:00Z",
    updated_at: "2026-06-15T00:00:00Z",
  },
  {
    id: "note-2",
    book_id: "book-1",
    path: "Plot Threads/Ash Gate.md",
    source: "user_notes",
    content: "# Ash Gate\n\nA sealed relic.",
    created_at: "2026-06-02T00:00:00Z",
    updated_at: "2026-06-14T00:00:00Z",
  },
]

const graph = {
  nodes: [
    { id: "Characters/Mira.md", label: "Mira" },
    { id: "Plot Threads/Ash Gate.md", label: "Ash Gate" },
  ],
  edges: [
    { source: "Characters/Mira.md", target: "Plot Threads/Ash Gate.md", label: "mentions" },
  ],
}

async function renderElement(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  await act(async () => {
    root?.render(element)
    await Promise.resolve()
  })
}

function text() {
  return container?.textContent ?? ""
}

function setFieldValue(field: HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement, value: string) {
  const prototype =
    field instanceof HTMLTextAreaElement
      ? HTMLTextAreaElement.prototype
      : field instanceof HTMLSelectElement
        ? HTMLSelectElement.prototype
        : HTMLInputElement.prototype
  const setter = Object.getOwnPropertyDescriptor(prototype, "value")?.set
  setter?.call(field, value)
  field.dispatchEvent(new Event(field instanceof HTMLSelectElement ? "change" : "input", { bubbles: true }))
}

function buttonByText(label: string) {
  const button = Array.from(container?.querySelectorAll("button") ?? []).find((item) =>
    item.textContent?.includes(label)
  )
  if (!button) throw new Error(`Missing button: ${label}`)
  return button
}

async function clickButton(label: string) {
  await act(async () => {
    buttonByText(label).dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await Promise.resolve()
  })
}

async function clickByAriaLabel(label: string) {
  const button = container?.querySelector(`button[aria-label="${label}"]`)
  if (!button) throw new Error(`Missing aria button: ${label}`)
  await act(async () => {
    button.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await Promise.resolve()
  })
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date("2026-06-16T12:00:00Z"))
  const storage = new Map<string, string>()
  Object.defineProperty(window, "localStorage", {
    configurable: true,
    value: {
      getItem: vi.fn((key: string) => storage.get(key) ?? null),
      setItem: vi.fn((key: string, value: string) => storage.set(key, value)),
      removeItem: vi.fn((key: string) => storage.delete(key)),
      clear: vi.fn(() => storage.clear()),
    },
  })
  ;(window as typeof window & {
    requestIdleCallback: (callback: IdleRequestCallback) => number
    cancelIdleCallback: (id: number) => void
  }).requestIdleCallback = (callback) => window.setTimeout(() => callback({ didTimeout: false, timeRemaining: () => 50 } as IdleDeadline), 0)
  ;(window as typeof window & { cancelIdleCallback: (id: number) => void }).cancelIdleCallback = (id) => window.clearTimeout(id)
  promptDialog.mockResolvedValue("Custom/Clues")
  window.URL.createObjectURL = vi.fn(() => "blob:notes")
  window.URL.revokeObjectURL = vi.fn()
  Object.defineProperty(navigator, "clipboard", {
    configurable: true,
    value: { writeText: vi.fn(async () => undefined) },
  })

  saveVaultNote.mockImplementation(async (_bookId, payload: { path: string; content: string }) => ({
    path: payload.path,
    content: payload.content,
    source: "user_notes",
    created_at: "2026-06-16T12:00:00Z",
    updated_at: "2026-06-16T12:00:00Z",
  }))
  deleteVaultNote.mockResolvedValue(undefined)
  getVaultGraph.mockResolvedValue(graph)
  exportVaultNotes.mockResolvedValue(new Blob(["notes"], { type: "application/zip" }))
  importVaultNotes.mockResolvedValue(undefined)
  listVaultNotes.mockResolvedValue(initialNotes)
  getVaultNoteRelations.mockResolvedValue({
    links: [],
    backlinks: [
      {
        id: "back-1",
        source_note_id: "note-2",
        source_note_path: "Plot Threads/Ash Gate.md",
        target_note_id: "note-1",
        target_note_path: "Characters/Mira.md",
        link_type: "wiki",
        created_at: "2026-06-16T10:00:00Z",
      },
    ],
    tags: [
      { id: "tag-1", book_id: "book-1", note_id: "note-1", note_path: "Characters/Mira.md", tag_name: "hero", created_at: "2026-06-16T10:00:00Z" },
    ],
    series_links: [],
  })
  getWorkspaceTree.mockResolvedValue({
    chapters: [{ chapter_number: 3, title: "The Gate" }],
    scene_groups: [],
    note_paths: [],
  })
  saveScene.mockResolvedValue({ title: "Mira" })
  confirmDialog.mockResolvedValue(true)
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
  vi.useRealTimers()
  vi.clearAllMocks()
})

describe("VaultNotesEditor runtime behavior", () => {
  it("renders, filters, edits, saves, moves, exports, and deletes vault notes", async () => {
    await renderElement(
      <VaultNotesEditor
        bookId="book-1"
        bookTitle="The Ember Gate"
        initialNotes={initialNotes as never}
        initialGraph={graph as never}
        isDark={false}
      />,
    )

    expect(text()).toContain("Notes")
    expect(text()).toContain("The Ember Gate")
    expect(text()).toContain("Mira")
    expect(text()).toContain("Ash Gate")
    expect(getWorkspaceTree).not.toHaveBeenCalled()
    expect(getVaultNoteRelations).not.toHaveBeenCalled()

    await clickButton("Details")
    await act(async () => {
      await Promise.resolve()
    })
    expect(getWorkspaceTree).toHaveBeenCalledWith("book-1")
    expect(getVaultNoteRelations).toHaveBeenCalledWith("book-1", "Characters/Mira.md")

    await clickButton("Details")
    expect(container?.querySelector("aside[aria-label='Note details']")).toBeNull()

    const search = container?.querySelector("input[aria-label='Search notes']") as HTMLInputElement
    await act(async () => {
      setFieldValue(search, "sealed")
      await Promise.resolve()
    })
    expect(text()).toContain("Ash Gate")

    await clickButton("Favorites")
    expect(text()).toContain("Star a note to keep it here.")
    await clickButton("Recent")

    await clickByAriaLabel("Add to favorites")
    await clickButton("Favorites")
    expect(text()).toContain("Mira")
    await clickButton("Recent")

    const textarea = container?.querySelector("textarea") as HTMLTextAreaElement
    await act(async () => {
      setFieldValue(textarea, "# Mira\n\nThe gate opens. The gate closes.")
      await Promise.resolve()
    })
    const findInput = container?.querySelector("input[aria-label='Find in this note']") as HTMLInputElement
    const replaceInput = container?.querySelector("input[aria-label='Replace with']") as HTMLInputElement
    await act(async () => {
      setFieldValue(findInput, "gate")
      setFieldValue(replaceInput, "door")
      await Promise.resolve()
    })
    await clickButton("Replace all")
    expect((container?.querySelector("textarea") as HTMLTextAreaElement).value).toContain("door opens")

    await clickButton("Save now")
    expect(saveVaultNote).toHaveBeenCalledWith("book-1", {
      path: "Characters/Mira.md",
      content: expect.stringContaining("door opens"),
    })

    await clickByAriaLabel("Copy note reference")
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("[[Mira]]")

    await clickByAriaLabel("Open full graph")
    expect(text()).toContain("Vault graph view")
    const graphClose = Array.from(container?.querySelectorAll("button") ?? []).filter((button) => button.textContent?.trim() === "Close").at(-1)
    await act(async () => graphClose?.click())
    await clickButton("Details")

    const titleInput = Array.from(container?.querySelectorAll("input") ?? []).find((input) => input.value === "Mira") as HTMLInputElement
    await act(async () => {
      setFieldValue(titleInput, "Mira Revised")
      await Promise.resolve()
    })
    await clickButton("Update path")
    expect(saveVaultNote).toHaveBeenCalledWith("book-1", {
      path: "Characters/Mira Revised.md",
      content: expect.stringContaining("door opens"),
    })
    expect(deleteVaultNote).toHaveBeenCalledWith("book-1", "Characters/Mira.md")

    await clickButton("New note")
    expect(saveVaultNote).toHaveBeenCalledWith("book-1", {
      path: expect.stringContaining("Untitled note.md"),
      content: expect.stringContaining("# Untitled note"),
    })

    await clickByAriaLabel("Duplicate selected note")
    expect(saveVaultNote).toHaveBeenCalledWith("book-1", {
      path: expect.stringContaining("Copy.md"),
      content: expect.any(String),
    })

    await clickButton("Export ZIP")
    expect(exportVaultNotes).toHaveBeenCalledWith("book-1")
    expect(window.URL.createObjectURL).toHaveBeenCalled()

    await clickButton("Send")
    expect(saveScene).toHaveBeenCalledWith("book-1", expect.objectContaining({
      status: "planned",
      body: expect.any(String),
    }))

    await clickButton("Delete")
    expect(confirmDialog).toHaveBeenCalledWith(expect.objectContaining({ title: "Delete note?" }))
    expect(deleteVaultNote).toHaveBeenCalled()
  })
})
