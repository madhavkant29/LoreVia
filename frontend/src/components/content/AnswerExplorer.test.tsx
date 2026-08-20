// @vitest-environment jsdom

import { act } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { AnswerExplorer, type AnswerExplorerItem } from "./AnswerExplorer"

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement>) => <a href={String(href)} {...props}>{children}</a>,
}))

const items: AnswerExplorerItem[] = [
  { slug: "timeline", title: "How do I manage time?", description: "Build a chronology.", category: "Continuity", readTime: "4 min read", parentSlug: "continuity", parentTitle: "Continuity guide" },
  { slug: "arc", title: "How do I track an arc?", description: "Follow decisions.", category: "Character craft", readTime: "4 min read", parentSlug: "characters", parentTitle: "Character guide" },
]

function changeSearch(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set
  setter?.call(input, value)
  input.dispatchEvent(new Event("input", { bubbles: true }))
}

let root: Root
let container: HTMLDivElement

beforeEach(() => {
  container = document.createElement("div")
  document.body.appendChild(container)
  root = createRoot(container)
})

afterEach(() => {
  act(() => root.unmount())
  container.remove()
})

describe("AnswerExplorer", () => {
  it("groups answers by broader guide and filters in memory", async () => {
    await act(async () => root.render(<AnswerExplorer items={items} />))
    expect(container.textContent).toContain("Continuity guide")
    expect(container.textContent).toContain("Character guide")

    const input = container.querySelector('input[type="search"]') as HTMLInputElement
    await act(async () => {
      changeSearch(input, "chronology")
    })
    expect(container.textContent).toContain("How do I manage time?")
    expect(container.textContent).not.toContain("How do I track an arc?")
    expect(container.textContent).toContain("1 answers")
  })

  it("shows a clearable empty state", async () => {
    await act(async () => root.render(<AnswerExplorer items={items} />))
    const input = container.querySelector('input[type="search"]') as HTMLInputElement
    await act(async () => {
      changeSearch(input, "unavailable phrase")
    })
    expect(container.textContent).toContain("No answers found")
    await act(async () => (container.querySelector(".editorial-empty-state button") as HTMLButtonElement).click())
    expect(container.textContent).toContain("2 answers")
  })
})
