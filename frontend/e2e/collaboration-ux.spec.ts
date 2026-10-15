import { expect, test, type Page } from "@playwright/test"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"

const path = "/sky-of-ash--book-1/collaboration"
const base = "/api/v1/books/book-1/collaborators"
const person = { id: "person-1", email: "editor.with.a.long.address@example.com", display_name: "Alexandra Editorial Collaborator", role: "commenter", invite_status: "active", permissions: { can_edit_manuscript: false, can_view_story_bible: false, can_run_ai_scans: false, can_export: false, can_comment: true, can_view_selected_chapters_only: true }, scope: { chapter_start: 2, chapter_end: 5, character_bible: false, continuity_report: false, reader_confusion_report: false } }
async function install(page: Page, options: { free?: boolean; nonowner?: boolean; count?: number } = {}) {
  await installMockApi(page, { userTier: options.free ? "free" : "author" })
  await page.addInitScript(() => {
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
    if (!localStorage.getItem("lorevia-preferences")) localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 }))
  })
  const state = { people: Array.from({ length: options.count ?? 1 }, (_, index) => ({ ...structuredClone(person), id: `person-${index + 1}`, email: index ? `person${index}@example.com` : person.email, display_name: index ? `Reader ${String(index).padStart(3, "0")}` : person.display_name })), failList: false, failActivity: false, failWrite: false, failBook: false, listRequests: 0, writes: [] as Array<Record<string, unknown>>, pending: null as Promise<void> | null }
  await page.route("**/api/v1/**", async route => {
    const url = new URL(route.request().url()); const method = route.request().method()
    if (url.pathname === "/api/v1/books/book-1" && method === "GET") {
      if (state.failBook) return route.fulfill({ status: 503, json: { detail: "Unavailable" } })
      if (options.nonowner) return route.fulfill({ json: { id: "book-1", title: "Sky of Ash", access_class: "collaborator", workspace_shell: "reader", mode: "reader", total_chapters: 5 } })
    }
    if (url.pathname === base && method === "GET") { state.listRequests++; return route.fulfill({ status: state.failList ? 503 : 200, json: state.failList ? { detail: "Unavailable" } : state.people }) }
    if (url.pathname.startsWith(base) && url.pathname.endsWith("/activity")) return route.fulfill({ status: state.failActivity ? 503 : 200, json: state.failActivity ? { detail: "Unavailable" } : { collaborator: state.people[0], assignments: [], chapter_comment_count: 35, annotation_count: 0, latest_activity_at: null, items: Array.from({ length: 35 }, (_, i) => ({ id: `activity-${i}`, title: `Chapter observation ${i + 1}`, body: "The motivation is clearer here. A long editorial note should remain readable without hiding the original chapter link.", kind: "chapter_comment", chapter_number: 2, created_at: "2026-10-01T12:00:00Z" })) } })
    if (url.pathname.startsWith(base) && ["POST", "PUT"].includes(method)) {
      const body = route.request().postDataJSON(); state.writes.push(body)
      if (state.pending) await state.pending
      if (state.failWrite) return route.fulfill({ status: 503, json: { detail: "Unavailable" } })
      const existing = state.people.find(row => row.id === url.pathname.split("/").at(-1))
      const result = { ...(existing ?? person), ...body, id: existing?.id ?? `created-${state.writes.length}` }
      state.people = [result, ...state.people.filter(row => row.id !== result.id)]
      return route.fulfill({ json: result })
    }
    return route.fallback()
  })
  return state
}
async function open(page: Page) { await page.goto(path); await expect(page.getByRole("heading", { name: "People with access" })).toBeVisible() }
async function invite(page: Page) { await page.getByRole("button", { name: "Invite collaborator" }).click(); await expect(page.getByLabel("Email", { exact: true })).toBeFocused() }

