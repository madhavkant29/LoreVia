import { expect, test, type Page } from "@playwright/test"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"
const path = "/sky-of-ash--book-1/advisor"
const api = "**/api/v1/intelligence/*/advisor/message-stream"
const checksApi = "**/api/v1/intelligence/*/advisor/suggestions"
const scanApi = "**/api/v1/intelligence/*/advisor/suggestions/scan"
const jobApi = "**/api/v1/intelligence/*/advisor/suggestions/jobs/*"
const result = { reply: "Nora can seed the oath earlier.", intent: "general", response_type: "standard", retrieved_passages: [{ chapter_num: 2, chapter_title: "The Ember Gate", excerpt: "Nora crossed the gate.", relevance: .9 }], cached: false }
const checks = { suggestions: [{ id: "thread-1", type: "dropped_thread", severity: "warning", title: "The missing oath", description: "The oath is introduced after Nora uses it.", chapter_ref: 2, action_label: "Ask about the oath", ask_prompt: "Where should I introduce the oath?", source: "heuristic" }], total: 1, book_title: "Sky of Ash", meta: { character_count: 4, state_count: 3, open_thread_count: 1, clue_count: 2, relationship_count: 2, world_element_count: 1, heuristic_count: 1, fallback_applied: false, proactive_audit_applied: true, scan_basis: ["characters", "character_states", "plot_threads"], data_gaps: [], audit_summary: "The oath needs an earlier setup." } }
const input = (page: Page) => page.getByRole("textbox", { name: "Advisor question", exact: true })
async function send(page: Page, question = "Where should the oath appear?") { await input(page).fill(question); await page.getByRole("button", { name: "Send", exact: true }).click() }
const stream = (value: unknown = result) => `event: done\ndata: ${JSON.stringify(value)}\n\n`

test.beforeEach(async ({ page }) => {
  await installMockApi(page)
  await page.addInitScript(() => { if (!localStorage.getItem("lorevia-preferences")) localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 })); document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax" })
  await page.route(api, (route) => route.fulfill({ contentType: "text/event-stream", body: stream() }))
  await page.route(checksApi, (route) => route.fulfill({ json: checks }))
})

test("advisor modes stay readable at four widths and both themes", async ({ page }, info) => {
  const errors: string[] = []; page.on("pageerror", (error) => errors.push(error.message))
  await page.goto(path); await expect(input(page)).toBeEnabled()
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
    await page.screenshot({ path: info.outputPath(`advisor-${width}.png`), fullPage: true, animations: "disabled" })
  }
  await page.getByRole("tab", { name: "Ask advisor", exact: true }).focus(); await page.keyboard.press("ArrowRight")
  await expect(page.getByRole("tab", { name: "Recommended checks" })).toBeFocused()
  await expect(page.getByText("The missing oath", { exact: true })).toBeVisible()
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.screenshot({ path: info.outputPath("checks-dark.png"), fullPage: true, animations: "disabled" })
  await page.getByRole("button", { name: "Help", exact: true }).focus(); await page.keyboard.press("Enter")
  await expect(page.getByRole("dialog")).toBeVisible(); await page.keyboard.press("Escape")
  await page.evaluate(() => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "light" }, version: 0 })))
  await page.reload(); await page.getByRole("tab", { name: "Recommended checks" }).click()
  await expect(page.locator("html")).not.toHaveClass(/dark/)
  await page.screenshot({ path: info.outputPath("checks-light.png"), fullPage: true, animations: "disabled" })
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  expect(errors).toEqual([])
})

