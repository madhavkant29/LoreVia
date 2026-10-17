import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"

import { CharacterProfileTabs, type CharacterProfileTab } from "./CharacterProfileTabs"

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
    const onSelect = vi.fn<(tab: CharacterProfileTab) => void>()
    const view = renderTabs(onSelect)

    expect(view.querySelector('button[aria-selected="true"]')?.textContent).toBe("Evidence")
    act(() => {
      view.querySelectorAll("button")[0]?.click()
    })
    expect(onSelect).toHaveBeenCalledWith("overview")
  })

  it("moves focus with arrows and Home/End while keeping a single tab stop", () => {
    const onSelect = vi.fn()
    const view = renderTabs(onSelect)
    expect(view.querySelectorAll('button[tabindex="0"]')).toHaveLength(1)
    const evidence = view.querySelector<HTMLButtonElement>('#character-tab-evidence')!
    act(() => evidence.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true })))
    expect(onSelect).toHaveBeenLastCalledWith("notes")
    expect(document.activeElement?.id).toBe("character-tab-notes")
    act(() => document.activeElement?.dispatchEvent(new KeyboardEvent("keydown", { key: "Home", bubbles: true })))
    expect(onSelect).toHaveBeenLastCalledWith("overview")
    act(() => document.activeElement?.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowLeft", bubbles: true })))
    expect(onSelect).toHaveBeenLastCalledWith("notes")
  })
})

function renderTabs(onSelect: (tab: CharacterProfileTab) => void) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => {
    root?.render(<CharacterProfileTabs active="evidence" isDark={false} onSelect={onSelect} />)
  })
  return container
}
