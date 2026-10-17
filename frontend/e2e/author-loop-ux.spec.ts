import { expect, test, type Page } from "@playwright/test"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"

const path = "/sky-of-ash--book-1/author-loop"
const base = "/api/v1/books/book-1"
const steps = ["Manuscript", "Characters", "Continuity", "Revision queue", "Invite readers", "Reader feedback"]
const stepIds = ["upload", "bible", "continuity", "issues", "invite", "feedback"]

async function step(page: Page, name: string) {
  const index = steps.indexOf(name)
  if ((page.viewportSize()?.width ?? 1280) < 640) await page.getByRole("combobox", { name: "Workflow step", exact: true }).selectOption(stepIds[index])
  else await page.getByRole("button", { name: `${index + 1} of 6 ${name}`, exact: true }).click()
}

async function installLoop(page: Page) {
  await installMockApi(page, { chapterReports: true })
  await page.addInitScript(() => { if (!localStorage.getItem("lorevia-preferences")) localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 })); document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax" })
  const assignment = (id: string) => ({ id, book_id: "book-1", reader_email: `${id}@example.com`, status_label: "Active", state: "active", scope_kind: "full_book" })
  const feedback = (id: string) => ({ id, kind: "chapter_comment", body: `Clarify the gate rule ${id}`, anchor_text: "The gate opened at midnight.", chapter_number: 2, author_status: "open", author_task_id: null as string | null, created_at: "2026-10-11T10:00:00Z", updated_at: "2026-10-11T10:00:00Z" })
  const round = (id: string) => ({ id, label: `Snapshot ${id}`, created_at: "2026-10-11T10:00:00Z", chapters: [], summary: { word_count: 1000, chapter_count: 3, scene_count: 4, open_finding_count: 2, high_severity_count: 1, open_beta_feedback_count: 1 } })
  const state = { fail: new Set<string>(), calls: [] as { name: string; body: Record<string, unknown> | null }[], assignments: [assignment("reader-1"), assignment("reader-2")], feedback: [feedback("feedback-1"), feedback("feedback-2")], rounds: Array.from({ length: 7 }, (_, index) => round(String(index + 1))) }
  await page.route((url) => url.pathname === base || url.pathname.startsWith(`${base}/`), async (route) => {
    const suffix = new URL(route.request().url()).pathname.slice(base.length)
    const method = route.request().method(); const name = `${method} ${suffix}`
    const body = method === "POST" || method === "PUT" ? route.request().postDataJSON() as Record<string, unknown> | null : null
    state.calls.push({ name, body })
    if (state.fail.has(name)) return route.fulfill({ status: 503, json: { detail: `Temporarily unavailable: ${suffix || "manuscript"}` } })
    if (suffix === "/beta-reads" && method === "GET") return route.fulfill({ json: { items: state.assignments } })
    if (suffix === "/beta-reads" && method === "POST") { const created = { ...assignment(`reader-${state.assignments.length + 1}`), reader_email: String(body?.reader_email) }; state.assignments.unshift(created); return route.fulfill({ json: created }) }
    if (suffix.startsWith("/beta-reads/")) {
      const id = suffix.split("/")[2]
      if (suffix.endsWith("/guest-link")) return route.fulfill({ json: { share_url: `https://example.test/review/${id}`, expires_at: "2026-10-18T10:00:00Z" } })
      if (method === "PUT") { const item = state.feedback.find((entry) => entry.id === suffix.split("/").at(-1))!; item.author_status = String(body?.author_status); item.author_task_id = body?.author_task_id as string | null }
      return route.fulfill({ json: { assignment: state.assignments.find((item) => item.id === id), author_questions: [], feedback_items: id === "reader-1" ? state.feedback : [], feedback_summary: { feedback_item_count: id === "reader-1" ? state.feedback.length : 0, confusing_count: 1, answer_count: 0 } } })
    }
    if (suffix === "/revision-rounds") {
      if (method === "POST") { const saved = { ...round(String(state.rounds.length + 1)), label: String(body?.label) }; state.rounds.push(saved); return route.fulfill({ json: saved }) }
      return route.fulfill({ json: { items: state.rounds } })
    }
    if (suffix.startsWith("/revision-rounds/")) return route.fulfill({ json: { base_round_id: suffix.split("/")[2], changed_chapters: [2], added_chapters: [4], removed_chapters: [1], chapter_delta: 0, word_count_delta: -120, scene_count_delta: -1, open_finding_delta: -2, open_beta_feedback_delta: -1 } })
    return route.fallback()
  })
  return state
}

