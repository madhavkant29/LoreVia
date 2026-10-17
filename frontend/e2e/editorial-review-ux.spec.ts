import { expect, test, type Page } from "@playwright/test"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"

const route = "/sky-of-ash--book-1/editorial-review"
const source = "The gate opened, Nora ran. She spoke the blood oath before Kael could stop her."
const verdict = "The scene has a strong conflict turn, but Nora's gate knowledge needs earlier support."
const reviewEndpoint = "**/api/v1/intelligence/book-1/advisor/editorial-review-stream"

test.beforeEach(async ({ page }) => {
  await installMockApi(page)
  await page.addInitScript(() => {
    if (!localStorage.getItem("lorevia-preferences")) localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 }))
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
})

async function runReview(page: Page) {
  await page.getByLabel("Chapter number").fill("1")
  await page.getByLabel("Passage text").fill(source)
  await page.getByRole("button", { name: "Run review", exact: true }).click()
  await expect(page.getByText(verdict, { exact: true })).toBeVisible()
}

test("editorial workspace and findings remain readable at four widths and both themes", async ({ page }, testInfo) => {
  const errors: string[] = []
  page.on("pageerror", (error) => errors.push(error.message))
  page.on("console", (message) => { if (message.type() === "error" && /hydration|did not match|cannot be a descendant/i.test(message.text())) errors.push(message.text()) })
  await page.goto(route)
  await expect(page.getByText("Paste a passage and run a review to begin.")).toBeVisible()
  // Confirm hydration before screenshot caret styling can mutate server markup.
  await page.getByRole("button", { name: "Help", exact: true }).click()
  await expect(page.getByRole("dialog")).toBeVisible()
  await page.keyboard.press("Escape")
  await page.screenshot({ path: testInfo.outputPath("empty-desktop.png"), fullPage: true })
  await runReview(page)
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    await page.screenshot({ path: testInfo.outputPath(`editorial-${width}.png`), fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  }
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  for (const theme of ["dark", "light"]) {
    await page.evaluate((theme) => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme }, version: 0 })), theme)
    await page.reload()
    await runReview(page)
    await page.getByText("Reviewed passage", { exact: true }).click()
    await expect(page.locator("details p")).toHaveText(source)
    await expect(page).toHaveTitle(/\S/)
    expect(await criticalAccessibilityViolations(page)).toEqual([])
    await page.screenshot({ path: testInfo.outputPath(`editorial-${theme}.png`), fullPage: true })
  }
  expect(errors).toEqual([])
})

test("review validation preserves oversized input and rejects invalid chapter numbers", async ({ page }) => {
  let requests = 0
  page.on("request", (request) => { if (request.url().includes("editorial-review-stream")) requests++ })
  await page.goto(route)
  const button = page.getByRole("button", { name: "Run review", exact: true })
  await expect(button).toBeDisabled()
  await page.getByLabel("Passage text").fill("x".repeat(12001))
  await expect(button).toBeDisabled()
  await expect(page.getByText(/Shorten the passage/)).toBeVisible()
  await expect(page.getByLabel("Passage text")).toHaveValue("x".repeat(12001))
  await page.getByLabel("Passage text").fill(source)
  for (const invalid of ["0", "-1", "1.5"]) {
    await page.getByLabel("Chapter number").fill(invalid)
    await expect(button).toBeDisabled()
    await expect(page.getByRole("main").getByRole("alert")).toContainText("whole chapter number")
  }
  expect(requests).toBe(0)
  await page.getByLabel("Chapter number").fill("")
  await button.click()
  await expect(page.getByRole("button", { name: "Passage 1" })).toBeVisible()
})

test("review progress locks inputs and failures retain the passage for retry", async ({ page }) => {
  let release!: () => void
  const gate = new Promise<void>((resolve) => { release = resolve })
  let fail = true
  await page.route(reviewEndpoint, async (request) => { await gate; return fail ? request.fulfill({ status: 503, json: {} }) : request.fallback() })
  await page.goto(route)
  await page.getByLabel("Passage text").fill(source)
  await page.getByRole("button", { name: "Run review" }).click()
  await expect(page.getByRole("button", { name: "Reviewing…" })).toBeDisabled()
  await expect(page.getByLabel("Passage text")).toBeDisabled()
  await expect(page.getByLabel("Chapter number")).toBeDisabled()
  release()
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Review failed")
  await expect(page.getByLabel("Passage text")).toHaveValue(source)
  fail = false
  await page.getByRole("button", { name: "Run review" }).click()
  await expect(page.getByText(verdict, { exact: true })).toBeVisible()
})

