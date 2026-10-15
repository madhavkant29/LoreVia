import { expect, test } from "@playwright/test"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"
import type { ContinuityFinding } from "@/types/book"

const route = "/sky-of-ash--book-1/analysis"
test.beforeEach(async ({ page }) => {
  await installMockApi(page, { activationPending: true, chapterReports: true })
  await page.addInitScript(() => {
    if (!localStorage.getItem("lorevia-preferences")) localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 }))
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
})

test("findings and chapter reports remain readable across screen sizes", async ({ page }, testInfo) => {
  const errors: string[] = []
  page.on("pageerror", (error) => errors.push(error.message))
  await page.goto(route)
  await expect(page.getByText("Nora may use gate knowledge before learning it", { exact: true })).toBeVisible()
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    await page.screenshot({ path: testInfo.outputPath(`findings-${width}.png`), fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  }
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.getByRole("tab", { name: "Chapter reports", exact: true }).click()
  await expect(page.getByRole("heading", { name: "Chapter 1 — Ashfall" })).toBeVisible()
  await expect(page).toHaveTitle(/\S/)
  await page.screenshot({ path: testInfo.outputPath("reports-390.png"), fullPage: true })
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  for (const theme of ["dark", "light"]) {
    await page.evaluate((theme) => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme }, version: 0 })), theme)
    await page.goto(route)
    await expect(page.getByText("Nora may use gate knowledge before learning it", { exact: true })).toBeVisible()
    await expect(page.getByRole("img", { name: "LoreVia", exact: true })).toHaveAttribute("src", theme === "dark" ? "/image.png" : "/imagelight.png")
    await page.getByText("Evidence and recommendation", { exact: true }).click()
    await expect(page.getByText("Kael finally told Nora that royal blood was the only key.", { exact: true })).toBeVisible()
    expect(await criticalAccessibilityViolations(page)).toEqual([])
    await page.screenshot({ path: testInfo.outputPath(`findings-${theme}-evidence.png`), fullPage: true })
    await page.getByRole("tab", { name: "Chapter reports", exact: true }).click()
    await expect(page.getByRole("heading", { name: "Chapter 1 — Ashfall" })).toBeVisible()
    await expect(page).toHaveTitle(/\S/)
    expect(await criticalAccessibilityViolations(page)).toEqual([])
  }
  expect(errors).toEqual([])
})

test("findings loading and retry never report an empty review queue", async ({ page }) => {
  let release!: () => void
  const wait = new Promise<void>((resolve) => { release = resolve })
  let failed = true
  await page.route("**/api/v1/books/book-1/continuity-findings**", async (request) => {
    await wait
    return failed ? request.fulfill({ status: 503, json: {} }) : request.fallback()
  })
  await page.goto(route)
  await expect(page.getByRole("status").filter({ hasText: "Loading continuity findings" })).toBeVisible()
  await expect(page.getByText(/No current continuity finding/)).toHaveCount(0)
  release()
  await expect(page.getByRole("button", { name: "Retry findings", exact: true })).toBeVisible({ timeout: 20000 })
  await expect(page.getByText(/No current continuity finding/)).toHaveCount(0)
  failed = false
  await page.getByRole("button", { name: "Retry findings", exact: true }).click()
  await expect(page.getByText("Nora may use gate knowledge before learning it", { exact: true })).toBeVisible()
})

test("a failed findings refresh retains cached evidence and retries", async ({ page }) => {
  let failed = false
  await page.route("**/api/v1/books/book-1/continuity-findings**", (request) => failed ? request.fulfill({ status: 503, json: {} }) : request.fallback())
  await page.goto(route)
  const finding = page.getByText("Nora may use gate knowledge before learning it", { exact: true })
  await expect(finding).toBeVisible()
  failed = true
  await page.getByRole("button", { name: "Refresh", exact: true }).click()
  await expect(page.getByRole("alert").filter({ hasText: "Previously loaded evidence remains below" })).toBeVisible()
  await expect(finding).toBeVisible()
  failed = false
  await page.getByRole("button", { name: "Retry findings", exact: true }).click()
  await expect(page.getByRole("button", { name: "Retry findings", exact: true })).toHaveCount(0)
})

