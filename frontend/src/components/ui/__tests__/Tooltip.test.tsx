// @vitest-environment jsdom

import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, describe, expect, it } from "vitest"

import { Tooltip } from "../Tooltip"

let container: HTMLDivElement | null = null
let root: Root | null = null

afterEach(() => {
  if (root) {
    act(() => {
      root?.unmount()
    })
  }
  container?.remove()
  container = null
  root = null
  document.body.innerHTML = ""
})

function renderTooltip() {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  act(() => {
    root?.render(
      <Tooltip content="Open project actions" className="w-full" align="end" side="bottom">
        <button type="button" aria-label="Project actions">
          Actions
        </button>
      </Tooltip>,
    )
  })

  return container
}

describe("Tooltip", () => {
  it("renders accessible tooltip content next to the trigger", () => {
    const rendered = renderTooltip()
    const tooltip = rendered.querySelector('[role="tooltip"]')
    const button = rendered.querySelector("button")

    expect(button?.getAttribute("aria-label")).toBe("Project actions")
    expect(button?.getAttribute("aria-describedby")).toBe(tooltip?.id)
    expect(tooltip?.textContent).toBe("Open project actions")
    expect(tooltip?.className).toContain("group-hover/tooltip:block")
    expect(tooltip?.className).toContain("group-focus-within/tooltip:block")
  })

  it("merges wrapper classes and placement classes", () => {
    const rendered = renderTooltip()
    const wrapper = rendered.firstElementChild
    const tooltip = rendered.querySelector('[role="tooltip"]')

    expect(wrapper?.className).toContain("group/tooltip")
    expect(wrapper?.className).toContain("w-full")
    expect(tooltip?.className).toContain("top-full")
    expect(tooltip?.className).toContain("right-0")
  })
})
