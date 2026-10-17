import { expect, test, type Page } from "@playwright/test"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"

const path = "/sky-of-ash--book-1/beta-feedback"
const authorBase = "/api/v1/books/book-1/beta-reads"
const readerBase = "/api/v1/beta-reads"
const assignment = (id: string) => ({ id, book_id: "book-1", reader_email: `${id}@example.com`, task_label: `Opening review ${id}`, state: "in_progress", view_bucket: "active", scope_kind: "chapter_range", chapter_start: 2, chapter_end: 3, window_days: 7, required_progress_pct: 100, progress_pct: 100, required_comment_count: 1, comment_count: 1, required_feedback_item_count: 1, feedback_item_count: 1, question_count: 1, answered_question_count: 0, starts_at: new Date(Date.now() - 86400000).toISOString(), expires_at: new Date(Date.now() + 6 * 86400000).toISOString(), status_label: "In progress", submission_allowed: false, current_chapter: 2, chapters_total: 2, chapters_read_count: 2 })
const question = (id: string) => ({ id: `question-${id}`, prompt: `Was the signal clear for ${id}?`, answer_count: 0, created_at: new Date().toISOString() })
const item = (id: string) => ({ id: `item-${id}`, kind: "scene_reaction", chapter_number: 2, body: `The signal raised the tension for ${id}.`, anchor_text: "A green light crossed the harbour.", reaction: "Tense", author_status: "open" })
async function install(page: Page, reader = false) {
  await installMockApi(page, { workspaceShell: reader ? "reader" : "author", bookMode: reader ? "reader" : "author" })
  await page.addInitScript(() => {
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
    if (!localStorage.getItem("lorevia-preferences")) localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 }))
  })
  const state = { fail: new Set<string>(), calls: [] as Array<{ name: string; body: Record<string, unknown> }>, assignments: [assignment("reader-1"), assignment("reader-2")], questions: { "reader-1": [question("reader-1")], "reader-2": [] } as Record<string, ReturnType<typeof question>[]>, items: { "reader-1": [item("reader-1")], "reader-2": [] } as Record<string, Array<Record<string, unknown>>>, wait: null as Promise<void> | null }
  const detail = (id: string) => ({ assignment: state.assignments.find((entry) => entry.id === id), author_questions: state.questions[id] ?? [], feedback_items: state.items[id] ?? [], feedback_summary: { answer_count: (state.items[id] ?? []).filter((entry) => entry.kind === "answer").length, feedback_item_count: (state.items[id] ?? []).length, confusing_count: 0, favorite_count: 0, boring_count: 0 } })
  await page.route(url => url.pathname === "/api/v1/books/book-1" || url.pathname === authorBase || url.pathname.startsWith(`${authorBase}/`) || url.pathname === readerBase || url.pathname.startsWith(`${readerBase}/`), async route => {
    const url = new URL(route.request().url()), method = route.request().method(), name = `${method} ${url.pathname}`
    const body = route.request().postDataJSON() ?? {}
    state.calls.push({ name, body })
    if (method !== "GET" && state.wait) await state.wait
    if (state.fail.has(name)) return route.fulfill({ status: 500, json: { detail: "Synthetic recovery failure" } })
    if (url.pathname === "/api/v1/books/book-1") {
      if (!reader) return route.fallback()
      return route.fulfill({ json: { id: "book-1", title: "Sky of Ash", author: "M. Vale", mode: "reader", workspace_shell: "reader", access_class: "reader_collaborator", status: "ready", work_type: "novel", total_chapters: 3, progress_pct: 100, collaboration_permissions: { can_comment: true, can_edit_manuscript: false } } })
    }
    const base = url.pathname.startsWith(authorBase) ? authorBase : readerBase
    const suffix = url.pathname.slice(base.length), id = suffix.split("/")[1]
    if (!suffix && method === "GET") return route.fulfill({ json: { items: state.assignments } })
    if (!suffix && method === "POST") {
      const created = { ...assignment("created"), ...body }; state.assignments.unshift(created); state.questions.created = []; state.items.created = []
      return route.fulfill({ json: created })
    }
    if (suffix.endsWith("/questions")) { const added = (body.questions as string[]).map((prompt, index) => ({ ...question(`${id}-${index}`), prompt })); state.questions[id] = [...(state.questions[id] ?? []), ...added]; return route.fulfill({ json: state.questions[id] }) }
    if (suffix.endsWith("/revoke") || suffix.endsWith("/submit-feedback") || suffix.endsWith("/start")) {
      const a = state.assignments.find(entry => entry.id === id)!
      if (suffix.endsWith("/revoke")) { a.state = "revoked"; a.view_bucket = "completed"; a.status_label = "Revoked" }
      if (suffix.endsWith("/submit-feedback")) { a.state = "submitted"; a.status_label = "Submitted" }
      if (suffix.endsWith("/start")) { a.state = "in_progress"; a.status_label = "In progress" }
      return route.fulfill({ json: a })
    }
    if (suffix.includes("/feedback-items") && method === "POST") { state.items[id] = [...state.items[id], { ...body, id: "saved-item" }]; if (body.kind === "answer") state.questions[id].find(entry => entry.id === body.question_id)!.answer_count++; return route.fulfill({ json: detail(id) }) }
    if (suffix.includes("/feedback-items") && method === "DELETE") { state.items[id] = state.items[id].filter(entry => entry.id !== suffix.split("/")[3]); return route.fulfill({ json: detail(id) }) }
    if (id && method === "GET" && state.assignments.some(entry => entry.id === id)) return route.fulfill({ json: detail(id) })
    return route.fallback()
  })
  return state
}
const select = (page: Page, id = "reader-1") => page.getByRole("button", { name: new RegExp(`${id}@example.com`) }).click()

