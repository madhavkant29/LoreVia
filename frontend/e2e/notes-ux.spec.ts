import { expect, test, type Page } from "@playwright/test"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"

const route = "/sky-of-ash--book-1/notes"
test.beforeEach(async ({ page }) => {
  await installMockApi(page)
  await page.addInitScript(() => {
    if (!localStorage.getItem("lorevia-preferences")) localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 }))
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
})

test("notes workspace remains readable across screen sizes", async ({ page }, testInfo) => {
  const pageErrors: string[] = []
  page.on("pageerror", (error) => pageErrors.push(error.message))
  await page.goto(route)
  await expect(page.getByLabel("Note content", { exact: true })).toBeVisible()
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    await page.screenshot({ path: testInfo.outputPath(`notes-${width}.png`), fullPage: true })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  }
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  for (const theme of ["dark", "light"]) {
    await page.evaluate((theme) => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme }, version: 0 })), theme)
    await page.reload()
    await expect(page.getByLabel("Note content", { exact: true })).toBeVisible()
    await page.screenshot({ path: testInfo.outputPath(`notes-${theme}-390.png`), fullPage: true })
    expect(await criticalAccessibilityViolations(page)).toEqual([])
    await page.getByRole("button", { name: "Browse notes", exact: true }).click()
    await expect(page.getByRole("dialog", { name: "Note library", exact: true })).toBeVisible()
    expect(await criticalAccessibilityViolations(page, '[role="dialog"]')).toEqual([])
    await page.screenshot({ path: testInfo.outputPath(`notes-library-${theme}.png`), fullPage: true })
    await page.keyboard.press("Escape")
    await expect(page.getByRole("button", { name: "Browse notes", exact: true })).toBeFocused()
    await page.getByRole("button", { name: "Details", exact: true }).click()
    await expect(page.getByText("No backlinks yet.")).toBeVisible()
    expect(await criticalAccessibilityViolations(page, '[role="dialog"]')).toEqual([])
    await page.screenshot({ path: testInfo.outputPath(`notes-details-${theme}.png`), fullPage: true })
    await page.keyboard.press("Escape")
    await expect(page.getByRole("button", { name: "Details", exact: true })).toBeFocused()
  }
  expect(pageErrors).toEqual([])
})

test("notes loading failure offers retry without presenting an empty editor", async ({ page }) => {
  let failed = true
  await page.route("**/api/v1/books/book-1/notes/vault/page**", (request) => failed ? request.fulfill({ status: 503, json: { detail: "Unavailable" } }) : request.fallback())
  await page.goto(route)
  await expect(page.getByRole("button", { name: "Retry notes", exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "New note", exact: true })).toHaveCount(0)
  failed = false
  await page.getByRole("button", { name: "Retry notes", exact: true }).click()
  await expect(page.getByLabel("Note content", { exact: true })).toBeVisible()
})

test("failed saves retain drafts, restore after reload, and can retry", async ({ page }) => {
  let failed = true
  await page.route("**/api/v1/books/book-1/notes/vault", (request) => failed && request.request().method() === "PUT" ? request.fulfill({ status: 503, json: { detail: "Unavailable" } }) : request.fallback())
  await page.goto(route)
  await page.getByLabel("Note content", { exact: true }).fill("A draft worth keeping")
  await expect(page.getByRole("alert").filter({ hasText: "Your draft is still here" })).toBeVisible()
  page.once("dialog", (dialog) => dialog.accept())
  await page.reload()
  await expect(page.getByLabel("Note content", { exact: true })).toHaveValue("A draft worth keeping")
  await expect(page.getByRole("button", { name: "Save recovered notes" })).toBeVisible()
  failed = false
  await page.getByRole("button", { name: "Save recovered notes" }).click()
  await expect(page.getByRole("button", { name: "Save recovered notes" })).toHaveCount(0)
  expect(await page.evaluate(() => Object.keys(sessionStorage).filter((key) => key.startsWith("lorevia:note-drafts:")))).toEqual([])
})

test("leaving notes flushes pending autosave and stays in place if saving fails", async ({ page }) => {
  let failed = true
  await page.route("**/api/v1/books/book-1/notes/vault", (request) => failed && request.request().method() === "PUT" ? request.fulfill({ status: 503, json: { detail: "Unavailable" } }) : request.fallback())
  await page.goto(route)
  await page.getByLabel("Note content", { exact: true }).fill("Save before leaving")
  await page.getByRole("link", { name: /Book overview/ }).click()
  await expect(page.getByRole("alert").filter({ hasText: "Could not save" })).toBeVisible()
  await expect(page).toHaveURL(/\/notes$/)
  await expect(page.locator("fieldset").first()).toBeEnabled()
  failed = false
  await page.getByRole("link", { name: /Book overview/ }).click()
  await expect(page).not.toHaveURL(/\/notes$/, { timeout: 30_000 })
  await page.goto(route)
  await expect(page.getByLabel("Note content", { exact: true })).toHaveValue("Save before leaving")
})

