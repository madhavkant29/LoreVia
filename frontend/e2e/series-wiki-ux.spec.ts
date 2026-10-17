import { expect, test, type Page } from "@playwright/test"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"

const path = "/sky-of-ash--book-1/cross-book-wiki"
const pair = (i = 0) => ({ left_book_id: "book-1", right_book_id: "book-2", left_name: i ? `Character ${String(i).padStart(3, "0")}` : "Nora Vale", right_name: i ? `Recurring character ${i}` : "Nora Veyl", similarity: .96 })
async function install(page: Page, options: { free?: boolean; nonowner?: boolean } = {}) {
  await installMockApi(page, { seriesBooks: true, userTier: options.free ? "free" : "author" })
  await page.addInitScript(() => {
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
    if (!localStorage.getItem("lorevia-preferences")) localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 }))
  })
  const state = { fail: new Set<string>(), reads: 0, titles: [{ id: "book-1", title: "Sky of Ash" }, { id: "book-2", title: "Embers Beyond the Gate" }, { id: "book-3", title: "The Third Watch" }], data: { series_name: "Ash Cycle" as string | null, comparison_book_ids: ["book-1", "book-2", "book-3"], character_matches: [pair(), { ...pair(), left_book_id: "book-2", right_book_id: "book-3", left_name: "Foreign source", right_name: "Third book reference", similarity: .97 }] as Array<Record<string, unknown>>, wiki_matches: [{ ...pair(), left_name: "Glass Road", right_name: "The Glassway", entry_type: "route", similarity: .94 }] as Array<Record<string, unknown>> } }
  await page.route("**/api/v1/**", async route => {
    const url = new URL(route.request().url())
    if (url.pathname === "/api/v1/books/book-1") {
      if (state.fail.has("book")) return route.fulfill({ status: 503, json: { detail: "Unavailable" } })
      if (options.nonowner) return route.fulfill({ json: { id: "book-1", title: "Sky of Ash", mode: "reader", workspace_shell: "reader", access_class: "reader_collaborator", collaboration_role: "reader_only", status: "ready" } })
    }
    if (url.pathname === "/api/v1/books/selector") return route.fulfill({ status: state.fail.has("titles") ? 503 : 200, json: state.fail.has("titles") ? { detail: "Unavailable" } : state.titles })
    if (url.pathname.endsWith("/cross-book-intelligence")) { state.reads++; return route.fulfill({ status: state.fail.has("references") ? 503 : 200, json: state.fail.has("references") ? { detail: "Unavailable" } : state.data }) }
    return route.fallback()
  })
  return state
}
async function open(page: Page) { await page.goto(path); await expect(page.getByRole("heading", { name: "Ash Cycle", exact: true })).toBeVisible() }

test("series wiki remains readable at four widths in both themes", async ({ page }, info) => {
  const state = await install(page)
  state.data.character_matches[0].left_name = "Nora Vale, Keeper of the Northern Gate and the Harbour Records"
  state.titles[1].title = "Embers Beyond the Gate: The Chronicle of the Northern Harbour and Its Last Keeper"
  await open(page)
  for (const theme of ["dark", "light"]) {
    if (theme === "light") { await page.evaluate(() => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "light" }, version: 0 }))); await page.reload(); await expect(page.getByRole("heading", { name: "Ash Cycle", exact: true })).toBeVisible() }
    for (const width of [1440, 1280, 768, 390]) { await page.setViewportSize({ width, height: 1000 }); expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy(); await page.screenshot({ path: info.outputPath(`${theme}-${width}.png`), fullPage: true }) }
    expect(await criticalAccessibilityViolations(page, "[data-series-wiki-workspace]")).toEqual([])
  }
  await expect(page.getByText(/up to 20 character pairs and 20 wiki pairs/)).toBeVisible()
})

test("series wiki distinguishes current book pairs from whole series pairs", async ({ page }) => {
  await install(page); await open(page)
  await expect(page.getByText("Foreign source", { exact: true })).toHaveCount(0)
  await page.getByRole("combobox", { name: "Book scope" }).selectOption("series")
  const detail = page.getByLabel("Selected series reference")
  await expect(detail.getByRole("heading", { name: "Foreign source ↔ Third book reference" })).toBeVisible()
  await expect(detail.getByText("Source reference", { exact: true })).toBeVisible(); await expect(detail.getByText("Current book reference", { exact: true })).toHaveCount(0)
  await expect(detail.getByRole("link", { name: "Open source book" })).toHaveAttribute("href", "/book-2")
  await expect(detail.getByRole("link", { name: "Open connected book" })).toHaveAttribute("href", "/book-3")
  await page.getByText("Books included (3)", { exact: true }).click(); await expect(page.getByRole("link", { name: "The Third Watch", exact: true })).toBeVisible()
})

