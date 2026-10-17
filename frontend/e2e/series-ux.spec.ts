import { expect, test, type Page } from "@playwright/test"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"

const project = { id: "book-1", title: "The Ember Gate", mode: "author", work_type: "screenplay", access_class: "owner", series_order: 1, primary_series_id: "series-1", series_name: "Gate Cycle", progress_pct: 25, chapters_read_count: 1, chapters_left: 3, marked_complete_in_series: false }
const spare = { ...project, id: "book-3", title: "The Last Crossing", primary_series_id: null, series_name: null, series_order: null }
const collection = [
  { id: "series-1", name: "Gate Cycle", description: "Three journeys across the old border.", books: [project] },
  { id: "series-2", name: "Northern Letters", description: "A companion cycle.", books: [] as typeof project[] },
]
const review = { cached: false, retrieved_passages: [{ book_title: "Earlier Crossing", chapter_num: 2, chapter_title: "The oath", excerpt: "Only the keeper may cross at dusk." }], review: { overall_verdict: "Clarify the crossing rule", thematic_fit: { notes: "The recurring oath fits." }, continuity_issues: [{ title: "Keeper identity", severity: "minor", description: "The new keeper is not introduced.", suggestion: "Name the keeper." }], cross_book_opportunities: [] } }
const list = (items = collection) => ({ items, total: items.length, limit: 100, offset: 0, has_more: false })
async function selectSecond(page: Page) { await page.getByRole("button", { name: "Northern Letters 0 projects" }).click() }

test.beforeEach(async ({ page }) => {
  await installMockApi(page)
  await page.addInitScript(() => { localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 })); document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax" })
  await page.route("**/api/v1/books/series?*", (route) => route.fulfill({ json: list() }))
  await page.route("**/api/v1/books/page?*", (route) => route.fulfill({ json: { items: [project, spare], next_cursor: null } }))
})

test("series stays readable at four widths and both themes with keyboard Help", async ({ page }, info) => {
  const errors: string[] = []; page.on("pageerror", (error) => errors.push(error.message))
  await page.goto("/series")
  await expect(page.getByRole("heading", { name: "Gate Cycle", exact: true })).toBeVisible()
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    if (width < 1024) await expect.poll(() => page.locator("aside").first().evaluate((element) => element.getBoundingClientRect().right)).toBeLessThanOrEqual(0)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
    await page.screenshot({ path: info.outputPath(`series-${width}.png`), fullPage: true, animations: "disabled" })
  }
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.getByRole("button", { name: "Help", exact: true }).focus(); await page.keyboard.press("Enter")
  await expect(page.getByRole("dialog")).toBeVisible(); await page.keyboard.press("Escape")
  await expect(page.getByRole("button", { name: "Help", exact: true })).toBeFocused()
  await page.getByRole("button", { name: "Toggle theme", exact: true }).click()
  await page.waitForTimeout(250)
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.screenshot({ path: info.outputPath("series-light-mobile.png"), fullPage: true })
  await page.getByLabel("Selected series", { exact: true }).selectOption("series-2")
  await expect(page.getByText("No projects have been added to this series.")).toBeVisible()
  expect(errors).toEqual([])
})

test("initial, partial, and refresh failures remain distinct and retryable", async ({ page }) => {
  let fail = true
  await page.route("**/api/v1/books/series?*", (route) => fail ? route.fulfill({ status: 503, json: {} }) : route.fallback())
  await page.goto("/series")
  await expect(page.getByText("Your series could not be loaded. Check your access or try again.")).toBeVisible()
  await expect(page.getByText(/No series yet/)).toHaveCount(0)
  fail = false; await page.getByRole("button", { name: "Retry series", exact: true }).click()
  await expect(page.getByRole("heading", { name: "Gate Cycle", exact: true })).toBeVisible()
  fail = true; await page.getByRole("button", { name: "Refresh series", exact: true }).click()
  await expect(page.getByText("Series could not be refreshed. Previously loaded projects remain visible.")).toBeVisible()
  await expect(page.getByRole("button", { name: "Add project", exact: true })).toBeDisabled()
  fail = false
  await page.route("**/api/v1/books/page?*", (route) => route.fulfill({ status: 503, json: {} }))
  await page.getByRole("button", { name: "Retry series", exact: true }).click()
  await expect(page.getByText("Available projects could not be loaded. Series browsing still works.")).toBeVisible()
  await selectSecond(page)
  await expect(page.getByRole("heading", { name: "Northern Letters", exact: true })).toBeVisible()
  await page.route("**/api/v1/books/page?*", (route) => route.fulfill({ json: { items: [spare], next_cursor: null } }))
  await page.getByRole("button", { name: "Retry available projects" }).click()
  await expect(page.getByRole("button", { name: "Add project", exact: true })).toBeEnabled()
})