test("beta feedback author workspace has readable responses and forms across widths and themes", async ({ page }, info) => {
  await install(page); await page.goto(path); await select(page)
  for (const width of [1440, 1280, 768, 390]) { await page.setViewportSize({ width, height: 1000 }); expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy(); await page.screenshot({ path: info.outputPath(`author-${width}.png`), fullPage: true }) }
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.getByRole("button", { name: "New assignment", exact: true }).click(); await expect(page.getByLabel("Reader email", { exact: true })).toBeFocused()
  await page.getByLabel("Scope", { exact: true }).selectOption("section"); await expect(page.getByLabel("Section label", { exact: true })).toBeVisible(); expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.screenshot({ path: info.outputPath("author-form-mobile.png"), fullPage: true })
  await page.evaluate(() => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "light" }, version: 0 }))); await page.reload(); await select(page)
  expect(await criticalAccessibilityViolations(page)).toEqual([]); await page.screenshot({ path: info.outputPath("author-light-mobile.png"), fullPage: true })
  await page.getByRole("button", { name: "Help", exact: true }).click(); await expect(page.getByRole("dialog")).toBeVisible(); await page.keyboard.press("Escape")
})

test("beta feedback recovers book, assignment and detail failures without redirecting or false empty states", async ({ page }) => {
  const state = await install(page); state.fail.add("GET /api/v1/books/book-1"); await page.goto(path)
  await expect(page.getByRole("button", { name: "Retry manuscript", exact: true })).toBeVisible(); await expect(page).toHaveURL(/beta-feedback/)
  state.fail.clear(); state.fail.add(`GET ${authorBase}`); await page.getByRole("button", { name: "Retry manuscript", exact: true }).click(); await expect(page.getByRole("button", { name: "Retry assignments", exact: true })).toBeVisible(); await expect(page.getByText("No beta read assignments yet.", { exact: true })).not.toBeVisible()
  state.fail.clear(); await page.getByRole("button", { name: "Retry assignments", exact: true }).click(); state.fail.add(`GET ${authorBase}/reader-1`); await select(page)
  await expect(page.getByRole("button", { name: "Retry selected responses", exact: true })).toBeVisible(); state.fail.clear(); await page.getByRole("button", { name: "Retry selected responses", exact: true }).click(); await expect(page.getByText("The signal raised the tension for reader-1.", { exact: true })).toBeVisible()
})

