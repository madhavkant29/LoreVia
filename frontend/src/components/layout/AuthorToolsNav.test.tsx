import React, { act, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"

import type { CollaborationPermissions } from "@/types/book"

const useQueryMock = vi.hoisted(() => vi.fn())
const useQueryClientMock = vi.hoisted(() => vi.fn())
const useAuthStoreMock = vi.hoisted(() => vi.fn())
const canUseAuthorFeaturesMock = vi.hoisted(() => vi.fn())
const uiPreferencesStoreMock = vi.hoisted(() => {
  const makeGlobalPreference = () => ({
    schema_version: 1,
    revision: 1,
    complexity_mode: "standard",
    dashboard_visibility: {},
    dashboard_order: [],
    public_tool_visibility: {},
    density: "comfortable",
    reader_toolbar_density: "standard",
    locked_tool_presentation: "compact",
    default_workspace_shell: "reader",
    mobile_actions: [],
    guidance_dismissals: {},
    recommendation_snoozes: {},
    updated_at: null,
  })
  const makeBookPreference = (bookId = "book-1", preset = "all", advancedToolOverride: "show" | "hide" | null = null) => ({
    book_id: bookId,
    schema_version: 1,
    revision: 1,
    book_preset: preset,
    advanced_tool_override: advancedToolOverride,
    hidden_book_tools: [],
    overview_cards: {},
    reader_actions: [],
    mobile_actions: [],
    panel_state: {},
    timeline_collapsed_sections: {},
    updated_at: null,
  })
  const listeners = new Set<() => void>()
  let state: any
  const notify = () => listeners.forEach((listener) => listener())
  const reset = () => {
    state = {
      preferences: makeGlobalPreference(),
      bookPreferences: { "book-1": makeBookPreference() },
      hydrateBook: vi.fn(),
      setBookPreset: vi.fn(async (bookId: string, preset: string) => {
        const current = state.bookPreferences[bookId] ?? makeBookPreference(bookId)
        state = {
          ...state,
          bookPreferences: {
            ...state.bookPreferences,
            [bookId]: { ...current, book_preset: preset },
          },
        }
        notify()
      }),
      patchBook: vi.fn(async (bookId: string, operations: Array<{ path: string; value?: unknown }>) => {
        const current = state.bookPreferences[bookId] ?? makeBookPreference(bookId)
        const next = { ...current }
        for (const operation of operations) {
          if (operation.path === "/advanced_tool_override") {
            next.advanced_tool_override = operation.value
          }
          if (operation.path === "/book_preset") {
            next.book_preset = operation.value
          }
          if (operation.path === "/hidden_book_tools" && Array.isArray(operation.value)) {
            next.hidden_book_tools = operation.value
          }
        }
        state = {
          ...state,
          bookPreferences: { ...state.bookPreferences, [bookId]: next },
        }
        notify()
      }),
    }
  }
  reset()
  return {
    getState: () => state,
    makeBookPreference,
    reset,
    subscribe: (listener: () => void) => {
      listeners.add(listener)
      return () => listeners.delete(listener)
    },
  }
})

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

vi.mock("@tanstack/react-query", () => ({
  useQuery: useQueryMock,
  useQueryClient: useQueryClientMock,
}))

vi.mock("@/components/billing/AuthorFeatureComponent", () => ({
  AuthorFeatureComponent: ({ children }: { children: ReactNode }) => <>{children}</>,
}))

vi.mock("@/lib/api/books", () => ({
  booksApi: {
    get: vi.fn(),
  },
}))

vi.mock("@/lib/billing/plans", () => ({
  canUseAuthorFeatures: canUseAuthorFeaturesMock,
}))

vi.mock("@/lib/stores/authStore", () => ({
  useAuthStore: useAuthStoreMock,
}))

vi.mock("@/lib/stores/uiPreferencesStore", async () => {
  const ReactModule = await vi.importActual<typeof import("react")>("react")
  return {
    defaultBookUiPreference: (bookId: string) => uiPreferencesStoreMock.makeBookPreference(bookId, "draft"),
    useUiPreferencesStore: (selector: (state: any) => unknown) =>
      ReactModule.useSyncExternalStore(
        uiPreferencesStoreMock.subscribe,
        () => selector(uiPreferencesStoreMock.getState()),
        () => selector(uiPreferencesStoreMock.getState()),
      ),
  }
})

import { AuthorToolsNav } from "./AuthorToolsNav"

let container: HTMLDivElement | null = null
let root: Root | null = null

describe("AuthorToolsNav", () => {
  beforeAll(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  })

  afterEach(() => {
    if (root) {
      act(() => {
        root?.unmount()
      })
    }
    if (container) {
      container.remove()
    }
    useQueryMock.mockReset()
    useQueryClientMock.mockReset()
    useAuthStoreMock.mockReset()
    canUseAuthorFeaturesMock.mockReset()
    uiPreferencesStoreMock.reset()
    container = null
    root = null
  })

  it("renders helper copy with rail reveal classes", () => {
    mockBaseState()

    const view = renderAuthorToolsNav()

    const nav = view.querySelector('[data-testid="author-tools-nav-rail"]')
    expect(nav).not.toBeNull()

    const overviewHelper = view.querySelector('[data-testid="author-nav-helper-overview"]')
    expect(overviewHelper?.textContent).toContain("progress, next steps")
    expect(overviewHelper?.className ?? "").toContain("group-hover/navwrap:max-h-20")
    expect(overviewHelper?.className ?? "").toContain("group-focus-within/navwrap:opacity-100")
  })

  it("does not leak helper copy for collaborator-restricted items", () => {
    mockBaseState({
      tier: "free",
      hasOwnAuthorAccess: false,
      collaborationPermissions: {
        can_edit_manuscript: true,
        can_run_ai_scans: false,
        can_view_story_bible: false,
        can_comment: true,
        can_export: false,
        can_view_selected_chapters_only: false,
      },
    })

    const view = renderAuthorToolsNav()

    expect(view.querySelector('[data-testid="author-nav-item-manuscript"]')?.textContent).toContain("Manuscript Editor")
    expect(view.querySelector('[data-testid="author-nav-helper-manuscript"]')?.textContent).toContain("working manuscript")
    expect(view.querySelector('[data-testid="author-nav-item-collaboration"]')).toBeNull()
    expect(view.querySelector('[data-testid="author-nav-helper-collaboration"]')).toBeNull()
    expect(view.querySelector('[data-testid="author-nav-item-export"]')).toBeNull()
    expect(view.querySelector('[data-testid="author-nav-helper-export"]')).toBeNull()
  })

  it("does not eagerly prefetch every author route", () => {
    mockBaseState()

    renderAuthorToolsNav()

    expect(useQueryMock).toHaveBeenCalledWith(
      expect.objectContaining({
        enabled: false,
        staleTime: Number.POSITIVE_INFINITY,
      })
    )
  })

  it("supports a compact rail size for tighter overview layouts", () => {
    mockBaseState()

    const view = renderAuthorToolsNav({ railSize: "compact" })

    const nav = view.querySelector('[data-testid="author-tools-nav-rail"]')
    const aside = nav?.querySelector("aside")
    expect(aside?.className ?? "").toContain("xl:w-[4.35rem]")
    expect(aside?.className ?? "").toContain("xl:group-hover/navwrap:w-[16.5rem]")
  })

  it("limits author navigation for a free owner when the book is in author mode", () => {
    mockBaseState({
      tier: "free",
      hasOwnAuthorAccess: false,
      collaborationPermissions: null,
    })

    const view = renderAuthorToolsNav()

    expect(view.querySelector('[data-testid="author-nav-item-manuscript"]')).toBeNull()
    expect(view.querySelector('[data-testid="author-nav-item-characters"]')).toBeNull()
    expect(view.querySelector('[data-testid="author-nav-item-advisor"]')?.textContent).toContain("Story Advisor")
    expect(view.querySelector('[data-testid="author-nav-item-export"]')?.textContent).toContain("Import & Export")
  })

  it("places notes workspace directly under the scene workspace", () => {
    mockBaseState()

    const view = renderAuthorToolsNav()
    const manuscriptItem = view.querySelector('[data-testid="author-nav-item-manuscript"]')
    const scenesItem = view.querySelector('[data-testid="author-nav-item-scenes"]')
    const notesItem = view.querySelector('[data-testid="author-nav-item-notes"]')

    expect(scenesItem?.textContent).toContain("Scene Workspace")
    expect(notesItem?.textContent).toContain("Notes Workspace")
    expect(notesItem?.getAttribute("href")).toBe("/book-1/notes")
    expect(
      Boolean(
        manuscriptItem &&
          scenesItem &&
          notesItem &&
          manuscriptItem.compareDocumentPosition(scenesItem) & Node.DOCUMENT_POSITION_FOLLOWING &&
          scenesItem.compareDocumentPosition(notesItem) & Node.DOCUMENT_POSITION_FOLLOWING
      )
    ).toBe(true)
  })

  it("reveals the advanced author lens entry on request", () => {
    mockBaseState()

    const view = renderAuthorToolsNav()
    expect(view.querySelector('[data-testid="author-nav-item-author-loop"]')).toBeNull()
    const toggle = Array.from(view.querySelectorAll("button")).find((button) => button.textContent?.includes("Show advanced tools"))
    act(() => toggle?.dispatchEvent(new MouseEvent("click", { bubbles: true })))

    expect(view.querySelector('[data-testid="author-nav-item-author-loop"]')?.textContent).toContain("Author Lens")
  })

  it("switches book presets from the author navigation", () => {
    mockBaseState()

    const view = renderAuthorToolsNav()
    const draftButton = findButton(view, "Draft")
    act(() => draftButton?.dispatchEvent(new MouseEvent("click", { bubbles: true })))

    expect(uiPreferencesStoreMock.getState().bookPreferences["book-1"].book_preset).toBe("draft")
    expect(view.querySelector('[data-testid="author-nav-item-characters"]')).toBeNull()
    expect(view.querySelector('[data-testid="author-nav-item-manuscript"]')?.textContent).toContain("Manuscript Editor")
  })

  it("keeps story bible preset focused on story memory tools", () => {
    mockBaseState()

    const view = renderAuthorToolsNav()
    const bibleButton = findButton(view, "Bible")
    act(() => bibleButton?.dispatchEvent(new MouseEvent("click", { bubbles: true })))

    expect(view.querySelector('[data-testid="author-nav-item-characters"]')?.textContent).toContain("Character Bible")
    expect(view.querySelector('[data-testid="author-nav-item-manuscript"]')).toBeNull()
  })

  it("groups story bible and analyze tools and hides advanced entries by default", () => {
    mockBaseState()

    const view = renderAuthorToolsNav()

    expect(view.querySelector('[data-testid="author-nav-item-timeline"]')?.textContent).toContain("Timeline")
    expect(view.querySelector('[data-testid="author-nav-item-cross-book-wiki"]')).toBeNull()
    expect(view.querySelector('[data-testid="author-nav-item-reports"]')?.textContent).toContain("Chapter Reports")
    expect(view.textContent).toContain("Analyze")
  })

  it("keeps reader-shell collaborators on reader navigation only", () => {
    mockBaseState({
      collaborationRole: "beta_reader",
      workspaceShell: "reader",
      collaborationPermissions: {
        can_edit_manuscript: false,
        can_run_ai_scans: false,
        can_view_story_bible: false,
        can_comment: true,
        can_export: false,
        can_view_selected_chapters_only: true,
      },
    })

    const view = renderAuthorToolsNav({ mode: "reader" })

    expect(view.querySelector('[data-testid="author-nav-item-beta-feedback"]')?.textContent).toContain("Feedback")
    expect(view.querySelector('[data-testid="author-nav-item-manuscript"]')).toBeNull()
    expect(view.querySelector('[data-testid="author-nav-item-collaboration"]')).toBeNull()
    expect(view.querySelector('[data-testid="author-nav-item-analysis"]')).toBeNull()
  })

  it("renders a chevron toggle for pinning the shared rail open", () => {
    mockBaseState()

    const view = renderAuthorToolsNav()

    expect(view.querySelector('[data-testid="author-nav-rail-toggle"]')).not.toBeNull()
  })
})

