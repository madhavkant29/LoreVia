import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"

import { CharacterProfileTabs } from "./CharacterProfileTabs"

let container: HTMLDivElement | null = null
let root: Root | null = null

describe("CharacterProfileTabs", () => {
  beforeAll(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  })

  afterEach(() => {
    act(() => root?.unmount())
    container?.remove()
    container = null
    root = null
  })

  it("marks the current profile tab and reports a new selection", () => {
    const onSelect = vi.fn()
    const view = renderTabs(onSelect)

    expect(view.querySelector('button[aria-selected="true"]')?.textContent).toBe("Evidence")
    act(() => {
      view.querySelectorAll("button")[0]?.click()
    })
    expect(onSelect).toHaveBeenCalledWith("overview")
  })
})

function renderTabs(onSelect: ReturnType<typeof vi.fn>) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => {
    root?.render(<CharacterProfileTabs active="evidence" isDark={false} onSelect={onSelect} />)
  })
  return container
}