test("notes support keyboard modes, search recovery, formatting and graph focus", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 1000 })
  await page.goto(route)
  await page.getByRole("button", { name: "Browse notes", exact: true }).click()
  await page.getByLabel("Search notes", { exact: true }).fill("Impossible search")
  await expect(page.getByText(/No notes here/)).toBeVisible()
  await page.getByRole("button", { name: "Clear filters" }).click()
  await expect(page.getByLabel("Search notes", { exact: true })).toHaveValue("")
  await page.keyboard.press("Escape")
  await page.getByRole("tab", { name: "edit", exact: true }).press("ArrowRight")
  await expect(page.getByRole("tab", { name: "preview", exact: true })).toBeFocused()
  await expect(page.getByRole("tabpanel")).toContainText("Revisit the bell motif")
  await page.getByRole("tab", { name: "preview", exact: true }).press("Home")
  await expect(page.getByRole("tab", { name: "edit", exact: true })).toHaveAttribute("aria-selected", "true")
  await page.getByText("More formatting", { exact: true }).click()
  await expect(page.getByRole("button", { name: "Heading 1", exact: true })).toBeVisible()
  await page.getByRole("button", { name: "Open full graph", exact: true }).click()
  const graph = page.getByRole("dialog", { name: "Vault graph view", exact: true })
  await expect(graph).toBeVisible()
  expect(await criticalAccessibilityViolations(page, '[role="dialog"]')).toEqual([])
  await page.keyboard.press("Escape")
  await expect(page.getByRole("button", { name: "Open full graph", exact: true })).toBeFocused()
})

test("note details and chapter notes expose recoverable secondary failures", async ({ page }) => {
  let failed = true
  await page.route("**/api/v1/books/book-1/notes/vault/relations**", (request) => failed ? request.fulfill({ status: 503, json: {} }) : request.fallback())
  await page.route("**/api/v1/books/book-1/notes", (request) => failed ? request.fulfill({ status: 503, json: {} }) : request.fallback())
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto(route)
  await page.getByRole("button", { name: "Details", exact: true }).click()
  await expect(page.getByRole("button", { name: "Retry note details" })).toBeVisible()
  await expect(page.getByText("No backlinks yet.")).toHaveCount(0)
  await page.getByRole("button", { name: /Chapter-linked notes/ }).click()
  await expect(page.getByRole("button", { name: "Retry chapter-linked notes" })).toBeVisible()
  failed = false
  await page.getByRole("button", { name: "Retry note details" }).click()
  await page.getByRole("button", { name: "Retry chapter-linked notes" }).click()
  await expect(page.getByText("No backlinks yet.")).toBeVisible()
  await expect(page.getByRole("article").getByRole("heading", { name: "Gate imagery" })).toBeVisible()
})

async function installNotes(page: Page, paths: string[]) {
  let notes = paths.map((path, index) => ({ id: `note-${index}`, book_id: "book-1", source: "user_notes", path, content: `# ${path}\n\nOriginal text`, created_at: "2026-05-08T10:00:00Z", updated_at: "2026-05-08T10:00:00Z" }))
  await page.route(/\/api\/v1\/books\/book-1\/notes\/vault(?:\/|$|\?)/, (request) => {
    const url = new URL(request.request().url()), method = request.request().method()
    if (method === "GET" && url.pathname.endsWith("/vault")) return request.fulfill({ json: notes })
    if (url.pathname.endsWith("/page")) return request.fulfill({ json: { items: notes, next_cursor: null, has_more: false } })
    if (method === "PUT") {
      const payload = request.request().postDataJSON()
      const result = { ...notes[0], ...payload, id: payload.path, source: "user_notes", persisted: true }
      notes = [result, ...notes.filter((note) => note.path !== payload.path)]
      return request.fulfill({ json: result })
    }
    if (method === "DELETE") {
      const path = decodeURIComponent(url.pathname.split("/vault/")[1])
      notes = notes.filter((note) => note.path !== path)
      return request.fulfill({ status: 204 })
    }
    if (url.pathname.endsWith("/graph")) return request.fulfill({ json: { nodes: notes.map((note) => ({ id: note.path, path: note.path, title: note.path, folder: "Custom", link_count: 0 })), edges: [] } })
    return request.fallback()
  })
  return () => notes
}

test("rename cannot overwrite another note and pending autosave cannot resurrect a moved note", async ({ page }) => {
  const notes = await installNotes(page, ["Custom/First.md", "Custom/Second.md"])
  await page.goto(route)
  await page.getByLabel("Note content", { exact: true }).fill("Renamed draft")
  await page.getByRole("button", { name: "Details", exact: true }).click()
  await page.getByLabel("File title", { exact: true }).fill("Second")
  await page.getByRole("button", { name: "Update path" }).click()
  await expect(page.getByRole("alert").filter({ hasText: "already uses that path" })).toBeVisible()
  await page.getByLabel("File title", { exact: true }).fill("Renamed")
  await page.getByRole("button", { name: "Update path" }).click()
  await expect(page.getByRole("heading", { name: "Renamed", exact: true })).toBeVisible()
  await expect.poll(() => notes().map((note) => note.path).sort()).toEqual(["Custom/Renamed.md", "Custom/Second.md"])
  expect(notes().find((note) => note.path === "Custom/Renamed.md")?.content).toBe("Renamed draft")
})

