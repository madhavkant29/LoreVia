// @vitest-environment jsdom

import { act, type ReactElement, type ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const paramsMock = vi.hoisted(() => ({ bookId: "book-1" }))
const booksApiMock = vi.hoisted(() => ({
  exportCharacterBible: vi.fn(),
  exportManuscript: vi.fn(),
  exportNovel: vi.fn(),
  exportVaultNotes: vi.fn(),
  get: vi.fn(),
  getWriterWorkspace: vi.fn(),
  importManuscript: vi.fn(),
  importVaultNotes: vi.fn(),
  listCharacterBibleVaultNotes: vi.fn(),
  previewCharacterBibleVault: vi.fn(),
  saveNovelSettings: vi.fn(),
}))
const worldBuildingApiMock = vi.hoisted(() => ({
  uploadDocuments: vi.fn(),
}))

vi.mock("next/navigation", () => ({
  useParams: () => paramsMock,
}))

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
    if (source.includes("AuthorToolsNav")) {
      return function AuthorToolsNavStub({ active, title }: { active: string; title: string }) {
        return <aside data-testid="author-tools-nav">{title}:{active}</aside>
      }
    }
    if (source.includes("VaultPreview")) {
      return function VaultPreviewStub({ preview }: { preview: { files?: Array<{ path: string }> } }) {
        return <div data-testid="vault-preview">{preview.files?.map((file) => file.path).join(", ")}</div>
      }
    }
    return function DynamicStub() {
      return <div data-testid="dynamic-stub" />
    }
  },
}))

vi.mock("@/components/reader/WorkspaceFamilyHeader", () => ({
  WorkspaceFamilyHeader: ({ actions, description, title }: { actions?: ReactNode; description: string; title: string }) => (
    <header>
      <h1>{title}</h1>
      <p>{description}</p>
      {actions}
    </header>
  ),
}))

vi.mock("@/components/ui/Skeleton", () => ({
  CardSkeleton: ({ className = "" }: { className?: string }) => <div className={className}>Card loading</div>,
  RowSkeleton: ({ className = "" }: { className?: string }) => <div className={className}>Row loading</div>,
  SidebarSkeleton: () => <div>Sidebar loading</div>,
  Skeleton: ({ className = "" }: { className?: string }) => <div className={className}>Loading</div>,
}))

vi.mock("@/components/ui/Tooltip", () => ({
  Tooltip: ({ children }: { children: ReactNode }) => <>{children}</>,
}))

vi.mock("@/lib/api/books", () => ({ booksApi: booksApiMock }))
vi.mock("@/lib/api/worldBuilding", () => ({ worldBuildingApi: worldBuildingApiMock }))
vi.mock("@/lib/billing/plans", () => ({ canUseAuthorFeatures: (tier?: string | null) => tier !== "free" }))
vi.mock("@/lib/stores/authStore", () => ({
  useAuthStore: (selector: (state: { user: { tier: string } }) => unknown) => selector({ user: { tier: "architect" } }),
}))
vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: () => ({ theme: "dark" }),
}))

import ExportStudioPage from "@/app/(reader)/[bookId]/export/page"

let root: Root | null = null
let container: HTMLDivElement | null = null
let queryClient: QueryClient | null = null
const objectUrlMock = vi.fn(() => "blob:lorevia-export")
const revokeObjectUrlMock = vi.fn()
const anchorClickMock = vi.fn()

const book = {
  id: "book-1",
  title: "The Ember Gate!",
  author: "A. Writer",
  genre: "Fantasy",
  status: "ready",
  cover_url: "https://example.test/cover.jpg",
  work_type: "novel",
  total_chapters: 12,
}

function fakeBlob(text: string) {
  const bytes = new TextEncoder().encode(text)
  return {
    arrayBuffer: async () => bytes.buffer,
  } as Blob
}

