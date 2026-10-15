import { expect, test } from "@playwright/test"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"

const quote = { id: "q1", book_id: "book-1", book_title: "Sky of Ash", chapter_number: 2, chapter_title: "The Ember Gate", character_name: "Mara", quote_text: "The gate remembers every oath.", note: "An echo in the final crossing.", created_at: "2026-09-20T10:00:00Z" }
test.beforeEach(async ({ page }) => {
  await installMockApi(page)
  await page.addInitScript(() => { if (!localStorage.getItem("lorevia-preferences")) localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 })); document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax" })
})

test("quotes remain readable at four widths and both themes with keyboard Help", async ({ page }, info) => {
  const errors: string[] = []; page.on("pageerror", (error) => errors.push(error.message))
  await page.goto("/quotes")
  await expect(page.locator("blockquote")).toContainText("The gate remembers every oath.")
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    if (width < 1024) await expect.poll(() => page.locator("aside").evaluate((element) => element.getBoundingClientRect().right)).toBeLessThanOrEqual(0)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
    await page.screenshot({ path: info.outputPath(`quotes-${width}.png`), fullPage: true, animations: "disabled" })
  }
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.getByRole("button", { name: "Help", exact: true }).focus(); await page.keyboard.press("Enter")
  await expect(page.getByRole("dialog")).toBeVisible(); await page.keyboard.press("Escape")
  await expect(page.getByRole("button", { name: "Help", exact: true })).toBeFocused()
  await page.getByRole("button", { name: "Toggle theme", exact: true }).click()
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.screenshot({ path: info.outputPath("quotes-light-mobile.png"), fullPage: true })
  expect(errors).toEqual([])
})

test("full passages and attached notes expand and clipboard failures keep text available", async ({ page, context }, info) => {
  const body = `${"An original synthetic passage. ".repeat(25)}The last line.`
  const note = `${"Revision context. ".repeat(20)}Final note.`
  await page.route("**/api/v1/books/quotes/page?*", (request) => request.fulfill({ json: { items: [{ ...quote, quote_text: body, note }], next_cursor: null, has_more: false } }))
  await page.goto("/quotes")
  await expect(page.locator("blockquote")).not.toContainText("The last line.")
  await page.getByRole("button", { name: "Read full quote and note" }).focus(); await page.keyboard.press("Enter")
  await expect(page.locator("blockquote")).toHaveText(body)
  await expect(page.getByText(/Final note\.$/)).toBeVisible()
  await context.grantPermissions(["clipboard-read", "clipboard-write"])
  await page.getByRole("button", { name: "Copy quote", exact: true }).click()
  await expect(page.getByText("Copied the complete quote text.")).toBeVisible()
  expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(body)
  await page.getByRole("button", { name: "Show less" }).click()
  await page.evaluate(() => Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: async () => { throw new Error("denied") } } }))
  await page.getByRole("button", { name: "Copy quote", exact: true }).click()
  await expect(page.getByText(/Could not copy/)).toBeVisible()
  await expect(page.locator("blockquote")).toHaveText(body)
  await page.setViewportSize({ width: 390, height: 1000 })
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }))
  await page.screenshot({ path: info.outputPath("quote-expanded-mobile.png"), fullPage: true })
})

test("book and text filters preserve separate books with identical titles and clear no results", async ({ page }) => {
  await page.route("**/api/v1/books/quotes/page?*", (request) => request.fulfill({ json: { items: [quote, { ...quote, id: "q2", book_id: "book-2", character_name: "Other character", quote_text: "Elsewhere", note: "Different note" }], next_cursor: null, has_more: false } }))
  await page.goto("/quotes")
  await expect(page.getByText("2 saved quotes across 2 books")).toBeVisible()
  await page.getByLabel("Book", { exact: true }).selectOption("book-2")
  await expect(page.locator("blockquote")).toHaveText("Elsewhere")
  await page.getByRole("searchbox", { name: "Search quotes" }).fill("Mara")
  await expect(page.getByRole("heading", { name: "No quotes match that search" })).toBeVisible()
  await page.getByRole("button", { name: "Show all quotes" }).click()
  for (const term of ["Mara", "echo", "every oath"]) {
    await page.getByRole("searchbox", { name: "Search quotes" }).fill(term)
    await expect(page.locator("blockquote")).toHaveText(quote.quote_text)
  }
  await expect(page.getByRole("link", { name: "Open chapter 2", exact: true })).toHaveAttribute("href", "/book-1/chapter/2")
  await page.getByRole("button", { name: "Clear filters" }).click()
  await expect(page.locator("blockquote")).toHaveCount(2)
})

