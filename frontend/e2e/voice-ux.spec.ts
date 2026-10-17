import { expect, test, type Page } from "@playwright/test"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"

const path = "/sky-of-ash--book-1/voice"
const api = "**/api/v1/intelligence/*/advisor/voice-consistency"
const input = (page: Page) => page.getByRole("textbox", { name: "Dialogue or chapter text for voice review" })
const run = (page: Page) => page.getByRole("button", { name: "Run voice review", exact: true })
const review = { review: { overall_verdict: "The submitted dialogue retains Nora's clipped cadence.", issues: [] }, characters_reviewed: ["Nora"], warnings: ["Only two baseline samples were available."], character_matches: [], retrieved_passages: [{ chapter_num: 2, chapter_title: "The Ember Gate", excerpt: "A baseline dialogue excerpt.", relevance: .8 }] }

test.beforeEach(async ({ page }) => {
  await installMockApi(page, { voiceConsistency: "selected-character" })
  await page.route("**/api/v1/books/book-1/scenes", (route) => route.request().method() === "POST" ? route.fulfill({ status: 201, json: { ...route.request().postDataJSON(), id: "voice-scene-1" } }) : route.fallback())
  await page.addInitScript(() => { if (!localStorage.getItem("lorevia-preferences")) localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 })); document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax" })
})

test("voice source and findings are readable at four widths and in both themes", async ({ page }, info) => {
  const errors: string[] = []; page.on("pageerror", (error) => errors.push(error.message))
  await page.goto(path); await expect(run(page)).toBeEnabled(); await run(page).click()
  await expect(page.getByRole("heading", { name: "Verdict", exact: true })).toBeVisible()
  if (await page.getByRole("button", { name: "Not now", exact: true }).isVisible()) await page.getByRole("button", { name: "Not now", exact: true }).click()
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }))
    await page.screenshot({ path: info.outputPath(`voice-${width}.png`), fullPage: true, animations: "disabled" })
  }
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.getByRole("button", { name: "Help", exact: true }).focus(); await page.keyboard.press("Enter")
  await expect(page.getByRole("dialog")).toBeVisible(); await page.keyboard.press("Escape")
  await page.evaluate(() => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "light" }, version: 0 })))
  page.once("dialog", (dialog) => dialog.accept()); await page.reload(); await expect(run(page)).toBeEnabled(); await run(page).click()
  await expect(page.getByRole("heading", { name: "Verdict", exact: true })).toBeVisible()
  await page.screenshot({ path: info.outputPath("voice-light.png"), fullPage: true, animations: "disabled" })
  expect(await criticalAccessibilityViolations(page)).toEqual([]); expect(errors).toEqual([])
})

test("voice drafts survive source changes, refresh, and declined discard or navigation", async ({ page }) => {
  await page.goto(path); await expect(run(page)).toBeEnabled()
  await input(page).fill("Edited chapter dialogue")
  await page.getByLabel("Chapter or passage", { exact: true }).selectOption("")
  await input(page).fill("A custom passage")
  await page.evaluate(() => window.dispatchEvent(new Event("online")))
  await expect(input(page)).toHaveValue("A custom passage")
  await page.getByLabel("Chapter or passage", { exact: true }).selectOption("2")
  await expect(input(page)).toHaveValue("Edited chapter dialogue")
  page.once("dialog", (dialog) => dialog.dismiss()); await page.getByRole("button", { name: "Discard passage edits" }).click()
  await expect(input(page)).toHaveValue("Edited chapter dialogue")
  page.once("dialog", (dialog) => dialog.dismiss()); await page.getByRole("link", { name: "Open manuscript", exact: true }).click()
  await expect(page).toHaveURL(new RegExp(`${path}$`))
  page.once("dialog", (dialog) => dialog.accept()); await page.getByRole("button", { name: "Discard passage edits" }).click()
  await expect(input(page)).toHaveValue(/Nora crossed the ember gate/)
  await page.getByLabel("Chapter or passage", { exact: true }).selectOption("")
  await expect(input(page)).toHaveValue("A custom passage")
})

