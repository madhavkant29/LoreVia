import { expect, test, type Page } from "@playwright/test"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"

const path = "/sky-of-ash--book-1/visibility"
const preferencePath = "/api/v1/auth/me/ui-preferences/books/book-1"
const initialPreference = { book_id: "book-1", schema_version: 1, revision: 1, book_preset: "draft", advanced_tool_override: null, hidden_book_tools: [], overview_cards: {}, reader_actions: [], mobile_actions: [], panel_state: {}, timeline_collapsed_sections: {}, updated_at: null }
async function install(page: Page) {
  await installMockApi(page)
  await page.addInitScript(() => {
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
    if (!localStorage.getItem("lorevia-preferences")) localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 }))
  })
  const state = { book: { id: "book-1", title: "Sky of Ash", status: "ready", access_class: "owner", workspace_shell: "author", mode: "author", total_chapters: 12, is_public: false, public_slug: "reserved-title", public_status: "draft", moderation_status: "clean", hidden_at: null, archived_at: null } as Record<string, unknown>, preference: structuredClone(initialPreference) as Record<string, unknown>, summary: { book_id: "book-1", access_class: "owner", workspace_shell: "author", badges: ["Private"], private_status: { state: "private", label: "Private workspace", detail: "Only authorized workspace users can access this project." }, collaborators: { state: "shared", label: "Shared collaborators", count: 2 }, beta_readers: { state: "active", label: "Beta readers assigned", count: 3 }, public_publishing: { state: "private", label: "Publishing is draft", detail: "Public visibility: private" }, public_discussion: { state: "active", label: "Public discussion active", count: 1 }, rights: { state: "unconfirmed", label: "Rights not confirmed" }, moderation: { state: "clean", label: "Moderation: clean", detail: "No reports requiring attention." }, public_url: "https://getlorevia.com/public/books/reserved-title" }, fail: new Set<string>(), writes: [] as Array<{ path: string; body: { operations: Array<{ op: string; path: string; value?: unknown }> } }>, summaryReads: 0, preferenceReads: 0, gate: null as Promise<void> | null }
  await page.route("**/api/v1/**", async route => {
    const url = new URL(route.request().url()); const method = route.request().method()
    if (url.pathname === "/api/v1/books/book-1") {
      if (state.fail.has("book")) return route.fulfill({ status: 503, json: { detail: "Unavailable" } })
      return route.fulfill({ json: state.book })
    }
    if (url.pathname.endsWith("/visibility-summary")) { state.summaryReads++; return route.fulfill({ status: state.fail.has("summary") ? 503 : 200, json: state.fail.has("summary") ? { detail: "Unavailable" } : state.summary }) }
    if (url.pathname === preferencePath && method === "GET") {
      state.preferenceReads++; if (state.gate) await state.gate
      return route.fulfill({ status: state.fail.has("preferences") ? 503 : 200, json: state.fail.has("preferences") ? { detail: "Unavailable" } : state.preference })
    }
    if (url.pathname.includes("/ui-preferences") && method === "PATCH") {
      const body = route.request().postDataJSON(); state.writes.push({ path: url.pathname, body })
      if (state.fail.has("sync")) return route.fulfill({ status: 503, json: { detail: "Offline" } })
      for (const operation of body.operations) {
        const [key, child] = operation.path.slice(1).split("/")
        if (child) { const target = { ...state.preference[key] as Record<string, unknown> }; if (operation.op === "unset") delete target[child]; else target[child] = operation.value; state.preference[key] = target }
        else state.preference[key] = operation.value
      }
      state.preference.revision = Number(state.preference.revision) + 1
      return route.fulfill({ json: state.preference })
    }
    return route.fallback()
  })
  return state
}
async function open(page: Page) { await page.goto(path); await expect(page.getByRole("heading", { name: "Private workspace", exact: true })).toBeVisible() }
async function advanced(page: Page) { await page.getByText("Advanced: workspace navigation", { exact: true }).click(); await expect(page.getByRole("button", { name: "Show Setup & Payoff", exact: true })).toBeEnabled() }

