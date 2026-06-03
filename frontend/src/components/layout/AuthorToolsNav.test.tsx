import React, { act, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"

import type { CollaborationPermissions } from "@/types/book"

const useQueryMock = vi.hoisted(() => vi.fn())
const useQueryClientMock = vi.hoisted(() => vi.fn())
const useAuthStoreMock = vi.hoisted(() => vi.fn())
const canUseAuthorFeaturesMock = vi.hoisted(() => vi.fn())

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

  it("shows author sections for a free owner when the book is in author mode", () => {
    mockBaseState({
      tier: "free",
      hasOwnAuthorAccess: false,
      collaborationPermissions: null,
    })

    const view = renderAuthorToolsNav()

    expect(view.querySelector('[data-testid="author-nav-item-manuscript"]')?.textContent).toContain("Manuscript Editor")
    expect(view.querySelector('[data-testid="author-nav-item-characters"]')?.textContent).toContain("Character Bible")
  })

  it("renders the author lens entry in the shared author rail", () => {
    mockBaseState()

    const view = renderAuthorToolsNav()

    expect(view.querySelector('[data-testid="author-nav-item-author-loop"]')?.textContent).toContain("Author Lens")
  })

  it("groups story bible and review center tools in the shared author rail", () => {
    mockBaseState()

    const view = renderAuthorToolsNav()

    expect(view.querySelector('[data-testid="author-nav-item-timeline"]')?.textContent).toContain("Timeline")
    expect(view.querySelector('[data-testid="author-nav-item-cross-book-wiki"]')?.textContent).toContain("Series Wiki")
    expect(view.querySelector('[data-testid="author-nav-item-reports"]')?.textContent).toContain("Chapter Reports")
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
