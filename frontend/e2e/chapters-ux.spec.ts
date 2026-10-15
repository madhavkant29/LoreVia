import { expect, test } from "@playwright/test"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"

const route = "/sky-of-ash--book-1/chapters"
test.beforeEach(async ({ page }) => {
  await installMockApi(page)
  await page.addInitScript(() => {
    if (!localStorage.getItem("lorevia-preferences")) localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 }))
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
})

test("chapters stay readable across screen sizes", async ({ page }, info) => {
  await page.goto(route)
  await expect(page.getByRole("heading", { name: "Chapters", level: 1 })).toBeVisible()
  await expect(page.getByRole("article")).toHaveCount(3)
  await expect.poll(() => page.locator("[data-chapter-navigator]").evaluate((el) => getComputedStyle(el).backgroundColor)).toBe("rgb(7, 18, 17)")
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
    await page.screenshot({ path: info.outputPath(`chapters-${width}.png`), fullPage: true })
  }
  expect(await criticalAccessibilityViolations(page, "main")).toEqual([])
  await page.getByRole("button", { name: "Show chapter recaps" }).click()
  await expect(page.getByText("Chapter recap is not available yet.")).toBeVisible()
  await page.getByText("Read chapter recap", { exact: true }).first().click()
  expect(await criticalAccessibilityViolations(page, "main")).toEqual([])
  await page.evaluate(() => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "light" }, version: 0 })))
  await page.reload()
  await expect(page.getByRole("heading", { name: "Chapters", level: 1 })).toBeVisible()
  await expect(page.getByRole("article")).toHaveCount(3)
  await expect.poll(() => page.locator("[data-chapter-navigator]").evaluate((el) => getComputedStyle(el).backgroundColor)).toBe("rgb(250, 250, 249)")
  expect(await criticalAccessibilityViolations(page, "main")).toEqual([])
  await page.screenshot({ path: info.outputPath("chapters-light-390.png"), fullPage: true })
})

test("chapter filters combine search and status and recover from no matches", async ({ page }) => {
  await page.goto(route)
  await page.getByRole("searchbox", { name: "Find a chapter" }).fill(" RIVER ")
  await expect(page.getByRole("article")).toHaveCount(1)
  await expect(page.getByText("1 of 3 chapters")).toBeVisible()
  await page.getByLabel("Status", { exact: true }).selectOption("read")
  await expect(page.getByText(/No chapters match these filters/)).toBeVisible()
  await page.getByRole("button", { name: "Clear filters" }).click()
  await expect(page.getByRole("article")).toHaveCount(3)
  await page.getByLabel("Status", { exact: true }).selectOption("queued")
  await expect(page.getByRole("article")).toHaveCount(1)
  await expect(page.getByRole("article")).toContainText("River of Glass")
  await page.getByRole("button", { name: "Open chapter 3: River of Glass" }).click()
  await expect(page).toHaveURL(/\/chapter\/3$/)
})

test("chapter list failures offer retry instead of an empty manuscript", async ({ page }) => {
  let fail = true
  await page.route("**/reader/book-1/chapters", (request) => fail ? request.fulfill({ status: 503, json: { detail: "Try later" } }) : request.fallback())
  await page.goto(route)
  await expect(page.getByText("Could not load the full chapter list.")).toBeVisible()
  await expect(page.getByText("No chapters yet")).toHaveCount(0)
  await expect(page.getByRole("button", { name: "Mark book as read" })).toBeDisabled()
  fail = false
  await page.getByRole("button", { name: "Retry", exact: true }).click()
  await expect(page.getByRole("article")).toHaveCount(3)
})

test("chapter recap failure can be retried or dismissed without hiding chapters", async ({ page }) => {
  let fail = true
  await page.route("**/reader/book-1/summary-collection", (request) => fail ? request.fulfill({ status: 503, json: { detail: "Try later" } }) : request.fallback())
  await page.goto(route)
  await page.getByRole("button", { name: "Show chapter recaps" }).click()
  await expect(page.getByText(/Could not load chapter recaps/)).toBeVisible()
  await expect(page.getByRole("article")).toHaveCount(3)
  await page.getByRole("button", { name: "Hide chapter recaps" }).click()
  await expect(page.getByText(/Could not load chapter recaps/)).toHaveCount(0)
  await page.getByRole("button", { name: "Show chapter recaps" }).click()
  await expect(page.getByText(/Could not load chapter recaps/)).toBeVisible()
  fail = false
  await page.getByRole("button", { name: "Retry", exact: true }).click()
  await expect(page.getByText("Read chapter recap", { exact: true })).toHaveCount(2)
})

