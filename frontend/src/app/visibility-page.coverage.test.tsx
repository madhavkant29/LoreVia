// @vitest-environment jsdom

import { act, type ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { createRoot } from "react-dom/client"
import { afterEach, describe, expect, it, vi } from "vitest"

const booksApiMock = vi.hoisted(() => ({
  get: vi.fn(),
  getVisibilitySummary: vi.fn(),
}))
const hydrateBook = vi.hoisted(() => vi.fn().mockResolvedValue(true))

vi.mock("@/lib/stores/authStore", () => ({ useAuthStore: (selector: (state: unknown) => unknown) => selector({ user: { tier: "author" } }) }))
vi.mock("next/navigation", () => ({ useParams: () => ({ bookId: "book-1" }) }))
vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string }) => <a href={href} {...props}>{children}</a>,
}))
vi.mock("@/components/reader/WorkspaceFamilyHeader", () => ({
  WorkspaceFamilyHeader: ({ description, title }: { description: string; title: string }) => <header><h1>{title}</h1><p>{description}</p></header>,
}))
vi.mock("@/components/ui/Button", () => ({
  Button: ({ children, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) => <button {...props}>{children}</button>,
}))
vi.mock("@/components/ui/StatusToast", () => ({ useStatusToast: () => vi.fn() }))
vi.mock("@/lib/api/books", () => ({ booksApi: booksApiMock }))
vi.mock("@/lib/stores/preferencesStore", () => ({ usePreferencesStore: () => ({ theme: "light" }) }))
vi.mock("@/lib/stores/uiPreferencesStore", () => ({
  defaultBookUiPreference: () => ({ book_preset: "all", hidden_book_tools: [], overview_cards: {} }),
  useUiPreferencesStore: (selector: (state: Record<string, unknown>) => unknown) => selector({
    hydrateBook,
    activeUserId: "user-1",
    pendingBookOperations: {},
    bookPreferences: {},
    setBookToolHidden: vi.fn(),
    setBookPreset: vi.fn(),
    patchBook: vi.fn(),
    setComplexityMode: vi.fn(),
    preferences: { complexity_mode: "standard" },
    retrySync: vi.fn(),
    syncState: "synced",
    syncMessage: null,
  }),
}))
vi.mock("@/lib/workspace/toolRegistry", () => ({
  toolsForPlacement: () => [{ id: "book.notes", label: "Notes", group: "Draft", nonHideable: false }],
}))
vi.mock("@/lib/workspace/toolResolver", () => ({
  resolveWorkspaceTools: () => [{ tool: { id: "book.notes", label: "Notes", group: "Draft" }, hidden: false }],
}))

import VisibilityCenterPage from "@/app/(reader)/[bookId]/visibility/page"

describe("VisibilityCenterPage", () => {
  afterEach(() => {
    document.body.innerHTML = ""
    vi.clearAllMocks()
  })

  it("shows one access model and defers navigation recovery until Advanced is opened", async () => {
    booksApiMock.get.mockResolvedValue({ id: "book-1", title: "The Ember Gate", access_class: "owner" })
    booksApiMock.getVisibilitySummary.mockResolvedValue({
      book_id: "book-1",
      access_class: "owner",
      workspace_shell: "author",
      badges: ["Private"],
      private_status: { state: "private", label: "Private workspace", detail: "Only invited people can open this book." },
      collaborators: { state: "shared", label: "Collaborators", count: 2, detail: "Two people have workspace access." },
      beta_readers: { state: "active", label: "Beta readers", count: 1, detail: "One active assignment." },
      public_publishing: { state: "private", label: "Public publishing", detail: "No public sample is published." },
      public_discussion: { state: "private", label: "Public discussion", detail: "Discussion is disabled." },
      rights: { state: "confirmed", label: "Rights", detail: "Ownership confirmed." },
      moderation: { state: "clean", label: "Moderation", detail: "No reports." },
      public_url: null,
    })

    const container = document.createElement("div")
    document.body.appendChild(container)
    const root = createRoot(container)
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    await act(async () => {
      root.render(<QueryClientProvider client={queryClient}><VisibilityCenterPage /></QueryClientProvider>)
      await Promise.resolve()
    })

    await act(async () => {
      await new Promise((resolve) => window.setTimeout(resolve, 0))
    })
    for (let attempt = 0; attempt < 20 && !container.textContent?.includes("Private workspace"); attempt++) {
      await act(async () => { await new Promise(resolve => window.setTimeout(resolve, 5)) })
    }
    expect(container.textContent).toContain("Access & Visibility")
    expect(container.textContent).toContain("Private workspace")
    expect(container.textContent).toContain("Not public")
    expect(container.textContent).toContain("Manage collaborators")
    expect(container.textContent).not.toContain("Hidden and visible tools")
    expect(hydrateBook).not.toHaveBeenCalled()

    const advanced = Array.from(container.querySelectorAll("details")).at(-1) as HTMLDetailsElement
    await act(async () => {
      advanced.open = true
      advanced.dispatchEvent(new Event("toggle"))
      await Promise.resolve()
    })
    expect(container.textContent).toContain("Hidden and visible tools")
    expect(hydrateBook).toHaveBeenCalledWith("book-1")

    act(() => root.unmount())
  })
})
