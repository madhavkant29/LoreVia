import { expect, test, type Page } from "@playwright/test"
import type { Character } from "@/types/character"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"

const route = "/sky-of-ash--book-1/characters"
test.beforeEach(async ({ page }) => {
  await installMockApi(page)
  await page.addInitScript(() => {
    if (!localStorage.getItem("lorevia-preferences")) localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 }))
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
})

async function openEdit(page: Page) {
  await page.getByRole("button", { name: "Character actions", exact: true }).click()
  await page.getByRole("button", { name: "Edit details", exact: true }).click()
  await expect(page.getByRole("heading", { name: "Edit profile", exact: true })).toBeVisible()
}

test("character load failures offer retry instead of an empty cast", async ({ page }) => {
  let failed = true
  await page.route("**/api/v1/books/book-1/characters", async (request) => {
    if (failed) return request.fulfill({ status: 503, json: { detail: "Temporarily unavailable" } })
    return request.fallback()
  })
  await page.goto(route)
  await expect(page.getByRole("button", { name: "Retry character roster" })).toBeVisible({ timeout: 20000 })
  await expect(page.getByRole("heading", { name: "No characters yet" })).toHaveCount(0)
  failed = false
  await page.getByRole("button", { name: "Retry character roster" }).click()
  await expect(page.getByRole("heading", { name: "Gregor", exact: true })).toBeVisible()
})

test("character editing preserves a failed save and can retry", async ({ page }) => {
  await page.goto(route)
  await expect(page.getByRole("heading", { name: "Gregor", exact: true })).toBeVisible()
  const characters = await page.evaluate(async () => (await fetch("/api/v1/books/book-1/characters")).json()) as Character[]
  const selected = characters.find((item) => item.name === "Gregor")!
  let failed = true
  await page.route("**/api/v1/books/book-1/characters", (request) => request.fulfill({ json: characters }))
  await page.route(`**/api/v1/books/book-1/characters/${selected.id}`, async (request) => {
    if (failed) return request.fulfill({ status: 503, json: { detail: "Unavailable" } })
    Object.assign(selected, request.request().postDataJSON())
    return request.fulfill({ json: selected })
  })
  await openEdit(page)
  await page.getByLabel("Name", { exact: true }).fill("Gregor Revised")
  await page.getByRole("button", { name: "Save changes", exact: true }).click()
  await expect(page.getByRole("alert").filter({ hasText: "Could not save character changes" })).toBeVisible()
  await expect(page.getByLabel("Name", { exact: true })).toHaveValue("Gregor Revised")
  failed = false
  await page.getByRole("button", { name: "Save changes", exact: true }).click()
  await expect(page.getByRole("heading", { name: "Gregor Revised", exact: true })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Edit profile", exact: true })).toHaveCount(0)
})

test("character drafts survive filtering and cancelled profile switches", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto(route)
  await openEdit(page)
  await page.getByLabel("Name", { exact: true }).fill("Gregor Draft")
  await page.getByLabel("Search characters").fill("Grete")
  await expect(page.getByRole("heading", { name: "Gregor", exact: true })).toBeVisible()
  await page.getByRole("button", { name: /Grete.*Supporting character/ }).click()
  await expect(page.getByRole("dialog", { name: "Discard character changes?" })).toBeVisible()
  await page.getByRole("button", { name: "Cancel", exact: true }).last().click()
  await expect(page.getByLabel("Name", { exact: true })).toHaveValue("Gregor Draft")
  await page.getByRole("button", { name: /Grete.*Supporting character/ }).click()
  await page.getByRole("button", { name: "Discard changes", exact: true }).click()
  await expect(page.getByRole("heading", { name: "Grete", exact: true })).toBeVisible()
  await page.getByRole("button", { name: "Clear filters", exact: true }).click()
  await expect(page.getByLabel("Search characters")).toHaveValue("")
})

test("character panels and tabs support keyboard navigation and focus return", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 1000 })
  await page.goto(route)
  await expect(page.getByRole("heading", { name: "Gregor", exact: true })).toBeVisible()
  await page.getByRole("button", { name: "Cast", exact: true }).click()
  await expect(page.getByRole("dialog", { name: "Character roster" })).toBeVisible()
  await page.getByLabel("Search characters").fill("No matching person")
  await page.getByRole("button", { name: "Clear filters", exact: true }).click()
  await page.keyboard.press("Escape")
  await expect(page.getByRole("button", { name: "Cast", exact: true })).toBeFocused()
  await page.getByRole("tab", { name: "Overview", exact: true }).focus()
  await page.keyboard.press("End")
  await expect(page.getByRole("tab", { name: "Notes", exact: true })).toHaveAttribute("aria-selected", "true")
  await page.keyboard.press("Home")
  await expect(page.getByRole("tab", { name: "Overview", exact: true })).toBeFocused()
  await page.getByRole("button", { name: "Character actions", exact: true }).click()
  await page.keyboard.press("Escape")
  await expect(page.getByRole("button", { name: "Character actions", exact: true })).toBeFocused()
  await page.getByRole("button", { name: "Details", exact: true }).click()
  const dialog = page.getByRole("dialog", { name: "Character details" })
  await expect(dialog).toBeVisible()
  await dialog.getByRole("tab", { name: "Insights", exact: true }).focus()
  await page.keyboard.press("ArrowRight")
  await expect(dialog.getByRole("tab", { name: "Evidence", exact: true })).toHaveAttribute("aria-selected", "true")
  await page.keyboard.press("Escape")
  await expect(page.getByRole("button", { name: "Details", exact: true })).toBeFocused()
})

