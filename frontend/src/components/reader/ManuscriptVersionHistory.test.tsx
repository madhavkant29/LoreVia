import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"

import { ManuscriptVersionHistory } from "./ManuscriptVersionHistory"

let container: HTMLDivElement | null = null
let root: Root | null = null

describe("ManuscriptVersionHistory", () => {
  beforeAll(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  })

  afterEach(() => {
    act(() => root?.unmount())
    container?.remove()
    container = null
    root = null
  })

  it("renders an empty state and delegates named snapshot creation", () => {
    const onCreateSnapshot = vi.fn()
    const view = renderHistory({ onCreateSnapshot })

    expect(view.textContent).toContain("No snapshots saved for this chapter yet.")
    clickButton(view, "Save named version")
    expect(onCreateSnapshot).toHaveBeenCalledOnce()
  })

  it("renders comparison text and delegates restore and compare actions", () => {
    const onPreviewSnapshot = vi.fn()
    const onRestoreSnapshot = vi.fn()
    const view = renderHistory({ includeVersion: true, onPreviewSnapshot, onRestoreSnapshot })

    expect(view.textContent).toContain("Saved passage")
    expect(view.textContent).toContain("Current passage")
    const comparePanels = Array.from(view.querySelectorAll("details"))
    expect(comparePanels).toHaveLength(2)
    expect(comparePanels.every((panel) => panel.open)).toBe(true)
    clickSummary(view, "Saved version")
    expect(comparePanels[0].open).toBe(false)
    clickSummary(view, "Saved version")
    expect(comparePanels[0].open).toBe(true)
    clickButton(view, "Restore")
    clickButton(view, "Compare")
    expect(buttonClass(view, "Restore")).toContain("rounded-none")
    expect(buttonClass(view, "Compare")).toContain("rounded-none")
    expect(onRestoreSnapshot).toHaveBeenCalledWith("version-1")
    expect(onPreviewSnapshot).toHaveBeenCalledWith("version-1")
  })
})

function renderHistory({
  includeVersion = false,
  onCreateSnapshot = vi.fn(),
  onPreviewSnapshot = vi.fn(),
  onRestoreSnapshot = vi.fn(),
}: {
  includeVersion?: boolean
  onCreateSnapshot?: () => void
  onPreviewSnapshot?: (versionId: string) => void
  onRestoreSnapshot?: (versionId: string) => void
} = {}) {
  const version = {
    id: "version-1",
    chapter_number: 3,
    title: "Chapter 3",
    word_count: 240,
    note: "Before rewrite",
    snapshot_kind: "manual",
    created_at: "2026-05-01T12:00:00Z",
  }

  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => {
    root?.render(
      <ManuscriptVersionHistory
        chapterNumber={3}
        chapterVersionDetail={includeVersion ? { ...version, text: "Saved passage", html: null } : null}
        chapterVersionNameDraft=""
        chapterVersions={includeVersion ? [version] : []}
        currentText="Current passage"
        isDark={false}
        restoringVersionId={null}
        onCreateSnapshot={onCreateSnapshot}
        onPreviewSnapshot={onPreviewSnapshot}
        onRestoreSnapshot={onRestoreSnapshot}
        onVersionNameChange={vi.fn()}
      />
    )
  })
  return container
}

function clickButton(view: HTMLDivElement, label: string) {
  const button = Array.from(view.querySelectorAll("button")).find((candidate) => candidate.textContent === label)
  if (!button) throw new Error(`Could not find ${label} button`)
  act(() => {
    button.click()
  })
}

function clickSummary(view: HTMLDivElement, label: string) {
  const summary = Array.from(view.querySelectorAll("summary")).find((candidate) => candidate.textContent === label)
  if (!summary) throw new Error(`Could not find ${label} summary`)
  act(() => {
    summary.click()
  })
}

function buttonClass(view: HTMLDivElement, label: string) {
  const button = Array.from(view.querySelectorAll("button")).find((candidate) => candidate.textContent === label)
  if (!button) throw new Error(`Could not find ${label} button`)
  return button.className
}
