import { expect, test } from "@playwright/test"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"

const route = "/sky-of-ash--book-1/search"
const api = "**/api/v1/reader/book-1/search?*"
const themeApi = "**/api/v1/reader/book-1/thematic-search?*"
const passage = { chapter_num: 2, chapter_title: "The Ember Gate", relevance: 0.91, summary: "The warning returns.", text: "The gatekeeper repeats the warning." }
test.beforeEach(async ({ page }) => {
  await installMockApi(page)
  await page.addInitScript(() => {
    if (!localStorage.getItem("lorevia-preferences")) localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 }))
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
})

test("search evidence is readable at four widths and both themes", async ({ page }, testInfo) => {
  const errors: string[] = []
  page.on("pageerror", (error) => errors.push(error.message))
  await page.goto(route)
  await page.getByRole("searchbox", { name: "Search manuscript" }).fill("gatekeeper warning")
  await page.getByRole("button", { name: "Search manuscript", exact: true }).click()
  await expect(page.getByRole("link", { name: "Open chapter 2" })).toBeVisible()
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
    await page.screenshot({ path: testInfo.outputPath(`search-${width}.png`), fullPage: true })
  }
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.getByRole("tab", { name: "Themes", exact: true }).click()
  await page.getByRole("button", { name: "Search manuscript", exact: true }).click()
  await expect(page.getByText("The ash road returns as a warning about inherited obligation.")).toBeVisible()
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.screenshot({ path: testInfo.outputPath("search-themes-dark.png"), fullPage: true })
  await page.evaluate(() => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "light" }, version: 0 })))
  await page.reload()
  await page.getByRole("searchbox", { name: "Search manuscript" }).fill("gate")
  await page.getByRole("button", { name: "Search manuscript", exact: true }).click()
  await expect(page.getByRole("link", { name: "Open chapter 2" })).toBeVisible()
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.screenshot({ path: testInfo.outputPath("search-light.png"), fullPage: true })
  expect(errors).toEqual([])
})

test("keyboard tabs preserve independent results and never trigger searches", async ({ page }) => {
  let requests = 0
  await page.route(api, (request) => { requests++; return request.fallback() })
  await page.route(themeApi, (request) => { requests++; return request.fallback() })
  await page.goto(`${route}?q=gate`)
  await expect(page.getByRole("heading", { name: "Results for “gate”" })).toBeVisible()
  expect(requests).toBe(1)
  await page.getByRole("tab", { name: "Passages", exact: true }).focus()
  await page.keyboard.press("End")
  await expect(page.getByRole("tab", { name: "Themes", exact: true })).toBeFocused()
  await expect(page.getByRole("heading", { name: "Trace an idea through the story" })).toBeVisible()
  expect(requests).toBe(1)
  await page.getByRole("searchbox", { name: "Search manuscript" }).fill("obligation")
  await page.getByRole("button", { name: "Search manuscript", exact: true }).click()
  await expect(page.getByRole("heading", { name: "Results for “obligation”" })).toBeVisible()
  await page.getByRole("tab", { name: "Passages", exact: true }).click()
  await expect(page.getByRole("heading", { name: "Results for “gate”" })).toBeVisible()
  await expect(page.getByRole("searchbox", { name: "Search manuscript" })).toHaveValue("obligation")
  expect(requests).toBe(2)
  await page.getByRole("button", { name: "Help", exact: true }).click()
  await expect(page.getByRole("dialog")).toBeVisible()
  await page.keyboard.press("Escape")
  await expect(page.getByRole("button", { name: "Help", exact: true })).toBeFocused()
})

