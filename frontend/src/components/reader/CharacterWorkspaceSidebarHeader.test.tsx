import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"

import { CharacterWorkspaceSidebarHeader } from "./CharacterWorkspaceSidebarHeader"

let container: HTMLDivElement | null = null
let root: Root | null = null

describe("CharacterWorkspaceSidebarHeader", () => {
  beforeAll(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
  })

  afterEach(() => {
    if (root) {
      act(() => root?.unmount())
    }
    container?.remove()
    container = null
    root = null
  })

  it("renders cast filters in profile mode", () => {
    const view = renderHeader("profile")
    expect(view.textContent).toContain("Cast")
    expect(view.querySelector('input[aria-label="Search characters"]')).not.toBeNull()
    expect(view.querySelector<HTMLSelectElement>('select[aria-label="Filter cast"]')?.value).toBe("all")
  })

  it("uses focused search copy outside profile mode", () => {
    const view = renderHeader("duplicates")
    expect(view.textContent).toContain("Duplicate review")
    expect(view.querySelector('input[aria-label="Search merge suggestions"]')).not.toBeNull()
    expect(view.querySelector("button")).toBeNull()
  })

  it("clears search and every active cast filter together", () => {
    renderHeader("profile")
    const changeSearch = vi.fn(), changeCast = vi.fn(), changeStatus = vi.fn(), changeRole = vi.fn()
    act(() => root?.render(<CharacterWorkspaceSidebarHeader isDark mode="profile" search="Mira" castFilter="main" statusFilter="flagged" roleFilter="mc" summary="1 character" onSearchChange={changeSearch} onCastFilterChange={changeCast} onStatusFilterChange={changeStatus} onRoleFilterChange={changeRole} />))
    act(() => container?.querySelector<HTMLButtonElement>("button")?.click())
    expect(changeSearch).toHaveBeenCalledWith("")
    expect(changeCast).toHaveBeenCalledWith("all")
    expect(changeStatus).toHaveBeenCalledWith("all")
    expect(changeRole).toHaveBeenCalledWith("all")
  })
})

function renderHeader(mode: "profile" | "duplicates") {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => {
    root?.render(
      <CharacterWorkspaceSidebarHeader
        castFilter="all"
        isDark={false}
        mode={mode}
        onCastFilterChange={vi.fn()}
        onSearchChange={vi.fn()}
        search=""
        summary="12 items"
      />
    )
  })
  return container
}
