import { expect, test } from "@playwright/test"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"

const route = "/sky-of-ash--book-1/foreshadowing"
const api = "**/api/v1/reader/book-1/foreshadowing"
const clue = { chapter_number: 1, chapter_title: "The gate", clue: "A warm brass key", foreshadows: "The gate was opened earlier." }
test.beforeEach(async ({ page }) => {
  await installMockApi(page)
  await page.addInitScript(() => {
    if (!localStorage.getItem("lorevia-preferences")) localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 }))
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
})

test("setup ledger is readable at four widths and both themes", async ({ page }, testInfo) => {
  const errors: string[] = []
  page.on("pageerror", (error) => errors.push(error.message))
  await page.goto(route)
  await expect(page.getByRole("tab", { name: "All setups 3" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Chapter 1", exact: true })).toBeVisible()
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
    await page.screenshot({ path: testInfo.outputPath(`setups-${width}.png`), fullPage: true })
  }
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.evaluate(() => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "light" }, version: 0 })))
  await page.reload()
  await expect(page.getByRole("link", { name: "Chapter 1", exact: true })).toBeVisible()
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.screenshot({ path: testInfo.outputPath("setups-light-mobile.png"), fullPage: true })
  expect(errors).toEqual([])
})

test("keyboard views and combined search/chapter filters recover to the complete ledger", async ({ page }) => {
  await page.goto(route)
  await page.getByRole("tab", { name: "All setups 3" }).focus()
  await page.keyboard.press("End")
  await expect(page.getByRole("tab", { name: "Unlinked 1" })).toBeFocused()
  await expect(page.getByText("A silver bell rings beneath the river.", { exact: true })).toBeVisible()
  await page.getByRole("combobox", { name: "Source chapter", exact: true }).selectOption("1")
  await expect(page.getByText(/No signals match these filters/)).toBeVisible()
  await page.getByRole("button", { name: "Clear filters" }).click()
  await page.getByRole("searchbox", { name: "Find a setup" }).fill(" FAMILY ")
  await expect(page.getByText("1 signal matching the current filters", { exact: true })).toBeVisible()
  await expect(page.getByText("Her family is connected to the hidden heir claim.")).toBeVisible()
  await page.getByRole("button", { name: "Clear filters" }).click()
  await expect(page.getByText("3 signals in available chapters", { exact: true })).toBeVisible()
  await page.getByRole("button", { name: "Help", exact: true }).click()
  await expect(page.getByRole("dialog")).toBeVisible()
  await page.keyboard.press("Escape")
  await expect(page.getByRole("button", { name: "Help", exact: true })).toBeFocused()
})

test("initial and refresh failures expose retries without false empty results", async ({ page }) => {
  let fail = true
  await page.route(api, (request) => fail ? request.fulfill({ status: 503, json: {} }) : request.fallback())
  await page.goto(route)
  await page.getByRole("button", { name: "Retry signals" }).waitFor()
  await expect(page.getByRole("heading", { name: "No setup signals yet" })).toHaveCount(0)
  fail = false
  await page.getByRole("button", { name: "Retry signals" }).click()
  await expect(page.getByRole("tab", { name: "All setups 3" })).toBeVisible()
  fail = true
  await page.getByRole("button", { name: "Refresh signals", exact: true }).click()
  await expect(page.getByText(/Previously loaded evidence remains visible/)).toBeVisible()
  await expect(page.getByText("The gate key is warm before the alarm sounds.", { exact: true })).toBeVisible()
  fail = false
  await page.getByRole("button", { name: "Retry signals" }).click()
  await expect(page.getByRole("button", { name: "Retry signals" })).toHaveCount(0)
})

test("source chapter checks recover and unavailable chapters stay unlinked", async ({ page }) => {
  let fail = true
  await page.route("**/api/v1/reader/book-1/chapters", (request) => request.fulfill(fail ? { status: 503, json: {} } : { json: { chapters: [{ number: 1, title: "Available chapter" }], read_upto: 1 } }))
  await page.goto(route)
  await page.getByRole("button", { name: "Retry chapter links" }).waitFor()
  await expect(page.getByRole("link", { name: /^Chapter / })).toHaveCount(0)
  fail = false
  await page.getByRole("button", { name: "Retry chapter links" }).click()
  await expect(page.getByRole("link", { name: "Chapter 1", exact: true })).toHaveAttribute("href", "/sky-of-ash--book-1/chapter/1")
  await expect(page.getByRole("link", { name: "Chapter 2", exact: true })).toHaveCount(0)
  await expect(page.getByText("Chapter unavailable", { exact: true })).toHaveCount(2)
})

test("loading, empty, and denied states remain distinct", async ({ page }) => {
  let release: (() => void) | undefined
  const wait = new Promise<void>((resolve) => { release = resolve })
  await page.route(api, async (request) => { await wait; await request.fulfill({ json: { items: [] } }) })
  await page.goto(route)
  await expect(page.getByText("Loading setup and payoff signals…", { exact: true })).toBeVisible()
  release?.()
  await expect(page.getByRole("heading", { name: "No setup signals yet" })).toBeVisible()
  await expect(page.getByRole("link", { name: "View chapters" })).toHaveAttribute("href", "/sky-of-ash--book-1/chapters")
  await page.route(api, (request) => request.fulfill({ status: 403, json: {} }))
  await page.reload()
  await expect(page.getByRole("button", { name: "Retry signals" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "No setup signals yet" })).toHaveCount(0)
})

test("large ledgers expose all rows and search beyond the initial slice", async ({ page }) => {
  await page.route(api, (request) => request.fulfill({ json: { items: Array.from({ length: 45 }, (_, index) => ({ ...clue, chapter_number: index + 1, clue: `Setup ${index + 1}` })) } }))
  await page.goto(route)
  await expect(page.getByText("45 signals in available chapters · showing 40", { exact: true })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Setup 45", exact: true })).toHaveCount(0)
  await page.getByRole("button", { name: "Show more signals" }).click()
  await expect(page.getByRole("heading", { name: "Setup 45", exact: true })).toBeVisible()
  await page.getByRole("searchbox", { name: "Find a setup" }).fill("Setup 45")
  await expect(page.getByText("1 signal matching the current filters", { exact: true })).toBeVisible()
})

test("long and sparse clues wrap without claiming resolved outcomes", async ({ page }, testInfo) => {
  await page.route(api, (request) => request.fulfill({ json: { items: [{ ...clue, chapter_title: "Unbroken".repeat(30), clue: "The clue unfolds. ".repeat(40), foreshadows: "   " }, { chapter_number: 0, chapter_title: null, clue: null, foreshadows: null }] } }))
  await page.setViewportSize({ width: 390, height: 1000 })
  await page.goto(route)
  await expect(page.getByRole("tab", { name: "Unlinked 2" })).toBeVisible()
  await expect(page.getByText("Chapter not located", { exact: true })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Setup text unavailable" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Chapter 0", exact: true })).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.screenshot({ path: testInfo.outputPath("setups-long-mobile.png"), fullPage: true })
})
