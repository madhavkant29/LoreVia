// @vitest-environment jsdom

import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { ReaderTools } from "./ReaderTools"

const capture = vi.fn()
vi.mock("@/lib/analytics/posthog", () => ({ capture: (...args: unknown[]) => capture(...args) }))

let root: Root
let container: HTMLDivElement

beforeEach(() => {
  container = document.createElement("div")
  document.body.appendChild(container)
  const body = document.createElement("article")
  body.dataset.editorialBody = ""
  Object.defineProperty(body, "offsetHeight", { value: 2000 })
  document.body.appendChild(body)
  root = createRoot(container)
  capture.mockReset()
})

afterEach(() => {
  act(() => root.unmount())
  document.body.innerHTML = ""
  vi.restoreAllMocks()
})

describe("ReaderTools", () => {
  it("renders mobile jump navigation aligned to H2 anchors", async () => {
    await act(async () => {
      root.render(<ReaderTools kind="blog" slug="story" title="Story" tableOfContents={[{ id: "first-step", label: "First step" }]} />)
    })

    expect(container.querySelector("details")?.textContent).toContain("Jump to a section")
    expect(container.querySelector('a[href="#first-step"]')?.textContent).toBe("First step")
  })

  it("copies the canonical browser URL and gives accessible feedback", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } })
    window.history.replaceState({}, "", "/blog/story")

    await act(async () => {
      root.render(<ReaderTools kind="blog" slug="story" title="Story" tableOfContents={[]} />)
    })
    await act(async () => {
      ;(container.querySelector('button[aria-label="Copy article link"]') as HTMLButtonElement).click()
      await Promise.resolve()
    })

    expect(writeText).toHaveBeenCalledWith("http://localhost:3000/blog/story")
    expect(container.textContent).toContain("Link copied")
    expect(capture).toHaveBeenCalledWith("editorial_article_shared", expect.objectContaining({ method: "copy" }))
  })

  it("falls back to copying when Web Share is unavailable", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText } })
    Object.defineProperty(navigator, "share", { configurable: true, value: undefined })

    await act(async () => {
      root.render(<ReaderTools kind="answer" slug="answer" title="Answer" tableOfContents={[]} />)
    })
    await act(async () => {
      ;(container.querySelector('button[aria-label="Share article"]') as HTMLButtonElement).click()
      await Promise.resolve()
    })
    expect(writeText).toHaveBeenCalledOnce()
  })

  it("records reading-depth milestones as the article is consumed", async () => {
    const body = document.querySelector<HTMLElement>("[data-editorial-body]")
    expect(body).toBeTruthy()
    vi.spyOn(body!, "getBoundingClientRect").mockReturnValue({
      top: -2200,
      bottom: 0,
      left: 0,
      right: 0,
      width: 700,
      height: 2000,
      x: 0,
      y: -2200,
      toJSON: () => ({}),
    })

    await act(async () => {
      root.render(<ReaderTools kind="blog" slug="story" title="Story" tableOfContents={[]} />)
    })

    expect(capture).toHaveBeenCalledWith("editorial_article_depth", { kind: "blog", slug: "story", depth_percent: 25 })
    expect(capture).toHaveBeenCalledWith("editorial_article_depth", { kind: "blog", slug: "story", depth_percent: 100 })
  })

  it("records delegated related-reading and CTA clicks", async () => {
    await act(async () => {
      root.render(<ReaderTools kind="answer" slug="answer" title="Answer" tableOfContents={[]} />)
    })

    const related = document.createElement("a")
    related.dataset.editorialEvent = "editorial_related_opened"
    related.dataset.editorialDestination = "/answers/next-answer"
    document.body.appendChild(related)
    related.click()

    const cta = document.createElement("a")
    cta.dataset.editorialEvent = "editorial_cta_opened"
    cta.dataset.editorialDestination = "/register"
    document.body.appendChild(cta)
    cta.click()

    expect(capture).toHaveBeenCalledWith("editorial_related_opened", {
      kind: "answer",
      slug: "answer",
      destination: "/answers/next-answer",
    })
    expect(capture).toHaveBeenCalledWith("editorial_cta_opened", {
      kind: "answer",
      slug: "answer",
      destination: "/register",
    })
  })
})
