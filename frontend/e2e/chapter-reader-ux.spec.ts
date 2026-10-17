import { expect, test, type Page } from "@playwright/test"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"

const path = "/sky-of-ash--book-1/chapter/2"
const character = { id: "char-nora", name: "Nora", aliases: [], role: "mc", first_chapter: 1, description: "Nora studies the harbour signals.", personality_tags: ["patient", "observant", "loyal", "restless"], motivations: ["Find the missing keeper"], fears: [] }
const passage = "Nora crossed the ember gate. The harbour lanterns stood in a line along the sea wall, each marking a different route home. She stopped to compare the signal with the record in her notebook."
async function install(page: Page, reader = false) {
  await installMockApi(page, { workspaceShell: reader ? "reader" : "author", bookMode: reader ? "reader" : "author" })
  await page.addInitScript(() => {
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
    if (!localStorage.getItem("lorevia-preferences")) localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 }))
  })
  const state = { fail: new Set<string>(), remote: false, empty: false, waitContext: null as Promise<void> | null, writes: [] as Array<{ path: string; body: Record<string, unknown> }>, annotations: [] as Array<Record<string, unknown>>, feedback: [] as Array<Record<string, unknown>> }
  const assignment = { id: "active-pass", book_id: "book-1", state: "in_progress", view_bucket: "active", chapter_start: 2, chapter_end: 2, reader_email: "reader@example.com", task_label: "Opening pass", starts_at: new Date(Date.now() - 86400000).toISOString(), expires_at: new Date(Date.now() + 86400000).toISOString() }
  await page.route(url => url.pathname.startsWith("/api/v1/reader/book-1/") || url.pathname === "/api/v1/books/book-1" || url.pathname === "/api/v1/books/book-1/annotations" || url.pathname === "/api/v1/beta-reads" || url.pathname.includes("/beta-reads/active-pass/") || url.pathname === "/api/v1/books/book-1/characters/char-nora" || url.pathname === "/reader-test.txt", async route => {
    const url = new URL(route.request().url()), method = route.request().method()
    if (method !== "GET") state.writes.push({ path: url.pathname, body: route.request().postDataJSON() ?? {} })
    if (state.fail.has(url.pathname)) return route.fulfill({ status: 503, json: { detail: "Synthetic offline state" } })
    if (url.pathname === "/reader-test.txt") return route.fulfill({ contentType: "text/plain", body: passage.repeat(20) })
    if (/\/chapter\/\d+$/.test(url.pathname)) return route.fulfill({ json: { chapter_number: Number(url.pathname.split("/").at(-1)), chapter_title: "The Ember Gate", total_chapters: 3, text_content: state.empty || state.remote ? null : Array.from({ length: 24 }, () => passage).join("\n\n"), text_url: state.remote ? "/reader-test.txt" : null, html_content: null, characters: [character], beta_feedback: [], media: [] } })
    if (url.pathname.endsWith("/chapters")) return route.fulfill({ json: { chapters: [1, 2, 5].map(number => ({ number, title: `Chapter ${number}`, processed: true, read: false })) } })
    if (url.pathname.endsWith("/context")) { if (state.waitContext) await state.waitContext; return route.fulfill({ json: { type: "character", character } }) }
    if (/\/summary\/\d+$/.test(url.pathname)) return route.fulfill({ json: { content: "Nora compares the harbour signals with an old notebook.", key_events: [], char_changes: [], clues: [] } })
    if (url.pathname.endsWith("/progress") && method === "PUT") return route.fulfill({ json: {} })
    if (url.pathname.endsWith("/quotes") && method === "POST") return route.fulfill({ json: { id: "saved-quote" } })
    if (url.pathname === "/api/v1/books/book-1" && reader) return route.fulfill({ json: { id: "book-1", title: "Sky of Ash", mode: "reader", workspace_shell: "reader", access_class: "reader_collaborator", status: "ready", total_chapters: 3, collaboration_permissions: { can_comment: true, can_edit_manuscript: false } } })
    if (url.pathname === "/api/v1/books/book-1/annotations") {
      if (method === "POST") { const annotation = { ...route.request().postDataJSON(), id: "saved-comment", created_by_label: "You", updated_at: new Date().toISOString() }; state.annotations.unshift(annotation); return route.fulfill({ json: annotation }) }
      return route.fulfill({ json: state.annotations })
    }
    if (url.pathname === "/api/v1/beta-reads") return route.fulfill({ json: { items: [assignment] } })
    if (url.pathname.endsWith("/active-pass/feedback-items")) { state.feedback.push({ ...route.request().postDataJSON(), id: "saved-feedback", created_at: new Date().toISOString(), updated_at: new Date().toISOString(), author_status: "open" }); return route.fulfill({ json: { assignment, feedback_items: state.feedback } }) }
    if (url.pathname.endsWith("/characters/char-nora") && method === "PUT") return route.fulfill({ json: { ...character, ...route.request().postDataJSON() } })
    return route.fallback()
  })
  return state
}