test("new series preserves failed drafts and selects the confirmed creation", async ({ page }) => {
  let rows = structuredClone(collection)
  let fail = true
  await page.route("**/api/v1/books/series?*", (route) => route.fulfill({ json: list(rows) }))
  await page.route("**/api/v1/books/series", async (route) => {
    if (fail) return route.fulfill({ status: 503, json: {} })
    const payload = route.request().postDataJSON()
    expect(payload).toEqual({ name: "Sea Letters", description: "A coastal cycle." })
    const created = { ...payload, id: "series-3", books: [] }; rows = [...rows, created]
    await route.fulfill({ json: created })
  })
  await page.goto("/series"); await page.getByRole("button", { name: "New series", exact: true }).click()
  await page.getByLabel("Series name", { exact: true }).fill("Sea Letters")
  await page.getByLabel("Series description").fill("A coastal cycle.")
  await page.getByRole("button", { name: "Create series", exact: true }).click()
  await expect(page.getByText(/Creation could not be confirmed/)).toBeVisible()
  await expect(page.getByLabel("Series name", { exact: true })).toHaveValue("Sea Letters")
  page.once("dialog", (dialog) => dialog.dismiss())
  await page.getByRole("button", { name: "Cancel new series" }).click()
  await expect(page.getByLabel("Series description")).toHaveValue("A coastal cycle.")
  fail = false; await page.getByRole("button", { name: "Refresh series", exact: true }).click()
  await expect(page.getByRole("button", { name: "Create series", exact: true })).toBeEnabled()
  await page.getByRole("button", { name: "Create series", exact: true }).click()
  await expect(page.getByRole("heading", { name: "Sea Letters", exact: true })).toBeVisible()
  await expect(page.getByText("No projects have been added to this series.")).toBeVisible()
})

test("project changes validate positions, explain effects, and preserve failed forms", async ({ page }) => {
  const rows = structuredClone(collection)
  let fail = true
  let completeCalls = 0
  await page.route("**/api/v1/books/series?*", (route) => route.fulfill({ json: list(rows) }))
  await page.route("**/api/v1/books/series/series-1/books/book-3", async (route) => {
    if (fail) return route.fulfill({ status: 503, json: {} })
    expect(route.request().postDataJSON()).toEqual({ position: 2 })
    rows[0].books.push({ ...project, ...spare, primary_series_id: "series-1", series_name: "Gate Cycle", series_order: 2 })
    await route.fulfill({ json: rows[0] })
  })
  await page.route("**/api/v1/books/series/series-1/books/book-1/status", async (route) => {
    completeCalls++; expect(route.request().postDataJSON()).toEqual({ marked_complete: true })
    rows[0].books[0].marked_complete_in_series = true
    await route.fulfill({ json: rows[0].books[0] })
  })
  await page.route("**/api/v1/books/series/series-1/books/book-1", async (route) => { rows[0].books = rows[0].books.filter((item) => item.id !== "book-1"); await route.fulfill({ json: rows[0] }) })
  await page.goto("/series"); await page.getByRole("button", { name: "Add project", exact: true }).click()
  await page.getByLabel("Project to add").selectOption("book-3"); await page.getByLabel("Series position").fill("-2")
  await expect(page.getByRole("button", { name: "Add", exact: true })).toBeDisabled()
  await expect(page.getByLabel("Series position")).toHaveValue("-2")
  await page.getByLabel("Series position").fill("2"); await page.getByRole("button", { name: "Add", exact: true }).click()
  await expect(page.getByText(/The change could not be confirmed/)).toBeVisible()
  await expect(page.getByLabel("Project to add")).toHaveValue("book-3")
  fail = false; await page.getByRole("button", { name: "Add", exact: true }).click()
  await expect(page.getByText("Project added. Review its position in the series below.")).toBeVisible()
  page.once("dialog", async (dialog) => { expect(dialog.message()).toContain("all of its chapters as read"); await dialog.dismiss() })
  await page.getByRole("button", { name: "Mark complete", exact: true }).first().click()
  expect(completeCalls).toBe(0)
  page.once("dialog", (dialog) => dialog.accept())
  await page.getByRole("button", { name: "Mark complete", exact: true }).first().click()
  await expect(page.getByRole("button", { name: "Marked complete", exact: true })).toBeDisabled()
  page.once("dialog", async (dialog) => { expect(dialog.message()).toContain("content will stay in your library"); await dialog.accept() })
  await page.getByRole("button", { name: "Remove", exact: true }).first().click()
  await expect(page.getByText("Project removed from this series. Its content remains in your library.")).toBeVisible()
  await expect(page.getByRole("link", { name: "The Ember Gate", exact: true })).toHaveCount(0)
})

