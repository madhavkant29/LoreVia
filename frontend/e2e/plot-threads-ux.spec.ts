import { expect, test } from "@playwright/test"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"

const route = "/sky-of-ash--book-1/plot-threads"
const listApi = "**/api/v1/reader/book-1/plot-threads/page?**"
const detailApi = "**/api/v1/reader/book-1/plot-threads/thread-gate"
const summary = { id: "thread-gate", title: "Who opened the gate?", type: "mystery", status: "developing", description: "A missing key points to an accomplice.", introduced_at: 1, first_mentioned: 1, last_mentioned: 2, resolved_at: null, mention_count: 3, importance: 1, tags: ["key"] }
const detail = { ...summary, note: "Keep the clue alive.", character_ids: [], related_characters: ["Nora Vale"], risk: "The question needs a payoff.", suggested_action: "Return to the gate." }

test.beforeEach(async ({ page }) => {
  await installMockApi(page)
  await page.addInitScript(() => {
    if (!localStorage.getItem("lorevia-preferences")) localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 }))
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
})

test("thread queues and details are readable at four widths and both themes", async ({ page }, testInfo) => {
  const errors: string[] = []
  page.on("pageerror", (error) => errors.push(error.message))
  page.on("console", (message) => { if (message.type() === "error" && /hydration|did not match/.test(message.text())) errors.push(message.text()) })
  await page.goto(route)
  await expect(page.getByRole("tab", { name: "Open 2" })).toBeVisible()
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
    await page.screenshot({ path: testInfo.outputPath(`threads-${width}.png`), fullPage: true })
  }
  for (const theme of ["dark", "light"]) {
    await page.evaluate((value) => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: value }, version: 0 })), theme)
    await page.reload()
    await page.getByRole("tab", { name: "Needs attention 1" }).click()
    await page.getByRole("button", { name: /The vanished map clue/ }).click()
    await expect(page.getByRole("textbox", { name: "Private note", exact: true })).toHaveValue("Restore near the archive scene.")
    await page.getByRole("textbox", { name: "Private note", exact: true }).fill("An unsaved revision reminder.")
    expect(await criticalAccessibilityViolations(page)).toEqual([])
    await page.screenshot({ path: testInfo.outputPath(`threads-details-${theme}.png`), fullPage: true })
    await page.getByRole("button", { name: "Discard changes", exact: true }).click()
  }
  expect(errors).toEqual([])
})

test("keyboard groups, search, chapter sources, and Help are operable", async ({ page }) => {
  await page.goto(route)
  await page.getByRole("tab", { name: "Open 2" }).focus()
  await page.keyboard.press("ArrowRight")
  await expect(page.getByRole("tab", { name: "Needs attention 1" })).toBeFocused()
  await page.getByRole("searchbox", { name: "Find a thread" }).fill("missing")
  await expect(page.getByText(/No threads match this search/)).toBeVisible()
  await page.getByRole("button", { name: "Clear search" }).click()
  await page.getByRole("button", { name: /The vanished map clue/ }).click()
  await expect(page.getByRole("link", { name: "Chapter 1", exact: true })).toHaveAttribute("href", "/sky-of-ash--book-1/chapter/1")
  await page.getByRole("button", { name: "Help", exact: true }).click()
  await expect(page.getByRole("dialog")).toBeVisible()
  await page.keyboard.press("Escape")
  await expect(page.getByRole("button", { name: "Help", exact: true })).toBeFocused()
})

