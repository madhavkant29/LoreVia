import { expect, test } from "@playwright/test"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"

const route = "/sky-of-ash--book-1/timeline"
const api = "**/api/v1/reader/book-1/timeline**"
const empty = { chapters: [], events: [], character_tracks: [], thread_tracks: [], relationship_markers: [] }

test.beforeEach(async ({ page }) => {
  await installMockApi(page)
  await page.addInitScript(() => {
    if (!localStorage.getItem("lorevia-preferences")) localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 }))
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
})

test("timeline views remain readable at four widths and both themes", async ({ page }, testInfo) => {
  const errors: string[] = []
  page.on("pageerror", (error) => errors.push(error.message))
  await page.goto(route)
  await expect(page.getByRole("heading", { name: "Grete takes control", exact: true })).toBeVisible()
  await page.getByRole("button", { name: "Help", exact: true }).click()
  await page.keyboard.press("Escape")
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    await page.screenshot({ path: testInfo.outputPath(`timeline-${width}.png`), fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
    await expect(page.getByRole("button", { name: "Collapse all", exact: true })).toBeVisible({ visible: width >= 768 })
  }
  for (const theme of ["dark", "light"]) {
    await page.evaluate((theme) => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme }, version: 0 })), theme)
    await page.reload()
    await expect(page.getByRole("heading", { name: "Grete takes control", exact: true })).toBeVisible()
    expect(await criticalAccessibilityViolations(page)).toEqual([])
    await page.screenshot({ path: testInfo.outputPath(`timeline-list-${theme}.png`), fullPage: true })
    await page.setViewportSize({ width: 1280, height: 1000 })
    expect(await criticalAccessibilityViolations(page)).toEqual([])
    await page.screenshot({ path: testInfo.outputPath(`timeline-lanes-${theme}.png`), fullPage: true })
    await page.setViewportSize({ width: 390, height: 1000 })
  }
  expect(errors).toEqual([])
})

test("lane filters, keyboard collapse, view switching and chapter links work", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 1000 })
  await page.goto(route)
  const characters = page.getByRole("button", { name: /Characters \(2\)/ })
  await characters.focus()
  await page.keyboard.press("Enter")
  await expect(characters).toHaveAttribute("aria-expanded", "false")
  await page.keyboard.press("Space")
  await expect(characters).toHaveAttribute("aria-expanded", "true")
  await page.getByRole("button", { name: "Collapse all", exact: true }).click()
  await expect(characters).toHaveAttribute("aria-expanded", "false")
  await page.getByRole("button", { name: "Expand all", exact: true }).click()
  await expect(characters).toHaveAttribute("aria-expanded", "true")
  await page.getByRole("combobox", { name: "Show", exact: true }).selectOption("relationships")
  await expect(page.getByRole("heading", { name: "Family survival", exact: true })).toHaveCount(0)
  await page.getByRole("combobox", { name: "View", exact: true }).selectOption("list")
  await expect(page.getByRole("heading", { name: "Timeline list", exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "Collapse all", exact: true })).toBeHidden()
  await expect(page.getByRole("link", { name: "Open chapter 3", exact: true })).toHaveAttribute("href", "/sky-of-ash--book-1/chapter/3")
  await page.getByRole("link", { name: "Open chapter 3", exact: true }).click()
  await expect(page).toHaveURL(/\/chapter\/3/)
})

test("event requests paginate and retry without losing loaded entries", async ({ page }) => {
  let fail = true
  const offsets: number[] = []
  await page.route(api, async (request) => {
    const url = new URL(request.request().url())
    if (url.searchParams.get("include") !== "events") return request.fallback()
    const offset = Number(url.searchParams.get("offset"))
    offsets.push(offset)
    if (offset && fail) return request.fulfill({ status: 503, json: {} })
    return request.fulfill({ json: { ...empty, events: [{ chapter_number: offset ? 3 : 1, chapter_title: null, kind: "turning_point", title: offset ? "Final event" : "First event", detail: null }], total_events: 2, has_more: !offset, next_offset: offset ? null : 100 } })
  })
  await page.goto(route)
  await page.getByRole("combobox", { name: "Show", exact: true }).selectOption("events")
  await expect(page.getByRole("heading", { name: "First event" })).toBeVisible()
  await page.getByRole("button", { name: "Load more story events" }).click()
  await expect(page.getByRole("button", { name: "Retry story events" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "First event" })).toBeVisible()
  fail = false
  await page.getByRole("button", { name: "Retry story events" }).click()
  await expect(page.getByRole("heading", { name: "Final event" })).toBeVisible()
  await expect(page.getByText("2 of 2 story events loaded", { exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "Load more story events" })).toHaveCount(0)
  expect(offsets).toContain(100)
})

