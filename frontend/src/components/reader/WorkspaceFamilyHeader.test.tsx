import React, { act, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

vi.mock("@/components/layout/AuthorToolsNav", () => ({
  AuthorToolsNav: ({ active }: { active: string }) => <nav data-testid="book-workspace-bar">{active}</nav>,
}))

vi.mock("@/lib/stores/preferencesStore", () => ({
  usePreferencesStore: (selector: (state: { theme: string }) => unknown) => selector({ theme: "light" }),
}))

import { WorkspaceFamilyHeader } from "./WorkspaceFamilyHeader"

let container: HTMLDivElement | null = null
let root: Root | null = null

describe("WorkspaceFamilyHeader", () => {
  beforeAll(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  })

  afterEach(() => {
    if (root) {
      act(() => {
        root?.unmount()
      })
    }
    container?.remove()
    container = null
    root = null
  })

  it("renders a story bible heading under the shared book bar", () => {
    const view = renderHeader("story-bible", "plot-threads")

    expect(view.textContent).toContain("Story Bible")
    expect(view.querySelector('[data-testid="book-workspace-bar"]')?.textContent).toBe("plot-threads")
    expect(view.querySelector('a[href="/book-1/characters"]')).toBeNull()
  })

  it("labels diagnostics as part of Review without a second route nav", () => {
    const view = renderHeader("review-center", "reports")

    expect(view.textContent).toContain("Review")
    expect(view.querySelector('[data-testid="book-workspace-bar"]')?.textContent).toBe("reports")
    expect(view.querySelector('a[href="/book-1/editorial-review"]')).toBeNull()
  })

  it("renders the supplied title and description", () => {
    const view = renderHeader("story-bible", "characters")

    expect(view.textContent).toContain("Workspace title")
    expect(view.textContent).toContain("Workspace description")
  })
})

function renderHeader(family: "story-bible" | "review-center", active: string) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  act(() => {
    root?.render(
      <WorkspaceFamilyHeader
        active={active}
        bookId="book-1"
        description="Workspace description"
        family={family}
        title="Workspace title"
      />
    )
  })

  return container
}
