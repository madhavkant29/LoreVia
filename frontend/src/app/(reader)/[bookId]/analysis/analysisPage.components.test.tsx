import { act, type ReactNode } from "react"
import { createRoot, type Root } from "react-dom/client"
import { afterEach, describe, expect, it, vi } from "vitest"
import type { ChapterConsistencyReport, ContinuityFinding } from "@/types/book"
import { booksApi } from "@/lib/api/books"
import { FindingsList } from "./analysisPage.findings"
import { ChapterReportsView } from "./analysisPage.reports"

vi.mock("next/link", () => ({ default: ({ children, href }: { children: ReactNode; href: string }) => <a href={href}>{children}</a> }))
let root: Root | undefined
let host: HTMLDivElement
afterEach(() => { act(() => root?.unmount()); document.body.innerHTML = ""; vi.restoreAllMocks() })
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
  it("loads older chapter reports only when requested", async () => {
    const onLoadMore = vi.fn()
    await render(<ChapterReportsView bookId="book" reports={[{ chapter_number: 50, chapter_title: "Later", summary: "", new_characters: [], relationship_changes: [], plot_threads_opened: [], plot_threads_resolved: [], continuity_flags: [] }]} hasMore onLoadMore={onLoadMore} isDark />)
    expect(onLoadMore).not.toHaveBeenCalled()
    await click("Load older reports")
    expect(onLoadMore).toHaveBeenCalledOnce()
  })
  it("shows passage-backed concerns and distinguishes missing from completed editorial reviews", async () => {
    const base = { chapter_title: "Opening", summary: "The door opens.", new_characters: [], relationship_changes: [], plot_threads_opened: [], plot_threads_resolved: [], continuity_flags: [] }
    await render(<ChapterReportsView bookId="book" reports={[
      { ...base, chapter_number: 1, editorial_concerns: [{ issue: "The decision is abrupt.", evidence: "The door opens.", suggestion: "Show the decision before the door moves." }] },
      { ...base, chapter_number: 2, editorial_concerns: [] },
      { ...base, chapter_number: 3, editorial_concerns: null },
      { ...base, chapter_number: 4, editorial_concerns: [], revision_question: { question: "What does the open door mean for Mara now?", evidence: "The door opens." } },
    ]} canReprocess isDark />)
    const articles = host.querySelectorAll("article")
    expect(articles[0].textContent).toContain("The decision is abrupt.")
    expect(articles[0].querySelector("blockquote")?.textContent).toBe("The door opens.")
    expect(articles[1].textContent).toContain("found no chapter-specific problem with supporting evidence")
    expect(articles[2].textContent).toContain("has not been recorded for this chapter yet")
    expect(articles[2].querySelector('a[href="/book/manuscript"]')?.textContent).toBe("Open Manuscript Editor")
    expect(articles[3].textContent).toContain("A question for revision")
    expect(articles[3].textContent).toContain("What does the open door mean for Mara now?")
    expect(articles[3].querySelector("blockquote")?.textContent).toBe("The door opens.")
  })
  it("starts an older chapter review only after explicit allowance confirmation", async () => {
    const reprocess = vi.spyOn(booksApi, "reprocessChapter").mockResolvedValue({ book_id: "book", status: "queued", chapters_queued: 1, total_words: 200, upload_charge_consumed: false })
    const report: ChapterConsistencyReport = { chapter_number: 3, chapter_title: "Departure", summary: "Mara leaves.", new_characters: [], relationship_changes: [], plot_threads_opened: [], plot_threads_resolved: [], continuity_flags: [], editorial_concerns: null }
    await render(<ChapterReportsView bookId="book" reports={[report]} canReprocess isDark />)
    expect(reprocess).not.toHaveBeenCalled()
    await click("Reprocess Chapter 3")
    expect(host.textContent).toContain("uses processed-word allowance")
    expect(reprocess).not.toHaveBeenCalled()
    await click("Cancel")
    expect(reprocess).not.toHaveBeenCalled()
    await click("Reprocess Chapter 3")
    await click("Start chapter reprocess")
    expect(reprocess).toHaveBeenCalledWith("book", 3)
    expect(host.textContent).toContain("Chapter 3 reprocessing started")
  })
  it("shows a retryable message when chapter reprocessing cannot start", async () => {
    vi.spyOn(booksApi, "reprocessChapter").mockRejectedValue({ isAxiosError: true, response: { status: 429 } })
    const report: ChapterConsistencyReport = { chapter_number: 3, chapter_title: "Departure", summary: "Mara leaves.", new_characters: [], relationship_changes: [], plot_threads_opened: [], plot_threads_resolved: [], continuity_flags: [], editorial_concerns: null }
    await render(<ChapterReportsView bookId="book" reports={[report]} canReprocess isDark />)
    await click("Reprocess Chapter 3")
    await click("Start chapter reprocess")
    expect(host.querySelector('[role="alert"]')?.textContent).toContain("Processing allowance is not available")
    expect(host.textContent).toContain("Start chapter reprocess")
  })
})