test("visibility preserves editorial readability at four widths in both themes", async ({ page }, info) => {
  await install(page); await open(page)
  await expect(page.getByRole("heading", { name: "Hidden and visible tools" })).toHaveCount(0)
  for (const theme of ["dark", "light"]) {
    if (theme === "light") { await page.evaluate(() => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "light" }, version: 0 }))); await page.reload(); await expect(page.getByRole("heading", { name: "Private workspace" })).toBeVisible() }
    for (const width of [1440, 1280, 768, 390]) { await page.setViewportSize({ width, height: 1000 }); expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy(); await page.screenshot({ path: info.outputPath(`${theme}-${width}.png`), fullPage: true }) }
    expect(await criticalAccessibilityViolations(page, "[data-visibility-workspace]")).toEqual([])
  }
  await page.getByText("Rights and moderation", { exact: true }).click(); await expect(page.getByText("Rights not confirmed", { exact: true })).toBeVisible()
  await advanced(page); await page.getByRole("searchbox", { name: "Search tools" }).fill("Setup")
  expect(await criticalAccessibilityViolations(page, "[data-visibility-workspace]")).toEqual([])
  await page.screenshot({ path: info.outputPath("advanced-mobile.png"), fullPage: true })
})

test("visibility distinguishes a reserved URL from publication and uses the real public route", async ({ page }) => {
  const state = await install(page); await open(page)
  await expect(page.getByRole("heading", { name: "Not public", exact: true })).toBeVisible(); await expect(page.getByRole("link", { name: "Open public page" })).toHaveCount(0)
  state.book.public_status = "pending_review"; await page.getByRole("button", { name: "Refresh access", exact: true }).click(); await expect(page.getByRole("heading", { name: "Awaiting review" })).toBeVisible()
  state.book.is_public = true; state.book.public_status = "published"; await page.getByRole("button", { name: "Refresh access", exact: true }).click()
  await expect(page.getByRole("link", { name: "Open public page" })).toHaveAttribute("href", "/public/reserved-title")
  state.book.moderation_status = "under_review"; await page.getByRole("button", { name: "Refresh access", exact: true }).click(); await expect(page.getByRole("heading", { name: "Not public", exact: true })).toBeVisible()
  await expect(page.getByRole("link", { name: "Open public page" })).toHaveCount(0)
  await expect(page.getByText(/not a count of unique readers/)).toBeVisible(); await expect(page.getByText(/posts awaiting moderation/)).toBeVisible()
  await expect(page.getByRole("link", { name: "Manage public uploads" })).toHaveAttribute("href", "/public/uploads")
})

test("visibility recovers failed project and status requests and retains stale status honestly", async ({ page }) => {
  const state = await install(page); state.fail.add("book"); await page.goto(path)
  await expect(page.getByRole("button", { name: "Retry project" })).toBeVisible(); expect(state.summaryReads).toBe(0)
  state.fail.delete("book"); state.fail.add("summary"); await page.getByRole("button", { name: "Retry project" }).click()
  await expect(page.getByText("Visibility status could not be loaded.")).toBeVisible(); await expect(page.getByRole("heading", { name: "Not public", exact: true })).toHaveCount(0)
  state.fail.clear(); await page.getByRole("button", { name: "Retry access status" }).click(); await expect(page.getByRole("heading", { name: "Private workspace" })).toBeVisible()
  state.fail.add("summary"); await page.getByRole("button", { name: "Refresh access", exact: true }).click(); await expect(page.getByText(/last loaded information/)).toBeVisible(); await expect(page.getByRole("heading", { name: "Private workspace" })).toBeVisible()
})

test("visibility gates private summary requests for nonowners", async ({ page }) => {
  const state = await install(page); state.book.access_class = "reader_collaborator"; state.book.collaboration_role = "reader_only"; await page.goto(path)
  await expect(page.getByText("Only the project owner can inspect sharing and publication status.")).toBeVisible(); expect(state.summaryReads).toBe(0); expect(state.preferenceReads).toBe(0)
})

test("visibility recovers preference loading without claiming a failed load was saved", async ({ page }) => {
  const state = await install(page); state.fail.add("preferences"); await open(page); await page.getByText("Advanced: workspace navigation", { exact: true }).click()
  await expect(page.getByRole("button", { name: "Retry navigation preferences" })).toBeVisible(); await expect(page.getByRole("button", { name: "Show Setup & Payoff", exact: true })).toBeDisabled()
  const readsBeforeRetry = state.preferenceReads
  state.fail.clear(); await page.getByRole("button", { name: "Retry navigation preferences" }).click(); await expect(page.getByRole("button", { name: "Show Setup & Payoff", exact: true })).toBeEnabled()
  expect(state.preferenceReads).toBeGreaterThan(readsBeforeRetry)
})