test("chapter reader remains editorial and readable across widths, themes and recap", async ({ page }, info) => {
  await install(page); await page.goto(path)
  await expect(page.getByRole("heading", { name: "The Ember Gate", exact: true })).toBeVisible()
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
    await page.screenshot({ path: info.outputPath(`reader-dark-${width}.png`) })
  }
  expect(await criticalAccessibilityViolations(page, "[data-chapter-reader]")).toEqual([])
  await page.getByRole("button", { name: "Menu", exact: true }).click()
  await page.getByRole("button", { name: "Use light theme", exact: true }).click()
  await page.keyboard.press("Escape")
  await page.screenshot({ path: info.outputPath("reader-light-mobile.png") })
  expect(await criticalAccessibilityViolations(page, "[data-chapter-reader]")).toEqual([])
  await page.getByRole("button", { name: "Recap", exact: true }).last().click()
  await expect(page.getByRole("dialog", { name: "Chapter 2 Summary" })).toBeVisible()
  await expect(page.getByText("Nora compares the harbour signals with an old notebook.")).toBeVisible()
  expect(await criticalAccessibilityViolations(page, '[role="dialog"]')).toEqual([])
  await page.screenshot({ path: info.outputPath("recap-mobile.png") }); await page.keyboard.press("Escape")
  await expect(page.getByRole("button", { name: "Recap", exact: true }).last()).toBeFocused()
  await page.setViewportSize({ width: 1440, height: 1000 }); await page.screenshot({ path: info.outputPath("reader-light-desktop.png") })
  expect(await criticalAccessibilityViolations(page, "[data-chapter-reader]")).toEqual([])
})

test("chapter reader recovers chapter, text, navigation and recap errors", async ({ page }) => {
  const state = await install(page)
  state.fail.add("/api/v1/reader/book-1/chapter/2"); await page.goto(path)
  await expect(page.getByRole("button", { name: "Retry chapter", exact: true })).toBeVisible(); expect(page.url()).toContain("/chapter/2")
  state.fail.clear(); state.remote = true; state.fail.add("/reader-test.txt")
  await page.getByRole("button", { name: "Retry chapter", exact: true }).click()
  await expect(page.getByText("The chapter text could not be loaded.")).toBeVisible()
  state.fail.clear(); await page.getByRole("button", { name: "Retry chapter text" }).click()
  await expect(page.getByRole("heading", { name: "The Ember Gate" })).toBeVisible()
  state.fail.add("/api/v1/reader/book-1/chapters"); await page.reload()
  await expect(page.getByRole("button", { name: "Retry navigation" })).toBeVisible(); state.fail.clear()
  await page.getByRole("button", { name: "Retry navigation" }).click()
  await expect(page.getByRole("link", { name: "Next chapter", exact: true }).first()).toHaveAttribute("href", "/sky-of-ash--book-1/chapter/5")
  state.fail.add("/api/v1/reader/book-1/summary/2"); await page.getByRole("button", { name: "Recap", exact: true }).first().click()
  await expect(page.getByRole("button", { name: "Retry recap" })).toBeVisible(); state.fail.clear()
  await page.getByRole("button", { name: "Retry recap" }).click(); await expect(page.getByText("Nora compares the harbour signals with an old notebook.")).toBeVisible()
  await page.keyboard.press("Escape"); state.remote = false; state.empty = true; await page.reload()
  await expect(page.getByText("This chapter does not contain reading text yet.")).toBeVisible()
})