test("world strings and long bibles render fully with retry and no stale series context", async ({ page }, info) => {
  let fail = true
  await page.route("**/world-building/series-analysis", (route) => fail ? route.fulfill({ status: 503, json: {} }) : route.fulfill({ json: { book_count: 1, analysis_count: 2, world_context: "The old gate opens at dusk.\nIts keeper holds the only key." } }))
  await page.route("**/books/series/series-1/bible", (route) => route.fulfill({ json: { episode_count: 8, episodes: [], recurring_characters: Array.from({ length: 8 }, (_, index) => ({ name: `Keeper ${index + 1}`, episode_count: 2 })), continuity_risks: [], unresolved_plot_threads: [], recurring_relationships: [], canon_entries: [] } }))
  await page.goto("/series"); await page.getByRole("button", { name: "World analysis", exact: true }).click()
  await expect(page.getByText("This series context could not be loaded.")).toBeVisible()
  fail = false; await page.getByRole("button", { name: "Retry series context" }).click()
  await expect(page.getByText(/Its keeper holds the only key/)).toBeVisible()
  await page.getByRole("button", { name: "Series bible", exact: true }).click()
  await expect(page.getByText("Keeper 8 · 2 episodes", { exact: true })).toHaveCount(0)
  await page.getByRole("button", { name: "Show all 8 recurring characters" }).click()
  await expect(page.getByText("Keeper 8 · 2 episodes", { exact: true })).toBeVisible()
  await page.setViewportSize({ width: 390, height: 1000 })
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }))
  await page.screenshot({ path: info.outputPath("series-bible-mobile.png"), fullPage: true, animations: "disabled" })
  let release: (() => void) | undefined
  const waiting = new Promise<void>((resolve) => { release = resolve })
  await page.route("**/world-building/series-analysis", async (route) => { await waiting; await route.fulfill({ json: { world_context: "Stale previous-series context" } }) })
  await page.getByRole("button", { name: "World analysis", exact: true }).click()
  await page.getByRole("button", { name: "Refresh context", exact: true }).click()
  await page.getByLabel("Selected series", { exact: true }).selectOption("series-2"); release?.()
  await expect(page.getByRole("heading", { name: "Northern Letters", exact: true })).toBeVisible()
  await expect(page.getByText("Stale previous-series context")).toHaveCount(0)
})

test("continuity validates intact input, submits the API contract, and preserves review provenance", async ({ page }, info) => {
  let fail = true
  await page.route("**/continuity-check-stream", (route) => {
    expect(route.request().postDataJSON()).toEqual({ messages: [], book_id: "book-1", text: "The stranger crosses at dusk.", chapter_num: 2 })
    return fail ? route.fulfill({ status: 503, json: {} }) : route.fulfill({ contentType: "text/event-stream", body: `event: done\ndata: ${JSON.stringify(review)}\n\n` })
  })
  await page.goto("/series"); await page.getByRole("button", { name: "Continuity check", exact: true }).click()
  await page.getByLabel("Project to check").selectOption("book-1")
  await page.getByLabel("Chapter or scene number").fill("-2")
  await page.getByLabel("Passage to cross-check").fill("The stranger crosses at dusk.")
  await expect(page.getByRole("button", { name: "Run continuity check" })).toBeDisabled()
  await expect(page.getByLabel("Chapter or scene number")).toHaveValue("-2")
  await page.getByLabel("Chapter or scene number").fill("2")
  await page.getByLabel("Passage to cross-check").fill("a".repeat(4001))
  await expect(page.getByText(/Use 4,000 characters or fewer/)).toBeVisible()
  await expect(page.getByRole("button", { name: "Run continuity check" })).toBeDisabled()
  await page.getByLabel("Passage to cross-check").fill("The stranger crosses at dusk.")
  await page.getByRole("button", { name: "Run continuity check" }).click()
  await expect(page.getByText(/The continuity check could not be completed/)).toBeVisible()
  await expect(page.getByLabel("Passage to cross-check")).toHaveValue("The stranger crosses at dusk.")
  fail = false; await page.getByRole("button", { name: "Run continuity check" }).click()
  await expect(page.getByRole("heading", { name: "Clarify the crossing rule" })).toBeVisible()
  await expect(page.getByText("Only the keeper may cross at dusk.", { exact: true })).toBeVisible()
  await page.getByLabel("Chapter or scene number").fill("3")
  await expect(page.getByText("Reviewed The Ember Gate · Chapter / scene 2")).toBeVisible()
  page.once("dialog", (dialog) => dialog.dismiss()); await selectSecond(page)
  await expect(page.getByLabel("Passage to cross-check")).toHaveValue("The stranger crosses at dusk.")
  await page.setViewportSize({ width: 390, height: 1000 })
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }))
  await page.screenshot({ path: info.outputPath("series-continuity-mobile.png"), fullPage: true, animations: "disabled" })
  page.once("dialog", (dialog) => dialog.accept()); await page.getByLabel("Selected series", { exact: true }).selectOption("series-2")
  await page.getByRole("button", { name: "Continuity check", exact: true }).click()
  await expect(page.getByLabel("Passage to cross-check")).toHaveValue("")
})

