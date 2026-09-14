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

  it("renders story bible tabs with the current surface selected", () => {
    const view = renderHeader("story-bible", "plot-threads")

    expect(view.textContent).toContain("Story Bible")
    expect(view.querySelector('a[href="/book-1/characters"]')).not.toBeNull()
    expect(view.querySelector('a[href="/book-1/cross-book-wiki"]')).not.toBeNull()
    expect(view.querySelector('a[href="/book-1/plot-threads"]')?.className).toContain("app-family-tab--active")
  })

  it("keeps diagnostics inside the review center family", () => {
    const view = renderHeader("review-center", "reports")

    expect(view.textContent).toContain("Review Center")
    expect(view.querySelector('a[href="/book-1/editorial-review"]')).not.toBeNull()
    expect(view.querySelector('a[href="/book-1/author-loop"]')).not.toBeNull()
    expect(view.querySelector('a[href="/book-1/reports"]')?.className).toContain("app-family-tab--active")
  })

  it("links child workspaces home to the book overview", () => {
    const view = renderHeader("story-bible", "characters")

    expect(view.querySelector('[data-testid="workspace-family-home-link"]')?.getAttribute("href")).toBe("/book-1")
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