test("revision workflow remains readable in every step, four widths and both themes", async ({ page }, info) => {
  test.setTimeout(120_000)
  await installLoop(page); const errors: string[] = []; page.on("pageerror", (error) => errors.push(error.message))
  await page.goto(path); await expect(page.getByRole("heading", { name: "Current manuscript", exact: true })).toBeVisible()
  await step(page, "Revision queue"); await expect(page.getByRole("heading", { name: "Revision snapshots", exact: true })).toBeVisible()
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 }); expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
    await page.screenshot({ path: info.outputPath(`workflow-${width}.png`), fullPage: true, animations: "disabled" })
  }
  for (const name of steps) { await step(page, name); await expect(page.getByRole("button", { name: "Refresh this step", exact: true })).toBeEnabled(); expect(await criticalAccessibilityViolations(page)).toEqual([]) }
  await page.screenshot({ path: info.outputPath("workflow-feedback-mobile.png"), fullPage: true, animations: "disabled" })
  await step(page, "Manuscript"); await page.getByRole("button", { name: "Open upload tools", exact: true }).click()
  await page.getByRole("button", { name: "Upload file", exact: true }).click()
  await expect(page.locator('input[type="file"]').first()).toBeAttached()
  await page.screenshot({ path: info.outputPath("workflow-upload-mobile.png"), fullPage: true, animations: "disabled" })
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.getByRole("button", { name: "Hide upload tools", exact: true }).click()
  await page.evaluate(() => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "light" }, version: 0 }))); await page.reload()
  for (const name of ["Revision queue", "Invite readers", "Reader feedback"]) { await step(page, name); await page.screenshot({ path: info.outputPath(`workflow-light-${name.replaceAll(" ", "-")}.png`), fullPage: true, animations: "disabled" }); expect(await criticalAccessibilityViolations(page)).toEqual([]) }
  await page.getByRole("button", { name: "Help", exact: true }).click(); await expect(page.getByRole("dialog")).toBeVisible(); await page.keyboard.press("Escape")
  expect(errors).toEqual([])
})

test("revision workflow retries failed step data without showing false empty states", async ({ page }) => {
  const state = await installLoop(page); state.fail.add("GET "); await page.goto(path)
  await expect(page.getByRole("button", { name: "Retry manuscript", exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "Open upload tools", exact: true })).not.toBeVisible()
  state.fail.clear(); await page.getByRole("button", { name: "Retry manuscript", exact: true }).click()
  await expect(page.getByRole("heading", { name: "Current manuscript", exact: true })).toBeVisible()
  state.fail.add("GET /characters"); await step(page, "Characters")
  await expect(page.getByRole("button", { name: "Retry characters", exact: true })).toBeVisible(); await expect(page.getByText("No character profiles are available yet.", { exact: true })).not.toBeVisible()
  state.fail.clear(); await page.getByRole("button", { name: "Retry characters", exact: true }).click(); await expect(page.getByText("Gregor", { exact: true }).first()).toBeVisible()
  state.fail.add("GET /beta-reads"); await step(page, "Reader feedback"); await expect(page.getByRole("button", { name: "Retry reader assignments", exact: true })).toBeVisible()
  state.fail.clear(); await page.getByRole("button", { name: "Retry reader assignments", exact: true }).click(); await expect(page.getByLabel("Reader assignment", { exact: true })).toBeVisible()
})

