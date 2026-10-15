import { expect, test, type Page } from "@playwright/test"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"
import { readFile } from "node:fs/promises"
import { unzipSync } from "fflate"

const route = "/sky-of-ash--book-1/export"
const vault = { root_folder: "Sky Vault", files: [{ path: "Sky Vault/Characters/Nora.md", content: "Nora keeps the key." }, { path: "Sky Vault/World/Gate.md", content: "The gate opens at dusk." }] }
const incoming = { format: "docx", preview_token: "preview-token", incoming_chapter_count: 1, changed_count: 1, new_count: 0, unchanged_count: 0, preserved_chapter_numbers: [2], chapters: [{ incoming_number: 1, incoming_title: "Changed opening", status: "changed", incoming_word_count: 15 }] }
async function chooseTask(page: Page, label: string, value: string) {
  if ((page.viewportSize()?.width ?? 1440) < 768) await page.getByLabel("Choose a file task").selectOption(value)
  else await page.getByRole("tab", { name: new RegExp(`^${label}`) }).click()
}
test.beforeEach(async ({ page }) => {
  await installMockApi(page)
  await page.addInitScript(() => {
    if (!localStorage.getItem("lorevia-preferences")) localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 }))
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
  for (const endpoint of ["manuscript/export?*", "export/character-bible?*", "notes/vault/export", "workflow-bridge/scrivener"]) await page.route(`**/api/v1/books/book-1/${endpoint}`, (request) => request.fulfill({ body: "mock exported file", contentType: "application/octet-stream" }))
  await page.route("**/api/v1/books/book-1/export/character-bible/preview", (request) => request.fulfill({ json: vault }))
  await page.route("**/api/v1/books/book-1/export/character-bible/notes", (request) => request.request().method() === "PUT" ? request.fulfill({ json: { ...request.request().postDataJSON(), persisted: true } }) : request.fulfill({ json: [] }))
  await page.route("**/api/v1/books/book-1/workflow-bridge/preview", (request) => request.fulfill({ json: incoming }))
  await page.route("**/api/v1/books/book-1/workflow-bridge/apply", (request) => request.fulfill({ json: { imported_chapters: [1] } }))
})

test("export tasks and options remain readable at four widths and both themes", async ({ page }, info) => {
  const errors: string[] = []; page.on("pageerror", (error) => errors.push(error.message))
  await page.goto(route)
  await expect(page.getByRole("heading", { name: "Export a manuscript" })).toBeVisible()
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
    await page.screenshot({ path: info.outputPath(`export-${width}.png`), fullPage: true })
  }
  for (const theme of ["dark", "light"]) {
    if (theme === "light") { await page.evaluate(() => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "light" }, version: 0 }))); await page.reload() }
    for (const [label, value] of [["Manuscript", "manuscript"], ["Reader edition", "novel"], ["Character bible", "character-bible"], ["Notes backup", "notes"], ["Import files", "import"]]) {
      await chooseTask(page, label, value)
      if (value === "novel") { await expect(page.getByLabel("Preface", { exact: true })).toHaveValue("A short note before the ash gates open."); await page.getByText("Publishing details", { exact: true }).click() }
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
      expect(await criticalAccessibilityViolations(page)).toEqual([])
      await page.screenshot({ path: info.outputPath(`${value}-${theme}.png`), fullPage: true })
    }
  }
  expect(errors).toEqual([])
})

test("publishing load and save failures preserve drafts and block stale exports", async ({ page }) => {
  let failLoad = true; let failSave = true
  await page.route("**/api/v1/books/book-1/writer-workspace", (request) => failLoad ? request.fulfill({ status: 503, json: {} }) : request.fallback())
  await page.route("**/api/v1/books/book-1/novel/settings", (request) => failSave ? request.fulfill({ status: 503, json: {} }) : request.fallback())
  await page.goto(route); await chooseTask(page, "Reader edition", "novel")
  await page.getByRole("button", { name: "Retry publishing details" }).waitFor()
  await expect(page.getByRole("button", { name: "Export novel", exact: true })).toBeDisabled()
  failLoad = false; await page.getByRole("button", { name: "Retry publishing details" }).click()
  await page.getByText("Publishing details", { exact: true }).click()
  await page.getByLabel("Preface", { exact: true }).fill("New publishing draft")
  await expect(page.getByRole("button", { name: "Export novel", exact: true })).toBeDisabled()
  await page.getByRole("button", { name: "Save novel settings" }).click()
  await expect(page.getByText(/Could not save the novel export settings/)).toBeVisible()
  await expect(page.getByLabel("Preface", { exact: true })).toHaveValue("New publishing draft")
  await chooseTask(page, "Manuscript", "manuscript"); await chooseTask(page, "Reader edition", "novel")
  await page.getByText(/Publishing details · unsaved changes/, { exact: true }).click()
  await expect(page.getByLabel("Preface", { exact: true })).toHaveValue("New publishing draft")
  page.once("dialog", (dialog) => dialog.dismiss())
  await page.getByRole("link", { name: "Open manuscript", exact: true }).click()
  await expect(page).toHaveURL(route)
  failSave = false; await page.getByRole("button", { name: "Save novel settings" }).click()
  await expect(page.getByText("Saved novel export settings.", { exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "Export novel", exact: true })).toBeEnabled()
})