test("answers retain separate evidence, complete world context and verified chapter links", async ({ page }, info) => {
  let calls = 0
  const requests: { messages: { role: string; content: string }[] }[] = []
  await page.route(api, (route) => { calls++; requests.push(route.request().postDataJSON()); return route.fulfill({ contentType: "text/event-stream", body: stream(calls === 1 ? { ...result, reply: "First answer. " + "LongText".repeat(50), world_analysis: { mode: "gap_detection", answer: "The old oath binds the keeper.", logic_alerts: Array.from({ length: 5 }, (_, i) => ({ title: `Rule ${i + 1}`, description: "Name the keeper." })), suggestions: [], citations: [], simulation_steps: ["Nora arrives", "The keeper speaks"] } } : { ...result, reply: "Second answer.", retrieved_passages: [] }) }) })
  await page.goto(path); await send(page)
  await page.getByText("Answer evidence (1 passage)", { exact: true }).click()
  await expect(page.getByRole("link", { name: "Open chapter 2", exact: true })).toHaveAttribute("href", "/sky-of-ash--book-1/manuscript?chapter=2")
  await page.getByText("Worldbuilding context", { exact: true }).click(); await expect(page.getByText("Rule 5", { exact: true })).toBeVisible()
  await send(page, "What comes next?")
  await expect(page.locator(".advisor-answer").last()).toContainText("Second answer.")
  await expect(page.getByText("Nora crossed the gate.", { exact: true })).toBeVisible()
  await page.getByText("Answer evidence (0 passages)", { exact: true }).click()
  await expect(page.getByText(/No manuscript excerpts were supplied/)).toBeVisible()
  expect(requests[1].messages).toHaveLength(3)
  await page.setViewportSize({ width: 390, height: 1000 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  await page.getByRole("button", { name: "Latest answer", exact: true }).click(); await expect(page.locator(".advisor-answer").last()).toBeFocused()
  await page.locator(".advisor-answer").last().evaluate((el) => el.scrollIntoView({ block: "start", behavior: "instant" }))
  await page.screenshot({ path: info.outputPath("answer-mobile.png"), animations: "disabled" })
  expect(await criticalAccessibilityViolations(page)).toEqual([])
})

test("failed streams retain drafts and partial answers without sending failures as history", async ({ page }, info) => {
  let fail = true; const payloads: unknown[] = []
  await page.route(api, (route) => { payloads.push(route.request().postDataJSON()); return route.fulfill({ contentType: "text/event-stream", body: fail ? 'event: delta\ndata: {"content":"A partial answer"}\n\n' : stream() }) })
  await page.goto(path); await send(page)
  await expect(page.getByText("A partial answer", { exact: true })).toBeVisible()
  await expect(input(page)).toHaveValue("Where should the oath appear?")
  await expect(page.getByText(/The answer did not finish/)).toBeVisible()
  await expect(page.locator("form").getByRole("status")).toContainText("The last answer is incomplete")
  await page.setViewportSize({ width: 390, height: 1000 })
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }))
  await page.screenshot({ path: info.outputPath("partial-answer-mobile.png"), fullPage: true, animations: "disabled" })
  fail = false; await page.getByRole("button", { name: "Retry question 1", exact: true }).click()
  await expect(page.locator(".advisor-answer").last()).toContainText("Answered")
  expect(payloads[0]).toEqual(payloads[1])
})

test("stop preserves the question and blocks duplicate sends", async ({ page }) => {
  let release!: () => void; let calls = 0
  const held = new Promise<void>((resolve) => { release = resolve })
  await page.route(api, async (route) => { calls++; await held; await route.fulfill({ contentType: "text/event-stream", body: stream() }).catch(() => {}) })
  await page.goto(path); await send(page)
  await expect.poll(() => calls).toBe(1)
  await expect(page.getByRole("button", { name: "Send", exact: true })).toBeDisabled()
  await page.getByRole("button", { name: "Stop waiting" }).click()
  await expect(input(page)).toHaveValue("Where should the oath appear?")
  await expect(page.getByText(/Waiting stopped/)).toBeVisible(); release()
})

test("drafts survive tab switches, IME composition and declined replacement or navigation", async ({ page }) => {
  await page.goto(path); await input(page).fill("Keep my question")
  await input(page).dispatchEvent("keydown", { key: "Enter", code: "Enter", isComposing: true })
  await expect(page.locator(".advisor-answer")).toHaveCount(0)
  await page.getByRole("tab", { name: "Recommended checks" }).click()
  page.once("dialog", (dialog) => dialog.dismiss()); await page.getByRole("button", { name: "Ask about the oath" }).click()
  await page.getByRole("tab", { name: "Ask advisor", exact: true }).click(); await expect(input(page)).toHaveValue("Keep my question")
  page.once("dialog", (dialog) => dialog.dismiss()); await page.getByRole("link", { name: "LoreVia Book overview Story advisor", exact: true }).click()
  await expect(page).toHaveURL(new RegExp(path + "$"))
  await input(page).fill("x".repeat(8001)); await page.getByRole("button", { name: "Send", exact: true }).click()
  await expect(page.locator("#advisor-input-error")).toContainText("8,000")
})

