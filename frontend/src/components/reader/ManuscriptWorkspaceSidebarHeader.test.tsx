import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"

import { ManuscriptWorkspaceSidebarHeader } from "./ManuscriptWorkspaceSidebarHeader"

let container: HTMLDivElement | null = null
let root: Root | null = null

describe("ManuscriptWorkspaceSidebarHeader", () => {
  beforeAll(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  })

  afterEach(() => {
    act(() => root?.unmount())
    container?.remove()
    container = null
    root = null
  })

  it("shows manuscript metrics and exposes explicit creation actions", () => {
    const onCreateChapter = vi.fn<() => void>()
    const onCreateScene = vi.fn<() => void>()
    const view = renderHeader(onCreateChapter, onCreateScene)

    expect(view.textContent).toContain("12,345 words")
    act(() => {
      view.querySelectorAll("button")[0]?.click()
      view.querySelectorAll("button")[1]?.click()
    })
    expect(onCreateChapter).toHaveBeenCalledOnce()
    expect(onCreateScene).toHaveBeenCalledOnce()
  })
})

function renderHeader(onCreateChapter: () => void, onCreateScene: () => void) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => {
    root?.render(
      <ManuscriptWorkspaceSidebarHeader
        bookTitle="Bloodline of Dawn"
        fullBookReadingTime="49 min read"
        fullBookWordCount={12345}
        isDark={false}
        onCreateChapter={onCreateChapter}
        onCreateScene={onCreateScene}
      />
    )
  })
  return container
}