test("downloads retain options after errors and lock controls during preparation", async ({ page }) => {
  let release: (() => void) | undefined; const waiting = new Promise<void>((resolve) => { release = resolve })
  let fail = true; let count = 0
  await page.route("**/api/v1/books/book-1/manuscript/export?*", async (request) => { count++; if (fail) return request.fulfill({ status: 422, json: { detail: "No chapter text ready" } }); await waiting; return request.fulfill({ body: "download" }) })
  await page.goto(route)
  await page.getByRole("button", { name: "PDF", exact: true }).click()
  await page.getByRole("button", { name: "Export manuscript", exact: true }).click()
  await expect(page.getByText(/No chapter text ready/)).toBeVisible()
  await expect(page.getByRole("button", { name: "PDF", exact: true })).toHaveAttribute("aria-pressed", "true")
  fail = false; await page.getByRole("button", { name: "Export manuscript", exact: true }).click()
  await expect(page.getByRole("button", { name: "DOCX", exact: true })).toBeDisabled()
  await expect(page.getByRole("tab", { name: /^Reader edition/ })).toBeDisabled()
  const downloaded = page.waitForEvent("download"); release?.()
  expect((await downloaded).suggestedFilename()).toBe("Sky-of-Ash-manuscript.pdf")
  expect(count).toBe(2)
})

test("imports validate files, require notes replacement acknowledgement, and keep failed selections", async ({ page }) => {
  let fail = true
  await page.route("**/api/v1/books/book-1/notes/vault/import", (request) => request.fulfill(fail ? { status: 503, json: {} } : { json: [] }))
  await page.goto(route); await chooseTask(page, "Import files", "import")
  await page.locator('input[type="file"][aria-label="Choose Story manuscript files"]').setInputFiles({ name: "bad.exe", mimeType: "application/octet-stream", buffer: Buffer.from("bad") })
  await expect(page.getByText(/bad.exe: choose/)).toBeVisible()
  await expect(page.getByRole("button", { name: "Import manuscript files", exact: true })).toBeDisabled()
  await page.getByRole("button", { name: "Clear selected files", exact: true }).click()
  await page.locator('input[type="file"][aria-label="Choose Vault notes ZIP files"]').setInputFiles({ name: "notes.zip", mimeType: "application/zip", buffer: Buffer.from("archive") })
  await expect(page.getByRole("button", { name: "Import notes ZIP", exact: true })).toBeDisabled()
  await page.getByLabel("I understand that matching note paths will be replaced.").check()
  await page.getByRole("button", { name: "Import notes ZIP", exact: true }).click()
  await expect(page.getByText(/The import could not be confirmed/)).toBeVisible()
  await expect(page.getByText("notes.zip (1 KB)", { exact: true })).toBeVisible()
  fail = false; await page.getByRole("button", { name: "Import notes ZIP", exact: true }).click()
  await expect(page.getByText("Imported notes.zip into the notes workspace.", { exact: true })).toBeVisible()
  await expect(page.getByLabel("I understand that matching note paths will be replaced.")).not.toBeChecked()
})

test("vault saves are serialized, failures retain drafts, and edited archives download", async ({ page }, info) => {
  let release: (() => void) | undefined; const waiting = new Promise<void>((resolve) => { release = resolve })
  const writes: string[] = []; let fail = false
  await page.route("**/api/v1/books/book-1/export/character-bible/notes", async (request) => {
    if (request.request().method() !== "PUT") return request.fulfill({ json: [] })
    const body = request.request().postDataJSON(); writes.push(body.content)
    if (writes.length === 1) await waiting
    await request.fulfill(fail ? { status: 503, json: {} } : { json: { ...body, persisted: true } })
  })
  await page.goto(route); await chooseTask(page, "Character bible", "character-bible")
  await page.getByRole("button", { name: "Preview export files" }).click()
  const editor = page.getByLabel("Vault note content")
  await editor.fill("First draft")
  await expect.poll(() => writes.length).toBe(1)
  await editor.fill("Latest draft")
  await page.waitForTimeout(800)
  expect(writes).toEqual(["First draft"])
  release?.(); await expect.poll(() => writes.length).toBe(2)
  await expect(page.getByText("This note is saved.", { exact: true })).toBeVisible()
  await expect(editor).toHaveValue("Latest draft")
  fail = true; await editor.fill("Recoverable draft")
  await expect(page.getByText(/Could not save Characters\/Nora.md/)).toBeVisible()
  await expect(editor).toHaveValue("Recoverable draft")
  fail = false; await page.getByRole("button", { name: "Save note", exact: true }).click()
  await expect(page.getByText("This note is saved.", { exact: true })).toBeVisible()
  page.once("dialog", (dialog) => dialog.dismiss()); await page.getByRole("button", { name: "Reset file", exact: true }).click()
  await expect(editor).toHaveValue("Recoverable draft")
  const downloaded = page.waitForEvent("download"); await page.getByRole("button", { name: "Download edited Vault ZIP" }).click()
  expect((await downloaded).suggestedFilename()).toBe("sky-vault-edited.zip")
  await page.setViewportSize({ width: 390, height: 1000 })
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.screenshot({ path: info.outputPath("vault-mobile.png"), fullPage: true })
})