test("chapter read actions explain failures, prevent competing writes and retry", async ({ page }) => {
  let fail = true
  let read = false
  let resume: () => void = () => {}
  const gate = new Promise<void>((resolve) => { resume = resolve })
  await page.route("**/reader/book-1/chapters", (request) => request.fulfill({ json: { read_upto: 0, chapters: [
    { number: 1, title: "Ashfall", read, processed: true, intelligence_available: true },
    { number: 2, title: "The Ember Gate", read: false, processed: true, intelligence_available: true },
  ] } }))
  await page.route("**/reader/book-1/progress/chapter-status?**", async (request) => {
    if (fail) return request.fulfill({ status: 503, json: { detail: "Try later" } })
    await gate
    read = true
    return request.fulfill({ json: { ok: true } })
  })
  await page.goto(route)
  const first = page.getByRole("article", { name: "Ashfall", exact: true })
  const second = page.getByRole("article", { name: "The Ember Gate", exact: true })
  await first.getByRole("button", { name: "Mark read", exact: true }).click()
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Could not update chapter 1")
  fail = false
  await page.getByRole("main").getByRole("alert").getByRole("button", { name: "Retry" }).click()
  await expect(first.getByRole("button", { name: "Saving..." })).toBeDisabled()
  await expect(second.getByRole("button", { name: "Mark read", exact: true })).toBeDisabled()
  await expect(second.getByRole("button", { name: "Remove", exact: true })).toBeDisabled()
  await expect(page.getByRole("button", { name: "Mark book as read" })).toBeDisabled()
  resume()
  await expect(page.getByRole("status")).toHaveText("Chapter 1 marked as read.")
  await expect(first.getByRole("button", { name: "Mark unread", exact: true })).toBeEnabled()
})

test("mark book read failure and success are announced", async ({ page }) => {
  let fail = true
  await page.route("**/reader/book-1/progress/mark-book-read", (request) => request.fulfill(fail ? { status: 503, json: { detail: "Try later" } } : { json: { ok: true } }))
  await page.goto(route)
  await page.getByRole("button", { name: "Mark book as read" }).click()
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Could not mark the book as read")
  fail = false
  await page.getByRole("main").getByRole("alert").getByRole("button", { name: "Retry" }).click()
  await expect(page.getByRole("status")).toHaveText("Book marked as read.")
})

test("chapter loading and empty states remain operable on mobile", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  let resume: () => void = () => {}
  const gate = new Promise<void>((resolve) => { resume = resolve })
  await page.route("**/reader/book-1/chapters", async (request) => { await gate; await request.fulfill({ json: { read_upto: 0, chapters: [] } }) })
  await page.goto(route)
  await expect(page.getByRole("status", { name: "Loading chapter list" })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
  resume()
  await expect(page.getByRole("heading", { name: "No chapters yet" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Mark book as read" })).toBeDisabled()
  await expect(page.getByRole("link", { name: "Open book overview" })).toHaveAttribute("href", "/sky-of-ash--book-1")
  await expect(page.getByRole("button", { name: "Help", exact: true })).toBeVisible()
})

test("long chapter titles wrap and read-only collaborators have no removal action", async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(route)
  const book = await page.evaluate(async () => (await fetch("/api/v1/books/book-1")).json())
  await page.route("**/api/v1/books/book-1", (request) => request.fulfill({ json: { ...book, collaboration_role: "viewer", collaboration_permissions: { can_edit_manuscript: false } } }))
  const title = "The archive beneath the northern observatory where every unwritten letter waits for its reader"
  await page.route("**/reader/book-1/chapters", (request) => request.fulfill({ json: { read_upto: 0, chapters: [{ number: 1, title, read: false, processed: false }] } }))
  await page.reload()
  await expect(page.getByRole("heading", { name: title })).toBeVisible()
  await expect(page.getByRole("button", { name: "Remove", exact: true })).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
  const heading = page.getByRole("heading", { name: title })
  expect(await heading.evaluate((el) => el.scrollHeight <= el.clientHeight)).toBe(true)
  await page.screenshot({ path: info.outputPath("chapters-long-title-390.png"), fullPage: true })
})

test("chapter removal failure preserves the row and requires confirmation again", async ({ page }) => {
  let fail = true
  await page.route("**/api/v1/books/book-1/chapters/2", (request) => fail ? request.fulfill({ status: 503, json: { detail: "Try later" } }) : request.fallback())
  await page.goto(route)
  const row = page.getByRole("article", { name: "The Ember Gate", exact: true })
  await row.getByRole("button", { name: "Remove", exact: true }).click()
  await page.getByRole("dialog").getByRole("button", { name: "Remove chapter", exact: true }).click()
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Could not remove chapter 2")
  await expect(row).toBeVisible()
  fail = false
  await page.getByRole("main").getByRole("alert").getByRole("button", { name: "Retry" }).click()
  await expect(page.getByRole("dialog", { name: "Remove Chapter 2?" })).toBeVisible()
  await page.getByRole("dialog").getByRole("button", { name: "Remove chapter", exact: true }).click()
  await expect(row).toHaveCount(0)
  await expect(page.getByRole("status")).toHaveText("Chapter 2 removed.")
})

test("a failed refresh keeps chapter rows available and Help restores keyboard focus", async ({ page }) => {
  let fail = false
  await page.route("**/reader/book-1/chapters", (request) => fail ? request.fulfill({ status: 503, json: { detail: "Try later" } }) : request.fallback())
  await page.route("**/reader/book-1/progress/mark-book-read", (request) => request.fulfill({ json: { ok: true } }))
  await page.goto(route)
  await expect(page.getByRole("article")).toHaveCount(3)
  fail = true
  await page.getByRole("button", { name: "Mark book as read" }).click()
  await expect(page.getByText(/Could not refresh the chapter list/)).toBeVisible()
  await expect(page.getByRole("article")).toHaveCount(3)
  fail = false
  await page.getByRole("button", { name: "Retry", exact: true }).click()
  await expect(page.getByText(/Could not refresh the chapter list/)).toHaveCount(0)
  const help = page.getByRole("button", { name: "Help", exact: true })
  await help.focus()
  await page.keyboard.press("Enter")
  await expect(page.getByRole("dialog")).toBeVisible()
  await page.keyboard.press("Escape")
  await expect(help).toBeFocused()
})