test("collaboration is readable at four widths in both themes with visible mobile actions", async ({ page }, info) => {
  await install(page); await open(page)
  for (const theme of ["dark", "light"]) {
    if (theme === "light") { await page.evaluate(() => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "light" }, version: 0 }))); await page.reload(); await expect(page.getByText(person.display_name, { exact: true })).toBeVisible() }
    for (const width of [1440, 1280, 768, 390]) {
      await page.setViewportSize({ width, height: 1000 })
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
      await expect(page.getByRole("button", { name: "Edit access", exact: true })).toBeVisible()
      await page.screenshot({ path: info.outputPath(`${theme}-${width}.png`), fullPage: true })
    }
    expect(await criticalAccessibilityViolations(page, "[data-collaboration-workspace]")).toEqual([])
  }
  await invite(page); await page.getByText("Advanced permissions and scope", { exact: true }).click()
  expect(await criticalAccessibilityViolations(page, "[data-collaboration-workspace]")).toEqual([])
  await page.screenshot({ path: info.outputPath("access-form-mobile.png"), fullPage: true })
})

test("collaboration separates failed loading from empty people and retries activity", async ({ page }) => {
  const state = await install(page); state.failList = true; await open(page)
  await expect(page.getByRole("button", { name: "Retry people" })).toBeVisible()
  await expect(page.getByText("No collaborators yet")).toHaveCount(0)
  await expect(page.getByRole("button", { name: "Invite collaborator" })).toBeDisabled()
  state.failList = false; await page.getByRole("button", { name: "Retry people" }).click(); await expect(page.getByText(person.display_name, { exact: true })).toBeVisible()
  state.failActivity = true; await page.getByRole("button", { name: "View activity" }).click(); await expect(page.getByRole("button", { name: "Retry activity" })).toBeVisible()
  state.failActivity = false; await page.getByRole("button", { name: "Retry activity" }).click(); await expect(page.getByText("Chapter observation 1", { exact: true })).toBeVisible()
  await expect(page.getByRole("link", { name: "Chapter 2", exact: true }).first()).toHaveAttribute("href", "/sky-of-ash--book-1/chapter/2")
  await page.getByRole("button", { name: "Show more activity (5 remaining)" }).click(); await expect(page.getByText("Chapter observation 35", { exact: true })).toBeVisible()
  await page.getByRole("button", { name: "Close activity" }).click(); await expect(page.getByRole("button", { name: "View activity" })).toBeFocused()
  state.failList = true; await page.getByRole("button", { name: "Refresh people" }).click(); await expect(page.getByText(/last loaded access/)).toBeVisible(); await expect(page.getByText(person.display_name, { exact: true })).toBeVisible()
  state.failList = false; state.people = []; await page.getByRole("button", { name: "Retry people" }).click(); await expect(page.getByText("No collaborators yet")).toBeVisible()
})

test("collaboration validates identity and scope before granting explicit access", async ({ page }) => {
  const state = await install(page); await open(page); await invite(page)
  const submit = page.getByRole("button", { name: "Grant access", exact: true })
  await submit.click(); await expect(page.getByRole("form").getByRole("alert")).toContainText("valid email")
  await page.getByLabel("Email", { exact: true }).fill(person.email.toUpperCase()); await submit.click(); await expect(page.getByRole("form").getByRole("alert")).toContainText("already listed")
  await page.getByLabel("Email", { exact: true }).fill("new@example.com")
  await page.getByLabel("From chapter").fill("5"); await page.getByLabel("Through chapter").fill("2"); await submit.click(); await expect(page.getByRole("form").getByRole("alert")).toContainText("later")
  expect(state.writes).toHaveLength(0)
  await page.getByLabel("Through chapter").fill("8"); await submit.click(); await expect(page.getByText("Access granted.", { exact: true })).toBeVisible()
  expect(state.writes[0]).toMatchObject({ email: "new@example.com", role: "commenter", scope: { chapter_start: 5, chapter_end: 8 } })
  await expect(page.getByRole("cell", { name: "Chapters 5–8", exact: false })).toBeVisible()
})