function renderAuthorToolsNav({ railSize, mode = "author" }: { railSize?: "default" | "compact"; mode?: "reader" | "author" } = {}) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  act(() => {
    root?.render(
      <AuthorToolsNav
        bookId="book-1"
        active="overview"
        isDark={false}
        currentChapter={2}
        mode={mode}
        variant="rail"
        railSize={railSize}
      />
    )
  })

  return container
}

function findButton(view: HTMLDivElement, label: string) {
  return Array.from(view.querySelectorAll("button")).find((button) => button.textContent?.includes(label))
}

function mockBaseState({
  tier = "pro",
  hasOwnAuthorAccess = true,
  collaborationPermissions = null,
  collaborationRole = collaborationPermissions ? "editor" : null,
  workspaceShell = "author",
}: {
  tier?: string
  hasOwnAuthorAccess?: boolean
  collaborationPermissions?: CollaborationPermissions | null
  collaborationRole?: string | null
  workspaceShell?: "reader" | "author"
} = {}) {
  useAuthStoreMock.mockImplementation((selector: (state: { user: { tier: string } | null }) => unknown) => selector({ user: tier ? { tier } : null }))
  canUseAuthorFeaturesMock.mockReturnValue(hasOwnAuthorAccess)
  useQueryClientMock.mockReturnValue({
    getQueryData: vi.fn().mockReturnValue(
      collaborationPermissions
        ? {
            collaboration_role: collaborationRole,
            workspace_shell: workspaceShell,
            collaboration_permissions: collaborationPermissions,
          }
        : null
    ),
  })
  useQueryMock.mockReturnValue({
    data: collaborationPermissions
      ? {
          collaboration_role: collaborationRole,
          workspace_shell: workspaceShell,
          collaboration_permissions: collaborationPermissions,
        }
      : null,
  })
}