test("timeline loading and errors offer recovery without a false empty state", async ({ page }) => {
  let release!: () => void
  const wait = new Promise<void>((resolve) => { release = resolve })
  let fail = true
  await page.route(api, async (request) => { await wait; return fail ? request.fulfill({ status: 503, json: {} }) : request.fallback() })
  await page.goto(route)
  await expect(page.getByText("Building your timeline...", { exact: true })).toBeVisible()
  await expect(page.getByRole("heading", { name: "No major-event data yet" })).toHaveCount(0)
  release()
  await expect(page.getByRole("button", { name: "Retry timeline" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "No major-event data yet" })).toHaveCount(0)
  fail = false
  await page.getByRole("button", { name: "Retry timeline" }).click()
  await expect(page.getByRole("heading", { name: "Grete takes control", exact: true })).toBeVisible()
  fail = true
  await page.getByRole("button", { name: "Refresh timeline" }).click()
  await expect(page.getByText("Timeline refresh failed. Previously loaded tracks remain visible.", { exact: true })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Gregor", exact: true })).toBeVisible()
})

test("empty timeline and empty lane give meaningful next steps", async ({ page }) => {
  await page.route(api, (request) => request.fulfill({ json: empty }))
  await page.goto(route)
  await expect(page.getByRole("heading", { name: "No major-event data yet" })).toBeVisible()
  await expect(page.getByRole("link", { name: "View chapters", exact: true })).toHaveAttribute("href", "/sky-of-ash--book-1/chapters")
  await page.unroute(api)
  await page.route(api, (request) => request.fulfill({ json: { ...empty, chapters: [{ number: 1, title: "The gate" }] } }))
  await page.reload()
  await page.getByRole("combobox", { name: "Show", exact: true }).selectOption("characters")
  await expect(page.getByText("No characters recorded in available chapters.", { exact: true })).toBeVisible()
  await page.getByRole("combobox", { name: "View", exact: true }).selectOption("list")
  await expect(page.getByText("No items match this lane. Choose another category in Show.", { exact: true })).toBeVisible()
})

test("sparse chapters and long entries never fabricate positions or overflow", async ({ page }, testInfo) => {
  await page.route(api, (request) => request.fulfill({ json: { ...empty, chapters: [1, 3, 5, 7, 9, 11, 13, 15].map((number) => ({ number, title: "Chapter title" })), character_tracks: [{ id: "long", name: "Nora".repeat(35), role: "Primary character", detail: "A long account of the journey. ".repeat(12), start_chapter: 2, end_chapter: 4 }], relationship_markers: [{ id: "missing", title: "Unplaced turn", chapter_number: 99, detail: null }] } }))
  await page.goto(route)
  await expect(page.locator('[data-timeline-mark="character-long"]')).toHaveCSS("left", "86px")
  await expect(page.locator('[data-timeline-mark="relationship-missing"]')).toHaveCount(0)
  await expect(page.locator('a[href$="/chapter/99"]')).toHaveCount(0)
  const grid = page.getByRole("region", { name: "Chapter lanes, horizontally scrollable" })
  await grid.focus()
  await page.keyboard.press("End")
  for (const width of [1280, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
    await page.screenshot({ path: testInfo.outputPath(`timeline-long-${width}.png`), fullPage: true })
  }
  await page.getByRole("combobox", { name: "View", exact: true }).selectOption("lanes")
  await expect(grid).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  await page.screenshot({ path: testInfo.outputPath("timeline-mobile-lanes.png"), fullPage: true })
})

test("reader view respects available chapters and book details can recover", async ({ page }) => {
  await installMockApi(page, { bookMode: "reader" })
  let fail = true
  await page.route("**/api/v1/books/book-1", async (request) => {
    if (fail) return request.fulfill({ status: 503, json: {} })
    return request.fallback()
  })
  await page.route(api, (request) => request.fulfill({ json: { ...empty, chapters: [{ number: 1, title: "The gate" }], character_tracks: [{ id: "nora", name: "Nora", role: null, detail: null, start_chapter: 1, end_chapter: 1 }] } }))
  await page.goto(route)
  await expect(page.getByRole("button", { name: "Retry book details" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Nora", exact: true })).toBeVisible()
  await expect(page.locator('main a[href$="/chapter/2"]')).toHaveCount(0)
  fail = false
  await page.getByRole("button", { name: "Retry book details" }).click()
  await expect(page.getByRole("button", { name: "Retry book details" })).toHaveCount(0)
  await expect(page.getByRole("heading", { name: "Major events", exact: true })).toBeVisible()
})