test("collaboration preserves failed drafts and serializes saving", async ({ page }) => {
  const state = await install(page); await open(page); await invite(page)
  await page.getByLabel("Email", { exact: true }).fill("new@example.com"); state.failWrite = true
  await page.getByRole("button", { name: "Grant access", exact: true }).click(); await expect(page.getByRole("form").getByRole("alert")).toContainText("draft is still here")
  await expect(page.getByLabel("Email", { exact: true })).toHaveValue("new@example.com")
  state.failWrite = false; let release!: () => void; state.pending = new Promise(resolve => { release = resolve })
  await page.getByRole("button", { name: "Grant access", exact: true }).click(); await expect(page.getByRole("button", { name: "Saving…", exact: true })).toBeDisabled(); await expect(page.getByLabel("Email", { exact: true })).toBeDisabled()
  await expect(page.getByRole("button", { name: "Revoke", exact: true })).toBeDisabled(); expect(state.writes).toHaveLength(2)
  release(); await expect(page.getByText("Access granted.", { exact: true })).toBeVisible()
})

test("collaboration edits, confirms revocation and restores existing access", async ({ page }) => {
  const state = await install(page); await open(page)
  await page.getByRole("button", { name: "Edit access", exact: true }).click(); await expect(page.getByLabel("Email", { exact: true })).toHaveAttribute("readonly", "")
  await page.getByRole("combobox", { name: "Role", exact: true }).selectOption("editor"); await expect(page.getByLabel("Limit to selected chapters")).not.toBeChecked()
  await page.getByRole("button", { name: "Save access changes" }).click(); await expect(page.getByText("Access changes saved.")).toBeVisible()
  expect(state.writes[0]).toMatchObject({ role: "editor", permissions: { can_edit_manuscript: true }, scope: { chapter_start: null, character_bible: true } })
  await page.getByRole("button", { name: "Revoke", exact: true }).click(); const dialog = page.getByRole("dialog")
  await expect(dialog).toContainText("Existing comments and activity remain")
  await dialog.getByRole("button", { name: "Keep access" }).click(); expect(state.writes).toHaveLength(1)
  await page.getByRole("button", { name: "Revoke", exact: true }).click(); await dialog.getByRole("button", { name: "Revoke access", exact: true }).click(); await expect(page.getByText("Collaborator access revoked.")).toBeVisible()
  await expect(page.getByText("No active collaborator access")).toBeVisible()
  await page.getByRole("button", { name: "Restore access", exact: true }).click(); await page.getByRole("form").getByRole("button", { name: "Restore access", exact: true }).click(); await expect(page.getByText("Access restored.")).toBeVisible()
  expect(state.writes[2]).toMatchObject({ invite_status: "active", role: "editor" }); expect(state.people).toHaveLength(1)
})

test("collaboration guards unsaved drafts and filters large lists", async ({ page }) => {
  await install(page, { count: 31 }); await open(page)
  await expect(page.getByText("Showing 25 of 31 people")).toBeVisible(); await page.getByRole("button", { name: "Show more people (6 remaining)" }).click(); await expect(page.getByText("Showing 31 of 31 people")).toBeVisible()
  await page.getByRole("searchbox", { name: "Search collaborators" }).fill("READER 030"); await expect(page.getByText("Showing 1 of 1 people")).toBeVisible()
  await page.getByRole("combobox", { name: "Access status" }).selectOption("revoked"); await expect(page.getByText("No collaborators match these filters.")).toBeVisible(); await page.getByRole("button", { name: "Clear filters" }).click()
  await invite(page); await page.getByLabel("Email", { exact: true }).fill("draft@example.com"); await page.getByRole("button", { name: "Cancel", exact: true }).first().click()
  await page.getByRole("dialog").getByRole("button", { name: "Keep editing" }).click(); await expect(page.getByLabel("Email", { exact: true })).toHaveValue("draft@example.com")
  page.once("dialog", dialog => dialog.dismiss()); await page.getByRole("link", { name: "Beta reader assignments", exact: true }).click(); await expect(page).toHaveURL(new RegExp("/collaboration$"))
  await page.getByRole("button", { name: "Cancel", exact: true }).first().click(); await page.getByRole("dialog").getByRole("button", { name: "Discard changes" }).click(); await expect(page.getByRole("form")).toHaveCount(0)
})

