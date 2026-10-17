import { expect, test, type Page } from "@playwright/test"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"
const path = "/series/series-1/ask"
const api = "**/api/v1/intelligence/series/series-1/advisor/message-stream"
const input = (page: Page) => page.getByRole("textbox", { name: "Question about Ash Cycle" })
const answer = { reply: "Nora keeps the gate open.", intent: "general", response_type: "standard", retrieved_passages: [], cached: false }
const stream = (reply = answer) => `event: delta\ndata: ${JSON.stringify({ content: reply.reply })}\n\nevent: done\ndata: ${JSON.stringify(reply)}\n\n`
async function ask(page: Page, question = "What changes for Nora?") { await input(page).fill(question); await page.getByRole("button", { name: "Ask", exact: true }).click() }

test.beforeEach(async ({ page }) => {
  await installMockApi(page)
  await page.addInitScript(() => { localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 })); document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax" })
})

test("series ask reads clearly at four widths and both themes", async ({ page }, info) => {
  const errors: string[] = []; page.on("pageerror", (error) => errors.push(error.message))
  await page.route(api, (route) => route.fulfill({ contentType: "text/event-stream", body: stream({ ...answer, reply: `## Across the series\n\n${"Nora returns to the gate and questions her earlier promise. ".repeat(12)}\n\n${"Longword".repeat(30)}` }) }))
  await page.goto(path)
  await expect(input(page)).toBeVisible()
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    if (width < 1024) await expect.poll(() => page.locator("aside").first().evaluate((el) => el.getBoundingClientRect().right)).toBeLessThanOrEqual(0)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
    await page.screenshot({ path: info.outputPath(`series-ask-${width}.png`), fullPage: true, animations: "disabled" })
  }
  await ask(page)
  await expect(page.getByText("No chapter excerpts were supplied with this answer.")).toBeVisible()
  await page.getByRole("button", { name: "Latest answer" }).click()
  await expect(page.locator(".series-answer")).toBeFocused()
  await expect(page.getByRole("heading", { name: "Across the series" })).toBeVisible()
  await page.locator(".series-answer").evaluate((element) => element.scrollIntoView({ block: "start", behavior: "instant" }))
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.screenshot({ path: info.outputPath("answer-dark.png"), animations: "disabled" })
  await page.getByRole("button", { name: "Toggle theme", exact: true }).click()
  await expect(page.locator("html")).not.toHaveClass(/dark/)
  await page.screenshot({ path: info.outputPath("answer-light.png"), animations: "disabled" })
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.getByRole("button", { name: "Help", exact: true }).focus(); await page.keyboard.press("Enter")
  await expect(page.getByRole("dialog")).toBeVisible(); await page.keyboard.press("Escape")
  expect(errors).toEqual([])
})

