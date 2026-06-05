import React, { act, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"

import {
  ManuscriptWriteRightRail,
  buildManuscriptRailAdvisorStorageKey,
  buildQuickVaultNoteFolder,
  getNotePreview,
} from "./ManuscriptWriteRightRail"
import type { BookNote, VaultNote } from "@/types/book"

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

const bookNote: BookNote = {
  id: "note-1",
  book_id: "book-1",
  book_title: "Book",
  chapter_number: 2,
  chapter_title: "Awoken",
  title: "Mirror reveal",
  body: "# Beat\n\nTrack the reflection clue.",
  created_at: "2026-06-05T10:00:00Z",
  updated_at: "2026-06-05T10:00:00Z",
}

const vaultNote: VaultNote = {
  id: "vault-1",
  book_id: "book-1",
  path: "Manual Editor/Chapter 2/Mirror reveal.md",
  source: "manual",
  content: "# Mirror reveal\n\nTrack the reflection clue.",
  created_at: "2026-06-05T10:00:00Z",
  updated_at: "2026-06-05T10:00:00Z",
}

function renderRail(props: Partial<React.ComponentProps<typeof ManuscriptWriteRightRail>> = {}) {
  const container = document.createElement("div")
  document.body.appendChild(container)
  const root = createRoot(container)

  act(() => {
    root.render(
      <ManuscriptWriteRightRail
        isDark
        bookId="book-1"
        totalChapters={4}
        activeRightPane="notes"
        onOpenRightPane={vi.fn()}
        selectedCharCard={null}
        onClearSelectedCharCard={vi.fn()}
        activeChapterContextCharacters={[]}
        characters={[]}
        onOpenCharCard={vi.fn()}
        activeThreadSummary={[]}
        plotThreads={[]}
        recentEventSummary={[]}
        warningSummary={[]}
        review={null}
        onTightenSelectedText={vi.fn()}
        suggestions={[]}
        chapterAnnotationsCount={0}
        chapterManualNotes={[bookNote]}
        generalNotes={[]}
        vaultNotes={[vaultNote]}
        activeChapterNumber={2}
        arcSummaryCharacter={null}
        {...props}
      />,
    )
  })

  return { container, root }
}

describe("ManuscriptWriteRightRail helpers", () => {
  it("builds a per-book advisor storage key", () => {
    expect(buildManuscriptRailAdvisorStorageKey("book-123")).toBe("lorevia:manuscript-rail-advisor:book-123")
  })

  it("routes quick notes to chapter or whole-book vault folders", () => {
    expect(buildQuickVaultNoteFolder("chapter", 4)).toEqual(["Chapter 4"])
    expect(buildQuickVaultNoteFolder("book", 4)).toEqual(["Whole Book"])
  })

  it("creates compact note previews from markdown content", () => {
    expect(getNotePreview("# Chapter beat\n\n**Fix** the reveal pacing.", 24)).toBe("Chapter beat Fix the rev...")
  })
})

describe("ManuscriptWriteRightRail UI", () => {
  let root: Root | null = null
  let container: HTMLDivElement | null = null
  let storage: Map<string, string>

  beforeAll(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    storage = new Map()
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      value: {
        getItem: vi.fn((key: string) => storage.get(key) ?? null),
        setItem: vi.fn((key: string, value: string) => storage.set(key, value)),
        clear: vi.fn(() => storage.clear()),
      },
    })
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
    storage.clear()
  })

  it("shows notes workspace files beside chapter-linked notes", () => {
    const rendered = renderRail()
    root = rendered.root
    container = rendered.container

    expect(container.textContent).toContain("Notes workspace")
    expect(container.textContent).toContain("Mirror reveal")
    expect(container.textContent).toContain("Manual Editor/Chapter 2/Mirror reveal.md")
    expect(container.textContent).toContain("Chapter notes")
  })

  it("loads previous advisor messages for the manuscript rail", async () => {
    window.localStorage.setItem(
      buildManuscriptRailAdvisorStorageKey("book-1"),
      JSON.stringify([{ role: "assistant", content: "Previously: strengthen the chapter transition." }]),
    )

    const rendered = renderRail({ activeRightPane: "advisor" })
    root = rendered.root
    container = rendered.container

    await act(async () => {
      await Promise.resolve()
    })

    expect(container.textContent).toContain("Chapter advisor")
    expect(container.textContent).toContain("Previously: strengthen the chapter transition.")
  })
})