test("collaboration denies free plans before fetching private people", async ({ page }) => {
  const state = await install(page, { free: true }); await page.goto(path)
  await expect(page.getByText("Managing collaborators requires an Author or Architect plan.")).toBeVisible(); expect(state.listRequests).toBe(0)
})


test("collaboration denies nonowners before fetching private people", async ({ page }) => {
  const state = await install(page, { nonowner: true }); await page.goto(path)
  await expect(page.getByText("Only the project owner can manage collaborator access.")).toBeVisible(); expect(state.listRequests).toBe(0)
})

test("collaboration recovers a failed project request", async ({ page }) => {
  const state = await install(page); state.failBook = true; await page.goto(path)
  await expect(page.getByRole("button", { name: "Retry project" })).toBeVisible(); expect(state.listRequests).toBe(0)
  state.failBook = false; await page.getByRole("button", { name: "Retry project" }).click()
  await expect(page.getByText(person.display_name, { exact: true })).toBeVisible()
})


test("collaboration makes failed revocation explicit and retains the person", async ({ page }) => {
  const state = await install(page); await open(page); state.failWrite = true
  await page.getByRole("button", { name: "Revoke", exact: true }).click(); await page.getByRole("dialog").getByRole("button", { name: "Revoke access", exact: true }).click()
  await expect(page.getByText("Could not confirm that access was revoked. Refresh the people list to check its current state.")).toBeVisible()
  await expect(page.getByRole("button", { name: "Revoke", exact: true })).toBeEnabled()
  state.failWrite = false; await page.getByRole("button", { name: "Refresh people" }).click(); await expect(page.getByRole("cell", { name: "Active", exact: true })).toBeVisible()
})

test("collaboration applies explicit resource permissions and shows readable activity", async ({ page }, info) => {
  const state = await install(page); await open(page); await page.getByRole("button", { name: "Edit access", exact: true }).click()
  await page.getByRole("combobox", { name: "Role", exact: true }).selectOption("editor")
  await page.getByText("Advanced permissions and scope", { exact: true }).click()
  await page.getByLabel("View story bible", { exact: true }).uncheck(); await page.getByLabel("Run review tools", { exact: true }).uncheck()
  await expect(page.getByLabel("Character bible", { exact: true })).toBeDisabled()
  await expect(page.getByLabel("Continuity report", { exact: true })).not.toBeChecked()
  await page.getByRole("button", { name: "Save access changes" }).click(); await expect(page.getByText("Access changes saved.")).toBeVisible()
  expect(state.writes[0]).toMatchObject({ scope: { character_bible: false, continuity_report: false, reader_confusion_report: false } })
  await page.getByRole("button", { name: "View activity" }).click(); await expect(page.getByText("Chapter observation 1", { exact: true })).toBeVisible()
  await page.locator("#activity-heading").evaluate(element => element.scrollIntoView({ block: "start", behavior: "instant" }))
  await expect(page.getByText("Chapter observation 1", { exact: true })).toBeInViewport()
  await page.screenshot({ path: info.outputPath("activity-desktop.png") })
  await page.setViewportSize({ width: 390, height: 1000 }); await page.getByRole("heading", { name: person.display_name, exact: true }).scrollIntoViewIfNeeded()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  expect(await criticalAccessibilityViolations(page, "[data-collaboration-workspace]")).toEqual([])
  await page.screenshot({ path: info.outputPath("activity-mobile.png") })
})
