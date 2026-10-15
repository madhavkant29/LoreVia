import { expect, test } from "@playwright/test"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"

const route = "/sky-of-ash--book-1/graph"
const graphApi = "**/api/v1/reader/book-1/relationships?**"
const evolutionApi = "**/api/v1/reader/book-1/relationship-evolution?**"

test.beforeEach(async ({ page }) => {
  await installMockApi(page)
  await page.addInitScript(() => {
    if (!localStorage.getItem("lorevia-preferences")) localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 }))
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
})

test("relationship map and history work at four widths and both themes", async ({ page }, testInfo) => {
  const errors: string[] = []
  page.on("pageerror", (error) => errors.push(error.message))
  await page.goto(route)
  await page.getByText("Browse characters and connections", { exact: true }).click()
  await expect(page.getByRole("button", { name: "Gregor", exact: true })).toBeVisible()
  await page.getByRole("button", { name: "Fit", exact: true }).click()
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    await page.getByRole("button", { name: "Fit", exact: true }).click()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
    await page.screenshot({ path: testInfo.outputPath(`graph-${width}.png`), fullPage: true })
  }
  for (const theme of ["dark", "light"]) {
    await page.evaluate((theme) => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme }, version: 0 })), theme)
    await page.reload()
    await page.getByText("Browse characters and connections", { exact: true }).click()
    await page.getByRole("button", { name: "Gregor", exact: true }).click()
    const dialog = page.getByRole("dialog", { name: "Graph details" })
    await expect(dialog).toBeVisible()
    expect(await criticalAccessibilityViolations(page)).toEqual([])
    await page.screenshot({ path: testInfo.outputPath(`graph-inspector-${theme}.png`), fullPage: true })
    await page.keyboard.press("Escape")
    await expect(page.getByRole("button", { name: "Gregor", exact: true })).toBeFocused()
    await page.getByRole("link", { name: "Evolution", exact: true }).click()
    await expect(page.getByRole("heading", { name: "Gregor ↔ Grete" })).toBeVisible()
    expect(await criticalAccessibilityViolations(page)).toEqual([])
    await page.screenshot({ path: testInfo.outputPath(`graph-evolution-${theme}.png`), fullPage: true })
    await page.getByRole("link", { name: "Map", exact: true }).click()
    await expect(page).toHaveURL(new RegExp(`${route}$`))
    await expect(page.getByText("Browse characters and connections", { exact: true })).toBeVisible()
  }
  expect(errors).toEqual([])
})

test("authors choose available manuscript chapters and readers stay within read chapters", async ({ page }) => {
  const chapters = [2, 5, 9].map((number) => ({ number, title: `Chapter ${number}`, processed: true, intelligence_available: true, read: number === 2 }))
  await page.route("**/api/v1/reader/book-1/chapters", (request) => request.fulfill({ json: { chapters, read_upto: 2 } }))
  await page.goto(route)
  await expect(page.getByRole("combobox", { name: "Up to manuscript chapter" })).toHaveValue("9")
  await page.getByRole("combobox", { name: "Up to manuscript chapter" }).selectOption("5")
  await page.getByRole("link", { name: "Evolution", exact: true }).click()
  await expect(page.getByRole("combobox", { name: "Up to manuscript chapter" })).toHaveValue("5")
  await installMockApi(page, { bookMode: "reader" })
  await page.route("**/api/v1/reader/book-1/chapters", (request) => request.fulfill({ json: { chapters, read_upto: 2 } }))
  await page.reload()
  await expect(page.getByRole("combobox", { name: "Up to read chapter" })).toHaveValue("2")
  await expect(page.getByRole("combobox", { name: "Up to read chapter" }).locator("option")).toHaveCount(1)
})