test("round-trip imports require a fresh reviewed preview after an uncertain apply", async ({ page }, info) => {
  let fail = true; let applies = 0
  await page.route("**/api/v1/books/book-1/workflow-bridge/apply", (request) => { applies++; return request.fulfill(fail ? { status: 409, json: { detail: "Draft changed since preview" } } : { json: { imported_chapters: [1] } }) })
  await page.goto(route); await page.getByText("Word and Scrivener round trip", { exact: true }).click()
  await page.getByLabel("Choose manuscript or Scrivener archive").setInputFiles({ name: "draft.docx", mimeType: "application/octet-stream", buffer: Buffer.from("document") })
  await expect(page.getByText("1 changed · 0 new · 0 unchanged · 1 preserved", { exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "Apply reviewed changes" })).toBeDisabled()
  await page.getByLabel(/I reviewed this preview/).check()
  await page.getByRole("button", { name: "Apply reviewed changes" }).click()
  await expect(page.getByText(/The import could not be confirmed/)).toBeVisible()
  await expect(page.getByRole("button", { name: "Apply reviewed changes" })).toHaveCount(0)
  await page.getByRole("button", { name: "Refresh preview" }).click()
  await expect(page.getByLabel(/I reviewed this preview/)).not.toBeChecked()
  fail = false; await page.getByLabel(/I reviewed this preview/).check()
  await page.setViewportSize({ width: 390, height: 1000 })
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.screenshot({ path: info.outputPath("round-trip-mobile.png"), fullPage: true })
  await page.getByRole("button", { name: "Apply reviewed changes" }).click()
  await expect(page.getByText("Updated 1 chapter(s). Chapters absent from the file were preserved.", { exact: true })).toBeVisible()
  expect(applies).toBe(2)
})

test("project failures recover and free users see actionable task restrictions", async ({ page }) => {
  let fail = true
  await page.route("**/api/v1/books/book-1", (request) => fail ? request.fulfill({ status: 503, json: {} }) : request.fallback())
  await page.goto(route); await page.getByRole("button", { name: "Retry project" }).waitFor()
  fail = false; await page.getByRole("button", { name: "Retry project" }).click()
  await expect(page.getByRole("button", { name: "Export manuscript", exact: true })).toBeVisible()
  await installMockApi(page, { userTier: "free" }); await page.reload()
  await chooseTask(page, "Notes backup", "notes")
  await expect(page.getByRole("heading", { name: "This file task is unavailable" })).toBeVisible()
  await expect(page.getByRole("link", { name: "View plans", exact: true })).toHaveAttribute("href", "/pricing")
  await chooseTask(page, "Reader edition", "novel")
  await expect(page.getByRole("button", { name: "Export novel", exact: true })).toBeEnabled()
})

test("keyboard task navigation, Help, and partial preview recovery remain operable", async ({ page }) => {
  let fail = true
  await page.route("**/api/v1/books/book-1/export/character-bible/notes", (request) => fail ? request.fulfill({ status: 503, json: {} }) : request.fulfill({ json: [] }))
  await page.goto(route)
  await page.getByRole("tab", { name: /^Manuscript/ }).focus(); await page.keyboard.press("ArrowRight")
  await expect(page.getByRole("tab", { name: /^Reader edition/ })).toBeFocused()
  await page.keyboard.press("ArrowRight")
  await expect(page.getByRole("tab", { name: /^Character bible/ })).toBeFocused()
  await page.getByRole("button", { name: "Preview export files" }).click()
  await expect(page.getByLabel("Vault note content")).toHaveValue("Nora keeps the key.")
  await expect(page.getByRole("button", { name: "Retry override list" })).toBeVisible()
  fail = false; await page.getByRole("button", { name: "Retry override list" }).click()
  await expect(page.getByRole("button", { name: "Retry override list" })).toHaveCount(0)
  await page.getByRole("button", { name: "View vault editor" }).click()
  await expect(page.locator('[id$="-vault"]')).toBeFocused()
  await page.getByRole("button", { name: "Help", exact: true }).click()
  await expect(page.getByRole("dialog")).toBeVisible(); await page.keyboard.press("Escape")
  await expect(page.getByRole("button", { name: "Help", exact: true })).toBeFocused()
})

