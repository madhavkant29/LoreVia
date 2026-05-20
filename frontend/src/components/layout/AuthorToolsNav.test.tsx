import React, { act, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"

import type { CollaborationPermissions } from "@/types/book"

const useQueryMock = vi.hoisted(() => vi.fn())
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
    expect(overviewHelper?.className ?? "").toContain("group-hover/rail:max-h-20")
    expect(overviewHelper?.className ?? "").toContain("group-focus-within/rail:opacity-100")
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
        staleTime: 60_000,
      })
    )
  })
})

function renderAuthorToolsNav() {
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
        mode="author"
        variant="rail"
      />
    )
  })

  return container
}

function mockBaseState({
  tier = "pro",
  hasOwnAuthorAccess = true,
  collaborationPermissions = null,
}: {
  tier?: string
  hasOwnAuthorAccess?: boolean
  collaborationPermissions?: CollaborationPermissions | null
} = {}) {
  useAuthStoreMock.mockImplementation((selector: (state: { user: { tier: string } | null }) => unknown) => selector({ user: tier ? { tier } : null }))
  canUseAuthorFeaturesMock.mockReturnValue(hasOwnAuthorAccess)
  useQueryMock.mockReturnValue({
    data: collaborationPermissions
      ? {
          collaboration_role: "editor",
          collaboration_permissions: collaborationPermissions,
        }
      : null,
  })
}
