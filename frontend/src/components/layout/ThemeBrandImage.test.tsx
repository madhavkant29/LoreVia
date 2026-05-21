import React from "react"
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it } from "vitest"

import { ThemeBrandImage } from "./ThemeBrandImage"

let container: HTMLDivElement | null = null
let root: Root | null = null

describe("ThemeBrandImage", () => {
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

  it("renders the light and dark lockup assets with theme visibility classes", () => {
    const view = renderComponent(<ThemeBrandImage variant="lockup" className="h-10 w-auto" priority />)
    const images = Array.from(view.querySelectorAll("img"))

    expect(images).toHaveLength(2)
    expect(images[0].getAttribute("src")).toBe("/logoandtextlight.png")
    expect(images[0].className).toContain("dark:hidden")
    expect(images[0].getAttribute("fetchpriority")).toBe("high")
    expect(images[1].getAttribute("src")).toBe("/logoandtext.png")
    expect(images[1].className).toContain("dark:block")
    expect(images[1].className).toContain("hidden")
  })

  it("renders the icon assets when the icon variant is requested", () => {
    const view = renderComponent(<ThemeBrandImage variant="icon" />)
    const images = Array.from(view.querySelectorAll("img"))

    expect(images[0].getAttribute("src")).toBe("/imagelight.png")
    expect(images[1].getAttribute("src")).toBe("/image.png")
  })
})

function renderComponent(element: React.ReactNode) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  act(() => {
    root?.render(element)
  })

  return container
}