test("series wiki filters names, titles, type and exact similarity with reset", async ({ page }) => {
  await install(page); await open(page)
  await page.getByRole("combobox", { name: "Reference type" }).selectOption("wiki")
  await expect(page.getByRole("heading", { name: "Glass Road ↔ The Glassway" }).first()).toBeVisible()
  await page.getByRole("combobox", { name: "Minimum similarity" }).selectOption("95"); await expect(page.getByRole("heading", { name: "No matches found" })).toBeVisible()
  await page.getByRole("combobox", { name: "Minimum similarity" }).selectOption("90"); await page.getByRole("searchbox", { name: "Search references" }).fill("EMBERS")
  await expect(page.getByRole("heading", { name: "Glass Road ↔ The Glassway" }).first()).toBeVisible()
  await page.getByRole("searchbox", { name: "Search references" }).fill("missing"); await expect(page.getByRole("heading", { name: "No matches found" })).toBeVisible()
  await page.getByRole("button", { name: "Reset filters", exact: true }).click(); await expect(page.getByRole("combobox", { name: "Reference type" })).toHaveValue("all")
  await expect(page.getByRole("heading", { name: "Nora Vale ↔ Nora Veyl" }).first()).toBeVisible()
})

test("series wiki recovers failures without presenting errors as empty comparisons", async ({ page }) => {
  const state = await install(page); state.fail.add("book"); await page.goto(path)
  await expect(page.getByRole("button", { name: "Retry project" })).toBeVisible(); expect(state.reads).toBe(0)
  state.fail.delete("book"); state.fail.add("references"); await page.getByRole("button", { name: "Retry project" }).click()
  await expect(page.getByRole("button", { name: "Retry references", exact: true })).toBeVisible(); await expect(page.getByRole("heading", { name: "No matches found" })).toHaveCount(0)
  state.fail.clear(); state.fail.add("titles"); await page.getByRole("button", { name: "Retry references", exact: true }).click()
  await page.reload(); await expect(page.getByRole("button", { name: "Retry book titles" })).toBeVisible()
  await expect(page.getByLabel("Selected series reference").getByText("Book book-2", { exact: true })).toBeVisible()
  state.fail.clear(); await page.getByRole("button", { name: "Retry book titles" }).click(); await expect(page.getByLabel("Selected series reference").getByText("Embers Beyond the Gate", { exact: true })).toBeVisible()
  state.fail.add("references"); await page.getByRole("button", { name: "Refresh references", exact: true }).click(); await expect(page.getByText(/last loaded comparison/)).toBeVisible()
  await expect(page.getByLabel("Selected series reference").getByRole("heading", { name: "Nora Vale ↔ Nora Veyl" })).toBeVisible()
})

test("series wiki distinguishes missing membership from indexed no-match results", async ({ page }) => {
  const state = await install(page); state.data.series_name = null; state.data.comparison_book_ids = ["book-1"]; state.data.character_matches = []; state.data.wiki_matches = []
  await page.goto(path); await expect(page.getByText(/Add at least two of your books/)).toBeVisible()
  state.data.series_name = "Ash Cycle"; state.data.comparison_book_ids.push("book-2"); await page.getByRole("button", { name: "Refresh references", exact: true }).click()
  await expect(page.getByText(/No indexed reference pairs were returned/)).toBeVisible()
  await expect(page.getByRole("link", { name: "Review series membership" })).toHaveAttribute("href", "/series")
})

test("series wiki expands and collapses mobile references and preserves selection on refresh", async ({ page }) => {
  const state = await install(page); await page.setViewportSize({ width: 390, height: 1000 }); await open(page)
  const first = page.getByRole("button", { name: /Nora Vale.*Hide reference/ }); await expect(first).toHaveAttribute("aria-expanded", "true"); await first.click()
  await expect(page.getByRole("heading", { name: "Nora Vale ↔ Nora Veyl" })).toHaveCount(0)
  await page.getByRole("button", { name: /Glass Road.*View reference/ }).click(); await expect(page.getByRole("heading", { name: "Glass Road ↔ The Glassway" })).toBeVisible()
  state.data.character_matches.unshift({ ...pair(9), similarity: 1 }); await page.getByRole("button", { name: "Refresh references", exact: true }).click()
  await expect(page.getByRole("heading", { name: "Glass Road ↔ The Glassway" })).toBeVisible()
  state.data.wiki_matches = []; await page.getByRole("button", { name: "Refresh references", exact: true }).click()
  await expect(page.getByRole("heading", { name: / ↔ / })).toHaveCount(0)
})

test("series wiki exposes all returned rows and handles incomplete or duplicate records", async ({ page }) => {
  const state = await install(page); state.data.character_matches = Array.from({ length: 130 }, (_, i) => pair(i)); state.data.character_matches.push(pair(), { ...pair(), similarity: "invalid" }); state.data.wiki_matches = []
  await open(page); await expect(page.getByText("Showing 25 of 130 matching pairs")).toBeVisible(); await expect(page.getByText(/1 incomplete or invalid/)).toBeVisible()
  while (await page.getByRole("button", { name: /^Show more references/ }).count()) await page.getByRole("button", { name: /^Show more references/ }).click()
  await expect(page.getByText("Showing 130 of 130 matching pairs")).toBeVisible(); await page.getByRole("button", { name: /Character 129/ }).first().click()
  await expect(page.getByLabel("Selected series reference").getByRole("heading", { name: "Character 129 ↔ Recurring character 129" })).toBeVisible()
})

for (const role of ["free", "nonowner"] as const) test(`series wiki prevents ${role} comparison requests`, async ({ page }) => {
  const state = await install(page, { [role]: true }); await page.goto(path)
  await expect(page.getByText(role === "free" ? "Series comparisons require an Author or Architect plan." : "Only the project owner can compare references across their books.")).toBeVisible()
  expect(state.reads).toBe(0)
})
