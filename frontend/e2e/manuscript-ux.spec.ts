import { expect, test } from "@playwright/test"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"

const route = "/sky-of-ash--book-1/manuscript"

test.beforeEach(async ({ page }) => {
  await installMockApi(page)
  await page.addInitScript(() => {
    localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 }))
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
})

test("manuscript supports keyboard tabs, dismissible menus and responsive drafting", async ({ page }, info) => {
  await page.route("**/api/v1/reader/book-1/chapter/3**", (request) => request.fulfill({ json: {
    chapter_number: 3, chapter_title: "River of Glass", content_version: 1, media: [],
    text_content: "The lantern keeper returned to the harbour before dawn. Every boat had vanished except the one she had promised never to sail.\n\nOn the quay, a folded map lay beneath a stone. The ink was still wet.\n\nShe knew the handwriting. That was what frightened her.",
    html_content: "<p>The lantern keeper returned to the harbour before dawn. Every boat had vanished except the one she had promised never to sail.</p><p>On the quay, a folded map lay beneath a stone. The ink was still wet.</p><p>She knew the handwriting. That was what frightened her.</p>",
  } }))
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto(route)
  const header = page.getByRole("banner").filter({ has: page.getByTestId("manuscript-home-link") })
  await expect(page.getByLabel("Chapter title", { exact: true })).toBeVisible()
  await expect(page.locator('[data-editor-key="chapter-3"]')).toContainText("The lantern keeper")
  const tabs = page.getByRole("tablist", { name: "Manuscript workspace modes" })
  await tabs.getByRole("tab", { name: "Write", exact: true }).focus()
  await page.keyboard.press("ArrowRight")
  await expect(tabs.getByRole("tab", { name: "Plan", exact: true })).toBeFocused()
  await expect(tabs.getByRole("tab", { name: "Plan", exact: true })).toHaveAttribute("aria-selected", "true")
  await page.keyboard.press("Home")
  await expect(tabs.getByRole("tab", { name: "Write", exact: true })).toBeFocused()
  await header.getByText("More", { exact: true }).click()
  await page.keyboard.press("Escape")
  await expect(header.locator("details")).not.toHaveAttribute("open", "")
  await header.getByText("More", { exact: true }).click()
  await header.getByRole("button", { name: "Editor settings" }).click()
  await expect(header.locator("details")).not.toHaveAttribute("open", "")
  await expect(page.getByRole("combobox", { name: "Index format" })).toBeVisible()
  await expect(page.locator('[data-lorevia-bottom-floating]').getByRole("button", { name: "Help", exact: true })).toHaveCount(0)
  await header.getByText("More", { exact: true }).click()
  await header.getByRole("button", { name: "Help", exact: true }).click()
  await expect(page.getByRole("dialog", { name: "LoreVia Support" })).toBeVisible()
  await page.keyboard.press("Escape")
  await expect(header.locator("summary")).toBeFocused()
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    await expect(page.getByLabel("Chapter title", { exact: true })).toBeVisible()
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
    await page.screenshot({ path: info.outputPath(`manuscript-${width}.png`), fullPage: true })
  }
  expect(await criticalAccessibilityViolations(page, "[data-manuscript-workspace]")).toEqual([])
  await page.evaluate(() => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "light" }, version: 0 })))
  await page.addInitScript(() => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "light" }, version: 0 })))
  await page.reload()
  await expect(page.getByLabel("Chapter title", { exact: true })).toBeVisible()
  await expect(page.locator("html")).not.toHaveClass(/dark/)
  expect(await criticalAccessibilityViolations(page, "[data-manuscript-workspace]")).toEqual([])
  await page.screenshot({ path: info.outputPath("manuscript-light-390.png"), fullPage: true })
})

test("manuscript mobile panels contain focus, close on Escape, and return to the draft", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(route)
  const outline = page.getByRole("button", { name: "Outline", exact: true })
  await outline.click()
  const dialog = page.getByRole("dialog", { name: "Manuscript outline" })
  await expect(dialog).toBeVisible()
  await dialog.getByRole("button", { name: "Close", exact: true }).focus()
  await page.keyboard.press("Shift+Tab")
  expect(await dialog.evaluate((element) => element.contains(document.activeElement))).toBe(true)
  await page.keyboard.press("Escape")
  await expect(dialog).toHaveCount(0)
  await expect(outline).toBeFocused()
  const inspector = page.getByRole("button", { name: "Inspector", exact: true })
  await inspector.click()
  await expect(page.getByRole("dialog", { name: "Writing inspector" })).toBeVisible()
  await page.keyboard.press("Escape")
  await expect(inspector).toBeFocused()
  await page.locator('[data-editor-key="chapter-3"]').fill("The lantern keeper returned to the silent harbour before dawn.")
  await expect(page.getByRole("button", { name: "Save now", exact: true })).toBeEnabled()
})

test("manuscript initial loading failures show recovery instead of an empty editor", async ({ page }) => {
  let fail = true
  await page.route("**/api/v1/books/book-1/manuscript-bootstrap**", (request) => fail
    ? request.fulfill({ status: 503, json: { detail: "Temporarily unavailable" } })
    : request.fallback())
  await page.goto(route)
  await expect(page.getByRole("heading", { name: "Unable to open manuscript" })).toBeVisible()
  await expect(page.locator("[contenteditable=true]")).toHaveCount(0)
  fail = false
  await page.getByRole("button", { name: "Try again" }).click()
  await expect(page.getByLabel("Chapter title", { exact: true })).toBeVisible()
})

test("manuscript failed chapter loads cannot be mistaken for a blank draft", async ({ page }) => {
  let fail = true
  await page.route("**/api/v1/reader/book-1/chapter/3**", (request) => fail
    ? request.fulfill({ status: 503, json: { detail: "Temporarily unavailable" } })
    : request.fallback())
  await page.goto(route)
  await expect(page.getByText("Chapter 3 could not be loaded. Check your connection and try again.")).toBeVisible()
  await expect(page.locator("[contenteditable=true]")).toHaveCount(0)
  fail = false
  await page.getByRole("button", { name: "Try again" }).click()
  await expect(page.getByLabel("Chapter title", { exact: true })).toBeVisible()
})