test("series context retries failures and distinguishes empty and missing series", async ({ page }) => {
  let fail = true
  await page.route("**/api/v1/books/series?*", (route) => fail ? route.fulfill({ status: 503, json: {} }) : route.fallback())
  await page.goto(path)
  await expect(page.getByText("Series context could not be loaded. Check your access or try again.")).toBeVisible()
  await expect(page.getByText("Series not found", { exact: true })).toHaveCount(0)
  fail = false; await page.getByRole("button", { name: "Retry series context" }).click()
  await expect(input(page)).toBeVisible()
  await page.goto("/series/series-2/ask")
  await expect(page.getByRole("heading", { name: "Add a project to begin" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Ask", exact: true })).toHaveCount(0)
  await page.goto("/series/missing/ask")
  await expect(page.getByRole("heading", { name: "Series not found" })).toBeVisible()
})

test("series context follows pagination to the selected series", async ({ page }) => {
  const offsets: string[] = []
  await page.route("**/api/v1/books/series?*", (route) => {
    const offset = new URL(route.request().url()).searchParams.get("offset") || "0"; offsets.push(offset)
    return offset === "0" ? route.fulfill({ json: { items: [{ id: "other", name: "Other", books: [] }], limit: 100, has_more: true } }) : route.fallback()
  })
  await page.goto(path); await expect(input(page)).toBeVisible(); expect(offsets).toEqual(["0", "100"])
})

test("interrupted answers keep partial text and retry excludes failed exchanges", async ({ page }) => {
  let fail = true; const payloads: unknown[] = []
  await page.route(api, (route) => { payloads.push(route.request().postDataJSON()); return route.fulfill({ contentType: "text/event-stream", body: fail ? 'event: delta\ndata: {"content":"Nora was about to"}\n\n' : stream() }) })
  await page.goto(path); await ask(page)
  await expect(page.getByText("Nora was about to", { exact: true })).toBeVisible()
  await expect(input(page)).toHaveValue("What changes for Nora?")
  await expect(page.getByText(/Question 1 · Incomplete/)).toBeVisible()
  fail = false; await page.getByRole("button", { name: "Retry question 1" }).click()
  await expect(page.getByText(answer.reply, { exact: true })).toBeVisible()
  expect(payloads).toEqual([{ messages: [{ role: "user", content: "What changes for Nora?" }] }, { messages: [{ role: "user", content: "What changes for Nora?" }] }])
})

test("stop prevents parallel requests and restores the pending question", async ({ page }) => {
  let release!: () => void; let calls = 0
  const held = new Promise<void>((resolve) => { release = resolve })
  await page.route(api, async (route) => { calls++; await held; await route.fulfill({ contentType: "text/event-stream", body: stream() }).catch(() => {}) })
  await page.goto(path); await ask(page)
  await expect(page.getByRole("button", { name: "Ask", exact: true })).toBeDisabled()
  await expect(input(page)).toBeDisabled()
  await expect.poll(() => calls).toBe(1)
  await page.getByRole("button", { name: "Stop waiting" }).click()
  await expect(input(page)).toHaveValue("What changes for Nora?")
  await expect(page.getByText(/Waiting stopped/)).toBeVisible()
  release()
  await expect(page.getByText(answer.reply, { exact: true })).toHaveCount(0)
})

test("draft validation, suggestion replacement, navigation, and clear are guarded", async ({ page }) => {
  await page.goto(path)
  await input(page).fill("x".repeat(8001)); await page.getByRole("button", { name: "Ask", exact: true }).click()
  await expect(page.locator("#series-question-error")).toContainText("8,000")
  await input(page).fill("Keep this draft")
  await page.getByText("Suggested questions", { exact: true }).click()
  page.once("dialog", (dialog) => dialog.dismiss())
  await page.getByRole("button", { name: "What unresolved plot threads remain?" }).click()
  await expect(input(page)).toHaveValue("Keep this draft")
  page.once("dialog", (dialog) => dialog.dismiss()); await page.getByRole("link", { name: "Back to series" }).click()
  await expect(page).toHaveURL(new RegExp(path + "$"))
  await ask(page)
  await expect(page.locator(".series-answer")).toContainText("Answered")
  await input(page).fill("Next draft")
  page.once("dialog", (dialog) => dialog.dismiss()); await page.getByRole("button", { name: "Clear conversation" }).click()
  await expect(page.locator(".series-answer")).toHaveCount(1)
  page.once("dialog", (dialog) => dialog.accept()); await page.getByRole("button", { name: "Clear conversation" }).click()
  await expect(page.locator(".series-answer")).toHaveCount(0); await expect(input(page)).toHaveValue("Next draft")
})

test("copy fallback retains the whole answer and excerpts never invent project links", async ({ page }) => {
  await page.addInitScript(() => Object.defineProperty(navigator, "clipboard", { value: { writeText: () => Promise.reject(new Error("Denied")) } }))
  await page.route(api, (route) => route.fulfill({ contentType: "text/event-stream", body: stream({ ...answer, retrieved_passages: [{ chapter_num: 2, chapter_title: "The oath", excerpt: "The keeper waited.", relevance: 0.9 }] } as typeof answer) }))
  await page.goto(path); await ask(page)
  await page.getByRole("button", { name: "Copy answer 1" }).click()
  await expect(page.getByRole("textbox", { name: "Copy text for answer 1" })).toHaveValue(`What changes for Nora?\n\n${answer.reply}`)
  await page.getByText("Read supplied excerpts", { exact: true }).click()
  await expect(page.getByText("The keeper waited.", { exact: true })).toBeVisible()
  await expect(page.locator(".series-answer a")).toHaveCount(0)
})

test("empty responses and access errors remain retryable failures", async ({ page }) => {
  await page.route(api, (route) => route.fulfill({ contentType: "text/event-stream", body: stream({ ...answer, reply: " " }) }))
  await page.goto(path); await ask(page)
  await expect(page.getByText(/The answer did not finish/)).toBeVisible()
  await page.route(api, (route) => route.fulfill({ status: 403, json: { detail: "forbidden" } }))
  await page.getByRole("button", { name: "Retry question 1" }).click()
  await expect(page.getByText(/cannot ask about this series/)).toBeVisible()
  await expect(input(page)).toHaveValue("What changes for Nora?")
})

test("keyboard composition does not submit and completed follow-ups retain their context", async ({ page, context }) => {
  const payloads: { messages: { role: string; content: string }[] }[] = []
  await context.grantPermissions(["clipboard-read", "clipboard-write"])
  await page.route(api, (route) => { payloads.push(route.request().postDataJSON()); return route.fulfill({ contentType: "text/event-stream", body: stream() }) })
  await page.goto(path); await input(page).fill("Who keeps the gate?")
  await input(page).dispatchEvent("keydown", { key: "Enter", code: "Enter", isComposing: true })
  expect(payloads).toHaveLength(0); await expect(input(page)).toHaveValue("Who keeps the gate?")
  await input(page).press("Enter"); await expect(page.locator(".series-answer")).toContainText("Answered")
  await page.getByRole("button", { name: "Copy answer 1" }).click()
  await expect(page.getByText("Answer copied.", { exact: true })).toBeVisible()
  expect((await page.evaluate(() => navigator.clipboard.readText())).replace(/\r\n/g, "\n")).toBe(`Who keeps the gate?\n\n${answer.reply}`)
  await ask(page, "Why does she stay?")
  await expect(page.locator(".series-answer").last()).toContainText("Answered")
  expect(payloads[1].messages).toEqual([{ role: "user", content: "Who keeps the gate?" }, { role: "assistant", content: answer.reply }, { role: "user", content: "Why does she stay?" }])
})

test("loading context has feedback and free accounts cannot send series questions", async ({ page }) => {
  let release!: () => void
  const held = new Promise<void>((resolve) => { release = resolve })
  await page.route("**/api/v1/books/series?*", async (route) => { await held; await route.fallback() })
  await page.goto(path)
  await expect(page.getByText("Loading series context…", { exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "Ask", exact: true })).toHaveCount(0)
  release(); await expect(input(page)).toBeVisible()
  await installMockApi(page, { userTier: "free" })
  await page.reload()
  await expect(page.getByRole("heading", { name: "Series mode is reserved for paid plans." })).toBeVisible()
  await expect(page.getByRole("link", { name: "View plans" })).toHaveAttribute("href", "/upgrade")
  await expect(page.getByRole("button", { name: "Ask", exact: true })).toHaveCount(0)
})

test("reconnecting does not replace the conversation or discard its draft", async ({ page, context }) => {
  await page.goto(path); await ask(page)
  await expect(page.locator(".series-answer")).toContainText("Answered")
  await input(page).fill("Keep this follow-up")
  await context.setOffline(true)
  await page.route("**/api/v1/books/series?*", (route) => route.fulfill({ status: 503, json: {} }))
  await page.evaluate(() => { window.addEventListener("online", () => { document.documentElement.dataset.seriesAskOnline = "yes" }, { once: true }) })
  await context.setOffline(false)
  await expect(page.locator("html")).toHaveAttribute("data-series-ask-online", "yes")
  await page.getByText("Projects in context (2)", { exact: true }).click()
  await expect(page.getByRole("link", { name: "Sky of Ash", exact: true })).toBeVisible()
  await expect(input(page)).toHaveValue("Keep this follow-up")
  await expect(page.locator(".series-answer")).toContainText("Answered")
  await page.getByRole("button", { name: "Ask", exact: true }).click()
  await expect(page.locator(".series-answer")).toHaveCount(2)
  await expect(page.locator(".series-answer").last()).toContainText("Answered")
})