test("voice protects the full passage at the length boundary and saves the submitted snapshot", async ({ page }) => {
  let release!: () => void; const held = new Promise<void>((resolve) => { release = resolve }); const requests: { text: string }[] = []
  await page.route(api, async (route) => { requests.push(route.request().postDataJSON()); await held; await route.fulfill({ json: review }) })
  await page.goto(path); await expect(run(page)).toBeEnabled()
  await input(page).fill("x".repeat(12001)); await expect(run(page)).toBeDisabled()
  await expect(page.getByText(/shorten the passage before reviewing/)).toBeVisible()
  expect(requests).toEqual([])
  await input(page).fill("x".repeat(12000)); await run(page).click()
  await expect(page.getByRole("button", { name: "Reviewing...", exact: true })).toBeDisabled()
  await input(page).fill("Later edited text"); release()
  await expect(page.getByText(/The editor or character focus has changed/)).toBeVisible()
  expect(requests).toHaveLength(1); expect(requests[0].text).toHaveLength(12000)
  await page.getByText("Read the reviewed passage", { exact: true }).click()
  await expect(page.locator("details").filter({ hasText: "Read the reviewed passage" })).toContainText("x".repeat(12000))
  const saved = page.waitForRequest((request) => request.method() === "POST" && new URL(request.url()).pathname === "/api/v1/books/book-1/scenes")
  await page.getByRole("button", { name: "Save snapshot", exact: true }).click()
  const payload = (await saved).postDataJSON()
  expect(payload.body).toContain("x".repeat(12000)); expect(payload.body).not.toContain("Later edited text")
  expect(payload.body).toContain("Only two baseline samples"); expect(payload.chapter_number).toBe(2)
  await expect(page.getByText(/Saved review scene to/)).toBeVisible()
})

test("voice retains earlier results through review failure and exposes evidence", async ({ page }) => {
  let fail = false
  await page.route(api, (route) => route.fulfill(fail ? { status: 503, json: { detail: "Review temporarily unavailable." } } : { json: review }))
  await page.goto(path); await expect(run(page)).toBeEnabled(); await run(page).click()
  await expect(page.getByText(review.review.overall_verdict, { exact: true })).toBeVisible()
  await page.getByText("Manuscript evidence (1 passage)", { exact: true }).click()
  await expect(page.getByText("A baseline dialogue excerpt.", { exact: true })).toBeVisible()
  await expect(page.getByRole("link", { name: "Open chapter 2", exact: true })).toHaveAttribute("href", "/sky-of-ash--book-1/manuscript?chapter=2")
  fail = true; await input(page).fill("Another passage"); await run(page).click()
  await expect(page.getByText("Review temporarily unavailable.", { exact: true })).toBeVisible()
  await expect(page.getByText(review.review.overall_verdict, { exact: true })).toBeVisible()
  await expect(input(page)).toHaveValue("Another passage")
})

test("voice query failures offer independent retries without replacing custom drafts", async ({ page }) => {
  let bookFailed = true; let chaptersFailed = true; let charactersFailed = true
  await page.route((url) => url.pathname === "/api/v1/books/book-1", (route) => bookFailed ? route.fulfill({ status: 503, json: { detail: "Unavailable" } }) : route.fallback())
  await page.route((url) => url.pathname === "/api/v1/reader/book-1/chapters", (route) => chaptersFailed ? route.fulfill({ status: 503, json: { detail: "Unavailable" } }) : route.fallback())
  await page.route((url) => url.pathname === "/api/v1/books/book-1/characters", (route) => charactersFailed ? route.fulfill({ status: 503, json: { detail: "Unavailable" } }) : route.fallback())
  await page.goto(path); await input(page).fill("Keep this custom draft")
  await expect(page.getByRole("button", { name: "Retry book context" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Retry chapter list" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Retry characters" })).toBeVisible()
  await expect(run(page)).toBeDisabled()
  bookFailed = false; await page.getByRole("button", { name: "Retry book context" }).click()
  await expect(run(page)).toBeEnabled()
  chaptersFailed = false; await page.getByRole("button", { name: "Retry chapter list" }).click()
  charactersFailed = false; await page.getByRole("button", { name: "Retry characters" }).click()
  await expect(page.getByLabel("Chapter or passage", { exact: true })).toHaveValue("")
  await expect(input(page)).toHaveValue("Keep this custom draft")
  await expect(page.getByLabel("Character focus", { exact: true }).locator('option[value="char-gregor"]')).toHaveCount(1)
})

test("voice chapter loading and errors do not masquerade as an empty passage", async ({ page }) => {
  let release!: () => void; const held = new Promise<void>((resolve) => { release = resolve }); let fail = true
  await page.route((url) => url.pathname === "/api/v1/reader/book-1/chapter/2", async (route) => { if (!fail) return route.fallback(); await held; await route.fulfill({ status: 503, json: { detail: "Unavailable" } }) })
  await page.goto(path); await expect(page.getByText("Loading chapter text...", { exact: true })).toBeVisible()
  await expect(run(page)).toBeDisabled(); release()
  await expect(page.getByRole("button", { name: "Retry chapter text" })).toBeVisible()
  fail = false; await page.getByRole("button", { name: "Retry chapter text" }).click()
  await expect(input(page)).toHaveValue(/Nora crossed the ember gate/); await expect(run(page)).toBeEnabled()
})