test("graph failures and history failures recover without false empty states", async ({ page }) => {
  let failGraph = true
  let failHistory = true
  await page.route(graphApi, (request) => failGraph ? request.fulfill({ status: 503, json: {} }) : request.fallback())
  await page.route(evolutionApi, (request) => failHistory ? request.fulfill({ status: 503, json: {} }) : request.fallback())
  await page.goto(route)
  await expect(page.getByRole("button", { name: "Retry graph" })).toBeVisible()
  await expect(page.getByText("No graphable relationships yet", { exact: true })).toHaveCount(0)
  failGraph = false
  await page.getByRole("button", { name: "Retry graph" }).click()
  await page.getByText("Browse characters and connections", { exact: true }).click()
  await expect(page.getByRole("button", { name: "Gregor", exact: true })).toBeVisible()
  failGraph = true
  await page.getByRole("button", { name: "Refresh graph" }).click()
  await expect(page.getByText("Graph refresh failed. Previously loaded data remains visible.", { exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "Gregor", exact: true })).toBeVisible()
  await page.getByRole("link", { name: "Evolution", exact: true }).click()
  await expect(page.getByRole("button", { name: "Retry history" })).toBeVisible()
  failHistory = false
  await page.getByRole("button", { name: "Retry history" }).click()
  await expect(page.getByRole("heading", { name: "Gregor ↔ Grete" })).toBeVisible()
})

test("corrections validate, retain failed drafts, and confirm discard and deletion", async ({ page }) => {
  let failSave = true
  let saves = 0
  let deletes = 0
  await page.route("**/api/v1/books/book-1/relationships/*", (request) => {
    if (request.request().method() === "PUT") { saves++; return failSave ? request.fulfill({ status: 503, json: {} }) : request.fulfill({ json: request.request().postDataJSON() }) }
    if (request.request().method() === "DELETE") { deletes++; return request.fulfill({ json: { deleted: true } }) }
    return request.fallback()
  })
  await page.setViewportSize({ width: 390, height: 1000 })
  await page.goto(route)
  await page.getByText("Browse characters and connections", { exact: true }).click()
  await page.getByRole("button", { name: /Gregor → Grete/ }).click()
  const dialog = page.getByRole("dialog", { name: "Graph details" })
  await expect(dialog).toBeVisible()
  await dialog.getByRole("spinbutton", { name: "Sentiment", exact: true }).fill("2")
  await dialog.getByRole("button", { name: "Save correction" }).click()
  await expect(dialog.getByText("Sentiment must be between −1 and 1, or blank.", { exact: true })).toBeVisible()
  expect(saves).toBe(0)
  await dialog.getByRole("spinbutton", { name: "Sentiment", exact: true }).fill("0.5")
  await dialog.getByRole("textbox", { name: "Relationship note", exact: true }).fill("A correction worth keeping.")
  await dialog.getByRole("button", { name: "Save correction" }).click()
  await expect(dialog.getByText("Could not save the relationship correction.", { exact: true })).toBeVisible()
  page.once("dialog", (prompt) => prompt.dismiss())
  await page.keyboard.press("Escape")
  await expect(dialog.getByRole("textbox", { name: "Relationship note", exact: true })).toHaveValue("A correction worth keeping.")
  failSave = false
  await dialog.getByRole("button", { name: "Save correction" }).click()
  await expect(dialog.getByText("Relationship correction saved.", { exact: true })).toBeVisible()
  page.once("dialog", (prompt) => prompt.dismiss())
  await dialog.getByRole("button", { name: "Delete relationship" }).click()
  expect(deletes).toBe(0)
  page.once("dialog", (prompt) => prompt.accept())
  await dialog.getByRole("button", { name: "Delete relationship" }).click()
  await expect(dialog).toHaveCount(0)
  await expect(page.getByText("Relationship removed.", { exact: true })).toBeVisible()
  expect(deletes).toBe(1)
})