test("beta feedback validates invitation sections and retains failed or hidden drafts", async ({ page }) => {
  const state = await install(page); await page.goto(path); await page.getByRole("button", { name: "New assignment", exact: true }).click()
  await page.getByLabel("Reader email", { exact: true }).fill("new@example.com"); await page.getByLabel("Scope", { exact: true }).selectOption("section"); await page.getByRole("button", { name: "Create beta read", exact: true }).click(); await expect(page.getByRole("status")).toContainText("Name the section")
  await page.getByLabel("Section label", { exact: true }).fill("Harbour opening"); await page.getByRole("button", { name: "Close form", exact: true }).click(); await page.getByRole("button", { name: "New assignment", exact: true }).click(); await expect(page.getByLabel("Section label", { exact: true })).toHaveValue("Harbour opening")
  page.once("dialog", dialog => dialog.dismiss()); await page.getByRole("link", { name: "Revision workflow", exact: true }).click(); await expect(page).toHaveURL(/beta-feedback/)
  state.fail.add(`POST ${authorBase}`); await page.getByRole("button", { name: "Create beta read", exact: true }).click(); await expect(page.getByRole("status")).toContainText("draft is retained"); await expect(page.getByLabel("Reader email", { exact: true })).toHaveValue("new@example.com")
  state.fail.clear(); await page.getByRole("button", { name: "Create beta read", exact: true }).click(); await expect(page.getByRole("status").filter({ hasText: "assignment created" })).toBeVisible(); expect(state.calls.filter(call => call.name === `POST ${authorBase}`).at(-1)?.body.section_label).toBe("Harbour opening")
})

test("beta feedback preserves assignment-specific question drafts and adds the first question", async ({ page }) => {
  const state = await install(page); await page.goto(path); await select(page)
  await page.getByLabel("Additional author questions", { exact: true }).fill("What did the light imply?"); await select(page, "reader-2"); await expect(page.getByLabel("Additional author questions", { exact: true })).toHaveValue(""); await page.getByLabel("Additional author questions", { exact: true }).fill("Which image stayed?")
  state.fail.add(`POST ${authorBase}/reader-2/questions`); await page.getByRole("button", { name: "Add questions", exact: true }).click(); await expect(page.getByRole("status")).toContainText("draft is retained"); state.fail.clear(); await page.getByRole("button", { name: "Add questions", exact: true }).click(); await expect(page.getByText("Which image stayed?", { exact: true })).toBeVisible()
  await select(page); await expect(page.getByLabel("Additional author questions", { exact: true })).toHaveValue("What did the light imply?")
})

test("beta feedback confirms revocation, retains feedback, and disables closed assignment writes", async ({ page }) => {
  const state = await install(page); await page.goto(path); await select(page)
  page.once("dialog", dialog => dialog.dismiss()); await page.getByRole("button", { name: "Revoke", exact: true }).click(); expect(state.calls.some(call => call.name.endsWith("/revoke"))).toBe(false)
  page.once("dialog", dialog => dialog.accept()); await page.getByRole("button", { name: "Revoke", exact: true }).click(); await expect(page.getByRole("status")).toContainText("Assignment revoked"); await expect(page.getByText("The signal raised the tension for reader-1.", { exact: true })).toBeVisible(); await expect(page.getByLabel("Additional author questions", { exact: true })).toBeDisabled()
})

