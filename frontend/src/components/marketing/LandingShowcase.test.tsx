import React from "react"
import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest"

import { LANDING_SHOWCASE_VISUALS, LandingShowcase } from "./LandingShowcase"

vi.mock("next/image", () => ({
  default: ({ alt, src, className, loading }: { alt: string; src: string; className?: string; loading?: "eager" | "lazy" }) => (
    <img alt={alt} className={className} src={src} loading={loading} />
  ),
}))

let container: HTMLDivElement | null = null
let root: Root | null = null
let observerCallback:
  | ((entries: Array<{ isIntersecting: boolean; intersectionRatio: number; target: Element }>) => void)
  | null = null

class MockIntersectionObserver {
  readonly root = null
  readonly rootMargin = ""
  readonly thresholds = []

  constructor(callback: typeof observerCallback) {
    observerCallback = callback
  }

  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() { return [] }
}

describe("LandingShowcase", () => {
  beforeAll(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    globalThis.IntersectionObserver = MockIntersectionObserver as unknown as typeof IntersectionObserver
  })

  afterEach(() => {
    if (root) act(() => root?.unmount())
    container?.remove()
    container = null
    root = null
    observerCallback = null
  })

  it("presents exactly three evidence-led product stories", () => {
    const view = renderComponent(<LandingShowcase />)
    const stories = view.querySelectorAll("[data-showcase-step]")

    expect(stories).toHaveLength(3)
    expect(view.textContent).toContain("From manuscript evidence to a revision decision.")
    expect(view.textContent).toContain("See the conflict beside the manuscript")
    expect(view.textContent).toContain("Follow what changed, who knows it, and when")
    expect(view.textContent).toContain("Turn a finding into a revision decision")
  })

  it("uses one lazy product image per story and no thumbnail swap controls", () => {
    const view = renderComponent(<LandingShowcase />)
    const images = Array.from(view.querySelectorAll("img"))

    expect(LANDING_SHOWCASE_VISUALS).toEqual([
      "/landing/manuscript-analysis-with-advisor.webp",
      "/landing/character-continuity.webp",
      "/landing/editorial-review-2.webp",
    ])
    expect(new Set(images.map((image) => image.getAttribute("src")))).toEqual(new Set(LANDING_SHOWCASE_VISUALS))
    expect(images.every((image) => image.getAttribute("loading") === "lazy")).toBe(true)
    expect(view.querySelectorAll("figure button")).toHaveLength(0)
  })

  it("renders proof points as a divided list instead of cards", () => {
    const view = renderComponent(<LandingShowcase />)

    expect(view.querySelectorAll("article ul")).toHaveLength(3)
    expect(view.querySelectorAll("article li")).toHaveLength(9)
    expect(view.querySelectorAll("article li.rounded-md")).toHaveLength(0)
  })

  it("updates the sticky product screenshot when a story enters view", () => {
    const view = renderComponent(<LandingShowcase />)
    const memoryStory = view.querySelector('[data-showcase-step="memory"]')

    act(() => {
      observerCallback?.([{ isIntersecting: true, intersectionRatio: 0.8, target: memoryStory as Element }])
    })

    const desktopFrame = view.querySelector(".sticky img")
    expect(desktopFrame?.getAttribute("src")).toBe("/landing/character-continuity.webp")
  })

  it("preserves full product screenshots without crop styling", () => {
    const view = renderComponent(<LandingShowcase />)

    expect(view.querySelector("img.object-cover")).toBeNull()
    expect(view.querySelector("img.object-contain")).not.toBeNull()
  })
})

function renderComponent(element: React.ReactNode) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
  act(() => root?.render(element))
  return container
}