test("large graphs load all connection pages and list filters stay usable", async ({ page }) => {
  const offsets: string[] = []
  await page.route(graphApi, (request) => {
    const offset = new URL(request.request().url()).searchParams.get("offset") || "0"
    offsets.push(offset)
    return request.fulfill({ json: { nodes: [{ id: "a", name: "Nora", role: null, first_chapter: 1 }, { id: "b", name: "Mara", role: null, first_chapter: 1 }, { id: "c", name: "Isolated", role: null, first_chapter: 1 }], edges: [{ id: `edge-${offset}`, source: "a", target: "b", type: offset === "0" ? "ally" : "rival", sentiment: 0, description: "Evidence", from_chapter: 1 }], has_more: offset === "0", next_offset: offset === "0" ? 100 : null, total_edges: 2 } })
  })
  await page.goto(route)
  await page.getByText("Browse characters and connections", { exact: true }).click()
  await expect(page.getByRole("heading", { name: "Connections (2)", exact: true })).toBeVisible()
  expect(offsets).toContain("100")
  await page.getByRole("button", { name: "Hide isolated", exact: true }).click()
  await expect(page.getByRole("button", { name: "Isolated", exact: true })).toHaveCount(0)
  await page.getByRole("combobox", { name: "Filter relationships" }).selectOption("rival")
  await expect(page.getByRole("heading", { name: "Connections (1)", exact: true })).toBeVisible()
  await page.getByRole("searchbox", { name: "Find in this graph" }).fill("missing")
  await expect(page.getByText("No characters match.", { exact: true })).toBeVisible()
  await expect(page.getByText("No connections match.", { exact: true })).toBeVisible()
})

test("empty and unavailable chapter scopes have clear recovery", async ({ page }) => {
  let fail = true
  await page.route("**/api/v1/reader/book-1/chapters", (request) => request.fulfill(fail ? { status: 503, json: {} } : { json: { chapters: [], read_upto: 0 } }))
  await page.goto(route)
  await expect(page.getByRole("button", { name: "Retry chapters" })).toBeVisible()
  await expect(page.getByText("No graphable relationships yet", { exact: true })).toHaveCount(0)
  fail = false
  await page.getByRole("button", { name: "Retry chapters" }).click()
  await expect(page.getByRole("heading", { name: "No chapters available for relationships yet" })).toBeVisible()
  await expect(page.getByRole("link", { name: "View chapters", exact: true })).toHaveAttribute("href", "/sky-of-ash--book-1/chapters")
})

test("empty graph and history do not imply failed loading", async ({ page }) => {
  await page.route(graphApi, (request) => request.fulfill({ json: { nodes: [], edges: [] } }))
  await page.route(evolutionApi, (request) => request.fulfill({ json: { pairs: [] } }))
  await page.goto(route)
  await expect(page.getByText("No graphable relationships yet", { exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "Retry graph" })).toHaveCount(0)
  await page.getByRole("link", { name: "Evolution", exact: true }).click()
  await expect(page.getByText(/No relationship changes are recorded through chapter/)).toBeVisible()
})

test("long labels and blocked device storage stay operable", async ({ page }, testInfo) => {
  const name = "Nora".repeat(35)
  await page.route(graphApi, (request) => request.fulfill({ json: { nodes: [{ id: "nora", name, role: "An unusually long character role", first_chapter: 1, description: "The journey continues. ".repeat(30) }], edges: [] } }))
  await page.addInitScript(() => {
    const original = Storage.prototype.setItem
    Storage.prototype.setItem = function(key, value) { if (key.startsWith("lorevia:graph")) throw new Error("Storage unavailable"); return original.call(this, key, value) }
  })
  await page.setViewportSize({ width: 390, height: 1000 })
  await page.goto(route)
  await page.getByText("Browse characters and connections", { exact: true }).click()
  await page.getByRole("button", { name, exact: true }).click()
  const dialog = page.getByRole("dialog", { name: "Graph details" })
  await dialog.getByRole("textbox", { name: "Display label", exact: true }).fill("Nora of the north")
  await expect(dialog.getByText(/Display labels stay in this session/)).toBeVisible()
  await expect(dialog.getByRole("heading", { name, exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.screenshot({ path: testInfo.outputPath("graph-long-mobile.png"), fullPage: true })
  await page.keyboard.press("Escape")
  await page.getByRole("button", { name: "Hide isolated", exact: true }).click()
  await expect(page.getByText("No characters match these filters", { exact: true })).toBeVisible()
  await page.getByRole("button", { name: "Clear graph filters" }).click()
  await expect(page.getByRole("button", { name, exact: true })).toBeVisible()
})