test("beta feedback reader workspace is accessible across widths and themes", async ({ page }, info) => {
  await install(page, true); await page.goto(path); await expect(page.getByRole("heading", { name: "Your beta read", exact: true })).toBeVisible()
  for (const width of [1440, 1280, 768, 390]) { await page.setViewportSize({ width, height: 1000 }); expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy(); await page.screenshot({ path: info.outputPath(`reader-${width}.png`), fullPage: true }) }
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.evaluate(() => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "light" }, version: 0 }))); await page.reload(); await expect(page.getByRole("heading", { name: "Your beta read", exact: true })).toBeVisible(); expect(await criticalAccessibilityViolations(page)).toEqual([]); await page.screenshot({ path: info.outputPath("reader-light-mobile.png"), fullPage: true })
})

test("beta feedback validates reader scope and answer requirements, retains failed feedback, then submits", async ({ page }) => {
  const state = await install(page, true); await page.goto(path); await page.getByLabel("Feedback body", { exact: true }).fill("The signal was clear."); await page.getByLabel("Feedback chapter number", { exact: true }).fill("1")
  await page.getByRole("button", { name: "Save feedback item", exact: true }).click(); await expect(page.getByRole("status")).toContainText("assigned scope")
  await page.getByLabel("Feedback type", { exact: true }).selectOption("answer"); await page.getByLabel("Feedback chapter number", { exact: true }).fill(""); await page.getByRole("button", { name: "Save feedback item", exact: true }).click(); await expect(page.getByRole("status")).toContainText("Select an author question")
  await page.getByLabel("Linked author question", { exact: true }).selectOption("question-reader-1"); state.fail.add(`POST ${readerBase}/reader-1/feedback-items`); await page.getByRole("button", { name: "Save feedback item", exact: true }).click(); await expect(page.getByRole("status")).toContainText("draft is retained"); await expect(page.getByLabel("Feedback body", { exact: true })).toHaveValue("The signal was clear.")
  state.fail.clear(); await page.getByRole("button", { name: "Save feedback item", exact: true }).click(); await expect(page.getByRole("status")).toContainText("Feedback saved"); await expect(page.getByLabel("Feedback body", { exact: true })).toHaveValue("")
  await page.getByLabel("Final review", { exact: true }).fill("The signal gives the ending a clear purpose."); await page.getByRole("button", { name: "Submit review", exact: true }).click(); await expect(page.getByRole("status").first()).toContainText("Review submitted"); await expect(page.getByRole("button", { name: "Save feedback item", exact: true })).toBeDisabled()
})

test("beta feedback protects reader drafts on assignment switches and confirms deletion", async ({ page }) => {
  const state = await install(page, true); await page.goto(path); await page.getByLabel("Feedback body", { exact: true }).fill("Keep this response")
  page.once("dialog", dialog => dialog.dismiss()); await page.getByLabel("Your assignment", { exact: true }).selectOption("reader-2"); await expect(page.getByLabel("Your assignment", { exact: true })).toHaveValue("reader-1"); await expect(page.getByLabel("Feedback body", { exact: true })).toHaveValue("Keep this response")
  page.once("dialog", dialog => dialog.dismiss()); await page.getByRole("button", { name: /Remove feedback:/ }).click(); expect(state.calls.some(call => call.name.startsWith("DELETE"))).toBe(false)
  page.once("dialog", dialog => dialog.accept()); await page.getByRole("button", { name: /Remove feedback:/ }).click(); await expect(page.getByText("No structured feedback saved yet.", { exact: true })).toBeVisible()
  page.once("dialog", dialog => dialog.accept()); await page.getByLabel("Your assignment", { exact: true }).selectOption("reader-2"); await expect(page.getByLabel("Feedback body", { exact: true })).toHaveValue("")
})

