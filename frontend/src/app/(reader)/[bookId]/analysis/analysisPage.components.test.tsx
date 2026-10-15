import { act, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, describe, expect, it, vi } from "vitest"
import type { ChapterConsistencyReport, ContinuityFinding } from "@/types/book"
import { FindingsList } from "./analysisPage.findings"
import { ChapterReportsView } from "./analysisPage.reports"

vi.mock("next/link", () => ({ default: ({ children, href }: { children: ReactNode; href: string }) => <a href={href}>{children}</a> }))
let root: Root | undefined
let host: HTMLDivElement
afterEach(() => { act(() => root?.unmount()); document.body.innerHTML = "" })
async function render(node: ReactNode) {
  host = document.createElement("div"); document.body.appendChild(host); root = createRoot(host)
  await act(async () => root?.render(node))
}
async function click(label: string) {
  await act(async () => [...host.querySelectorAll("button")].find((button) => button.textContent?.includes(label))?.click())
}
const seed = { id: "one", title: "Oath conflict", explanation: "Check the source", severity: "high", category: "knowledge", evidence: [], is_stale: false, decision: null } as unknown as ContinuityFinding

describe("analysis evidence views", () => {
  it("shows additional findings on request instead of dropping them", async () => {
    const findings = Array.from({ length: 14 }, (_, index) => ({ ...seed, id: String(index), title: `Finding ${index}` }))
    await render(<FindingsList bookId="book" findings={findings} isDark />)
    expect(host.querySelectorAll("article")).toHaveLength(12)
    await click("Show more findings")
    expect(host.querySelectorAll("article")).toHaveLength(14)
  })
  it("offers reviewed and stale findings and explains missing evidence", async () => {
    await render(<FindingsList bookId="book" findings={[seed, { ...seed, id: "stale", title: "Older version", is_stale: true }]} isDark={false} />)
    expect(host.textContent).toContain("No manuscript excerpts are attached")
    await click("Stale after edits")
    expect(host.querySelector("article")?.textContent).toContain("Older version")
    expect(host.textContent).toContain("earlier manuscript version")
    await click("Reviewed")
    expect(host.textContent).toContain("No reviewed findings yet")
  })
  it("searches and clears the active finding group", async () => {
    await render(<FindingsList bookId="book" findings={[seed]} isDark />)
    const input = host.querySelector("input")!
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(input, "missing")
      input.dispatchEvent(new Event("input", { bubbles: true }))
    })
    expect(host.querySelectorAll("article")).toHaveLength(0)
    await click("Clear search")
    expect(host.querySelectorAll("article")).toHaveLength(1)
  })
  it("updates report counts and recovers a filter removed by a refresh", async () => {
    const reports = [1, 2].map((chapter_number) => ({ chapter_number, chapter_title: `Part ${chapter_number}`, summary: "", new_characters: [], relationship_changes: [], plot_threads_opened: [], plot_threads_resolved: ["Oath"], continuity_flags: [] }))
    await render(<ChapterReportsView bookId="book" reports={reports} isDark />)
    const select = host.querySelector("select")!
    await act(async () => { select.value = "2"; select.dispatchEvent(new Event("change", { bubbles: true })) })
    expect(host.querySelectorAll("article")).toHaveLength(1)
    expect(host.querySelector('[aria-label="Chapter report summary"]')?.textContent).toContain("Chapters shown1")
    await act(async () => root?.render(<ChapterReportsView bookId="book" reports={[reports[0]]} isDark />))
    expect(select.value).toBe("all")
    expect(host.querySelector("article")?.textContent).toContain("Chapter 1")
  })
  it("keeps the report empty state actionable", async () => {
    await render(<ChapterReportsView bookId="book" reports={[] as ChapterConsistencyReport[]} isDark />)
    expect(host.querySelector("a")?.getAttribute("href")).toBe("/book/chapters")
  })
})
