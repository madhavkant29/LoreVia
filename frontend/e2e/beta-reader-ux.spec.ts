import { expect, test } from "@playwright/test"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"

const route = "/sky-of-ash--book-1/ai-beta-reader"
const reports = "**/advisor/beta-reader/reports"
const job = "**/advisor/beta-reader/jobs/*"

test.beforeEach(async ({ page }) => {
  await installMockApi(page)
  await page.addInitScript(() => {
    if (!localStorage.getItem("lorevia-preferences")) localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 }))
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
})

test("beta reader report and configuration work at four widths and both themes", async ({ page }, testInfo) => {
  const errors: string[] = []
  page.on("pageerror", (error) => errors.push(error.message))
  await page.goto(route)
  await expect(page.getByRole("heading", { name: "Reader report", exact: true })).toBeVisible()
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    await page.screenshot({ path: testInfo.outputPath(`beta-report-${width}.png`), fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  }
  for (const theme of ["dark", "light"]) {
    await page.evaluate((theme) => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme }, version: 0 })), theme)
    await page.reload()
    await expect(page.getByRole("heading", { name: "Reader report", exact: true })).toBeVisible()
    for (const tab of ["Reader report", "Overused language", "Character voices", "Revision priorities"]) {
      await page.getByRole("tab", { name: tab, exact: true }).click()
      expect(await criticalAccessibilityViolations(page)).toEqual([])
      await page.screenshot({ path: testInfo.outputPath(`beta-${theme}-${tab.replaceAll(" ", "-")}.png`), fullPage: true })
    }
    await page.getByRole("button", { name: "New run", exact: true }).click()
    await expect(page.getByRole("button", { name: "Run reader pass" })).toBeEnabled()
    await page.getByText("Limit voice comparison to selected characters", { exact: true }).click()
    expect(await criticalAccessibilityViolations(page)).toEqual([])
    await page.screenshot({ path: testInfo.outputPath(`beta-config-${theme}.png`), fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  }
  expect(errors).toEqual([])
})

test("report loading and failed loads do not masquerade as empty results", async ({ page }) => {
  let release!: () => void
  const wait = new Promise<void>((resolve) => { release = resolve })
  let fail = true
  await page.route(reports, async (request) => { await wait; return fail ? request.fulfill({ status: 503, json: {} }) : request.fallback() })
  await page.goto(route)
  await expect(page.getByText("Loading saved reports…", { exact: true })).toBeVisible()
  await expect(page.getByText("No reader report yet", { exact: true })).toHaveCount(0)
  release()
  await expect(page.getByRole("button", { name: "Retry saved reports" })).toBeVisible()
  await expect(page.getByText("No saved reports yet.", { exact: true })).toHaveCount(0)
  fail = false
  await page.getByRole("button", { name: "Retry saved reports" }).click()
  await expect(page.getByRole("heading", { name: "Reader report", exact: true })).toBeVisible()
})

test("configuration retries failed chapter and character sources", async ({ page }) => {
  let fail = true
  await page.route("**/api/v1/reader/book-1/chapters**", (request) => fail ? request.fulfill({ status: 503, json: {} }) : request.fallback())
  await page.route("**/api/v1/books/book-1/characters?**", (request) => fail ? request.fulfill({ status: 503, json: {} }) : request.fallback())
  await page.goto(route)
  await page.getByRole("button", { name: "New run" }).click()
  await page.getByText("Limit voice comparison to selected characters", { exact: true }).click()
  await expect(page.getByRole("button", { name: "Retry chapters" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Retry characters" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Run reader pass" })).toBeDisabled()
  fail = false
  await page.getByRole("button", { name: "Retry chapters" }).click()
  await page.getByRole("button", { name: "Retry characters" }).click()
  await expect(page.getByRole("button", { name: "Run reader pass" })).toBeEnabled()
  await expect(page.getByRole("checkbox", { name: "Gregor", exact: true })).toBeVisible()
})

test("passages preserve over-limit text and allow optional chapter context to stay empty", async ({ page }) => {
  let submitted: Record<string, unknown> = {}
  page.on("request", (request) => { if (request.method() === "POST" && request.url().endsWith("/advisor/beta-reader")) submitted = request.postDataJSON() })
  await page.goto(route)
  await page.getByRole("button", { name: "New run" }).click()
  await expect(page.getByRole("button", { name: "Run reader pass" })).toBeEnabled()
  await page.getByRole("radio", { name: /^Passage / }).click()
  await page.getByRole("combobox", { name: "Chapter context", exact: true }).selectOption("")
  await page.getByLabel("Passage for AI beta reader").fill("x".repeat(12001))
  await expect(page.getByRole("button", { name: "Run reader pass" })).toBeDisabled()
  await expect(page.getByLabel("Passage for AI beta reader")).toHaveValue("x".repeat(12001))
  await page.getByLabel("Passage for AI beta reader").fill("Nora reached the gate.")
  await expect(page.getByRole("combobox", { name: "Chapter context", exact: true })).toHaveValue("")
  await page.getByRole("button", { name: "Run reader pass" }).click()
  await expect(page.getByRole("heading", { name: "Reader report", exact: true })).toBeVisible()
  expect(submitted.chapter_number).toBeNull()
  expect(submitted.text).toBe("Nora reached the gate.")
})

