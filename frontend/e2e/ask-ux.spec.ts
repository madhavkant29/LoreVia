import { expect, test } from "@playwright/test"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"
const route = "/sky-of-ash--book-1/ask"
const api = "**/api/v1/intelligence/book-1/qa-stream"
const inputLabel = "Ask LoreVia a grounded question about the story"

test.beforeEach(async ({ page }) => {
  await installMockApi(page, { bookMode: "reader" })
  await page.addInitScript(() => {
    if (!localStorage.getItem("lorevia-preferences")) localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 }))
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
})

test("question and cited answers remain readable at four widths and both themes", async ({ page }, testInfo) => {
  const errors: string[] = []
  page.on("pageerror", (error) => errors.push(error.message))
  await page.goto(route)
  await expect(page.getByText("Up to Chapter 2", { exact: true })).toBeVisible()
  await page.getByRole("textbox", { name: inputLabel }).fill("Where does Nora last appear?")
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
    await page.screenshot({ path: testInfo.outputPath(`ask-${width}.png`), fullPage: true })
  }
  await page.getByRole("button", { name: "Ask", exact: true }).click()
  await expect(page.getByRole("link", { name: "Jump to chapter 2" })).toBeVisible()
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.screenshot({ path: testInfo.outputPath("ask-answer-dark.png"), fullPage: true })
  await page.evaluate(() => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "light" }, version: 0 })))
  await page.reload()
  await expect(page.getByText("Up to Chapter 2", { exact: true })).toBeVisible()
  await page.getByRole("textbox", { name: inputLabel }).fill("Where does Nora last appear?")
  await page.getByRole("button", { name: "Ask", exact: true }).click()
  await expect(page.getByRole("link", { name: "Jump to chapter 2" })).toBeVisible()
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.screenshot({ path: testInfo.outputPath("ask-answer-light.png"), fullPage: true })
  expect(errors).toEqual([])
})

test("context failures disable submission and retry preserves a drafted question", async ({ page }) => {
  let fail = true
  let requests = 0
  await page.route("**/api/v1/reader/book-1/progress", (request) => fail ? request.fulfill({ status: 503, json: {} }) : request.fallback())
  await page.route(api, (request) => { requests++; return request.fallback() })
  await page.goto(route)
  await page.getByRole("textbox", { name: inputLabel }).fill("Where is Nora?")
  await page.getByRole("button", { name: "Retry reading progress" }).waitFor()
  await expect(page.getByRole("button", { name: "Ask", exact: true })).toBeDisabled()
  expect(requests).toBe(0)
  fail = false
  await page.getByRole("button", { name: "Retry reading progress" }).click()
  await expect(page.getByRole("button", { name: "Ask", exact: true })).toBeEnabled()
  await expect(page.getByRole("textbox", { name: inputLabel })).toHaveValue("Where is Nora?")
  await page.getByRole("button", { name: "Ask", exact: true }).click()
  await expect(page.getByRole("link", { name: "Jump to chapter 2" })).toBeVisible()
})

test("interrupted streams retain partial text and the retry uses the original question", async ({ page }) => {
  let fail = true
  const questions: string[] = []
  await page.route(api, (request) => {
    questions.push(request.request().postDataJSON().question)
    return fail ? request.fulfill({ contentType: "text/event-stream", body: `event: delta\ndata: ${JSON.stringify({ content: "The gate was open when" })}\n\n` }) : request.fallback()
  })
  await page.goto(route)
  await expect(page.getByText("Up to Chapter 2", { exact: true })).toBeVisible()
  await page.getByRole("textbox", { name: inputLabel }).fill("Who opened the gate?")
  await page.getByRole("button", { name: "Ask", exact: true }).click()
  await expect(page.getByText("The gate was open when", { exact: true })).toBeVisible()
  await expect(page.getByRole("textbox", { name: inputLabel })).toHaveValue("Who opened the gate?")
  await expect(page.getByText(/Answer · Chapters 1-2 · Incomplete/)).toBeVisible()
  fail = false
  await page.getByRole("button", { name: "Retry question" }).click()
  await expect(page.getByRole("link", { name: "Jump to chapter 2" })).toBeVisible()
  expect(questions).toEqual(["Who opened the gate?", "Who opened the gate?"])
})

test("stopping a pending answer keeps the question and prevents parallel requests", async ({ page }) => {
  let release: (() => void) | undefined
  let requests = 0
  const hold = new Promise<void>((resolve) => { release = resolve })
  await page.route(api, async (request) => { requests++; await hold; await request.fulfill({ contentType: "text/event-stream", body: "" }).catch(() => {}) })
  await page.goto(route)
  await expect(page.getByText("Up to Chapter 2", { exact: true })).toBeVisible()
  await page.getByRole("textbox", { name: inputLabel }).fill("Who carries the key?")
  await page.getByRole("button", { name: "Ask", exact: true }).click()
  await expect(page.getByRole("button", { name: "Asking...", exact: true })).toBeDisabled()
  await expect.poll(() => requests).toBe(1)
  await page.getByRole("button", { name: "Stop answer" }).click()
  await expect(page.getByRole("textbox", { name: inputLabel })).toHaveValue("Who carries the key?")
  await expect(page.getByRole("button", { name: "Retry question" })).toBeEnabled()
  release?.()
  expect(requests).toBe(1)
})

