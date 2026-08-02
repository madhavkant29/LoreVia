import { readdirSync } from "node:fs"

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
  takeRecords() {
    return []
  }
}

describe("LandingShowcase", () => {
  beforeAll(() => {
    ;(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true
    globalThis.IntersectionObserver = MockIntersectionObserver as unknown as typeof IntersectionObserver
    window.matchMedia = vi.fn().mockReturnValue({ matches: false })
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
    observerCallback = null
  })

  it("renders the manuscript analysis screenshot first", () => {
    const view = renderComponent(<LandingShowcase />)

    expect(view.textContent).toContain("One manuscript. Every hidden inconsistency surfaced.")
    expect(view.textContent).toContain("Analyze the full manuscript")
    expect(view.querySelector('img[src="/landing/manuscript-analysis.png"]')).not.toBeNull()
  })

  it("uses every landing screenshot asset in the showcase", () => {
    const view = renderComponent(<LandingShowcase />)
    const landingVisuals = readdirSync("public/landing")
      .filter((fileName) => fileName.endsWith(".png"))
      .map((fileName) => `/landing/${fileName}`)

    for (const visual of landingVisuals) {
      expect(view.querySelector(`img[src="${visual}"]`)).not.toBeNull()
    }
    expect([...LANDING_SHOWCASE_VISUALS].sort()).toEqual([...landingVisuals].sort())
    expect(new Set(LANDING_SHOWCASE_VISUALS).size).toBe(LANDING_SHOWCASE_VISUALS.length)
  })

  it("keeps paired showcase screenshots in their intended order", () => {
    const view = renderComponent(<LandingShowcase />)
    const images = Array.from(view.querySelectorAll("img")).map((image) => image.getAttribute("src"))

    expect(images.indexOf("/landing/manuscript-analysis.png")).toBeLessThan(
      images.indexOf("/landing/manuscript-analysis-with-advisor.png"),
    )
    expect(images.indexOf("/landing/editorial-review.png")).toBeLessThan(
      images.indexOf("/landing/editorial-review-2.png"),
    )
  })

  it("shows paired screenshots as a non-scrollable stacked-card preview", () => {
    const view = renderComponent(<LandingShowcase />)
    const firstPairedImage = view.querySelector('img[src="/landing/manuscript-analysis.png"]')
    const secondPairedImages = view.querySelectorAll('img[src="/landing/manuscript-analysis-with-advisor.png"]')
    const secondPairedImage = secondPairedImages[secondPairedImages.length - 1]
    const stackedWrapper = firstPairedImage?.parentElement?.parentElement
    const firstImagePanel = firstPairedImage?.parentElement
    const secondImagePanel = secondPairedImage?.parentElement

    expect(stackedWrapper?.className).toContain("relative")
    expect(stackedWrapper?.className).toContain("overflow-visible")
    expect(stackedWrapper?.className).toContain("lg:pb-[12%]")
    expect(stackedWrapper?.className).not.toContain("overflow-y-auto")
    expect(stackedWrapper?.className).not.toContain("snap")
    expect(firstImagePanel?.className).toContain("relative")
    expect(firstImagePanel?.className).toContain("z-20")
    expect(firstPairedImage?.className).toContain("transition-opacity")
    expect(firstPairedImage?.className).toContain("duration-[900ms]")
    expect(secondImagePanel?.className).toContain("relative")
    expect(secondImagePanel?.className).toContain("mx-auto")
    expect(secondImagePanel?.className).toContain("mt-3")
    expect(secondImagePanel?.className).toContain("w-[58%]")
    expect(secondImagePanel?.className).toContain("max-w-[260px]")
    expect(secondImagePanel?.className).toContain("lg:absolute")
    expect(secondImagePanel?.className).toContain("lg:left-1/2")
    expect(secondImagePanel?.className).toContain("lg:top-[88%]")
    expect(secondImagePanel?.className).toContain("lg:w-[46%]")
    expect(secondImagePanel?.className).toContain("lg:max-w-[520px]")
    expect(secondImagePanel?.className).toContain("z-10")
    expect(secondImagePanel?.className).toContain("cursor-pointer")
    expect(secondImagePanel?.className).not.toContain("pointer-events-none")
    expect(secondImagePanel?.className).toContain("transition-[filter,opacity,box-shadow,border-color,transform]")
    expect(secondImagePanel?.className).toContain("duration-[900ms]")
    expect(secondImagePanel?.className).toContain("ease-[cubic-bezier(0.22,1,0.36,1)]")
  })

  it("swaps the paired preview thumbnail after clicking it", () => {
    const view = renderComponent(<LandingShowcase />)
    const secondImages = view.querySelectorAll('img[src="/landing/manuscript-analysis-with-advisor.png"]')
    const previewButton = secondImages[secondImages.length - 1]?.parentElement

    expect(previewButton?.tagName).toBe("BUTTON")
    expect(previewButton?.querySelector("img")?.getAttribute("src")).toBe(
      "/landing/manuscript-analysis-with-advisor.png",
    )

    act(() => {
      previewButton?.dispatchEvent(new MouseEvent("click", { bubbles: true }))
    })

    expect(previewButton?.querySelector("img")?.getAttribute("src")).toBe(
      "/landing/manuscript-analysis.png",
    )
  })

  it("updates the sticky product screenshot when a feature section enters view", () => {
    const view = renderComponent(<LandingShowcase />)
    const graphSection = view.querySelector('[data-showcase-step="graph"]')

    expect(graphSection).not.toBeNull()

    act(() => {
      observerCallback?.([
        {
          isIntersecting: true,
          intersectionRatio: 0.8,
          target: graphSection as Element,
        },
      ])
    })

    expect(view.querySelector('img[src="/landing/relationship-graph.png"]')).not.toBeNull()
  })

  it("renders product screenshots without crop styling", () => {
    const view = renderComponent(<LandingShowcase />)

    expect(view.querySelector("img.object-cover")).toBeNull()
    expect(view.querySelector("img.object-contain")).not.toBeNull()
  })

  it("lazy loads every below-fold showcase screenshot", () => {
    const view = renderComponent(<LandingShowcase />)
    const images = Array.from(view.querySelectorAll("img"))

    expect(images.length).toBeGreaterThan(0)
    expect(images.every((image) => image.getAttribute("loading") === "lazy")).toBe(true)
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