test("chapter reader preserves font preferences and restores a canonical bookmark without a zero write", async ({ page }) => {
  const state = await install(page)
  await page.addInitScript(() => { localStorage.setItem("reader-font-size", "24"); localStorage.setItem("reader-bookmark:book-1", JSON.stringify({ bookId: "book-1", chapter: 2, scrollPct: 0.6 })) })
  await page.goto(path); const surface = page.getByRole("region", { name: "Chapter reading surface" })
  await expect(page.locator(".reader-text")).toHaveCSS("font-size", "24px")
  await expect.poll(() => surface.evaluate(el => el.scrollTop)).toBeGreaterThan(100)
  expect(state.writes.filter(call => call.path.endsWith("/progress"))).toHaveLength(0)
  expect(await page.evaluate(() => JSON.parse(localStorage.getItem("reader-bookmark:book-1")!).scrollPct)).toBe(0.6)
  await surface.hover(); await page.mouse.wheel(0, 600)
  await expect.poll(() => state.writes.filter(call => call.path.endsWith("/progress")).length).toBeGreaterThan(0)
})

test("chapter navigation uses sparse numbers and closed context does not reopen", async ({ page }, info) => {
  const state = await install(page); await page.setViewportSize({ width: 1440, height: 1000 }); await page.goto(path)
  await expect(page.getByRole("link", { name: "Next chapter", exact: true }).first()).toHaveAttribute("href", "/sky-of-ash--book-1/chapter/5")
  let resolve: () => void = () => {}; state.waitContext = new Promise<void>(done => { resolve = done })
  await page.locator(".reader-text").getByRole("button", { name: "Nora", exact: true }).first().click()
  await expect(page.getByRole("dialog", { name: "Character details" })).toBeVisible()
  await page.getByRole("button", { name: "Close context panel" }).click(); resolve(); state.waitContext = null
  await expect(page.getByRole("dialog", { name: "Character details" })).toHaveCount(0)
  state.fail.add("/api/v1/reader/book-1/context")
  await page.locator(".reader-text").getByRole("button", { name: "Nora", exact: true }).first().click()
  await expect(page.getByRole("button", { name: "Retry context" })).toBeVisible(); state.fail.clear()
  await page.getByRole("button", { name: "Retry context" }).click(); await expect(page.getByText(character.description)).toBeVisible()
  await page.screenshot({ path: info.outputPath("context-desktop.png") })
  await page.setViewportSize({ width: 768, height: 1000 }); await expect(page.getByRole("dialog", { name: "Character details" })).toHaveAttribute("aria-modal", "true")
  await page.screenshot({ path: info.outputPath("context-tablet.png") })
  await page.setViewportSize({ width: 390, height: 844 }); expect(await criticalAccessibilityViolations(page, "[data-reader-context]")).toEqual([])
  await page.screenshot({ path: info.outputPath("context-mobile.png") }); await page.keyboard.press("Escape")
  await expect(page.getByRole("dialog", { name: "Character details" })).toHaveCount(0)
})

test("chapter comments preserve failed drafts, protect navigation and save to the scoped beta assignment", async ({ page }, info) => {
  const state = await install(page, true); await page.setViewportSize({ width: 390, height: 900 }); await page.goto(path)
  const comment = page.getByRole("textbox", { name: "Chapter comment", exact: true }); await comment.fill("The signal is clear, but the keeper’s reaction needs a pause.")
  page.once("dialog", dialog => dialog.dismiss()); await page.getByRole("link", { name: "Project overview", exact: true }).click()
  expect(page.url()).toContain("/chapter/2")
  state.fail.add("/api/v1/beta-reads/active-pass/feedback-items")
  await page.getByRole("button", { name: "Leave chapter comment", exact: true }).click()
  await expect(page.getByRole("status").filter({ hasText: "Could not confirm the comment save" })).toBeVisible()
  await expect(comment).toHaveValue("The signal is clear, but the keeper’s reaction needs a pause.")
  state.fail.clear(); await page.getByRole("button", { name: "Leave chapter comment", exact: true }).click()
  await expect(comment).toHaveValue(""); await expect(page.getByText("Comment saved.", { exact: true })).toBeVisible()
  expect(state.writes.some(call => call.path.endsWith("/annotations"))).toBe(false)
  expect(state.feedback).toHaveLength(1); await page.screenshot({ path: info.outputPath("comments-mobile.png") })
})

