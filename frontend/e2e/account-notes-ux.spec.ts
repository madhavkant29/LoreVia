import { expect, test } from "@playwright/test"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"

const note = { id: "note-1", book_id: "book-1", book_title: "Sky of Ash", chapter_number: 2, chapter_title: "The Ember Gate", title: "Gate oath continuity", body: "<p>Mara keeps the <strong>silver key</strong>.</p>", tags: ["revise"], updated_at: "2026-09-20T10:00:00Z" }
test.beforeEach(async ({ page }) => {
  await installMockApi(page)
  await page.addInitScript(() => { if (!localStorage.getItem("lorevia-preferences")) localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 })); document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax" })
})

test("account notes keep readable rows and keyboard actions at four widths and both themes", async ({ page }, info) => {
  await page.goto("/notes")
  await expect(page.getByRole("heading", { name: "Gate oath continuity" })).toBeVisible()
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    if (width < 1024) await expect.poll(() => page.locator("aside").evaluate((element) => element.getBoundingClientRect().right)).toBeLessThanOrEqual(0)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
    await page.screenshot({ path: info.outputPath(`notes-${width}.png`), fullPage: true, animations: "disabled" })
  }
  await page.getByRole("button", { name: "Read note: Gate oath continuity" }).focus(); await page.keyboard.press("Enter")
  await expect(page.getByRole("button", { name: "Close note: Gate oath continuity" })).toHaveAttribute("aria-expanded", "true")
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.getByRole("button", { name: "Help", exact: true }).click(); await page.keyboard.press("Escape")
  await expect(page.getByRole("button", { name: "Help", exact: true })).toBeFocused()
  await page.evaluate(() => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "light" }, version: 0 })))
  await page.reload()
  await page.getByRole("button", { name: "Read note: Gate oath continuity" }).click()
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.screenshot({ path: info.outputPath("notes-light-expanded.png"), fullPage: true })
})