test("all finding statuses and results beyond the first six are reachable", async ({ page }) => {
  await page.goto(route)
  const seed = await page.evaluate(async () => (await fetch("/api/v1/books/book-1/continuity-findings")).json()) as ContinuityFinding[]
  const findings = Array.from({ length: 15 }, (_, index) => ({ ...seed[0], id: `finding-${index}`, title: `Finding ${index + 1}` }))
  findings.push({ ...seed[0], id: "reviewed", title: "Intentional mystery", decision: "intentional" })
  findings.push({ ...seed[0], id: "stale", title: "Earlier manuscript issue", is_stale: true, decision: "accepted" })
  await page.route("**/api/v1/books/book-1/continuity-findings**", (request) => request.fulfill({ json: findings }))
  await page.reload()
  await expect(page.getByRole("button", { name: "Needs review 15", exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "Reviewed 1", exact: true })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Finding 12", exact: true })).toBeVisible()
  await page.getByRole("button", { name: "Show more findings (3 remaining)" }).click()
  await expect(page.getByRole("heading", { name: "Finding 15", exact: true })).toBeVisible()
  await page.getByRole("button", { name: "Reviewed 1", exact: true }).click()
  await expect(page.getByRole("heading", { name: "Intentional mystery" })).toBeVisible()
  await page.getByRole("button", { name: "Stale after edits 1", exact: true }).click()
  await expect(page.getByText(/refer to an earlier manuscript version/)).toBeVisible()
  await page.getByLabel("Search findings", { exact: true }).fill("not present")
  await expect(page.getByText(/No findings match this search/)).toBeVisible()
  await page.getByRole("button", { name: "Clear search" }).click()
  await expect(page.getByRole("heading", { name: "Earlier manuscript issue" })).toBeVisible()
})

test("chapter report filters update summary counts and tabs work from the keyboard", async ({ page }) => {
  await page.goto(route)
  await page.getByRole("tab", { name: "Findings list", exact: true }).focus()
  await page.keyboard.press("End")
  const tab = page.getByRole("tab", { name: "Chapter reports", exact: true })
  await expect(tab).toBeFocused()
  await expect(tab).toHaveAttribute("aria-selected", "true")
  await page.getByLabel("Filter chapter reports").selectOption("2")
  await expect(page.getByRole("heading", { name: "Chapter 1 — Ashfall" })).toHaveCount(0)
  const summary = page.getByLabel("Chapter report summary")
  await expect(summary).toContainText("Chapters shown1")
  await expect(summary).toContainText("Recorded changes1")
  await expect(summary).toContainText("Continuity flags0")
  await tab.focus()
  await page.keyboard.press("Home")
  await expect(page.getByRole("tab", { name: "Findings list", exact: true })).toBeFocused()
  await page.getByRole("button", { name: "Help", exact: true }).click()
  await expect(page.getByRole("dialog")).toBeVisible()
  await page.keyboard.press("Escape")
  await expect(page.getByRole("button", { name: "Help", exact: true })).toBeFocused()
})

test("chapter reports have retry and an actionable empty state", async ({ page }) => {
  let failed = true
  await page.route("**/api/v1/books/book-1/chapter-reports**", (request) => failed ? request.fulfill({ status: 503, json: {} }) : request.fulfill({ json: [] }))
  await page.goto(`${route}?view=chapters`)
  await expect(page.getByRole("button", { name: "Retry chapter reports", exact: true })).toBeVisible()
  await expect(page.getByText(/No chapter reports are available/)).toHaveCount(0)
  failed = false
  await page.getByRole("button", { name: "Retry chapter reports", exact: true }).click()
  await expect(page.getByText(/No chapter reports are available/)).toBeVisible()
  await expect(page.getByRole("link", { name: "Open Chapters", exact: true })).toHaveAttribute("href", "/sky-of-ash--book-1/chapters")
})

test("book metadata failures can retry without hiding findings", async ({ page }) => {
  let failed = true
  await page.route("**/api/v1/books/book-1", (request) => failed ? request.fulfill({ status: 503, json: {} }) : request.fallback())
  await page.goto(route)
  await expect(page.getByRole("button", { name: "Retry book details", exact: true })).toBeVisible()
  await expect(page.getByText("Nora may use gate knowledge before learning it", { exact: true })).toBeVisible()
  failed = false
  await page.getByRole("button", { name: "Retry book details", exact: true }).click()
  await expect(page.getByRole("button", { name: "Retry book details", exact: true })).toHaveCount(0)
})

test("long findings and reports wrap without hiding source controls", async ({ page }, testInfo) => {
  await page.goto(route)
  const findings = await page.evaluate(async () => (await fetch("/api/v1/books/book-1/continuity-findings")).json()) as ContinuityFinding[]
  const title = "A continuity question about the gate keeper and the promise recorded in the eastern archives"
  findings[0].title = title
  findings[0].explanation = "Unbroken reference: " + "x".repeat(140)
  findings[0].evidence[0].chapter_number = 0
  await page.route("**/api/v1/books/book-1/continuity-findings**", (request) => request.fulfill({ json: findings }))
  let requestedLimit = ""
  await page.route("**/api/v1/books/book-1/chapter-reports**", (request) => {
    requestedLimit = new URL(request.request().url()).searchParams.get("limit") ?? ""
    return request.fulfill({ json: [{ chapter_number: 99, chapter_title: title, summary: "z".repeat(180), new_characters: [], relationship_changes: [], plot_threads_opened: [], plot_threads_resolved: [], continuity_flags: ["y".repeat(160)] }] })
  })
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    await page.goto(route)
    await expect(page.getByRole("img", { name: "LoreVia", exact: true })).toHaveAttribute("src", "/image.png")
    await page.getByText("Evidence and recommendation", { exact: true }).click()
    await expect(page.getByText(/Chapter unavailable/)).toBeVisible()
    await expect(page.getByRole("link", { name: "Read source chapter 2" })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
    await page.screenshot({ path: testInfo.outputPath(`findings-long-${width}.png`), fullPage: true })
    await page.getByRole("tab", { name: "Chapter reports", exact: true }).click()
    await expect(page.getByRole("heading", { name: `Chapter 99 — ${title}` })).toBeVisible()
    expect(requestedLimit).toBe("50")
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
    await page.screenshot({ path: testInfo.outputPath(`reports-long-${width}.png`), fullPage: true })
  }
})

test("an empty findings response remains distinct from an unavailable response", async ({ page }) => {
  await page.route("**/api/v1/books/book-1/continuity-findings**", (request) => request.fulfill({ json: [] }))
  await page.goto(route)
  await expect(page.getByText(/No current continuity finding needs a decision/)).toBeVisible()
  await expect(page.getByRole("button", { name: "Needs review 0", exact: true })).toBeVisible()
  await expect(page.getByRole("link", { name: "Resume revision workflow", exact: true })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Manuscript review", exact: true })).toBeVisible()
})
