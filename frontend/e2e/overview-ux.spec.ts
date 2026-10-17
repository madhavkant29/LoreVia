import { expect, test } from "@playwright/test"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"

const route = "/sky-of-ash--book-1"
for (const mode of ["author", "reader"] as const) {
  test(`overview ${mode} keeps core actions readable across screen sizes`, async ({ page }, info) => {
    await installMockApi(page, { bookMode: mode, workspaceShell: mode, readerBootstrapProfile: "critical" })
    await page.addInitScript(() => {
      localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 }))
      document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
    })
    await page.goto(route)
    await expect(page.getByRole("button", { name: mode === "author" ? "Open Manuscript Editor" : "Continue Reading", exact: true })).toBeVisible()
    for (const width of [1440, 1280, 768, 390]) {
      await page.setViewportSize({ width, height: 1000 })
      expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
      await page.screenshot({ path: info.outputPath(`overview-${mode}-${width}.png`), fullPage: true })
    }
    expect(await criticalAccessibilityViolations(page, "[data-book-overview]")).toEqual([])
    if (mode === "reader") {
      await expect(page.getByText(/1 highlight/).first()).toBeVisible()
      await expect(page.getByText("Reading details & story memory", { exact: true })).toBeVisible()
      await expect(page.getByRole("searchbox", { name: "Search this book, notes, or summaries" })).toBeVisible()
      for (const action of ["Browse chapter recaps", "Open Notes", "Open Highlights", "Ask about this book", "View all chapters"]) {
        await expect(page.getByRole("button", { name: action, exact: true })).toBeVisible()
      }
    } else {
      await expect(page.getByText("At a glance", { exact: true })).toBeVisible()
      await expect(page.getByText("Up next", { exact: true })).toBeVisible()
      const tabs = page.getByRole("tablist", { name: "Author command center" })
      await expect(tabs).toBeVisible()
      await expect(page.getByRole("link", { name: "Resume revision workflow" })).toBeVisible()
      await expect(page.getByRole("button", { name: /^View calendar/ })).toBeVisible()
      expect(await criticalAccessibilityViolations(page, "#overview-details-panel")).toEqual([])
      expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
      await page.screenshot({ path: info.outputPath("overview-planning-390.png"), fullPage: true })
      await page.locator("#author-goal-calendar").scrollIntoViewIfNeeded()
      await page.screenshot({ path: info.outputPath("overview-calendar-390.png") })
      await tabs.getByRole("tab", { name: "Planning", exact: true }).focus()
      await page.keyboard.press("End")
      await expect(tabs.getByRole("tab", { name: "Statistics", exact: true })).toBeFocused()
      await expect(page.getByRole("tabpanel", { name: "Statistics" })).toBeVisible()
      expect(await criticalAccessibilityViolations(page, "#overview-details-panel")).toEqual([])
      await tabs.getByRole("tab", { name: "Story Map", exact: true }).click()
      expect(await criticalAccessibilityViolations(page, "#overview-details-panel")).toEqual([])
      await page.getByTestId("author-workspace-details").locator("summary").click()
    }
    await page.getByRole("button", { name: "Switch to light mode" }).click()
    await expect(page.locator("html")).not.toHaveClass(/dark/)
    await expect.poll(() => page.locator("[data-book-overview]").evaluate((el) => getComputedStyle(el).backgroundColor)).toBe("rgb(248, 244, 238)")
    await expect.poll(() => page.getByTestId("author-nav-item-chapters").evaluate((el) => getComputedStyle(el).color)).toBe("rgb(120, 113, 108)")
    expect(await criticalAccessibilityViolations(page, "[data-book-overview]")).toEqual([])
    await page.screenshot({ path: info.outputPath(`overview-${mode}-light-390.png`), fullPage: true })
  })
}

test("overview stays on the book after a load failure and retries", async ({ page }) => {
  await installMockApi(page)
  let fail = true
  await page.route("**/books/book-1/reader-bootstrap**", (request) => fail
    ? request.fulfill({ status: 503, json: { detail: "Try later" } })
    : request.fallback())
  await page.goto(route)
  await expect(page.getByRole("heading", { name: "Failed to load book overview" })).toBeVisible()
  await expect(page).toHaveURL(new RegExp(`${route}$`))
  fail = false
  await page.getByRole("button", { name: "Try again" }).click()
  await expect(page.getByRole("heading", { name: "Book overview" })).toBeVisible()
})

test("Story Map conversion confirms the saved task and opens its list", async ({ page }) => {
  await installMockApi(page, { readerBootstrapProfile: "critical" })
  await page.goto(route)
  await page.getByRole("tab", { name: "Story Map", exact: true }).click()
  const convert = page.getByRole("button", { name: "Convert to task", exact: true }).first()
  await expect(convert).toBeEnabled()
  await convert.click()
  await expect(page.getByRole("status").getByText(/task added to Planning/)).toBeVisible()
  await expect(page.getByRole("button", { name: "Task created", exact: true }).first()).toBeDisabled()
  await page.getByRole("button", { name: "View tasks", exact: true }).click()
  await expect(page.locator("#author-project-tasks")).toBeVisible()
  await expect(page.locator("#author-project-tasks li")).not.toHaveCount(0)
  await page.locator("#author-project-tasks li button").first().click()
  const taskDialog = page.getByRole("dialog")
  await expect(taskDialog).toBeVisible()
  await expect(taskDialog.getByText("Source finding")).toBeVisible()
  await expect(taskDialog.getByText("Due", { exact: true })).toBeVisible()
  await taskDialog.getByRole("button", { name: "Close task details" }).click()
  await expect(taskDialog).toBeHidden()
  await page.locator("#author-project-tasks li button").first().click()
  await taskDialog.getByRole("button", { name: "Delete task", exact: true }).click()
  await expect(taskDialog.getByText("The source finding will stay on the revision board.", { exact: false })).toBeVisible()
  await taskDialog.getByRole("button", { name: "Confirm delete" }).click()
  await expect(taskDialog).toBeHidden()
  await expect(page.locator("#author-project-tasks li")).toHaveCount(0)
  await page.getByRole("tab", { name: "Story Map", exact: true }).click()
  await expect(page.getByRole("button", { name: "Convert to task", exact: true }).first()).toBeEnabled()
})