test("initial and refresh failures preserve quote context and recover explicitly", async ({ page }) => {
  let fail = true
  await page.route("**/api/v1/books/quotes/page?*", (request) => fail ? request.fulfill({ status: 503, json: {} }) : request.fallback())
  await page.goto("/quotes"); await page.getByRole("button", { name: "Retry quotes", exact: true }).waitFor()
  await expect(page.getByRole("heading", { name: "No quotes saved yet" })).toHaveCount(0)
  fail = false; await page.getByRole("button", { name: "Retry quotes", exact: true }).click()
  await expect(page.locator("blockquote")).toContainText("The gate remembers")
  await page.getByRole("searchbox", { name: "Search quotes" }).fill("oath")
  fail = true; await page.getByRole("button", { name: "Refresh quotes", exact: true }).click()
  await expect(page.getByText("Quotes could not be refreshed. Previously loaded passages are still shown.")).toBeVisible()
  await expect(page.locator("blockquote")).toContainText("The gate remembers")
  await expect(page.getByRole("searchbox", { name: "Search quotes" })).toHaveValue("oath")
  fail = false; await page.getByRole("button", { name: "Retry quotes", exact: true }).click()
  await expect(page.getByText("Quotes could not be refreshed. Previously loaded passages are still shown.")).toHaveCount(0)
})

test("all quote pages remain searchable and Show more reveals later rows", async ({ page }) => {
  await page.route("**/api/v1/books/quotes/page?*", (request) => request.fulfill({ json: new URL(request.request().url()).searchParams.has("cursor") ? { items: [{ ...quote, id: "last", quote_text: "Final page passage" }], next_cursor: null, has_more: false } : { items: Array.from({ length: 30 }, (_, i) => ({ ...quote, id: `q-${i}` })), next_cursor: "second", has_more: true } }))
  await page.goto("/quotes")
  await expect(page.getByText("31 saved quotes across 1 book")).toBeVisible()
  await expect(page.getByText("Final page passage", { exact: true })).toHaveCount(0)
  await page.getByRole("button", { name: "Show 6 more quotes" }).click()
  await expect(page.getByText("Final page passage", { exact: true })).toBeVisible()
  await page.getByRole("searchbox", { name: "Search quotes" }).fill("Final page passage")
  await expect(page.locator("blockquote")).toHaveText("Final page passage")
})

test("looping pagination exposes failure rather than a misleading partial collection", async ({ page }) => {
  let fail = true
  await page.route("**/api/v1/books/quotes/page?*", (request) => fail ? request.fulfill({ json: { items: [quote], next_cursor: "loop", has_more: true } }) : request.fallback())
  await page.goto("/quotes"); await page.getByRole("button", { name: "Retry quotes", exact: true }).waitFor()
  await expect(page.locator("blockquote")).toHaveCount(0)
  fail = false; await page.getByRole("button", { name: "Retry quotes", exact: true }).click()
  await expect(page.locator("blockquote")).toContainText("The gate remembers")
})

test("loading, empty, and restricted collections have distinct next actions", async ({ page }) => {
  let release: (() => void) | undefined
  const waiting = new Promise<void>((resolve) => { release = resolve })
  await page.route("**/api/v1/books/quotes/page?*", async (request) => { await waiting; await request.fulfill({ json: { items: [], next_cursor: null, has_more: false } }) })
  await page.goto("/quotes")
  await expect(page.getByText("Loading saved quotes…", { exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "Refreshing…", exact: true })).toBeDisabled()
  release?.()
  await expect(page.getByRole("link", { name: "Choose a book" })).toHaveAttribute("href", "/library")
  await installMockApi(page, { userTier: "free" }); await page.reload()
  await expect(page.getByRole("heading", { name: "Saved quotes require an active trial or paid plan." })).toBeVisible()
  await expect(page.getByRole("link", { name: "View plans", exact: true })).toHaveAttribute("href", "/pricing")
})

test("long and missing metadata wrap without inventing chapter sources", async ({ page }, info) => {
  await page.route("**/api/v1/books/quotes/page?*", (request) => request.fulfill({ json: { items: [{ ...quote, book_title: "UnbrokenTitle".repeat(22), chapter_number: -2, character_name: "LongCharacter".repeat(20), created_at: "bad", quote_text: "", note: null }], next_cursor: null, has_more: false } }))
  await page.setViewportSize({ width: 390, height: 1000 }); await page.goto("/quotes")
  await expect(page.getByText("Save date unavailable")).toBeVisible()
  await expect(page.getByText("No passage text is available for this saved quote.")).toBeVisible()
  await expect(page.getByRole("button", { name: "Copy quote" })).toHaveCount(0)
  await expect(page.getByRole("link", { name: "Open book", exact: true })).toHaveAttribute("href", "/book-1")
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.screenshot({ path: info.outputPath("quotes-long-mobile.png"), fullPage: true })
})