test("voice note and scene saves recover visibly and serialize writes", async ({ page }) => {
  await page.route(api, (route) => route.fulfill({ json: review }))
  let fail = true; let writes = 0; let release!: () => void; const held = new Promise<void>((resolve) => { release = resolve })
  await page.route((url) => url.pathname === "/api/v1/books/book-1/notes/vault", async (route) => {
    if (route.request().method() !== "PUT") return route.fallback()
    writes++
    if (fail) return route.fulfill({ status: 503, json: { detail: "Save temporarily unavailable." } })
    await held; return route.fallback()
  })
  await page.goto(path); await expect(run(page)).toBeEnabled(); await run(page).click()
  await page.getByRole("button", { name: "Save review note", exact: true }).click()
  await expect(page.getByText(/Check Notes before trying again/)).toBeVisible()
  fail = false; await page.getByRole("button", { name: "Save review note", exact: true }).click()
  await expect(page.getByRole("button", { name: "Save snapshot", exact: true })).toBeDisabled()
  await expect(page.getByRole("button", { name: "Save review note", exact: true })).toBeDisabled()
  release(); await expect(page.getByText(/Saved voice note to/)).toBeVisible(); expect(writes).toBe(2)
  let sceneFailed = true
  await page.route((url) => url.pathname === "/api/v1/books/book-1/workspace/tree", (route) => sceneFailed ? route.fulfill({ status: 503, json: { detail: "Scene list unavailable." } }) : route.fallback())
  await page.getByRole("button", { name: "Save snapshot", exact: true }).click()
  await expect(page.getByText(/Check Scenes before trying again/)).toBeVisible()
  await expect(page.getByText(review.review.overall_verdict, { exact: true })).toBeVisible()
  sceneFailed = false; await page.getByRole("button", { name: "Save snapshot", exact: true }).click()
  await expect(page.getByText(/Saved review scene to/)).toBeVisible()
})

test("voice empty choices and long evidence stay usable on mobile", async ({ page }, info) => {
  await page.route((url) => url.pathname === "/api/v1/reader/book-1/chapters", (route) => route.fulfill({ json: { chapters: [], current_chapter: null } }))
  await page.route((url) => url.pathname === "/api/v1/books/book-1/characters", (route) => route.fulfill({ json: [] }))
  await page.route(api, (route) => route.fulfill({ json: { ...review, review: { overall_verdict: "LongWord".repeat(100), issues: [] }, retrieved_passages: [{ chapter_num: 99, excerpt: "LongExcerpt".repeat(100), chapter_title: "Unavailable chapter", relevance: 0 }] } }))
  await page.setViewportSize({ width: 390, height: 1000 }); await page.goto(path)
  await expect(page.getByText(/No chapters yet/)).toBeVisible()
  await expect(page.getByText(/No character choices yet/)).toBeVisible()
  await input(page).fill("   "); await expect(run(page)).toBeDisabled()
  await input(page).fill("Original dialogue"); await run(page).click()
  await page.getByText("Manuscript evidence (1 passage)", { exact: true }).click()
  await expect(page.getByText(/This chapter is not available/)).toBeVisible()
  await expect(page.getByRole("link", { name: "Open chapter 99" })).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  await page.screenshot({ path: info.outputPath("voice-long-mobile.png"), fullPage: true, animations: "disabled" })
  expect(await criticalAccessibilityViolations(page)).toEqual([])
})

test("voice finding notes keep the reviewed character after a focus change", async ({ page }) => {
  await page.goto(path); await expect(run(page)).toBeEnabled()
  await page.getByLabel("Character focus", { exact: true }).selectOption("char-gregor")
  await run(page).click(); await expect(page.getByText("Reviewed: Gregor", { exact: true })).toBeVisible()
  await page.getByLabel("Character focus", { exact: true }).selectOption("char-grete")
  await expect(page.getByText(/The editor or character focus has changed/)).toBeVisible()
  await page.getByText("If this change is intentional", { exact: true }).focus(); await page.keyboard.press("Enter")
  await expect(page.locator("details[open]")).toContainText("Gregor")
  const saved = page.waitForRequest((request) => request.method() === "PUT" && new URL(request.url()).pathname === "/api/v1/books/book-1/notes/vault")
  await page.getByRole("button", { name: "Save note: Gregor slips into abstract explanation" }).click()
  const content = (await saved).postDataJSON().content as string
  expect(content).toContain("Character focus: Gregor"); expect(content).toContain("Chapter 2")
  expect(content).toContain("Gregor slips into abstract explanation")
  await expect(page.getByText(/Saved voice note to/)).toBeVisible()
  await page.getByRole("link", { name: "View review", exact: true }).click()
  await expect(page.getByRole("heading", { name: "Character voice", exact: true })).toBeFocused()
})
