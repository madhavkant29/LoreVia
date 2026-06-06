import React, { act, createRef, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"

import { ManuscriptNonWriteWorkspace } from "./ManuscriptNonWriteWorkspace"

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: { href: string; children: ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

describe("ManuscriptNonWriteWorkspace", () => {
  let container: HTMLDivElement | null = null
  let root: Root | null = null

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

  it("offers the expanded manuscript font families in page setup", () => {
    container = document.createElement("div")
    document.body.appendChild(container)
    root = createRoot(container)

    act(() => {
      root?.render(
        <ManuscriptNonWriteWorkspace
          isDark={false}
          bookId="book-1"
          activeChapterNumber={1}
          preWritingCheck={null}
          editorMode="chapter"
          onEditorModeChange={vi.fn()}
          draftSurfaceMode="edit"
          onDraftSurfaceModeChange={vi.fn()}
          leftRailVisible
          onToggleLeftRail={vi.fn()}
          chapterWordCount={120}
          fullBookWordCount={120}
          chapterPageSummaryLabel="1 page"
          fullBookPageSummaryLabel="1 page"
          draftSurfaceSummaryLabel="Draft"
          showPageSetup
          onTogglePageSetup={vi.fn()}
          showSearchTools={false}
          onToggleSearchTools={vi.fn()}
          fontFamily="times"
          onFontFamilyChange={vi.fn()}
          fontSize={12}
          onFontSizeChange={vi.fn()}
          lineHeight={1.8}
          onLineHeightChange={vi.fn()}
          firstLineIndent={false}
          onToggleFirstLineIndent={vi.fn()}
          showPageGuides
          onToggleShowPageGuides={vi.fn()}
          searchInputRef={createRef<HTMLInputElement>()}
          recallQuery=""
          onRecallQueryChange={vi.fn()}
          replaceQuery=""
          onReplaceQueryChange={vi.fn()}
          replaceValue=""
          onReplaceValueChange={vi.fn()}
          onReplaceInCurrentChapter={vi.fn()}
          onReplaceEverywhere={vi.fn()}
          recallCharacter={null}
          recallLoading={false}
          recallResults={[]}
          activeFindIndex={0}
          onJumpToChapter={vi.fn()}
          inlineContinuity={null}
          logicSelectionText=""
          continuityLoading={false}
        />
      )
    })

    const options = Array.from(container.querySelectorAll("option")).map((option) => option.textContent)
    expect(options).toContain("Italian Old Style")
    expect(options).toContain("EB Garamond")
  })
})