async function renderPage(element: ReactElement) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })

  await act(async () => {
    root?.render(<QueryClientProvider client={queryClient}>{element}</QueryClientProvider>)
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

function button(label: string) {
  const match = Array.from(container?.querySelectorAll("button") ?? []).find((item) =>
    item.textContent?.includes(label)
  )
  if (!match) throw new Error(`Missing button: ${label}`)
  return match
}

async function click(label: string) {
  await act(async () => {
    button(label).dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await Promise.resolve()
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

function setInputFiles(input: HTMLInputElement, files: File[]) {
  Object.defineProperty(input, "files", {
    configurable: true,
    value: files,
  })
  input.dispatchEvent(new Event("change", { bubbles: true }))
}

beforeEach(() => {
  booksApiMock.get.mockResolvedValue(book)
  booksApiMock.getWriterWorkspace.mockResolvedValue({
    novel_preface: "A note before the gate opens.",
    novel_front_matter: { dedication: "For the gatekeepers." },
    novel_epub_metadata: { publisher: "Lore Press", language: "en", isbn: "", description: "", series_name: "", series_number: "" },
  })
  booksApiMock.exportCharacterBible.mockResolvedValue(fakeBlob("character bible"))
  booksApiMock.exportManuscript.mockResolvedValue(fakeBlob("manuscript"))
  booksApiMock.exportNovel.mockResolvedValue(fakeBlob("novel"))
  booksApiMock.exportVaultNotes.mockResolvedValue(fakeBlob("notes"))
  booksApiMock.previewCharacterBibleVault.mockResolvedValue({ files: [{ path: "Characters/Mira.md" }] })
  booksApiMock.listCharacterBibleVaultNotes.mockResolvedValue([{ id: "note-1", path: "Characters/Mira.md" }])
  booksApiMock.saveNovelSettings.mockResolvedValue({
    preface: "Saved preface.",
    front_matter: { dedication: "Saved dedication.", acknowledgements: "", copyright_page: "", about_author: "", series_book_list: "" },
    epub_metadata: { publisher: "Saved Press", language: "en", isbn: "123", description: "Blurb", series_name: "Gate", series_number: "1" },
  })
  booksApiMock.importManuscript.mockResolvedValue({ imported_chapters: [{ number: 1 }], total_chapters: 1 })
  booksApiMock.importVaultNotes.mockResolvedValue({})
  worldBuildingApiMock.uploadDocuments.mockResolvedValue({})
  Object.defineProperty(window.URL, "createObjectURL", { configurable: true, value: objectUrlMock })
  Object.defineProperty(window.URL, "revokeObjectURL", { configurable: true, value: revokeObjectUrlMock })
  Object.defineProperty(HTMLAnchorElement.prototype, "click", { configurable: true, value: anchorClickMock })
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

describe("ExportStudioPage", () => {
  it("renders export studio and drives export, preview, import, and settings actions", async () => {
    await renderPage(<ExportStudioPage />)
    await waitForText("Ship clean outputs")

    expect(text()).toContain("The Ember Gate!")
    expect(text()).toContain("Bring material into this book")
    expect(text()).toContain("A note before the gate opens.")

    await click("DOCX")
    await click("EPUB")

    const checkboxes = Array.from(container?.querySelectorAll('input[type="checkbox"]') ?? []) as HTMLInputElement[]
    await act(async () => {
      checkboxes.forEach((item) => item.dispatchEvent(new MouseEvent("click", { bubbles: true })))
      await Promise.resolve()
    })
    expect(text()).toContain("Image placement")
    expect(text()).toContain("Include stored captions")

    const textareas = Array.from(container?.querySelectorAll("textarea") ?? []) as HTMLTextAreaElement[]
    await act(async () => {
      setFieldValue(textareas[0], "Updated preface")
      setFieldValue(textareas[1], "Updated dedication")
      await Promise.resolve()
    })
    const inputs = Array.from(container?.querySelectorAll('input:not([type="checkbox"]):not([type="file"])') ?? []) as HTMLInputElement[]
    await act(async () => {
      setFieldValue(inputs[0], "Indie Press")
      setFieldValue(inputs[2], "9780000000000")
      await Promise.resolve()
    })

    await click("Save novel settings")
    expect(booksApiMock.saveNovelSettings).toHaveBeenCalledWith("book-1", expect.objectContaining({
      preface: "Updated preface",
      front_matter: expect.objectContaining({ dedication: "Updated dedication" }),
      epub_metadata: expect.objectContaining({ publisher: "Indie Press", isbn: "9780000000000" }),
    }))
    expect(text()).toContain("Saved novel export settings.")

    await click("Preview export files")
    expect(booksApiMock.previewCharacterBibleVault).toHaveBeenCalledWith("book-1")
    expect(text()).toContain("Loaded the character bible file preview.")
    expect(text()).toContain("Characters/Mira.md")

    await click("Export character bible")
    expect(booksApiMock.exportCharacterBible).toHaveBeenCalledWith("book-1", "docx", "serif")
    expect(objectUrlMock).toHaveBeenCalled()
    expect(text()).toContain("Downloaded character bible as DOCX.")

    await click("Vault ZIP")
    await click("Export manuscript")
    expect(booksApiMock.exportManuscript).toHaveBeenCalledWith("book-1", "epub", "standard_manuscript", false, "serif", true)
    expect(text()).toContain("Downloaded manuscript as EPUB.")

    await click("Export novel")
    expect(booksApiMock.exportNovel).toHaveBeenCalledWith("book-1", "pdf", "standard_novel", true, "serif", expect.objectContaining({
      includeImageCaptions: false,
      previewChapters: 2,
    }))
    expect(text()).toContain("Downloaded first 2-chapter sample as PDF.")

    await click("Export notes ZIP")
    expect(booksApiMock.exportVaultNotes).toHaveBeenCalledWith("book-1")
    expect(text()).toContain("Downloaded notes workspace ZIP.")

    const fileInputs = Array.from(container?.querySelectorAll('input[type="file"]') ?? []) as HTMLInputElement[]
    const manuscriptFile = new File(["chapter"], "chapter-one.md", { type: "text/markdown" })
    const notesFile = new File(["notes"], "notes.zip", { type: "application/zip" })
    const worldFile = new File(["world"], "world.md", { type: "text/markdown" })
    await act(async () => {
      setInputFiles(fileInputs[0], [manuscriptFile])
      setInputFiles(fileInputs[1], [notesFile])
      setInputFiles(fileInputs[2], [worldFile])
      await Promise.resolve()
    })
    expect(text()).toContain("chapter-one.md")
    expect(text()).toContain("notes.zip")
    expect(text()).toContain("world.md")

    await click("Import manuscript files")
    expect(booksApiMock.importManuscript).toHaveBeenCalledWith("book-1", expect.objectContaining({
      files: [manuscriptFile],
      workType: "novel",
    }))
    expect(text()).toContain("Imported 1 chapter files into this book.")

    await click("Import notes ZIP")
    expect(booksApiMock.importVaultNotes).toHaveBeenCalledWith("book-1", notesFile)
    expect(text()).toContain("Imported notes.zip into the notes workspace.")

    await click("Import worldbuilding")
    expect(worldBuildingApiMock.uploadDocuments).toHaveBeenCalledWith("book-1", { files: [worldFile] })
    expect(text()).toContain("Imported 1 worldbuilding file.")

    await click("Export everything")
    await waitForText("Downloaded one ZIP with all manuscript, novel, character bible, and notes export files.")
    expect(booksApiMock.exportCharacterBible).toHaveBeenCalledTimes(5)
    expect(booksApiMock.exportManuscript).toHaveBeenCalledTimes(5)
    expect(booksApiMock.exportNovel).toHaveBeenCalledTimes(4)
    expect(text()).toContain("Downloaded one ZIP with all manuscript, novel, character bible, and notes export files.")
  })

  it("shows loading and error/fallback states", async () => {
    booksApiMock.get.mockResolvedValueOnce(null)

    await renderPage(<ExportStudioPage />)
    expect(text()).toContain("Loading export studio")

    act(() => {
      root?.unmount()
    })
    container?.remove()
    root = null
    container = null
    queryClient?.clear()

    booksApiMock.get.mockResolvedValueOnce(book)
    booksApiMock.getWriterWorkspace.mockResolvedValueOnce(null)
    booksApiMock.exportCharacterBible.mockRejectedValueOnce(new Error("fail"))
    booksApiMock.previewCharacterBibleVault.mockRejectedValueOnce(new Error("fail"))

    await renderPage(<ExportStudioPage />)
    await waitForText("Ship clean outputs")

    await click("Preview export files")
    expect(text()).toContain("Could not load the vault preview.")

    await click("Export character bible")
    expect(text()).toContain("Could not export the character bible.")
  })
})
