import { expect, test } from "@playwright/test"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"

const projects = [
  { id: "book-1", title: "Sky of Ash", status: "ready" },
  { id: "book-2", title: "The Cartographer’s Account of Every City That Disappeared Before Dawn", status: "ready" },
  { id: "book-3", title: "Letters from the Winter Sea", status: "failed" },
  { id: "book-4", title: "The Unfinished Atlas", status: "processing" },
].map((book) => ({
  ...book, author: "M. Vale", genre: "Fantasy", mode: "author", format: "docx",
  work_type: "novel", access_class: "owner", workspace_shell: "author", total_chapters: 12,
  total_words: 31500, progress_pct: 64, created_at: "2026-09-28T12:00:00Z",
  archived_at: null, hidden_at: null, processing: null,
}))

test.beforeEach(async ({ page }) => {
  await installMockApi(page)
  await page.addInitScript(() => {
    localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 }))
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
})

test("library filters, explicit pins, keyboard dismissal and responsive views", async ({ page }, testInfo) => {
  await page.route("**/api/v1/books/page**", (route) => route.fulfill({ json: { items: projects, next_cursor: null } }))
  await page.goto("/library")
  const workspace = page.getByTestId("library-workspace")
  await expect(workspace.getByRole("article")).toHaveCount(4)
  await expect(page.getByRole("heading", { name: "Pinned projects" })).toHaveCount(0)
  await page.keyboard.press("/")
  await expect(page.getByRole("searchbox")).toBeFocused()
  await page.getByRole("searchbox").fill("not a manuscript")
  await expect(workspace).toContainText("No projects match this view")
  await page.getByRole("button", { name: "Reset filters", exact: true }).click()
  await page.getByRole("combobox", { name: "Project status" }).selectOption("failed")
  await expect(workspace.getByRole("article")).toHaveCount(1)
  await page.getByRole("button", { name: "Reset filters", exact: true }).click()
  const actions = page.getByRole("button", { name: "Open actions for Sky of Ash" })
  await actions.click()
  await expect(page.getByRole("button", { name: "Pin project", exact: true })).toBeFocused()
  await page.keyboard.press("Escape")
  await expect(actions).toBeFocused()
  await expect(actions).toHaveAttribute("aria-expanded", "false")
  await actions.click()
  await page.getByRole("button", { name: "Pin project", exact: true }).click()
  await expect(page.getByRole("heading", { name: "Pinned projects" })).toBeVisible()
  await actions.click()
  await page.getByRole("button", { name: "Unpin project", exact: true }).click()
  await expect(page.getByRole("heading", { name: "Pinned projects" })).toHaveCount(0)
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    await page.getByRole("button", { name: "Grid view" }).click()
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
    await page.screenshot({ path: testInfo.outputPath(`library-grid-${width}.png`), fullPage: true })
    await page.getByRole("button", { name: "List view" }).click()
    await expect(workspace.getByRole("article")).toHaveCount(4)
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
    await page.screenshot({ path: testInfo.outputPath(`library-list-${width}.png`), fullPage: true })
  }
  expect(await criticalAccessibilityViolations(page, '[data-testid="library-workspace"]')).toEqual([])
  await page.setViewportSize({ width: 1280, height: 900 })
  await page.getByRole("button", { name: "Toggle theme" }).click()
  await expect(page.locator("html")).not.toHaveClass(/dark/)
  await expect(workspace.locator("../..")).toHaveCSS("background-color", "rgb(244, 246, 248)")
  expect(await criticalAccessibilityViolations(page, '[data-testid="library-workspace"]')).toEqual([])
  await page.screenshot({ path: testInfo.outputPath("library-light.png"), fullPage: true })
})

test("library offers a useful action when every project is archived", async ({ page }) => {
  await page.route("**/api/v1/books/page**", (route) => route.fulfill({ json: { items: [{ ...projects[0], archived_at: "2026-09-29T12:00:00Z" }], next_cursor: null } }))
  await page.goto("/library")
  await expect(page.getByText("Your projects are archived")).toBeVisible()
  await page.getByRole("button", { name: "Show archived projects" }).click()
  await expect(page.getByRole("link", { name: "Open Sky of Ash" })).toBeVisible()
  await page.getByRole("button", { name: "Open actions for Sky of Ash" }).click()
  await expect(page.getByRole("button", { name: "Restore", exact: true })).toBeVisible()
})

test("library pagination keeps loaded projects on failure and stops at the last page", async ({ page }) => {
  let fail = true
  await page.route("**/api/v1/books/page**", async (route) => {
    if (!new URL(route.request().url()).searchParams.get("cursor")) {
      return route.fulfill({ json: { items: [projects[0]], next_cursor: "next" } })
    }
    if (fail) return route.fulfill({ status: 500, json: { detail: "Temporary failure" } })
    return route.fulfill({ json: { items: [projects[1]], next_cursor: null } })
  })
  await page.goto("/library")
  await page.getByRole("button", { name: "Load more projects" }).click()
  await expect(page.getByRole("alert").filter({ hasText: "Could not load more projects" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Open Sky of Ash" })).toBeVisible()
  fail = false
  await page.getByRole("button", { name: "Retry loading projects" }).click()
  await expect(page.getByTestId("library-workspace").getByRole("article")).toHaveCount(2)
  await expect(page.getByRole("button", { name: "Load more projects" })).toHaveCount(0)
})

test("library archive errors preserve the project and offer actionable feedback", async ({ page }) => {
  await page.route("**/api/v1/books/book-1/archive", (route) => route.fulfill({ status: 500, json: { detail: "Temporary failure" } }))
  await page.goto("/library")
  await page.getByRole("button", { name: "Open actions for Sky of Ash" }).click()
  await page.getByRole("button", { name: "Archive", exact: true }).click()
  await expect(page.getByRole("alert").filter({ hasText: "Could not archive" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Open Sky of Ash" })).toBeVisible()
})

test("library loading, error recovery and first-use states", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 })
  let release: () => void = () => {}
  const pending = new Promise<void>((resolve) => { release = resolve })
  let failed = true
  await page.route("**/api/v1/books/page**", async (route) => {
    await pending
    return route.fulfill(failed ? { status: 500, json: { detail: "Temporary failure" } } : { json: { items: [], next_cursor: null } })
  })
  await page.goto("/library")
  await expect(page.getByRole("status", { name: "Loading all projects" })).toBeVisible()
  release()
  await expect(page.getByText("Failed to load library")).toBeVisible({ timeout: 20000 })
  failed = false
  await page.getByRole("button", { name: "Try again" }).click()
  await expect(page.getByTestId("first-manuscript-hero")).toBeVisible()
  await expect(page.locator("h1")).toHaveCount(1)
  expect(await criticalAccessibilityViolations(page, '[data-testid="library-workspace"]')).toEqual([])
  await page.screenshot({ path: testInfo.outputPath("library-first-use.png"), fullPage: true })
  await page.getByRole("button", { name: "Upload manuscript", exact: true }).click()
  await expect(page.getByRole("dialog", { name: "Upload manuscript" })).toBeVisible()
})