test("selected reviews retain their source for downloads and preserve unsent edits", async ({ page }) => {
  let reportUrl = ""
  await page.route("**/advisor/continuity-report**", async (request) => {
    reportUrl = request.request().url()
    await request.fulfill({ contentType: "application/pdf", body: "%PDF-1.4\nmock" })
  })
  await page.goto(route)
  await runReview(page)
  await page.getByLabel("Passage text").fill("A second version.")
  await page.getByLabel("Chapter number").fill("2")
  await page.getByRole("button", { name: "Run review" }).click()
  await expect(page.getByRole("button", { name: "Chapter 2" })).toBeVisible()
  await page.getByLabel("Passage text").fill("An unsent revision.")
  await page.getByLabel("Chapter number").fill("3")
  await page.getByRole("button", { name: "Chapter 1" }).click()
  await expect(page.getByLabel("Passage text")).toHaveValue("An unsent revision.")
  await expect(page.getByText(/this review still refers to its original passage/)).toBeVisible()
  const download = page.waitForEvent("download")
  await page.getByRole("button", { name: "Download continuity report" }).click()
  expect((await download).suggestedFilename()).toBe("continuity-report.pdf")
  expect(new URL(reportUrl).searchParams.get("text")).toBe(source)
  expect(new URL(reportUrl).searchParams.get("chapter_num")).toBe("1")
  await expect(page.getByRole("status")).toContainText("Continuity report downloaded")
})

test("failed report downloads and note saves have visible feedback and retry", async ({ page }) => {
  let fail = true
  await page.route("**/advisor/continuity-report**", (request) => fail ? request.fulfill({ status: 503, json: {} }) : request.fulfill({ contentType: "application/pdf", body: "%PDF-1.4\nmock" }))
  await page.route("**/books/book-1/notes/vault**", (request) => fail ? request.fulfill({ status: 503, json: {} }) : request.fallback())
  await page.goto(route)
  await runReview(page)
  await page.getByRole("button", { name: "Download continuity report" }).click()
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Could not complete")
  await page.getByRole("button", { name: "Save summary note" }).click()
  await expect(page.getByRole("main").getByRole("alert")).toHaveCount(2)
  fail = false
  await page.getByRole("button", { name: "Save summary note" }).click()
  await expect(page.getByRole("status")).toContainText("Saved to Notes")
  const download = page.waitForEvent("download")
  await page.getByRole("button", { name: "Download continuity report" }).click()
  await download
  await expect(page.getByRole("main").getByRole("alert")).toHaveCount(0)
})

test("source links, anchors, and keyboard help are reachable", async ({ page }) => {
  await page.goto(route)
  await runReview(page)
  await expect(page.getByText("Nora watched the gate from the ash market.", { exact: false })).toBeVisible()
  await expect(page.getByRole("link", { name: "Chapter 2 — The Ember Gate", exact: true })).toHaveAttribute("href", "/sky-of-ash--book-1/chapter/2")
  await page.getByRole("button", { name: "Help", exact: true }).focus()
  await page.keyboard.press("Enter")
  await expect(page.getByRole("dialog")).toBeVisible()
  await page.keyboard.press("Escape")
  await expect(page.getByRole("button", { name: "Help", exact: true })).toBeFocused()
})

test("a clean review distinguishes missing evidence from verified manuscript consistency", async ({ page }) => {
  await page.route(reviewEndpoint, (request) => request.fulfill({ contentType: "text/event-stream", body: `event: done\ndata: ${JSON.stringify({ review: { overall_verdict: "No specific issue identified.", thematic_fit: { score: "strong", notes: "The theme is sustained." }, continuity_issues: [], grammar_issues: [], formatting_notes: [], insertion_opportunities: [] }, retrieved_passages: [] })}\n\n` }))
  await page.goto(route)
  await page.getByLabel("Passage text").fill(source)
  await page.getByRole("button", { name: "Run review" }).click()
  await expect(page.getByText("No continuity or grammar issues found", { exact: true })).toBeVisible()
  await expect(page.getByText(/No cross-referenced passages were returned/)).toBeVisible()
  await expect(page.getByText(/Check the source evidence before treating the passage as verified/)).toBeVisible()
})

test("long reports wrap without hiding recommendations or source evidence", async ({ page }, testInfo) => {
  const long = "ExtraordinaryManuscriptEvidence".repeat(15)
  await page.route(reviewEndpoint, (request) => request.fulfill({ contentType: "text/event-stream", body: `event: done\ndata: ${JSON.stringify({ review: { overall_verdict: long, thematic_fit: { score: "weak", notes: long }, continuity_issues: [{ type: "timeline", severity: "critical", title: long, description: long, suggestion: long }], grammar_issues: [{ issue: "Long wording", original: long, fix: long }], formatting_notes: [long], insertion_opportunities: [] }, retrieved_passages: [{ chapter_num: 0, chapter_title: long, excerpt: long, relevance: 0.9 }] })}\n\n` }))
  await page.goto(route)
  await page.getByLabel("Passage text").fill(source)
  await page.getByRole("button", { name: "Run review" }).click()
  await expect(page.getByText("Source chapter unavailable", { exact: true })).toBeVisible()
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
    await page.screenshot({ path: testInfo.outputPath(`editorial-long-${width}.png`), fullPage: true })
  }
})

test("book detail failures are recoverable without discarding the entered passage", async ({ page }) => {
  let fail = true
  await page.route("**/api/v1/books/book-1", (request) => fail ? request.fulfill({ status: 503, json: {} }) : request.fallback())
  await page.goto(route)
  await page.getByLabel("Passage text").fill(source)
  await expect(page.getByRole("button", { name: "Retry manuscript details" })).toBeVisible()
  fail = false
  await page.getByRole("button", { name: "Retry manuscript details" }).click()
  await expect(page.getByRole("button", { name: "Retry manuscript details" })).toHaveCount(0)
  await expect(page.getByLabel("Passage text")).toHaveValue(source)
})