test("mobile profile edits survive cancelled navigation and cast selection", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 1000 })
  await page.goto(route)
  await page.getByRole("button", { name: "Edit profile", exact: true }).click()
  await page.getByLabel("Name", { exact: true }).fill("Gregor Draft")
  await page.getByRole("link", { name: /Book overview/ }).first().click()
  await expect(page.getByRole("dialog", { name: "Leave with unsaved character changes?" })).toBeVisible()
  await page.getByRole("button", { name: "Keep editing", exact: true }).click()
  await expect(page.getByLabel("Name", { exact: true })).toHaveValue("Gregor Draft")
  await page.getByRole("button", { name: "Cast", exact: true }).click()
  await page.getByRole("button", { name: /Grete.*Supporting character/ }).click()
  const confirmation = page.getByRole("dialog", { name: "Discard character changes?" })
  await expect(confirmation).toBeVisible()
  await confirmation.getByRole("button", { name: "Cancel", exact: true }).click()
  await expect(page.getByLabel("Name", { exact: true })).toHaveValue("Gregor Draft")
})

test("graph selection cannot silently replace an edited profile", async ({ page }) => {
  await page.goto(route)
  await page.getByRole("button", { name: "Edit profile", exact: true }).click()
  await page.getByLabel("Name", { exact: true }).fill("Gregor Draft")
  await page.getByRole("tab", { name: "Relationships", exact: true }).click()
  await expect(page.getByText("Graph details", { exact: true })).toBeVisible()
  await page.evaluate(() => {
    (window as Window & { __LOREVIA_RELATIONSHIP_GRAPH__?: { selectNode: (id: string) => void } }).__LOREVIA_RELATIONSHIP_GRAPH__?.selectNode("char-grete")
  })
  const confirmation = page.getByRole("dialog", { name: "Discard character changes?" })
  await expect(confirmation).toBeVisible()
  await confirmation.getByRole("button", { name: "Cancel", exact: true }).click()
  await page.getByRole("tab", { name: "Overview", exact: true }).click()
  await expect(page.getByLabel("Name", { exact: true })).toHaveValue("Gregor Draft")
  await expect(page.getByRole("heading", { name: "Gregor", exact: true })).toBeVisible()
})

test("review load errors retain profiles and recover without reloading", async ({ page }) => {
  let failed = true
  await page.route("**/api/v1/books/book-1/character-review?**", async (request) => {
    if (failed) return request.fulfill({ status: 503, json: { detail: "Unavailable" } })
    return request.fallback()
  })
  await page.goto(route)
  await expect(page.getByRole("heading", { name: "Gregor", exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "Retry review queue" })).toBeVisible({ timeout: 20000 })
  failed = false
  await page.getByRole("button", { name: "Retry review queue" }).click()
  await expect(page.getByRole("button", { name: "Retry review queue" })).toHaveCount(0)
  await expect(page.getByRole("heading", { name: "Gregor", exact: true })).toBeVisible()
})

test("character sections and author tools remain accessible", async ({ page }, info) => {
  for (const [theme, width] of [["dark", 1440], ["light", 390]] as const) {
    await page.setViewportSize({ width, height: 1000 })
    await page.goto(route)
    await page.evaluate((theme) => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme }, version: 0 })), theme)
    await page.reload()
    await expect(page.getByRole("heading", { name: "Gregor", exact: true })).toBeVisible()
    for (const name of ["Relationships", "Mentions", "Timeline", "Arc", "Continuity", "Evidence", "Notes"]) {
      await page.getByRole("tab", { name, exact: true }).click()
      if (name === "Relationships") {
        await expect(page.getByText("Graph details", { exact: true })).toBeVisible()
        await expect(page.getByRole("button", { name: "Close graph inspector", exact: true })).toHaveCount(0)
      }
      expect(await criticalAccessibilityViolations(page, "main"), name + " " + theme).toEqual([])
      expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
    }
    for (const name of ["Review duplicate suggestions", "Open review queue", "Open repair workspace"]) {
      await page.getByRole("button", { name: "Open menu", exact: true }).click()
      await page.getByRole("button", { name, exact: true }).click()
      await page.getByRole("button", { name: "Review queue", exact: true }).evaluate(async (button) => {
        await Promise.all(button.getAnimations().map((animation) => animation.finished.catch(() => undefined)))
      })
      expect(await criticalAccessibilityViolations(page, "main"), name + " " + theme).toEqual([])
      expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
      await page.screenshot({ path: info.outputPath(theme + "-" + name.replaceAll(" ", "-") + ".png"), fullPage: true })
    }
  }
})