test("overview loading stays within the mobile viewport and announces its state", async ({ page }) => {
  await installMockApi(page)
  await page.setViewportSize({ width: 390, height: 844 })
  let resume: () => void = () => {}
  const gate = new Promise<void>((resolve) => { resume = resolve })
  await page.route("**/books/book-1/reader-bootstrap**", async (request) => { await gate; await request.fallback() })
  await page.goto(route)
  await expect(page.getByRole("status", { name: "Loading book overview" })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
  resume()
  await expect(page.getByRole("heading", { name: "Book overview" })).toBeVisible()
})

test("overview restores the previous workspace and explains a failed switch", async ({ page }) => {
  await installMockApi(page)
  await page.route("**/books/book-1/mode", (request) => request.fulfill({ status: 503, json: { detail: "Try later" } }))
  await page.goto(route)
  await page.getByRole("button", { name: "Reading workspace", exact: true }).click()
  await expect(page.getByRole("alert").filter({ hasText: "workspace could not be changed" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Writing workspace", exact: true })).toHaveAttribute("aria-pressed", "true")
  await expect(page.getByRole("button", { name: "Open Manuscript Editor" })).toBeVisible()
})

test("overview offers recovery when secondary revision data fails", async ({ page }) => {
  await installMockApi(page, { readerBootstrapProfile: "critical" })
  let fail = true
  await page.route("**/books/book-1/revision-intelligence**", (request) => fail
    ? request.fulfill({ status: 503, json: { detail: "Try later" } })
    : request.fallback())
  await page.goto(route)
  await expect(page.getByText("Revision intelligence could not be loaded.")).toBeVisible()
  await expect(page.getByRole("button", { name: "Open Manuscript Editor" })).toBeVisible()
  fail = false
  await page.getByRole("button", { name: "Retry", exact: true }).click()
  await expect(page.getByRole("heading", { name: "Revision pressure at a glance." })).toBeVisible()
})

test("overview keeps notes accessible when saved items fail and retries", async ({ page }) => {
  await installMockApi(page, { bookMode: "reader", workspaceShell: "reader", readerBootstrapProfile: "critical" })
  let fail = true
  await page.route("**/books/quotes/page**", (request) => fail
    ? request.fulfill({ status: 503, json: { detail: "Try later" } })
    : request.fallback())
  await page.goto(route)
  await expect(page.getByText("Saved items could not be refreshed. Retry or open your notes and highlights directly.")).toBeVisible()
  await expect(page.getByRole("button", { name: "Open Notes", exact: true })).toBeEnabled()
  fail = false
  await page.getByRole("button", { name: "Retry", exact: true }).click()
  await expect(page.getByText(/1 highlight/).first()).toBeVisible()
})

test("overview reports a processing retry failure without losing the project", async ({ page }) => {
  await installMockApi(page)
  const bootstrapResponse = page.waitForResponse("**/books/book-1/reader-bootstrap**")
  await page.goto(route)
  const bootstrap = await (await bootstrapResponse).json()
  bootstrap.overview.book.status = "failed"
  bootstrap.overview.book.processing = { status: "failed", stage: "failed", progress_pct: 35, last_error: "Local test failure", retry_available: true }
  await page.route("**/books/book-1/reader-bootstrap**", (request) => request.fulfill({ json: bootstrap }))
  await page.route("**/books/book-1/processing/retry", (request) => request.fulfill({ status: 503, json: { detail: "Try later" } }))
  await page.reload()
  await page.getByRole("button", { name: "Retry processing", exact: true }).first().click()
  await expect(page.getByRole("alert").filter({ hasText: "Processing could not be restarted" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Open Manuscript Editor" })).toBeVisible()
})

test("overview handles a long title and an empty chapter list on mobile", async ({ page }) => {
  await installMockApi(page, { workspaceShell: "reader", bookMode: "reader" })
  const response = page.waitForResponse("**/books/book-1/reader-bootstrap**")
  await page.goto(route)
  const bootstrap = await (await response).json()
  const title = "The Lantern Keeper and the Unfinished Atlas of Every Harbour Beyond the Northern Sea"
  bootstrap.overview.book.title = title
  bootstrap.overview.book.total_chapters = 0
  bootstrap.overview.chapter_list.chapters = []
  bootstrap.overview.summary_collection.summaries = []
  bootstrap.overview.progress = { current_chapter: 1, scroll_pct: 0, chapters_read_count: 0, percent_complete: 0, chapters_left: 0 }
  await page.route("**/books/book-1/reader-bootstrap**", (request) => request.fulfill({ json: bootstrap }))
  await page.setViewportSize({ width: 390, height: 844 })
  await page.reload()
  await expect(page.getByRole("heading", { name: title, exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "Continue Reading", exact: true })).toBeDisabled()
  await expect(page.getByText("This book has no chapters yet. Browse chapters to see available content.")).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
})