test("visibility reveals only the selected tool and undoes its navigation change", async ({ page }) => {
  const state = await install(page); await open(page); await advanced(page)
  const show = page.getByRole("button", { name: "Show Setup & Payoff", exact: true }); await show.click()
  await expect(page.getByRole("button", { name: "Hide Setup & Payoff", exact: true })).toBeFocused()
  await expect.poll(() => state.writes.length).toBe(1)
  expect(state.writes[0].path).toBe(preferencePath)
  expect(state.preference.book_preset).toBe("draft"); expect(state.preference.advanced_tool_override).toBeNull()
  expect(state.writes[0].body.operations.map(operation => operation.path)).toEqual(["/hidden_book_tools", "/overview_cards/book.foreshadowing"])
  await expect(page.getByRole("button", { name: "Show World Gaps", exact: true })).toBeVisible()
  await page.getByRole("button", { name: "Undo navigation change" }).click(); await expect(page.getByRole("button", { name: "Show Setup & Payoff", exact: true })).toBeEnabled()
  await expect.poll(() => state.writes.length).toBe(2)
  expect((state.preference.overview_cards as Record<string, unknown>)["book.foreshadowing"]).toBeUndefined()
})

test("visibility retains pending navigation changes and retries sync", async ({ page }) => {
  const state = await install(page); await open(page); await advanced(page); state.fail.add("sync")
  await page.getByRole("button", { name: "Show Setup & Payoff", exact: true }).click(); await expect(page.getByText(/Navigation changes are pending sync/)).toBeVisible()
  await expect(page.getByRole("button", { name: "Hide Setup & Payoff", exact: true })).toBeVisible(); state.fail.delete("sync")
  await page.getByRole("button", { name: "Retry navigation sync" }).click(); await expect(page.getByRole("button", { name: "Retry navigation sync" })).toHaveCount(0)
  await page.reload(); await page.getByText("Advanced: workspace navigation", { exact: true }).click(); await expect(page.getByRole("button", { name: "Hide Setup & Payoff", exact: true })).toBeEnabled()
})

test("visibility searches and filters navigation without hiding its recovery route", async ({ page }) => {
  await install(page); await open(page); await advanced(page)
  await expect(page.getByRole("button", { name: "Hide Access & Visibility", exact: true })).toHaveCount(0)
  await page.getByRole("searchbox", { name: "Search tools" }).fill("setup"); await page.getByRole("combobox", { name: "Navigation visibility" }).selectOption("hidden")
  await expect(page.getByRole("button", { name: "Show Setup & Payoff", exact: true })).toBeVisible()
  await page.getByRole("combobox", { name: "Navigation visibility" }).selectOption("visible"); await expect(page.getByText("No tools match these filters.")).toBeVisible()
  await page.getByRole("combobox", { name: "Navigation visibility" }).selectOption("hidden")
  await page.getByRole("button", { name: "Show Setup & Payoff", exact: true }).click(); await expect(page.getByRole("searchbox", { name: "Search tools" })).toBeFocused()
  await page.getByRole("button", { name: "Clear tool filters" }).click(); await expect(page.getByRole("button", { name: "Show World Gaps", exact: true })).toBeVisible()
})

test("visibility keeps zero counts and long moderation details readable", async ({ page }, info) => {
  const state = await install(page)
  state.summary.collaborators.count = 0; state.summary.collaborators.state = "not_shared"; state.summary.collaborators.label = "No active collaborators"
  state.summary.beta_readers.count = 0; state.summary.public_discussion.count = 0
  state.summary.moderation.state = "under_review"; state.summary.moderation.label = "Moderation: under review"
  state.summary.moderation.detail = "The public edition is under review. " + "Editorial context and the source declaration are available to the moderation team. ".repeat(6)
  await open(page); await expect(page.getByText("0 assignments", { exact: true })).toBeVisible(); await expect(page.getByText("0 posts", { exact: true })).toBeVisible()
  await page.getByText("Rights and moderation", { exact: true }).click(); await page.setViewportSize({ width: 390, height: 1000 })
  await page.getByText("Moderation: under review", { exact: true }).scrollIntoViewIfNeeded()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  expect(await criticalAccessibilityViolations(page, "[data-visibility-workspace]")).toEqual([])
  await page.screenshot({ path: info.outputPath("moderation-mobile.png") })
})