test("checks recover initial errors, retain previous findings and restore hidden choices", async ({ page }) => {
  let fail = true
  await page.route(checksApi, (route) => fail ? route.fulfill({ status: 503, json: {} }) : route.fulfill({ json: checks }))
  await page.goto(path); await page.getByRole("tab", { name: "Recommended checks" }).click()
  await expect(page.getByText(/Recommended checks could not be loaded/)).toBeVisible()
  await expect(page.getByText("No active scan findings.", { exact: false })).toHaveCount(0)
  fail = false; await page.getByRole("button", { name: "Retry loading checks" }).click()
  await expect(page.getByText("The missing oath", { exact: true })).toBeVisible()
  fail = true; await page.getByRole("button", { name: "Reload checks", exact: true }).click()
  await expect(page.getByText(/Recommended checks could not be loaded/)).toBeVisible()
  await expect(page.getByText("The missing oath", { exact: true })).toBeVisible()
  await page.getByRole("button", { name: "Mark as intentional", exact: true }).click()
  await expect(page.getByText(/All current checks are hidden/)).toBeVisible()
  await page.getByText(/Hidden checks \(1 in this report\)/).click()
  await page.getByRole("button", { name: "Restore The missing oath", exact: true }).click()
  await expect(page.getByText("The missing oath", { exact: true })).toBeVisible()
  await page.getByRole("button", { name: "Dismiss", exact: true }).click()
  fail = false; await page.reload(); await page.getByRole("tab", { name: "Recommended checks" }).click()
  await expect(page.getByText(/All current checks are hidden/)).toBeVisible()
  await page.getByText(/Hidden checks \(1 in this report\)/).click(); await page.getByRole("button", { name: "Restore all hidden checks" }).click()
  await expect(page.getByText("The missing oath", { exact: true })).toBeVisible()
})

test("scan status interruption resumes the same job and survives reload", async ({ page }) => {
  let starts = 0; let fail = true; let complete = false
  await page.route(scanApi, (route) => { starts++; return route.fulfill({ json: { job_id: "scan-1", cached: false, status: "queued" } }) })
  await page.route(jobApi, (route) => fail ? route.fulfill({ status: 503, json: {} }) : route.fulfill({ json: { job_id: "scan-1", status: complete ? "complete" : "running", result: complete ? checks : null } }))
  await page.goto(path); await page.getByRole("tab", { name: "Recommended checks" }).click(); await page.getByRole("button", { name: "Refresh checks", exact: true }).click()
  await expect(page.getByText(/scan status could not be checked/)).toBeVisible()
  await expect(page.getByText("The missing oath", { exact: true })).toBeVisible()
  await page.getByRole("button", { name: "Stop checking", exact: true }).click()
  await expect(page.getByText(/Status checking paused. Server/)).toBeVisible()
  fail = false; await page.reload(); await page.getByRole("tab", { name: "Recommended checks" }).click()
  await expect(page.getByText("Checking extracted story evidence…", { exact: true })).toBeVisible()
  complete = true; await page.getByRole("button", { name: "Resume checking", exact: true }).click()
  await expect(page.getByText("Checks updated.", { exact: true })).toBeVisible()
  expect(starts).toBe(1)
})

test("cached scan failures stay errors and an empty report does not imply a clean manuscript", async ({ page }) => {
  await page.route(scanApi, (route) => route.fulfill({ json: { cached: true, job_id: "cached" } }))
  await page.goto(path); await page.getByRole("tab", { name: "Recommended checks" }).click()
  await expect(page.getByText("The missing oath", { exact: true })).toBeVisible()
  await page.route(checksApi, (route) => route.fulfill({ status: 503, json: {} }))
  await page.getByRole("button", { name: "Refresh checks", exact: true }).click()
  await expect(page.getByText(/Recommended checks could not be loaded/)).toBeVisible()
  await expect(page.getByText("Latest available checks loaded.", { exact: true })).toHaveCount(0)
  await page.route(checksApi, (route) => route.fulfill({ json: { ...checks, suggestions: [], total: 0 } }))
  await page.getByRole("button", { name: "Retry loading checks" }).click()
  await expect(page.getByText(/does not confirm the manuscript is free/)).toBeVisible()
})