test("pending continuity prevents competing actions and can stop waiting without losing text", async ({ page }) => {
  let release: (() => void) | undefined
  const waiting = new Promise<void>((resolve) => { release = resolve })
  await page.route("**/continuity-check-stream", async (route) => { await waiting; await route.fulfill({ contentType: "text/event-stream", body: `event: done\ndata: ${JSON.stringify(review)}\n\n` }).catch(() => {}) })
  await page.goto("/series"); await page.getByRole("button", { name: "Continuity check", exact: true }).click()
  await page.getByLabel("Project to check").selectOption("book-1"); await page.getByLabel("Passage to cross-check").fill("Keep this passage.")
  await page.getByRole("button", { name: "Run continuity check" }).click()
  await expect(page.getByRole("button", { name: "Refresh series", exact: true })).toBeDisabled()
  await expect(page.getByRole("button", { name: "Add project", exact: true })).toBeDisabled()
  await expect(page.getByRole("button", { name: "Northern Letters 0 projects" })).toBeDisabled()
  await page.getByRole("button", { name: "Stop waiting" }).click()
  await expect(page.getByText(/Stopped waiting for this check/)).toBeVisible()
  await expect(page.getByLabel("Passage to cross-check")).toHaveValue("Keep this passage.")
  await expect(page.getByRole("button", { name: "Refresh series", exact: true })).toBeEnabled()
  release?.()
})

test("pagination, empty series, long names, and plan gates remain operable", async ({ page }, info) => {
  await page.route("**/api/v1/books/series?*", (route) => route.fulfill({ json: new URL(route.request().url()).searchParams.get("offset") === "0" ? { ...list(), has_more: true } : list([{ ...collection[1], id: "series-last", name: "UnbrokenSeriesTitle".repeat(18) }]) }))
  await page.route("**/api/v1/books/page?*", (route) => route.fulfill({ json: new URL(route.request().url()).searchParams.has("cursor") ? { items: [spare], next_cursor: null } : { items: [project], next_cursor: "next" } }))
  await page.setViewportSize({ width: 390, height: 1000 }); await page.goto("/series")
  await expect(page.getByText("Your series (3)")).toBeVisible()
  await page.getByLabel("Selected series", { exact: true }).selectOption("series-last")
  await page.getByRole("button", { name: "Add project", exact: true }).click()
  await page.getByLabel("Project to add").selectOption("book-3")
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }))
  await page.screenshot({ path: info.outputPath("series-long-mobile.png"), fullPage: true })
  await page.route("**/api/v1/books/series?*", (route) => route.fulfill({ json: list([]) }))
  await page.getByRole("button", { name: "Refresh series", exact: true }).click()
  await expect(page.getByText(/No series yet/)).toBeVisible()
  await installMockApi(page, { userTier: "free" }); await page.reload()
  await expect(page.getByText("Series mode is reserved for paid plans.")).toBeVisible()
  await expect(page.getByRole("link", { name: "View plans", exact: true })).toHaveAttribute("href", "/pricing")
})

test("series loading and malformed pagination do not masquerade as an empty workspace", async ({ page }) => {
  let release: (() => void) | undefined
  const waiting = new Promise<void>((resolve) => { release = resolve })
  await page.route("**/api/v1/books/series?*", async (route) => { await waiting; await route.fulfill({ json: { ...list(), has_more: true } }) })
  await page.goto("/series")
  await expect(page.getByText("Loading your series…", { exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "Refreshing…", exact: true })).toBeDisabled()
  release?.()
  await expect(page.getByRole("button", { name: "Retry series", exact: true })).toBeVisible()
  await expect(page.getByText(/No series yet/)).toHaveCount(0)
  await page.route("**/api/v1/books/series?*", (route) => route.fulfill({ json: list() }))
  await page.getByRole("button", { name: "Retry series", exact: true }).click()
  await expect(page.getByRole("heading", { name: "Gate Cycle", exact: true })).toBeVisible()
})