test("failed searches retain earlier evidence and retry the failed query", async ({ page }) => {
  let fail = false
  const queries: string[] = []
  await page.route(api, (request) => { queries.push(new URL(request.request().url()).searchParams.get("q") ?? ""); return fail ? request.fulfill({ status: 503, json: {} }) : request.fallback() })
  await page.goto(`${route}?q=gate`)
  await expect(page.getByRole("link", { name: "Open chapter 2" })).toBeVisible()
  fail = true
  await page.getByRole("searchbox", { name: "Search manuscript" }).fill("missing scene")
  await page.getByRole("button", { name: "Search manuscript", exact: true }).click()
  await expect(page.getByText("Search failed. Please try again.", { exact: true })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Results for “gate”" })).toBeVisible()
  await page.getByRole("searchbox", { name: "Search manuscript" }).fill("unsent edit")
  fail = false
  await page.getByRole("button", { name: "Retry search" }).click()
  await expect(page.getByRole("heading", { name: "Results for “missing scene”" })).toBeVisible()
  await expect(page.getByRole("searchbox", { name: "Search manuscript" })).toHaveValue("unsent edit")
  expect(queries).toEqual(["gate", "missing scene", "missing scene"])
})

test("chapter links seed an explicit upper bound and malformed bounds prevent submission", async ({ page }) => {
  const scopes: Array<string | null> = []
  await page.route(api, (request) => { scopes.push(new URL(request.request().url()).searchParams.get("chapter")); return request.fulfill({ json: [passage, { ...passage, chapter_num: 99, text: "Out of scope evidence" }] }) })
  await page.goto(`${route}?q=gate&chapter=2`)
  await expect(page.getByText("Passages · chapters 1–2", { exact: true })).toBeVisible()
  expect(scopes).toEqual(["2"])
  await expect(page.getByText("Out of scope evidence", { exact: true })).toHaveCount(0)
  await page.getByLabel("Search through chapter", { exact: true }).fill("-1")
  await expect(page.getByRole("button", { name: "Search manuscript", exact: true })).toBeDisabled()
  await expect(page.getByText(/Enter a whole chapter number/)).toBeVisible()
  await page.getByLabel("Search through chapter", { exact: true }).fill("")
  await page.getByRole("button", { name: "Search manuscript", exact: true }).click()
  await expect(page.getByText("Passages · full book scope", { exact: true })).toBeVisible()
  expect(scopes).toEqual(["2", null])
})

test("pending requests remain labelled when switching modes and cannot duplicate", async ({ page }) => {
  let release: (() => void) | undefined
  const wait = new Promise<void>((resolve) => { release = resolve })
  let requests = 0
  await page.route(api, async (request) => { requests++; await wait; await request.fulfill({ json: [passage] }) })
  await page.goto(`${route}?q=gate`)
  await expect(page.getByText("Searching passages for “gate”…", { exact: true })).toBeVisible()
  await page.getByRole("tab", { name: "Themes", exact: true }).click()
  await expect(page.getByRole("button", { name: "Searching…", exact: true })).toBeDisabled()
  release?.()
  await expect(page.getByRole("heading", { name: "Trace an idea through the story" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Results for “gate”" })).toHaveCount(0)
  await page.getByRole("tab", { name: "Passages", exact: true }).click()
  await expect(page.getByText("The warning returns.", { exact: true })).toBeVisible()
  expect(requests).toBe(1)
})

test("building index, empty, access, and rate-limit states stay distinct", async ({ page }) => {
  await page.goto(route)
  await page.getByRole("tab", { name: "Themes", exact: true }).click()
  await page.route(themeApi, (request) => request.fulfill({ json: { results: [], index_status: "building" } }))
  await page.getByRole("searchbox", { name: "Search manuscript" }).fill("obligation")
  await page.getByRole("button", { name: "Search manuscript", exact: true }).click()
  await expect(page.getByText(/The theme index is still building/)).toBeVisible()
  await expect(page.getByText(/No matching themes returned/)).toBeVisible()
  await page.route(themeApi, (request) => request.fulfill({ status: 403, json: {} }))
  await page.getByRole("button", { name: "Search manuscript", exact: true }).click()
  await expect(page.getByText(/Check your access or choose another scope/)).toBeVisible()
  await page.route(themeApi, (request) => request.fulfill({ status: 429, json: { detail: "Too many requests" } }))
  await page.getByRole("button", { name: "Retry search" }).click()
  await expect(page.getByText(/temporarily rate limited/)).toBeVisible()
})

test("manuscript and source failures recover without losing input or evidence", async ({ page }) => {
  let bookFail = true
  let chapterFail = true
  await page.route("**/api/v1/books/book-1", (request) => bookFail ? request.fulfill({ status: 503, json: {} }) : request.fallback())
  await page.route("**/api/v1/reader/book-1/chapters", (request) => chapterFail ? request.fulfill({ status: 503, json: {} }) : request.fulfill({ json: { chapters: [{ number: 2, title: "Gate" }] } }))
  await page.goto(route)
  await page.getByRole("button", { name: "Retry manuscript" }).waitFor()
  await page.getByRole("searchbox").fill("gate")
  await expect(page.getByRole("button", { name: "Search", exact: true })).toBeDisabled()
  bookFail = false
  await page.getByRole("button", { name: "Retry manuscript" }).click()
  await page.getByRole("button", { name: "Search manuscript", exact: true }).click()
  await page.getByRole("button", { name: "Retry chapter links" }).waitFor()
  await expect(page.getByRole("link", { name: "Open chapter 2" })).toHaveCount(0)
  chapterFail = false
  await page.getByRole("button", { name: "Retry chapter links" }).click()
  await expect(page.getByRole("link", { name: "Open chapter 2" })).toBeVisible()
  await expect(page.getByRole("searchbox")).toHaveValue("gate")
})

test("long and sparse evidence wraps and invalid source chapters stay unlinked", async ({ page }, testInfo) => {
  await page.route(api, (request) => request.fulfill({ json: [{ ...passage, chapter_title: "Unbroken".repeat(30), summary: "A long summary. ".repeat(30), text: "A source excerpt. ".repeat(60) }, { ...passage, chapter_num: 0, text: null, summary: null }, { ...passage, chapter_num: 99 }] }))
  await page.setViewportSize({ width: 390, height: 1000 })
  await page.goto(`${route}?q=gate`)
  await expect(page.getByText("Chapter unavailable", { exact: true })).toBeVisible()
  await expect(page.getByText("Source excerpt unavailable.", { exact: true })).toBeVisible()
  await expect(page.getByRole("link", { name: "Open chapter 0" })).toHaveCount(0)
  await expect(page.getByRole("link", { name: "Open chapter 99" })).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.screenshot({ path: testInfo.outputPath("search-long.png"), fullPage: true })
})

test("reader results link to the reading view and empty passages offer recovery", async ({ page }) => {
  await installMockApi(page, { bookMode: "reader" })
  await page.goto(`${route}?q=gate`)
  await expect(page.getByRole("heading", { name: "Search this book" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Open chapter 2" })).toHaveAttribute("href", "/sky-of-ash--book-1/chapter/2")
  await expect(page.getByRole("link", { name: "Need an answer instead?" })).toHaveAttribute("href", "/sky-of-ash--book-1/ask")
  await page.route(api, (request) => request.fulfill({ json: [] }))
  await page.getByRole("searchbox", { name: "Search story" }).fill("unmatched phrase")
  await page.getByRole("button", { name: "Search", exact: true }).click()
  await expect(page.getByText(/No matching passages returned/)).toBeVisible()
  await expect(page.getByRole("heading", { name: "Results for “unmatched phrase”" })).toBeVisible()
})
