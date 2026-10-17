import React, { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it } from "vitest"

import { RecentActivityList } from "./RecentActivityList"

let container: HTMLDivElement | null = null
let root: Root | null = null

describe("RecentActivityList", () => {
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

  it("uses a flat three-item summary in compact mode", () => {
    const view = renderList("compact")

    expect(view.querySelector("section")?.className).toContain("border-y")
    expect(view.textContent).toContain("First signal")
    expect(view.textContent).toContain("Third signal")
    expect(view.textContent).not.toContain("Fourth signal")
    expect(view.textContent).not.toContain("4 signals")
  })

  it("keeps the fuller panel treatment as the default", () => {
    const view = renderList()

    expect(view.querySelector("section")?.className).toContain("app-panel")
    expect(view.textContent).toContain("Fourth signal")
  })
})

function renderList(variant?: "panel" | "compact") {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  act(() => {
    root?.render(
      <RecentActivityList
        title="Project signals"
        variant={variant}
        items={[1, 2, 3, 4].map((number) => ({
          id: String(number),
          label: `${ordinal(number)} signal`,
          detail: `Detail ${number}`,
        }))}
      />,
    )
  })

  return container
}

function ordinal(number: number) {
  return ["", "First", "Second", "Third", "Fourth"][number]
}