test("suggestions edit the question, recent questions persist and can be cleared", async ({ page }) => {
  let requests = 0
  await page.route(api, (request) => { requests++; return request.fallback() })
  await page.goto(route)
  await expect(page.getByText("Up to Chapter 2", { exact: true })).toBeVisible()
  await page.getByText("Suggested questions", { exact: true }).click()
  await page.getByRole("button", { name: "Use question: When did this character last appear?" }).click()
  expect(requests).toBe(0)
  await expect(page.getByRole("textbox", { name: inputLabel })).toBeFocused()
  await page.getByRole("textbox", { name: inputLabel }).fill("When did Nora last appear?")
  await page.getByRole("button", { name: "Ask", exact: true }).click()
  await expect(page.getByRole("link", { name: "Jump to chapter 2" })).toBeVisible()
  await page.reload()
  await page.getByText("Recent questions on this device (1)", { exact: true }).click()
  await page.getByRole("button", { name: "When did Nora last appear?", exact: true }).click()
  await expect(page.getByRole("textbox", { name: inputLabel })).toHaveValue("When did Nora last appear?")
  await page.getByRole("button", { name: "Clear recent questions" }).click()
  await expect(page.getByText("Recent questions on this device (1)", { exact: true })).toHaveCount(0)
  expect(requests).toBe(1)
})

test("long answers and unavailable citations do not overflow or fabricate links", async ({ page }, testInfo) => {
  await page.route(api, (request) => request.fulfill({ contentType: "text/event-stream", body: `event: done\ndata: ${JSON.stringify({ answer: "Unbroken".repeat(50), citations: [{ chapter_num: 99, chapter_title: "Future chapter", excerpt: "A future reveal", source_type: "passage" }, { chapter_num: 0, chapter_title: null, excerpt: "Missing source", source_type: "summary" }] })}\n\n` }))
  await page.setViewportSize({ width: 390, height: 1000 })
  await page.goto(route)
  await expect(page.getByText("Up to Chapter 2", { exact: true })).toBeVisible()
  await page.getByRole("textbox", { name: inputLabel }).fill("What does the clue mean?")
  await page.getByRole("button", { name: "Ask", exact: true }).click()
  await expect(page.getByText(/Some returned sources fall outside this chapter scope/)).toBeVisible()
  await expect(page.getByText("A future reveal", { exact: true })).toHaveCount(0)
  await expect(page.getByRole("link", { name: /Jump to chapter/ })).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.screenshot({ path: testInfo.outputPath("ask-long-mobile.png"), fullPage: true })
})

test("missing manuscript and empty progress recover without sending a question", async ({ page }) => {
  let fail = true
  await page.route("**/api/v1/books/book-1", (request) => fail ? request.fulfill({ status: 503, json: {} }) : request.fallback())
  await page.route("**/api/v1/reader/book-1/progress", (request) => request.fulfill({ json: { current_chapter: 0, progress_pct: 0 } }))
  await page.goto(route)
  await page.getByRole("button", { name: "Retry manuscript" }).waitFor()
  await page.getByRole("textbox", { name: inputLabel }).fill("Where is the gate?")
  await expect(page.getByRole("button", { name: "Ask", exact: true })).toBeDisabled()
  fail = false
  await page.getByRole("button", { name: "Retry manuscript" }).click()
  await expect(page.getByRole("link", { name: "Choose a chapter", exact: true })).toHaveAttribute("href", "/sky-of-ash--book-1/chapters")
  await expect(page.getByRole("button", { name: "Ask", exact: true })).toBeDisabled()
})

test("blocked recent-question storage does not prevent answers", async ({ page }) => {
  const errors: string[] = []
  page.on("pageerror", (error) => errors.push(error.message))
  await page.addInitScript(() => {
    const original = Storage.prototype.setItem
    Storage.prototype.setItem = function(key, value) { if (key.startsWith("lorevia-ask-recent")) throw new Error("Storage unavailable"); return original.call(this, key, value) }
  })
  await page.goto(route)
  await expect(page.getByText("Up to Chapter 2", { exact: true })).toBeVisible()
  await page.getByRole("textbox", { name: inputLabel }).fill("Where does Nora appear?")
  await page.getByRole("button", { name: "Ask", exact: true }).click()
  await expect(page.getByRole("link", { name: "Jump to chapter 2" })).toBeVisible()
  await expect(page.getByText(/Device storage is unavailable/)).toBeVisible()
  await page.getByRole("button", { name: "View latest answer", exact: true }).click()
  await expect(page.locator("article").last()).toBeFocused()
  expect(errors).toEqual([])
})

test("rate limits and empty final responses preserve retryable questions", async ({ page }) => {
  let limited = true
  await page.route(api, (request) => request.fulfill(limited ? { status: 429, json: { detail: "Too many questions" } } : { contentType: "text/event-stream", body: `event: done\ndata: ${JSON.stringify({ answer: "", citations: [] })}\n\n` }))
  await page.goto(route)
  await expect(page.getByText("Up to Chapter 2", { exact: true })).toBeVisible()
  await page.getByRole("textbox", { name: inputLabel }).fill("Where is the gate?")
  await page.getByRole("button", { name: "Ask", exact: true }).click()
  await expect(page.getByRole("main").getByRole("alert")).toContainText("Too many questions")
  await expect(page.getByRole("textbox", { name: inputLabel })).toHaveValue("Where is the gate?")
  limited = false
  await page.getByRole("button", { name: "Retry question" }).click()
  await expect(page.getByRole("main").getByRole("alert")).toContainText("The answer did not finish")
  await expect(page.getByRole("textbox", { name: inputLabel })).toHaveValue("Where is the gate?")
})