test("bulk ZIP includes every format with the chosen reader-edition scope", async ({ page }) => {
  const novelScopes: string[] = []
  page.on("request", (request) => { if (request.url().includes("/novel/export?")) novelScopes.push(new URL(request.url()).searchParams.get("preview_chapters") ?? "all") })
  await page.goto(route); await chooseTask(page, "Reader edition", "novel")
  await page.getByLabel("Export first 2 chapters only", { exact: false }).check()
  await chooseTask(page, "Notes backup", "notes")
  await page.getByText("Download every available format", { exact: true }).click()
  await expect(page.getByText(/first 2 novel chapters only/)).toBeVisible()
  const downloading = page.waitForEvent("download"); await page.getByRole("button", { name: "Export everything", exact: true }).click()
  const download = await downloading
  expect(download.suggestedFilename()).toBe("Sky-of-Ash-all-exports.zip")
  const entries = Object.keys(unzipSync(await readFile((await download.path())!)))
  expect(entries).toHaveLength(13)
  expect(entries).toContain("novel/Sky-of-Ash-novel-preview.epub")
  expect(entries).toContain("FONT-NOTICE.txt")
  expect(novelScopes).toEqual(["2", "2", "2"])
})

test("long publishing fields are preserved and validated without truncation", async ({ page }, info) => {
  await page.setViewportSize({ width: 390, height: 1000 })
  await page.goto(route); await chooseTask(page, "Reader edition", "novel")
  await page.getByText("Publishing details", { exact: true }).click()
  const longText = "Unbroken".repeat(90)
  await page.getByLabel("Publisher", { exact: true }).fill(longText)
  await expect(page.getByText("Publisher must be 500 characters or fewer.", { exact: true })).toBeVisible()
  await expect(page.getByLabel("Publisher", { exact: true })).toHaveValue(longText)
  await expect(page.getByRole("button", { name: "Save novel settings" })).toBeDisabled()
  await expect(page.getByRole("button", { name: "Export novel", exact: true })).toBeDisabled()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.screenshot({ path: info.outputPath("publishing-validation-mobile.png"), fullPage: true })
})

test("large vault previews keep every file reachable and round-trip review is readable in light mode", async ({ page }, info) => {
  const longPath = `Sky Vault/World/${"LongUnbrokenName".repeat(12)}.md`
  await page.addInitScript(() => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "light" }, version: 0 })))
  await page.route("**/api/v1/books/book-1/export/character-bible/preview", (request) => request.fulfill({ json: {
    root_folder: "Sky Vault", files: [...Array.from({ length: 100 }, (_, index) => ({ path: `Sky Vault/Characters/Person-${index}.md`, content: `Reference ${index}` })), { path: longPath, content: "Rare final entry" }],
  } }))
  await page.setViewportSize({ width: 390, height: 1000 })
  await page.goto(route); await chooseTask(page, "Character bible", "character-bible")
  await page.getByRole("button", { name: "Preview export files" }).click()
  await expect(page.getByText("101 notes visible", { exact: true })).toBeVisible()
  await page.getByLabel("Search notes or content").fill("Rare final entry")
  await page.getByRole("button", { name: longPath.replace("Sky Vault/", ""), exact: true }).click()
  await expect(page.getByLabel("Vault note content")).toHaveValue("Rare final entry")
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.screenshot({ path: info.outputPath("vault-long-light.png"), fullPage: true })
  await page.getByLabel("Search notes or content").fill("no-such-file")
  await expect(page.getByText("No notes match that search.")).toBeVisible()
  await expect(page.getByLabel("Vault note content")).toHaveValue("Rare final entry")
  await page.getByRole("button", { name: "Clear search", exact: true }).click()
  await expect(page.getByText("101 notes visible", { exact: true })).toBeVisible()
  await chooseTask(page, "Manuscript", "manuscript")
  await page.getByText("Word and Scrivener round trip", { exact: true }).click()
  await page.getByLabel("Choose manuscript or Scrivener archive").setInputFiles({ name: "draft.docx", mimeType: "application/octet-stream", buffer: Buffer.from("document") })
  await page.getByLabel(/I reviewed this preview/).check()
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.screenshot({ path: info.outputPath("round-trip-light.png"), fullPage: true })
})