test("expired scan jobs unlock recovery without automatically starting another scan", async ({ page }) => {
  let starts = 0
  await page.route(scanApi, (route) => { starts++; return route.fulfill({ json: { job_id: "expired", cached: false, status: "queued" } }) })
  await page.route(jobApi, (route) => route.fulfill({ status: 404, json: { detail: "suggestion scan job not found" } }))
  await page.goto(path); await page.getByRole("tab", { name: "Recommended checks" }).click()
  await page.getByRole("button", { name: "Refresh checks", exact: true }).click()
  await expect(page.getByText(/This scan could no longer be found/)).toBeVisible()
  await expect(page.getByRole("button", { name: "Refresh checks", exact: true })).toBeEnabled()
  await expect(page.getByRole("button", { name: "Resume checking", exact: true })).toHaveCount(0)
  expect(starts).toBe(1)
})

test("note saving prevents parallel writes and recovers the original failed payload", async ({ page }) => {
  let fail = true; let calls = 0; let release!: () => void
  const held = new Promise<void>((resolve) => { release = resolve })
  const payloads: unknown[] = []
  await page.route("**/api/v1/books/*/notes/vault", async (route) => {
    if (route.request().method() !== "PUT") return route.fallback()
    calls++; payloads.push(route.request().postDataJSON())
    if (fail) { await held; return route.fulfill({ status: 503, json: {} }) }
    return route.fulfill({ json: { path: "Story Advisor/Advisor insight.md" } })
  })
  await page.goto(path); await send(page)
  await page.getByRole("button", { name: "Save to notes", exact: true }).click()
  await expect.poll(() => calls).toBe(1)
  await expect(page.getByRole("button", { name: "Save to notes", exact: true })).toBeDisabled()
  await page.getByRole("tab", { name: "Recommended checks" }).click()
  await expect(page.getByRole("button", { name: "Save note", exact: true })).toBeDisabled()
  release(); await expect(page.getByText(/Note saving could not be confirmed/)).toBeVisible()
  fail = false; await page.getByRole("button", { name: "Retry saving note", exact: true }).click()
  await expect(page.getByText("Saved to Story Advisor.", { exact: true })).toBeVisible()
  expect(payloads[1]).toEqual(payloads[0]); expect(calls).toBe(2)
})

test("copy works, denied copying has a manual fallback, and clearing keeps the draft", async ({ page, context }) => {
  await context.grantPermissions(["clipboard-read", "clipboard-write"])
  await page.goto(path); await send(page)
  await page.getByRole("button", { name: "Copy answer 1", exact: true }).click()
  await expect(page.getByText("Answer copied.", { exact: true })).toBeVisible()
  expect((await page.evaluate(() => navigator.clipboard.readText())).replace(/\r\n/g, "\n")).toBe(`Where should the oath appear?\n\n${result.reply}`)
  await page.evaluate(() => Object.defineProperty(navigator, "clipboard", { value: { writeText: () => Promise.reject(new Error("Denied")) }, configurable: true }))
  await page.getByRole("button", { name: "Copy answer 1", exact: true }).click()
  await expect(page.getByRole("textbox", { name: "Copy text for answer 1" })).toHaveValue(`Where should the oath appear?\n\n${result.reply}`)
  await input(page).fill("Next question")
  page.once("dialog", (dialog) => dialog.dismiss()); await page.getByRole("button", { name: "Clear conversation" }).click()
  await expect(page.locator(".advisor-answer")).toHaveCount(1)
  page.once("dialog", (dialog) => dialog.accept()); await page.getByRole("button", { name: "Clear conversation" }).click()
  await expect(page.locator(".advisor-answer")).toHaveCount(0); await expect(input(page)).toHaveValue("Next question")
})