test("beta feedback serializes slow writes and preserves confirmed results after refresh failure", async ({ page }) => {
  const state = await install(page); await page.goto(path); await select(page)
  let finish!: () => void; state.wait = new Promise<void>(resolve => { finish = resolve })
  await page.getByLabel("Additional author questions", { exact: true }).fill("Why this signal?"); await page.getByRole("button", { name: "Add questions", exact: true }).click(); await expect(page.getByRole("button", { name: "New assignment", exact: true })).toBeDisabled(); await expect(page.getByLabel("Additional author questions", { exact: true })).toBeDisabled(); finish(); state.wait = null
  await expect(page.getByRole("status")).toContainText("Questions added"); state.fail.add(`GET ${authorBase}/reader-1`); await page.getByRole("button", { name: "Refresh workspace", exact: true }).click(); await expect(page.getByRole("button", { name: "Retry selected responses", exact: true })).toBeVisible(); await expect(page.getByText("Why this signal?", { exact: true })).toBeVisible()
})

test("beta feedback reader recovers list and detail failures and explains closed assignments", async ({ page }) => {
  const state = await install(page, true); state.fail.add(`GET ${readerBase}`); await page.goto(path)
  await expect(page.getByRole("button", { name: "Retry your assignments", exact: true })).toBeVisible(); await expect(page.getByText(/No beta read is selected/)).not.toBeVisible()
  state.fail.clear(); state.fail.add(`GET ${readerBase}/reader-1`); await page.getByRole("button", { name: "Retry your assignments", exact: true }).click(); await expect(page.getByRole("button", { name: "Retry your feedback", exact: true })).toBeVisible()
  state.fail.clear(); await page.getByRole("button", { name: "Retry your feedback", exact: true }).click(); await expect(page.getByLabel("Feedback chapter number", { exact: true })).toHaveValue("2")
  state.assignments[1].state = "revoked"; state.assignments[1].status_label = "Revoked"; await page.getByLabel("Your assignment", { exact: true }).selectOption("reader-2"); await expect(page.getByText(/This assignment is read-only/)).toBeVisible(); await expect(page.getByLabel("Feedback body", { exact: true })).toBeDisabled(); await expect(page.getByRole("button", { name: "Submit review", exact: true })).toBeDisabled()
})

test("beta feedback reader sees requirements and keeps a failed final review", async ({ page }) => {
  const state = await install(page, true); await page.goto(path)
  await page.getByLabel("Final review", { exact: true }).fill("The signal resolves the opening mystery."); await page.getByRole("button", { name: "Submit review", exact: true }).click(); await expect(page.getByRole("dialog", { name: "Complete these before submitting" })).toBeVisible(); expect(state.calls.some(call => call.name.endsWith("/submit-feedback"))).toBe(false)
  await page.keyboard.press("Escape"); state.questions["reader-1"][0].answer_count = 1; await page.getByRole("button", { name: "Refresh workspace", exact: true }).click(); await expect(page.getByRole("heading", { name: "Before submitting", exact: true })).not.toBeVisible()
  state.fail.add(`POST ${readerBase}/reader-1/submit-feedback`); await page.getByRole("button", { name: "Submit review", exact: true }).click(); await expect(page.getByRole("status").first()).toContainText("draft is retained"); await expect(page.getByLabel("Final review", { exact: true })).toHaveValue("The signal resolves the opening mystery.")
  state.fail.clear(); await page.getByRole("button", { name: "Submit review", exact: true }).click(); await expect(page.getByRole("status").first()).toContainText("Review submitted")
})

test("beta feedback handles empty assignments and long response text without clipping", async ({ page }) => {
  const state = await install(page); state.assignments = []; await page.goto(path); await expect(page.getByText("No beta read assignments yet.", { exact: true })).toBeVisible()
  state.assignments = [assignment("reader-1")]; state.assignments[0].task_label = "Long-title-".repeat(30); const body = "Signal".repeat(80); state.items["reader-1"][0].body = body
  await page.getByRole("button", { name: "Refresh workspace", exact: true }).click(); await select(page); await page.setViewportSize({ width: 390, height: 844 }); await expect(page.getByText(body, { exact: true })).toBeVisible(); expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
})