test("search uses readable text and tags while identical book titles remain separate", async ({ page }) => {
  await page.route("**/api/v1/books/notes/page?*", (request) => request.fulfill({ json: { items: [note, { ...note, id: "n2", book_id: "book-2", title: "Other manuscript note", body: "Elsewhere", tags: [] }], next_cursor: null, has_more: false } }))
  await page.goto("/notes")
  await expect(page.getByText("2 saved notes across 2 manuscripts")).toBeVisible()
  await page.getByRole("searchbox", { name: "Search notes" }).fill("silver key")
  await expect(page.getByRole("heading", { name: "Gate oath continuity" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Other manuscript note" })).toHaveCount(0)
  await page.getByRole("searchbox", { name: "Search notes" }).fill("strong")
  await expect(page.getByRole("heading", { name: "No notes match that search" })).toBeVisible()
  await page.getByRole("button", { name: "Show all notes" }).click()
  await page.getByLabel("Manuscript", { exact: true }).selectOption("book-2")
  await expect(page.getByRole("heading", { name: "Other manuscript note" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Gate oath continuity" })).toHaveCount(0)
  await page.getByRole("button", { name: "Clear filters" }).click()
  await page.getByRole("searchbox", { name: "Search notes" }).fill("revise")
  await expect(page.getByRole("heading", { name: "Gate oath continuity" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Open chapter 2", exact: true })).toHaveAttribute("href", "/book-1/chapter/2")
  await expect(page.getByRole("link", { name: "Book notes workspace", exact: true })).toHaveAttribute("href", "/book-1/notes")
})

test("initial and refresh failures expose recovery and preserve previous notes and filters", async ({ page }) => {
  let fail = true
  await page.route("**/api/v1/books/notes/page?*", (request) => fail ? request.fulfill({ status: 503, json: {} }) : request.fallback())
  await page.goto("/notes"); await page.getByRole("button", { name: "Retry notes", exact: true }).waitFor()
  await expect(page.getByRole("heading", { name: "No notes saved yet" })).toHaveCount(0)
  fail = false; await page.getByRole("button", { name: "Retry notes", exact: true }).click()
  await page.getByRole("searchbox", { name: "Search notes" }).fill("silver key")
  await expect(page.getByRole("heading", { name: "Gate oath continuity" })).toBeVisible()
  fail = true; await page.getByRole("button", { name: "Refresh notes", exact: true }).click()
  await expect(page.getByText("Notes could not be refreshed. Previously loaded notes are still shown.")).toBeVisible()
  await expect(page.getByRole("searchbox", { name: "Search notes" })).toHaveValue("silver key")
  await expect(page.getByRole("heading", { name: "Gate oath continuity" })).toBeVisible()
  fail = false; await page.getByRole("button", { name: "Retry notes", exact: true }).click()
  await expect(page.getByText("Notes could not be refreshed. Previously loaded notes are still shown.")).toHaveCount(0)
})

test("all cursor pages remain searchable and later rows are reachable", async ({ page }) => {
  const requests: string[] = []
  await page.route("**/api/v1/books/notes/page?*", (request) => {
    const url = new URL(request.request().url()); const cursor = url.searchParams.get("cursor"); requests.push(cursor ?? "first")
    expect(url.searchParams.get("include_body")).toBe("true")
    return request.fulfill({ json: cursor ? { items: [{ ...note, id: "last", title: "Final-page note", body: "Last page evidence" }], next_cursor: null, has_more: false } : { items: Array.from({ length: 30 }, (_, i) => ({ ...note, id: `n-${i}`, title: `Note ${i}` })), next_cursor: "second", has_more: true } })
  })
  await page.goto("/notes")
  await expect(page.getByText("31 saved notes across 1 manuscript")).toBeVisible()
  await expect(page.getByRole("heading", { name: "Final-page note", exact: true })).toHaveCount(0)
  await page.getByRole("button", { name: "Show 6 more notes" }).click()
  await expect(page.getByRole("heading", { name: "Final-page note", exact: true })).toBeVisible()
  await page.getByRole("searchbox", { name: "Search notes" }).fill("Last page evidence")
  await expect(page.getByRole("heading", { name: "Final-page note", exact: true })).toBeVisible()
  expect(requests).toEqual(["first", "second"])
})

test("incomplete pagination never displays a misleading empty or complete index", async ({ page }) => {
  let fail = true
  await page.route("**/api/v1/books/notes/page?*", (request) => fail ? request.fulfill({ json: { items: [note], has_more: true, next_cursor: null } }) : request.fallback())
  await page.goto("/notes"); await page.getByRole("button", { name: "Retry notes", exact: true }).waitFor()
  await expect(page.getByRole("heading", { name: "Gate oath continuity" })).toHaveCount(0)
  fail = false; await page.getByRole("button", { name: "Retry notes", exact: true }).click()
  await expect(page.getByRole("heading", { name: "Gate oath continuity" })).toBeVisible()
})

test("empty and plan-restricted indexes provide an appropriate next action", async ({ page }) => {
  await page.route("**/api/v1/books/notes/page?*", (request) => request.fulfill({ json: { items: [], next_cursor: null, has_more: false } }))
  await page.goto("/notes")
  await expect(page.getByRole("link", { name: "Choose a manuscript" })).toHaveAttribute("href", "/library")
  await installMockApi(page, { userTier: "free" }); await page.reload()
  await expect(page.getByRole("heading", { name: "Notes require an active trial or paid plan." })).toBeVisible()
  await expect(page.getByRole("link", { name: "View plans", exact: true })).toHaveAttribute("href", "/pricing")
})

test("loading stays distinct from an empty index and prevents duplicate refreshes", async ({ page }) => {
  let release: (() => void) | undefined
  const waiting = new Promise<void>((resolve) => { release = resolve })
  let requests = 0
  await page.route("**/api/v1/books/notes/page?*", async (request) => { requests++; await waiting; await request.fallback() })
  await page.goto("/notes")
  await expect(page.getByText("Loading saved manuscript notes…", { exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "Refreshing…", exact: true })).toBeDisabled()
  await expect(page.getByRole("heading", { name: "No notes saved yet" })).toHaveCount(0)
  release?.()
  await expect(page.getByRole("heading", { name: "Gate oath continuity" })).toBeVisible()
  expect(requests).toBe(1)
})

test("long and malformed notes wrap and expose the complete readable body", async ({ page }, info) => {
  const longTitle = "UnbrokenTitle".repeat(25)
  await page.route("**/api/v1/books/notes/page?*", (request) => request.fulfill({ json: { items: [{ ...note, title: longTitle, book_title: longTitle, chapter_number: -2, updated_at: "bad", body: `<p style="color:#fff;background-color:#fff;font-size:4px">${"Long text ".repeat(120)}Ending evidence.</p>` }, { ...note, id: "empty", title: null, body: "", chapter_number: null }], next_cursor: null, has_more: false } }))
  await page.setViewportSize({ width: 390, height: 1000 }); await page.goto("/notes")
  await page.getByRole("button", { name: `Read note: ${longTitle}`, exact: true }).click()
  await expect(page.getByText(/Ending evidence\.$/)).toBeVisible()
  await expect(page.getByText("Update date unavailable")).toBeVisible()
  await expect(page.getByRole("link", { name: /^Open chapter/ })).toHaveCount(0)
  await expect(page.getByText("No text in this note.")).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }))
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBe(0)
  await page.screenshot({ path: info.outputPath("notes-long-mobile.png"), fullPage: true })
})