test("list and detail failures expose retries and retain cached threads", async ({ page }) => {
  let fail = true
  await page.route(listApi, (request) => fail ? request.fulfill({ status: 503, json: {} }) : request.fallback())
  await page.goto(route)
  await page.getByRole("button", { name: "Retry plot threads" }).waitFor()
  await expect(page.getByRole("heading", { name: "No plot threads yet" })).toHaveCount(0)
  fail = false
  await page.getByRole("button", { name: "Retry plot threads" }).click()
  await expect(page.getByRole("button", { name: /Who opened the gate/ })).toBeVisible()
  fail = true
  await page.getByRole("button", { name: "Refresh threads", exact: true }).click()
  await expect(page.getByText(/Refresh failed. Previously loaded threads/)).toBeVisible()
  let detailFails = true
  await page.route(detailApi, (request) => detailFails ? request.fulfill({ status: 503, json: {} }) : request.fallback())
  await page.getByRole("button", { name: /Who opened the gate/ }).click()
  await expect(page.getByRole("button", { name: "Retry thread details" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Save changes", exact: true })).toHaveCount(0)
  detailFails = false
  await page.getByRole("button", { name: "Retry thread details" }).click()
  await expect(page.getByRole("textbox", { name: "Private note", exact: true })).toBeVisible()
})

test("failed saves preserve drafts, guard navigation, and move saved statuses between groups", async ({ page }) => {
  let current = { ...detail }
  let fail = true
  let writes = 0
  await page.route(listApi, (request) => request.fulfill({ json: { items: [current], has_more: false, next_cursor: null } }))
  await page.route(detailApi, async (request) => {
    if (request.request().method() === "PUT") {
      writes++
      if (fail) return request.fulfill({ status: 503, json: {} })
      current = { ...current, ...request.request().postDataJSON() }
    }
    return request.fulfill({ json: current })
  })
  await page.goto(route)
  await page.getByRole("button", { name: /Who opened the gate/ }).click()
  await page.getByRole("textbox", { name: "Private note", exact: true }).fill("Return the key in the finale.")
  await page.getByRole("combobox", { name: "Status", exact: true }).selectOption("resolved")
  await page.getByRole("button", { name: "Save changes", exact: true }).click()
  await expect(page.getByRole("alert").filter({ hasText: "Changes could not be saved" })).toBeVisible()
  page.once("dialog", (dialog) => dialog.dismiss())
  await page.getByRole("button", { name: "Close", exact: true }).click()
  await expect(page.getByRole("textbox", { name: "Private note", exact: true })).toHaveValue("Return the key in the finale.")
  page.once("dialog", (dialog) => dialog.dismiss())
  await page.getByRole("tab", { name: "Needs attention 0" }).click()
  await expect(page.getByRole("tab", { name: "Open 1" })).toHaveAttribute("aria-selected", "true")
  fail = false
  await page.getByRole("button", { name: "Save changes", exact: true }).click()
  await expect(page.getByText("Thread changes saved.", { exact: true })).toBeVisible()
  await expect(page.getByRole("tab", { name: "Resolved 1" })).toHaveAttribute("aria-selected", "true")
  await expect(page.getByRole("button", { name: "Save changes", exact: true })).toBeDisabled()
  expect(writes).toBe(2)
  await page.reload()
  await page.getByRole("tab", { name: "Resolved 1" }).click()
  await page.getByRole("button", { name: /Who opened the gate/ }).click()
  await expect(page.getByRole("textbox", { name: "Private note", exact: true })).toHaveValue("Return the key in the finale.")
})

test("copying to Notes handles failures and avoids duplicate copies", async ({ page }) => {
  let fail = true
  let writes = 0
  await page.route("**/books/book-1/notes/vault**", (request) => {
    if (["PUT", "POST"].includes(request.request().method())) writes++
    return fail ? request.fulfill({ status: 503, json: {} }) : request.fallback()
  })
  await page.goto(route)
  await page.getByRole("button", { name: /Who opened the gate/ }).click()
  await page.getByRole("textbox", { name: "Private note", exact: true }).fill("Copy this working reminder.")
  await page.getByRole("button", { name: "Save to notes", exact: true }).click()
  await expect(page.getByText(/The copy could not be saved/)).toBeVisible()
  fail = false
  await page.getByRole("button", { name: "Save to notes", exact: true }).click()
  await expect(page.getByRole("button", { name: "Copied to Notes", exact: true })).toBeDisabled()
  await expect(page.getByText("Unsaved changes", { exact: true })).toBeVisible()
  expect(writes).toBe(2) // One failed write and one successful retry.
})

test("all cursor pages and rows beyond the initial slice remain reachable", async ({ page }) => {
  const requests: string[] = []
  await page.route(listApi, (request) => {
    const cursor = new URL(request.request().url()).searchParams.get("cursor")
    requests.push(cursor ?? "first")
    return request.fulfill({ json: { items: cursor ? [{ ...summary, id: "last", title: "Final thread" }] : Array.from({ length: 31 }, (_, index) => ({ ...summary, id: `thread-${index}`, title: `Oath ${index}` })), has_more: !cursor, next_cursor: cursor ? null : "next" } })
  })
  await page.goto(route)
  await expect(page.getByRole("tab", { name: "Open 32" })).toBeVisible()
  await expect(page.getByRole("button", { name: /Final thread/ })).toHaveCount(0)
  await page.getByRole("button", { name: "Show more threads" }).click()
  await expect(page.getByRole("button", { name: /Final thread/ })).toBeVisible()
  await page.getByRole("searchbox", { name: "Find a thread" }).fill("Final")
  await expect(page.getByText("1 match in this group", { exact: true })).toBeVisible()
  expect(requests).toEqual(["first", "next"])
})

test("empty and unavailable manuscripts have distinct recovery states", async ({ page }) => {
  let empty = true
  await page.route(listApi, (request) => request.fulfill(empty ? { json: { items: [], has_more: false, next_cursor: null } } : { status: 403, json: {} }))
  await page.goto(route)
  await expect(page.getByRole("heading", { name: "No plot threads yet" })).toBeVisible()
  await expect(page.getByRole("link", { name: "View chapters" })).toHaveAttribute("href", "/sky-of-ash--book-1/chapters")
  empty = false
  await page.reload()
  await expect(page.getByText(/requires the manuscript owner's author access/)).toBeVisible()
  await expect(page.getByRole("heading", { name: "No plot threads yet" })).toHaveCount(0)
})

test("long content and missing evidence wrap without inventing sources", async ({ page }, testInfo) => {
  const long = { ...detail, title: "Unbroken".repeat(30), description: "The question remains. ".repeat(25), introduced_at: null, first_mentioned: null, last_mentioned: null, related_characters: [], note: null, risk: null }
  await page.route(listApi, (request) => request.fulfill({ json: { items: [long], has_more: false, next_cursor: null } }))
  await page.route(detailApi, (request) => request.fulfill({ json: long }))
  await page.setViewportSize({ width: 390, height: 1000 })
  await page.goto(route)
  await page.getByRole("button", { name: /Unbroken/ }).click()
  await expect(page.getByText("No source chapter is recorded.", { exact: true })).toBeVisible()
  await expect(page.getByRole("link", { name: /^Chapter / })).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.screenshot({ path: testInfo.outputPath("threads-long-mobile.png"), fullPage: true })
})

test("chapter references recover after failure and do not link unavailable chapters", async ({ page }, testInfo) => {
  let fail = true
  await page.route("**/api/v1/reader/book-1/chapters", (request) => request.fulfill(fail ? { status: 503, json: {} } : { json: { chapters: [{ number: 1, title: "The gate", read: true, processed: true, intelligence_available: true }], read_upto: 1 } }))
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto(route)
  await page.getByRole("tab", { name: "Needs attention 1" }).click()
  await page.getByRole("button", { name: /The vanished map clue/ }).click()
  await page.getByRole("button", { name: "Retry chapter links" }).waitFor()
  await expect(page.getByRole("link", { name: /^Chapter / })).toHaveCount(0)
  fail = false
  await page.getByRole("button", { name: "Retry chapter links" }).click()
  await expect(page.getByRole("link", { name: "Chapter 1", exact: true })).toBeVisible()
  await expect(page.getByText("Chapter 2 (unavailable)", { exact: true })).toBeVisible()
  await page.getByRole("textbox", { name: "Private note", exact: true }).fill("Revisit this scene.")
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.screenshot({ path: testInfo.outputPath("threads-final-desktop.png"), fullPage: true })
  await page.setViewportSize({ width: 390, height: 1000 })
  await page.screenshot({ path: testInfo.outputPath("threads-final-mobile.png"), fullPage: true })
  await page.getByRole("button", { name: "Discard changes", exact: true }).click()
})