test("repair preview failure prevents applying a plan until retry succeeds", async ({ page }) => {
  let failed = true
  await page.route("**/api/v1/books/book-1/character-review/reprocess?**", (request) => failed
    ? request.fulfill({ status: 503, json: { detail: "Unavailable" } }) : request.fallback())
  await page.goto(route)
  await expect(page.getByRole("heading", { name: "Gregor", exact: true })).toBeVisible()
  await page.getByRole("button", { name: "Open menu", exact: true }).click()
  await page.getByRole("button", { name: "Open repair workspace", exact: true }).click()
  await expect(page.getByRole("button", { name: "Retry repair preview" })).toBeVisible({ timeout: 20000 })
  await expect(page.getByRole("button", { name: "Apply repair plan", exact: true })).toBeDisabled()
  failed = false
  await page.getByRole("button", { name: "Retry repair preview" }).click()
  await expect(page.getByRole("button", { name: "Apply repair plan", exact: true })).toBeEnabled()
})

test("character evidence failure offers an effective retry", async ({ page }) => {
  let failed = true
  await page.route("**/api/v1/reader/book-1/search?**", (request) => failed
    ? request.fulfill({ status: 503, json: { detail: "Unavailable" } }) : request.fallback())
  await page.goto(route)
  await expect(page.getByRole("heading", { name: "Gregor", exact: true })).toBeVisible()
  await page.getByRole("tab", { name: "Evidence", exact: true }).click()
  await expect(page.getByRole("button", { name: "Retry evidence" })).toBeVisible()
  failed = false
  await page.getByRole("button", { name: "Retry evidence" }).click()
  await expect(page.getByRole("button", { name: "Retry evidence" })).toHaveCount(0)
  await expect(page.getByRole("heading", { name: "Passage evidence", exact: true })).toBeVisible()
})

test("long character names wrap and an empty cast offers a working create action", async ({ page }, info) => {
  await page.goto(route)
  await expect(page.getByRole("heading", { name: "Gregor", exact: true })).toBeVisible()
  const characters = await page.evaluate(async () => (await fetch("/api/v1/books/book-1/characters")).json()) as Character[]
  characters[0].name = "Gregor of the Northern Crossing with a Very Long Family Name"
  await page.route("**/api/v1/books/book-1/characters", (request) => request.fulfill({ json: characters }))
  await page.reload()
  await expect(page.getByRole("heading", { name: characters[0].name, exact: true })).toBeVisible()
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
    await page.screenshot({ path: info.outputPath(`characters-long-${width}.png`), fullPage: true })
  }
  await page.route("**/api/v1/books/book-1/characters", (request) => request.fulfill({ json: [] }))
  await page.route("**/api/v1/books/book-1/character-review?**", (request) => request.fulfill({ json: { candidates: [], duplicate_suggestions: [], relationship_candidates: [], shadow_characters: [], decision_events: [], counts: { pending_candidates: 0, pending_duplicate_suggestions: 0, pending_relationship_candidates: 0 } } }))
  await page.reload()
  await expect(page.getByText("No character profiles were saved from this manuscript.")).toBeVisible()
  await page.getByRole("button", { name: "Add character manually", exact: true }).click()
  await expect(page.getByRole("heading", { name: "New character", exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "Create character", exact: true })).toBeDisabled()
  await page.getByLabel("Name", { exact: true }).fill("Nora")
  await expect(page.getByRole("button", { name: "Create character", exact: true })).toBeEnabled()
})

test("character workspace is readable across screen sizes", async ({ page }, info) => {
  await page.goto(route)
  await expect(page.getByRole("heading", { name: "Gregor", exact: true })).toBeVisible()
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
    await page.screenshot({ path: info.outputPath(`characters-${width}.png`), fullPage: true })
  }
  expect(await criticalAccessibilityViolations(page, "body")).toEqual([])
  await page.getByRole("button", { name: "Cast", exact: true }).click()
  await page.screenshot({ path: info.outputPath("characters-cast-390.png"), fullPage: true })
  expect(await criticalAccessibilityViolations(page, "body")).toEqual([])
  await page.getByRole("button", { name: "Close", exact: true }).click()
  await page.getByRole("button", { name: "Details", exact: true }).click()
  await page.screenshot({ path: info.outputPath("characters-details-390.png"), fullPage: true })
  expect(await criticalAccessibilityViolations(page, "body")).toEqual([])
  await page.getByRole("button", { name: "Close", exact: true }).click()
  await page.evaluate(() => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "light" }, version: 0 })))
  await page.reload()
  await expect(page.getByRole("heading", { name: "Gregor", exact: true })).toBeVisible()
  await page.screenshot({ path: info.outputPath("characters-light-390.png"), fullPage: true })
  expect(await criticalAccessibilityViolations(page, "body")).toEqual([])
})
