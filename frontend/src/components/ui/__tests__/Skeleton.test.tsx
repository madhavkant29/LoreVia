// @vitest-environment jsdom

import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, describe, expect, it } from "vitest"

import {
  CardSkeleton,
  DashboardSkeleton,
  EditorSkeleton,
  MetricCardSkeleton,
  RowSkeleton,
  SidebarSkeleton,
  Skeleton,
} from "../Skeleton"

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

function renderSkeleton(variant: "text" | "card" | "circle" = "text", className?: string) {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)

  act(() => {
    root?.render(<Skeleton variant={variant} className={className} />)
  })

  return container.firstElementChild as HTMLDivElement | null
}

describe("Skeleton", () => {
  it("renders text variant with correct default classes", () => {
    const el = renderSkeleton("text")

    expect(el).not.toBeNull()
    expect(el?.className).toContain("animate-pulse")
    expect(el?.className).toContain("bg-muted")
    expect(el?.className).toContain("h-4")
    expect(el?.className).toContain("w-full")
    expect(el?.className).toMatch(/(?:^|\s)rounded(?:\s|$)/)
    expect(el?.className).not.toContain("rounded-full")
    expect(el?.className).not.toContain("rounded-md")
  })

  it("renders card variant with rounded-md and h-48", () => {
    const el = renderSkeleton("card")

    expect(el).not.toBeNull()
    expect(el?.className).toContain("animate-pulse")
    expect(el?.className).toContain("bg-muted")
    expect(el?.className).toContain("h-48")
    expect(el?.className).toContain("rounded-md")
    expect(el?.className).not.toContain("rounded-full")
  })

  it("renders circle variant with rounded-full", () => {
    const el = renderSkeleton("circle")

    expect(el).not.toBeNull()
    expect(el?.className).toContain("animate-pulse")
    expect(el?.className).toContain("bg-muted")
    expect(el?.className).toContain("h-10")
    expect(el?.className).toContain("w-10")
    expect(el?.className).toContain("rounded-full")
    expect(el?.className).not.toContain("rounded-md")
    expect(el?.className).not.toMatch(/(?:^|\s)rounded(?:\s|$)/)
  })

  it("merges custom className with variant defaults", () => {
    const el = renderSkeleton("text", "h-6 w-3/4")

    expect(el).not.toBeNull()
    expect(el?.className).toContain("animate-pulse")
    expect(el?.className).toContain("bg-muted")
    expect(el?.className).toContain("h-6")
    expect(el?.className).toContain("w-3/4")
  })

  it("defaults to text variant when no variant is provided", () => {
    container = document.createElement("div")
    document.body.appendChild(container)
    root = createRoot(container)

    act(() => {
      root?.render(<Skeleton />)
    })

    const el = container.firstElementChild as HTMLDivElement | null

    expect(el).not.toBeNull()
    expect(el?.className).toContain("h-4")
    expect(el?.className).toContain("w-full")
    expect(el?.className).toMatch(/(?:^|\s)rounded(?:\s|$)/)
  })

  it("has the animate-pulse animation class for all variants", () => {
    const textEl = renderSkeleton("text")
    const cardEl = renderSkeleton("card")
    const circleEl = renderSkeleton("circle")

    expect(textEl?.className).toContain("animate-pulse")
    expect(cardEl?.className).toContain("animate-pulse")
    expect(circleEl?.className).toContain("animate-pulse")
  })

  it("renders as a div element", () => {
    const el = renderSkeleton("text")

    expect(el?.tagName).toBe("DIV")
  })

  it("marks primitive skeleton blocks as decorative", () => {
    const el = renderSkeleton("text")

    expect(el?.getAttribute("aria-hidden")).toBe("true")
  })

  it("exports layout skeleton primitives", () => {
    container = document.createElement("div")
    document.body.appendChild(container)
    root = createRoot(container)

    act(() => {
      root?.render(
        <div>
          <CardSkeleton />
          <RowSkeleton />
          <MetricCardSkeleton />
          <SidebarSkeleton />
          <EditorSkeleton />
          <DashboardSkeleton />
        </div>,
      )
    })

    expect(container.querySelectorAll(".animate-pulse").length).toBeGreaterThan(10)
    expect(container.querySelector('[role="status"]')?.getAttribute("aria-busy")).toBe("true")
  })
})