test("a polling outage preserves the active job and resumes after reload without another run", async ({ page }) => {
  let fail = true
  let starts = 0
  page.on("request", (request) => { if (request.method() === "POST" && request.url().endsWith("/advisor/beta-reader")) starts++ })
  await page.route(job, (request) => fail ? request.fulfill({ status: 503, json: {} }) : request.fallback())
  await page.goto(route)
  await page.getByRole("button", { name: "New run" }).click()
  await page.getByRole("button", { name: "Run reader pass" }).click()
  await expect(page.getByText(/Could not check progress/)).toBeVisible()
  await expect(page.getByRole("button", { name: "Run reader pass" })).toHaveCount(0)
  await page.reload()
  await expect(page.getByRole("button", { name: "Check progress now" })).toBeVisible()
  fail = false
  await page.getByRole("button", { name: "Check progress now" }).click()
  await expect(page.getByRole("heading", { name: "Reader report", exact: true })).toBeVisible()
  expect(starts).toBe(1)
  expect(await page.evaluate(() => sessionStorage.getItem("lorevia:beta-reader-job:sky-of-ash--book-1"))).toBeNull()
})

test("report filters reset incompatible types and tabs support arrow keys", async ({ page }) => {
  await page.goto(route)
  const reader = page.getByRole("tab", { name: "Reader report", exact: true })
  await reader.focus()
  await page.keyboard.press("End")
  await expect(page.getByRole("tab", { name: "Revision priorities", exact: true })).toBeFocused()
  await page.getByRole("combobox", { name: "Severity", exact: true }).selectOption("low")
  await expect(page.getByText("No revision candidates match these filters.")).toBeVisible()
  await page.getByRole("button", { name: "Clear filters" }).click()
  await expect(page.getByRole("button", { name: "Create revision task" })).toBeVisible()
  await reader.click()
  await page.getByRole("combobox", { name: "Finding type", exact: true }).selectOption("pacing")
  await reader.focus()
  await page.keyboard.press("ArrowRight")
  await expect(page.getByRole("tab", { name: "Overused language" })).toBeFocused()
  await expect(page.getByRole("heading", { name: "“silver gate”" })).toBeVisible()
  await expect(page.getByRole("combobox", { name: "Finding type", exact: true })).toHaveValue("all")
})

test("empty reports offer a first run without inventing findings", async ({ page }) => {
  await page.route(reports, (request) => request.fulfill({ json: { reports: [] } }))
  await page.goto(route)
  await expect(page.getByRole("heading", { name: "No reader report yet" })).toBeVisible()
  await page.getByRole("button", { name: "Configure first run" }).click()
  await expect(page.getByRole("heading", { name: "Configure a reader pass" })).toBeFocused()
  await expect(page.getByRole("button", { name: "Run reader pass" })).toBeEnabled()
})

test("failed runs retain configuration and failed saves can be retried", async ({ page }) => {
  let failJob = true
  let failSave = true
  await page.route(job, (request) => failJob ? request.fulfill({ json: { status: "failed", report: null, error: "unavailable", progress: null } }) : request.fallback())
  await page.route("**/books/book-1/notes/vault**", (request) => failSave ? request.fulfill({ status: 503, json: {} }) : request.fallback())
  await page.goto(route)
  await page.getByRole("button", { name: "New run" }).click()
  await page.getByRole("button", { name: "Run reader pass" }).click()
  await expect(page.getByText(/The reader pass could not finish/)).toBeVisible()
  await expect(page.getByRole("heading", { name: "Configure a reader pass" })).toBeFocused()
  failJob = false
  await page.getByRole("button", { name: "Run reader pass" }).click()
  await expect(page.getByRole("heading", { name: "Reader report", exact: true })).toBeFocused()
  await page.getByRole("button", { name: "Save to notes" }).click()
  await expect(page.getByText(/Could not save this report to notes/)).toBeVisible()
  failSave = false
  await page.getByRole("button", { name: "Save to notes" }).click()
  await expect(page.getByText(/Saved report to AI Beta Reader/)).toBeVisible()
  await expect(page.getByText(/Could not save this report to notes/)).toHaveCount(0)
})

test("long reader reports and evidence remain reachable without page overflow", async ({ page }, testInfo) => {
  await page.goto(route)
  await expect(page.getByRole("heading", { name: "Reader report", exact: true })).toBeVisible()
  const seed = await page.evaluate(async () => (await fetch("/api/v1/intelligence/book-1/advisor/beta-reader/reports")).json())
  const report = seed.reports[0]
  const long = "ManuscriptEvidenceWithoutSpaces".repeat(18)
  report.overall_impression = long
  report.findings[0].title = long
  report.findings[0].description = long
  report.findings[0].evidence[0].excerpt = long
  report.overused_terms[0].term = long
  report.coverage.missing_chapters = [3]
  await page.route(reports, (request) => request.fulfill({ json: { reports: [report] } }))
  await page.reload()
  await expect(page.getByText(/Not analyzed: Chapter 3/)).toBeVisible()
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
    await page.screenshot({ path: testInfo.outputPath(`beta-long-${width}.png`), fullPage: true })
  }
  await page.getByRole("tab", { name: "Overused language", exact: true }).click()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
})

test("book loading errors preserve the distinction from scan permission denial", async ({ page }) => {
  let fail = true
  await page.route("**/api/v1/books/book-1", (request) => fail ? request.fulfill({ status: 503, json: {} }) : request.fallback())
  await page.goto(route)
  await expect(page.getByRole("button", { name: "Retry manuscript", exact: true })).toBeVisible()
  await expect(page.getByText("Permission required", { exact: true })).toHaveCount(0)
  fail = false
  await page.getByRole("button", { name: "Retry manuscript", exact: true }).click()
  await expect(page.getByRole("heading", { name: "Reader report", exact: true })).toBeVisible()
  await page.getByRole("button", { name: "Help", exact: true }).click()
  await expect(page.getByRole("dialog")).toBeVisible()
  await page.keyboard.press("Escape")
  await expect(page.getByRole("button", { name: "Help", exact: true })).toBeFocused()
})