test("chapter reader keeps quote drafts after a failed save and protects dismissal", async ({ page }, info) => {
  const state = await install(page); await page.setViewportSize({ width: 390, height: 900 }); await page.goto(path)
  await page.getByRole("button", { name: "Menu", exact: true }).click()
  await page.getByRole("button", { name: "Turn on quote selection mode" }).click(); await page.keyboard.press("Escape")
  await page.locator(".reader-text p").first().evaluate(element => {
    const range = document.createRange(); range.selectNodeContents(element)
    const selection = window.getSelection(); selection?.removeAllRanges(); selection?.addRange(range)
    element.dispatchEvent(new MouseEvent("mouseup", { bubbles: true }))
  })
  await expect(page.getByRole("dialog", { name: "Line bookmark" })).toBeVisible()
  await page.getByLabel("Line bookmark note").fill("The signal foreshadows the missing keeper.")
  page.once("dialog", dialog => dialog.dismiss()); await page.getByRole("button", { name: "Close context panel" }).click()
  await expect(page.getByLabel("Line bookmark note")).toHaveValue("The signal foreshadows the missing keeper.")
  state.fail.add("/api/v1/reader/book-1/quotes"); await page.getByRole("button", { name: "Save line bookmark" }).click()
  await expect(page.getByRole("status").filter({ hasText: "Could not confirm the bookmark save" })).toBeVisible()
  await expect(page.getByLabel("Line bookmark note")).toHaveValue("The signal foreshadows the missing keeper.")
  state.fail.clear(); await page.getByRole("button", { name: "Save line bookmark" }).click()
  await expect(page.getByText("Line bookmark saved in Quotes.")).toBeVisible()
  await expect(page.getByRole("link", { name: "Open saved quotes" })).toHaveAttribute("href", "/quotes")
  await expect(page.getByRole("button", { name: "Save line bookmark" })).toBeDisabled()
  await page.screenshot({ path: info.outputPath("quote-mobile.png") }); await page.keyboard.press("Escape")
})

test("chapter reader supports confirmed character edits and respects reader permissions", async ({ page }) => {
  const state = await install(page); await page.goto(path)
  await page.locator(".reader-text").getByRole("button", { name: "Nora", exact: true }).first().click()
  await page.getByRole("button", { name: "Edit", exact: true }).click(); await page.getByLabel("Character name", { exact: true }).fill("Nora Vale")
  state.fail.add("/api/v1/books/book-1/characters/char-nora"); await page.getByRole("button", { name: "Save Changes" }).click()
  await expect(page.getByRole("alert")).toContainText("Could not save character changes")
  await expect(page.getByLabel("Character name", { exact: true })).toHaveValue("Nora Vale")
  state.fail.clear(); await page.getByRole("button", { name: "Save Changes" }).click()
  await expect(page.getByRole("heading", { name: "Nora Vale", exact: true })).toBeVisible()
  await page.getByRole("button", { name: "Close context panel" }).click()
  await install(page, true); await page.reload()
  await page.locator(".reader-text").getByRole("button", { name: "Nora", exact: true }).first().click()
  await expect(page.getByText(character.description)).toBeVisible(); await expect(page.getByRole("button", { name: "Edit", exact: true })).toHaveCount(0)
})

test("chapter reader reports progress sync failures and still reads with blocked storage", async ({ page }) => {
  const state = await install(page); state.fail.add("/api/v1/reader/book-1/progress"); await page.goto(path)
  await page.getByRole("region", { name: "Chapter reading surface" }).hover(); await page.mouse.wheel(0, 700)
  await expect(page.getByRole("button", { name: "Retry sync" })).toBeVisible(); state.fail.clear(); await page.getByRole("button", { name: "Retry sync" }).click()
  await expect(page.getByRole("button", { name: "Retry sync" })).toHaveCount(0)
  await page.addInitScript(() => {
    const read = Storage.prototype.getItem, write = Storage.prototype.setItem
    Storage.prototype.getItem = function(key) { if (key.startsWith("reader-")) throw new Error("Storage unavailable"); return read.call(this, key) }
    Storage.prototype.setItem = function(key, value) { if (key.startsWith("reader-")) throw new Error("Storage unavailable"); return write.call(this, key, value) }
  })
  await page.reload(); await expect(page.getByRole("heading", { name: "The Ember Gate", exact: true })).toBeVisible()
  await expect(page.getByText("This browser could not save your position. Keep this page open to retain your place.")).toBeVisible()
})