test("project and chapter failures are recoverable and free accounts retain their question access", async ({ page }) => {
  let fail = true
  await page.route("**/api/v1/books/book-1", (route) => fail ? route.fulfill({ status: 503, json: {} }) : route.fallback())
  await page.goto(path)
  await expect(page.getByText("Project context could not be loaded. Check your access or try again.", { exact: true })).toBeVisible()
  await expect(input(page)).toHaveCount(0)
  fail = false; await page.getByRole("button", { name: "Retry project context" }).click()
  await expect(input(page)).toBeEnabled()
  await page.route("**/api/v1/reader/book-1/chapters**", (route) => route.fulfill({ status: 503, json: {} }))
  await send(page); await page.getByText("Answer evidence (1 passage)", { exact: true }).click()
  await expect(page.getByRole("button", { name: "Retry source chapters" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Open chapter 2" })).toHaveCount(0)
  await page.unroute("**/api/v1/reader/book-1/chapters**")
  await page.getByRole("button", { name: "Retry source chapters" }).click()
  await expect(page.getByRole("link", { name: "Open chapter 2" })).toBeVisible()
  await installMockApi(page, { userTier: "free" })
  await page.route(api, (route) => route.fulfill({ contentType: "text/event-stream", body: stream() }))
  await page.reload()
  await expect(page.getByText(/Free accounts include one Story Advisor turn per week/)).toBeVisible()
  await expect(page.getByRole("tab", { name: "Recommended checks" })).toHaveCount(0)
  await send(page); await expect(page.locator(".advisor-answer")).toContainText("Answered")
  await expect(page.getByRole("button", { name: "Save to notes", exact: true })).toHaveCount(0)
})

test("a scan observation timeout resumes its existing job", async ({ page }) => {
  let starts = 0; let complete = false
  await page.clock.install()
  await page.route(scanApi, (route) => { starts++; return route.fulfill({ json: { job_id: "slow-scan", cached: false, status: "queued" } }) })
  await page.route(jobApi, (route) => route.fulfill({ json: { job_id: "slow-scan", status: complete ? "complete" : "running", result: complete ? checks : null } }))
  await page.goto(path); await page.getByRole("tab", { name: "Recommended checks" }).click()
  await page.getByRole("button", { name: "Refresh checks", exact: true }).click()
  await expect(page.getByText("Checking extracted story evidence…", { exact: true })).toBeVisible()
  await page.clock.fastForward(241000)
  await expect(page.getByText(/Status checking paused after four minutes/)).toBeVisible()
  await expect(page.getByRole("button", { name: "Refresh checks", exact: true })).toBeDisabled()
  complete = true; await page.getByRole("button", { name: "Resume checking", exact: true }).click()
  await expect(page.getByText("Checks updated.", { exact: true })).toBeVisible()
  expect(starts).toBe(1)
})

test("empty answers remain incomplete and browser storage failures are explained", async ({ page }) => {
  await page.addInitScript(() => {
    const getItem = Storage.prototype.getItem; const setItem = Storage.prototype.setItem
    Storage.prototype.getItem = function(key) { if (key.startsWith("lorevia-advisor-")) throw new Error("Unavailable"); return getItem.call(this, key) }
    Storage.prototype.setItem = function(key, value) { if (key.startsWith("lorevia-advisor-")) throw new Error("Unavailable"); return setItem.call(this, key, value) }
  })
  await page.route(api, (route) => route.fulfill({ contentType: "text/event-stream", body: stream({ ...result, reply: " " }) }))
  await page.goto(path); await send(page)
  await expect(page.getByText(/The answer did not finish/)).toBeVisible()
  await expect(input(page)).toHaveValue("Where should the oath appear?")
  await page.getByRole("tab", { name: "Recommended checks" }).click()
  await expect(page.getByText(/Browser storage is unavailable/)).toBeVisible()
  await page.getByRole("button", { name: "Dismiss", exact: true }).click()
  await expect(page.getByText(/All current checks are hidden/)).toBeVisible()
})

test("existing hidden checks migrate once and restored findings stay restored", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("lorevia-advisor-scan:sky-of-ash--book-1", JSON.stringify({ dismissed: ["thread-1"], intentional: [] })))
  await page.goto(path); await page.getByRole("tab", { name: "Recommended checks" }).click()
  await expect(page.getByText(/All current checks are hidden/)).toBeVisible()
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem("lorevia-advisor-scan:user-1:book-1") || "{}").dismissed)).toEqual(["thread-1"])
  await page.getByText(/Hidden checks \(1 in this report\)/).click()
  await page.getByRole("button", { name: "Restore all hidden checks" }).click()
  await page.reload(); await page.getByRole("tab", { name: "Recommended checks" }).click()
  await expect(page.getByText("The missing oath", { exact: true })).toBeVisible()
  await expect(page.getByText(/All current checks are hidden/)).toHaveCount(0)
})