test("revision workflow retains invitation drafts, validates ranges and recovers failed sends", async ({ page }) => {
  const state = await installLoop(page); await page.goto(path); await step(page, "Invite readers")
  await page.getByLabel("Reader email", { exact: true }).fill("reader@example.com"); await page.getByLabel("Scope", { exact: true }).selectOption("chapter_range")
  await page.getByLabel("From chapter", { exact: true }).fill("1.5"); await page.getByRole("button", { name: "Send beta invite", exact: true }).click()
  await expect(page.getByText(/Enter whole chapter numbers/)).toBeVisible(); expect(state.calls.filter((call) => call.name === "POST /beta-reads")).toHaveLength(0)
  await page.getByLabel("From chapter", { exact: true }).fill("1"); await page.getByLabel("Through chapter", { exact: true }).fill("3")
  await step(page, "Characters"); await step(page, "Invite readers"); await expect(page.getByLabel("Reader email", { exact: true })).toHaveValue("reader@example.com")
  page.once("dialog", (dialog) => dialog.dismiss()); await page.getByRole("link", { name: "Back to findings", exact: true }).click(); await expect(page).toHaveURL(new RegExp("author-loop$"))
  state.fail.add("POST /beta-reads"); await page.getByRole("button", { name: "Send beta invite", exact: true }).click(); await expect(page.getByText(/Your draft is retained/)).toBeVisible()
  state.fail.clear(); await page.getByRole("button", { name: "Send beta invite", exact: true }).click(); await expect(page.getByText(/Invitation created for reader@example.com/)).toBeVisible()
  await expect(page.getByLabel("Reader email", { exact: true })).toHaveValue("")
  expect(state.calls.filter((call) => call.name === "POST /beta-reads").at(-1)?.body).toMatchObject({ chapter_start: 1, chapter_end: 3, window_days: 7 })
})

test("revision workflow retains failed decisions and can undo a report dismissal", async ({ page }) => {
  const state = await installLoop(page); await page.goto(`${path}#revision-control`)
  const card = page.getByRole("article").filter({ has: page.getByRole("heading", { name: "Chapter 2 assumption may break later payoff", exact: true }) })
  state.fail.add("PUT /writer-workspace"); await card.getByRole("button", { name: /Create task/ }).click(); await expect(page.getByText(/previous decision is retained/)).toBeVisible()
  state.fail.clear(); await card.getByRole("button", { name: /Create task/ }).click(); await expect(card.getByRole("button", { name: /Create task/ })).toBeDisabled()
  await expect(card.getByText("Task created", { exact: true })).toBeVisible()
  await card.getByRole("button", { name: /Dismiss:/ }).click(); await expect(card).toHaveCount(0)
  await page.getByRole("button", { name: "Undo dismissal", exact: true }).click(); await expect(card).toBeVisible()
  const tasks = state.calls.filter((call) => call.name === "PUT /writer-workspace").at(-1)?.body?.goal_calendar as { id: string }[]
  expect(tasks.filter((task) => task.id === "revision-task:rev-impact-1")).toHaveLength(1)
})

