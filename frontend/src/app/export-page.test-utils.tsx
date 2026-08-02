import { act, type ReactElement, type ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, vi } from "vitest"

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

import ExportStudioPageComponent from "@/app/(reader)/[bookId]/export/page"

let root: Root | null = null
let container: HTMLDivElement | null = null
let queryClient: QueryClient | null = null
const objectUrlMock = vi.fn(() => "blob:lorevia-export")
const revokeObjectUrlMock = vi.fn()
const anchorClickMock = vi.fn()

export const ExportStudioPage = ExportStudioPageComponent
export { anchorClickMock, booksApiMock, objectUrlMock, revokeObjectUrlMock, worldBuildingApiMock }

export const book = {
  id: "book-1",
  title: "The Ember Gate!",
  author: "A. Writer",
  genre: "Fantasy",
  status: "ready",
  cover_url: "https://example.test/cover.jpg",
  work_type: "novel",
  total_chapters: 12,
}

export function fakeBlob(text: string) {
  const bytes = new TextEncoder().encode(text)
  return {
    arrayBuffer: async () => bytes.buffer,
  } as Blob
}

export async function renderPage(element: ReactElement) {
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

export function cleanupExportPage() {
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
}

export async function waitForText(expected: string) {
  for (let index = 0; index < 30; index += 1) {
    if ((container?.textContent ?? "").includes(expected)) return
    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 0))
    })
  }
  throw new Error(`Expected text not found: ${expected}. Saw: ${container?.textContent}`)
}

export function getContainer() {
  if (!container) throw new Error("Export page test container is not mounted.")
  return container
}

export function text() {
  return container?.textContent ?? ""
}

function button(label: string) {
  const match = Array.from(container?.querySelectorAll("button") ?? []).find((item) =>
    item.textContent?.includes(label)
  )
  if (!match) throw new Error(`Missing button: ${label}`)
  return match
}

export async function click(label: string) {
  await act(async () => {
    button(label).dispatchEvent(new MouseEvent("click", { bubbles: true }))
    await Promise.resolve()
    await Promise.resolve()
  })
}

export function setFieldValue(field: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement, value: string) {
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

export function setInputFiles(input: HTMLInputElement, files: File[]) {
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
  cleanupExportPage()
  document.body.innerHTML = ""
  vi.clearAllMocks()
})