test("empty notes and action failures provide a next step", async ({ page }) => {
  await installNotes(page, [])
  let failed = true
  await page.route("**/api/v1/books/book-1/notes/vault", (request) => failed && request.request().method() === "PUT" ? request.fulfill({ status: 503, json: {} }) : request.fallback())
  await page.goto(route)
  await expect(page.getByText("Create or select a note to begin.")).toBeVisible()
  await page.getByRole("button", { name: "New note", exact: true }).click()
  await expect(page.getByRole("alert").filter({ hasText: "Could not create" })).toBeVisible()
  failed = false
  await page.getByRole("button", { name: "New note", exact: true }).click()
  await expect(page.getByLabel("Note content", { exact: true })).toHaveValue(/Untitled note/)
})

test("long note titles wrap and filtering keeps the active draft", async ({ page }, testInfo) => {
  const title = "A very long reference title about the forgotten road and the keeper of the eastern archives"
  await installNotes(page, [`Custom/${title}.md`, "Custom/Another reference.md"])
  await page.goto(route)
  await page.getByLabel("Note content", { exact: true }).fill("Working draft")
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    if (width === 390) await page.getByRole("button", { name: "Browse notes", exact: true }).click()
    await page.getByLabel("Search notes", { exact: true }).fill("Another reference")
    if (width === 390) await page.keyboard.press("Escape")
    await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible()
    await expect(page.getByLabel("Note content", { exact: true })).toHaveValue("Working draft")
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
    await page.screenshot({ path: testInfo.outputPath(`notes-long-${width}.png`), fullPage: true })
  }
})

test("delete errors are visible in the mobile details dialog and deletion can retry", async ({ page }) => {
  const notes = await installNotes(page, ["Custom/First.md", "Custom/Second.md"])
  let failed = true
  await page.route(/\/api\/v1\/books\/book-1\/notes\/vault\//, (request) => failed && request.request().method() === "DELETE" ? request.fulfill({ status: 503, json: {} }) : request.fallback())
  await page.setViewportSize({ width: 390, height: 1000 })
  await page.goto(route)
  await page.getByLabel("Note content", { exact: true }).fill("Pending before deletion")
  await page.getByRole("button", { name: "Details", exact: true }).click()
  await page.getByRole("button", { name: "Delete", exact: true }).click()
  await page.getByRole("button", { name: "Delete note", exact: true }).click()
  await expect(page.getByRole("dialog", { name: "Note details", exact: true }).getByRole("alert")).toContainText("Could not delete")
  failed = false
  await page.getByRole("button", { name: "Delete", exact: true }).click()
  await page.getByRole("button", { name: "Delete note", exact: true }).click()
  await expect.poll(() => notes().map((note) => note.path)).toEqual(["Custom/Second.md"])
  await page.keyboard.press("Escape")
  await expect(page.getByRole("heading", { name: "Second", exact: true })).toBeVisible()
})

test("a partial rename keeps both copies visible and never hides the original", async ({ page }) => {
  const notes = await installNotes(page, ["Custom/First.md"])
  await page.route(/\/api\/v1\/books\/book-1\/notes\/vault\//, (request) => request.request().method() === "DELETE" ? request.fulfill({ status: 503, json: {} }) : request.fallback())
  await page.goto(route)
  await page.getByRole("button", { name: "Details", exact: true }).click()
  await page.getByLabel("File title", { exact: true }).fill("Copy")
  await page.getByRole("button", { name: "Update path" }).click()
  await expect(page.getByRole("alert").filter({ hasText: "Could not finish moving" })).toBeVisible()
  expect(notes().map((note) => note.path).sort()).toEqual(["Custom/Copy.md", "Custom/First.md"])
  await expect(page.getByRole("button", { name: /First.*May/ })).toBeVisible()
  await expect(page.getByRole("button", { name: /Copy.*May/ })).toBeVisible()
})

test("note graph remains accessible in light mode", async ({ page }, testInfo) => {
  await installNotes(page, ["Custom/First.md", "Custom/Second.md"])
  await page.goto(route)
  await page.evaluate(() => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "light" }, version: 0 })))
  await page.reload()
  await page.setViewportSize({ width: 390, height: 1000 })
  await page.getByRole("button", { name: "Open full graph", exact: true }).click()
  await expect(page.getByRole("button", { name: "Zoom in graph" })).toBeVisible()
  expect(await criticalAccessibilityViolations(page, '[role="dialog"]')).toEqual([])
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  await page.screenshot({ path: testInfo.outputPath("notes-graph-light.png"), fullPage: true })
  await page.getByRole("dialog").getByRole("button", { name: "Custom/Second.md", exact: true }).click()
  await expect(page.getByRole("dialog")).toHaveCount(0)
  await expect(page.getByRole("heading", { name: "Second", exact: true })).toBeVisible()
})