test("converted revision tasks can be opened from the confirmation", async ({ page }) => {
  await installLoop(page)
  await page.goto(`${path}#revision-control`)
  const card = page.getByRole("article").filter({ has: page.getByRole("heading", { name: "Chapter 2 assumption may break later payoff", exact: true }) })
  await card.getByRole("button", { name: /Create task/ }).click()
  await expect(page.getByRole("status").getByText("Added to your revision queue.")).toBeVisible()
  await page.getByRole("link", { name: "View tasks", exact: true }).click()
  await expect(page).toHaveURL(/sky-of-ash--book-1#author-project-tasks$/)
  await expect(page.locator("#author-project-tasks")).toContainText("Chapter 2 assumption may break later payoff")
})

test("revision workflow links partial feedback task saves without duplication", async ({ page }) => {
  const state = await installLoop(page); await page.goto(`${path}#beta-consensus`)
  const card = page.getByRole("article").filter({ hasText: "Clarify the gate rule feedback-1" })
  state.fail.add("PUT /beta-reads/reader-1/feedback-items/feedback-1")
  await card.getByRole("button", { name: "Convert to task", exact: true }).click(); await expect(page.getByText(/task was saved, but the feedback status/)).toBeVisible()
  state.fail.clear(); await card.getByRole("button", { name: "Convert to task", exact: true }).click(); await expect(card.getByRole("button", { name: "Task created", exact: true })).toBeDisabled()
  const tasks = state.calls.filter((call) => call.name === "PUT /writer-workspace").flatMap((call) => call.body?.goal_calendar as { id: string }[])
  expect(tasks.filter((task) => task.id === "revision-task:beta-feedback:feedback-1")).toHaveLength(1)
  expect(state.feedback[0].author_task_id).toBe("revision-task:beta-feedback:feedback-1")
  await card.getByRole("button", { name: /Resolve feedback/ }).click(); await card.getByRole("button", { name: /Reopen feedback/ }).click()
  expect(state.feedback[0].author_status).toBe("open")
})

test("revision workflow snapshots preserve drafts and show complete comparison results", async ({ page }) => {
  const state = await installLoop(page); state.fail.add("GET /revision-rounds"); await page.goto(`${path}#revision-control`)
  await expect(page.getByText(/Snapshots could not be loaded/)).toBeVisible(); state.fail.clear(); await page.getByRole("button", { name: "Refresh snapshots", exact: true }).click()
  await page.getByLabel("Revision round label", { exact: true }).fill("Before the gate revision")
  await step(page, "Characters"); await step(page, "Revision queue"); await expect(page.getByLabel("Revision round label", { exact: true })).toHaveValue("Before the gate revision")
  state.fail.add("POST /revision-rounds"); await page.getByRole("button", { name: "Capture round", exact: true }).click(); await expect(page.getByText(/Your label is retained/)).toBeVisible()
  state.fail.clear(); await page.getByRole("button", { name: "Capture round", exact: true }).click(); await expect(page.getByText("Captured Before the gate revision.", { exact: true })).toBeVisible()
  await page.getByRole("button", { name: "Show all 8 snapshots", exact: true }).click(); await expect(page.getByRole("heading", { name: "Snapshot 1", exact: true })).toBeVisible()
  state.fail.add("GET /revision-rounds/1/compare"); await page.getByRole("button", { name: "Compare snapshot: Snapshot 1", exact: true }).click(); await expect(page.getByText(/previous comparison is retained/)).toBeVisible()
  state.fail.clear(); await page.getByRole("button", { name: "Compare snapshot: Snapshot 1", exact: true }).click()
  await expect(page.getByText("Removed chapters: 1", { exact: true })).toBeVisible(); await expect(page.getByText("Changed chapters: 2", { exact: true })).toBeVisible()
  await expect(page.getByText(/-120 words/)).toBeVisible()
})

test("revision workflow supports manual link copying and isolates reader selections", async ({ page }) => {
  await installLoop(page)
  await page.addInitScript(() => Object.defineProperty(navigator, "clipboard", { configurable: true, value: { writeText: async () => { throw new Error("denied") } } }))
  await page.goto(`${path}#beta-consensus`); await page.getByRole("button", { name: "Copy private review link", exact: true }).click()
  await expect(page.getByLabel("Private review link", { exact: true })).toHaveValue("https://example.test/review/reader-1")
  await expect(page.getByText(/Clipboard access failed/)).toBeVisible()
  await page.getByLabel("Reader assignment", { exact: true }).selectOption("reader-2")
  await expect(page.getByText("This reader has not returned feedback yet.", { exact: true })).toBeVisible()
  await expect(page.getByLabel("Private review link", { exact: true })).toHaveCount(0)
  await expect(page.getByText("Clarify the gate rule feedback-1", { exact: true })).toHaveCount(0)
})

test("revision workflow exposes large character and findings lists without clipping", async ({ page }) => {
  await installLoop(page)
  await page.route(`**${base}/characters?**`, (route) => route.fulfill({ json: Array.from({ length: 15 }, (_, index) => ({ id: `character-${index}`, name: `Character ${index + 1}`, description: "A keeper of the tide archives.", aliases: [], first_chapter: 1 })) }))
  await page.route(`**${base}/revision-intelligence`, (route) => route.fulfill({ json: { change_impacts: Array.from({ length: 20 }, (_, index) => ({ id: `finding-${index}`, title: `Gate finding ${index + 1}`, description: "The manuscript changes the opening rule.", category: "continuity", severity: "medium", chapter_ref: 2, status: "pending" })), genre_checks: [], revision_plan: [], scene_advice: [], confusion_map: [], voice_alerts: [] } }))
  await page.goto(path); await step(page, "Characters")
  await page.getByRole("button", { name: "Show all 15 characters", exact: true }).click(); await expect(page.getByText("Character 15", { exact: true })).toBeVisible()
  await page.getByRole("button", { name: "Show fewer characters", exact: true }).click(); await expect(page.getByText("Character 15", { exact: true })).toHaveCount(0)
  await step(page, "Revision queue"); await page.getByRole("button", { name: /Show all \d+ findings/ }).click()
  await expect(page.getByRole("heading", { name: "Gate finding 20", exact: true })).toBeVisible()
  await page.setViewportSize({ width: 390, height: 1000 }); expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
})

test("revision workflow resumes the latest step after a deep link and tolerates blocked storage", async ({ page }) => {
  await installLoop(page); const errors: string[] = []; page.on("pageerror", (error) => errors.push(error.message))
  await page.goto(`${path}#revision-control`); await expect(page.getByRole("heading", { name: "Revision snapshots", exact: true })).toBeVisible()
  await step(page, "Characters"); await page.reload(); await expect(page.getByRole("heading", { name: "Character review", exact: true })).toBeVisible()
  await page.addInitScript(() => {
    const get = Storage.prototype.getItem; const set = Storage.prototype.setItem
    Storage.prototype.getItem = function(key) { if (key.startsWith("lorevia:author-loop:")) throw new Error("blocked"); return get.call(this, key) }
    Storage.prototype.setItem = function(key, value) { if (key.startsWith("lorevia:author-loop:")) throw new Error("blocked"); return set.call(this, key, value) }
  })
  await page.reload(); await expect(page.getByText(/Device storage is unavailable/)).toBeVisible()
  await step(page, "Invite readers"); await expect(page.getByLabel("Reader email", { exact: true })).toBeVisible(); expect(errors).toEqual([])
})

test("revision workflow serializes a slow invite and preserves its submitted fields", async ({ page }) => {
  const state = await installLoop(page)
  let release!: () => void; const gate = new Promise<void>((resolve) => { release = resolve })
  await page.route(`**${base}/beta-reads`, async (route) => { if (route.request().method() === "POST") await gate; return route.fallback() })
  await page.goto(path); await step(page, "Invite readers"); await page.getByLabel("Reader email", { exact: true }).fill("slow-reader@example.com")
  await page.getByRole("button", { name: "Send beta invite", exact: true }).click()
  await expect(page.getByLabel("Reader email", { exact: true })).toBeDisabled(); await expect(page.getByRole("button", { name: "Sending invite…", exact: true })).toBeDisabled()
  await step(page, "Characters"); await step(page, "Invite readers"); await expect(page.getByLabel("Reader email", { exact: true })).toHaveValue("slow-reader@example.com")
  release(); await expect(page.getByText(/Invitation created for slow-reader@example.com/)).toBeVisible()
  expect(state.calls.filter((call) => call.name === "POST /beta-reads")).toHaveLength(1)
})

test("revision workflow keeps upload drafts and files through hiding and step changes", async ({ page }) => {
  await installLoop(page); await page.goto(path)
  await page.getByRole("button", { name: "Open upload tools", exact: true }).click()
  await page.getByLabel("Chapter title", { exact: true }).fill("The signal")
  await page.locator("textarea").fill("Mara watches a green signal cross the empty harbour.")
  await page.getByRole("button", { name: "Hide upload tools", exact: true }).click()
  await step(page, "Characters"); await step(page, "Manuscript")
  await page.getByRole("button", { name: "Open upload tools", exact: true }).click()
  await expect(page.getByLabel("Chapter title", { exact: true })).toHaveValue("The signal")
  await expect(page.locator("textarea")).toHaveValue("Mara watches a green signal cross the empty harbour.")
  await page.getByRole("button", { name: "Upload file", exact: true }).click()
  await page.locator('input[type="file"]').first().setInputFiles({ name: "signal.txt", mimeType: "text/plain", buffer: Buffer.from("Mara watches the harbour.") })
  await step(page, "Characters"); await step(page, "Manuscript")
  await expect(page.getByText("signal.txt", { exact: true }).first()).toBeVisible()
  page.once("dialog", (dialog) => dialog.dismiss())
  await page.getByRole("link", { name: "Back to findings", exact: true }).click()
  await expect(page).toHaveURL(/author-loop/)
  await expect(page.getByText("signal.txt", { exact: true }).first()).toBeVisible()
})
