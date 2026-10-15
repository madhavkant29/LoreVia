import { expect, test, type Page } from "@playwright/test"
import type { ManuscriptWorkspaceTree, WorkspaceScene } from "@/types/book"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"

const route = "/sky-of-ash--book-1/scenes"
test.beforeEach(async ({ page }) => {
  await installMockApi(page)
  await page.addInitScript(() => {
    if (!localStorage.getItem("lorevia-preferences")) localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 }))
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
})

test("scene workspace stays readable across screen sizes", async ({ page }, info) => {
  await page.goto(route)
  await expect(page.getByLabel("Scene title")).toHaveValue("Gate Crossing")
  await expect(page.getByText("Nora crosses into the city.", { exact: true })).toBeVisible()
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)).toBe(false)
    await page.screenshot({ path: info.outputPath(`scenes-${width}.png`), fullPage: true })
  }
  expect(await criticalAccessibilityViolations(page, "main")).toEqual([])
  await page.getByRole("button", { name: "Details", exact: true }).click()
  await expect(page.getByRole("dialog", { name: "Scene details" })).toBeVisible()
  await page.screenshot({ path: info.outputPath("scenes-details-390.png"), fullPage: true })
  expect(await criticalAccessibilityViolations(page, '[role="dialog"]')).toEqual([])
  await page.keyboard.press("Escape")
  await expect(page.getByRole("button", { name: "Details", exact: true })).toBeFocused()
  await page.evaluate(() => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "light" }, version: 0 })))
  await page.reload()
  await expect(page.getByLabel("Scene title")).toHaveValue("Gate Crossing")
  await expect(page.getByRole("textbox", { name: "Scene text", exact: true })).toHaveText("Nora crosses into the city.")
  await expect.poll(() => page.locator("[data-scene-workspace]").evaluate((el) => getComputedStyle(el).backgroundColor)).toBe("rgb(250, 250, 249)")
  expect(await criticalAccessibilityViolations(page, "main")).toEqual([])
  await page.screenshot({ path: info.outputPath("scenes-light-390.png"), fullPage: true })
})

async function installSceneWrites(page: Page) {
  const state = {
    tree: await page.evaluate(async () => (await fetch("/api/v1/books/book-1/workspace/tree?include_scene_bodies=true")).json()) as ManuscriptWorkspaceTree,
    failSave: false,
    failDelete: false,
    failTree: false,
    saves: [] as Partial<WorkspaceScene>[],
  }
  await page.route("**/api/v1/books/book-1/workspace/tree**", (request) => request.fulfill(state.failTree ? { status: 503, json: { detail: "Try later" } } : { json: state.tree }))
  await page.route("**/api/v1/books/book-1/scenes", (request) => {
    if (request.request().method() !== "POST") return request.fallback()
    const payload = request.request().postDataJSON() as Partial<WorkspaceScene>
    state.saves.push(payload)
    const created = { ...state.tree.scene_groups[0].scenes[0], ...payload, id: "new-scene-1" }
    state.tree.scene_groups[0].scenes.push(created)
    return request.fulfill({ status: 201, json: created })
  })
  await page.route("**/api/v1/books/book-1/scenes/**", (request) => {
    const id = new URL(request.request().url()).pathname.split("/").pop()
    if (request.request().method() === "PUT") {
      if (state.failSave) return request.fulfill({ status: 503, json: { detail: "Try later" } })
      const payload = request.request().postDataJSON() as Partial<WorkspaceScene>
      state.saves.push(payload)
      state.tree.scene_groups.forEach((group) => { group.scenes = group.scenes.map((scene) => scene.id === id ? { ...scene, ...payload } : scene) })
      return request.fulfill({ json: { ...payload, id } })
    }
    if (request.request().method() === "DELETE") {
      if (state.failDelete) return request.fulfill({ status: 503, json: { detail: "Try later" } })
      state.tree.scene_groups.forEach((group) => { group.scenes = group.scenes.filter((scene) => scene.id !== id) })
      return request.fulfill({ status: 204, body: "" })
    }
    return request.fallback()
  })
  return state
}

test("scene save errors preserve edits and keyboard save retries the current draft", async ({ page }) => {
  await page.goto(route)
  await expect(page.getByLabel("Scene title")).toHaveValue("Gate Crossing")
  const state = await installSceneWrites(page)
  state.failSave = true
  await page.getByLabel("Scene title").fill("The revised gate crossing")
  const editor = page.getByRole("textbox", { name: "Scene text", exact: true })
  await editor.fill("Nora waits beneath the bell tower for the courier.")
  await page.getByRole("button", { name: "Save scene", exact: true }).click()
  await expect(page.getByRole("alert").filter({ hasText: "Could not save this scene" })).toBeVisible()
  await expect(editor).toHaveText("Nora waits beneath the bell tower for the courier.")
  state.failSave = false
  await editor.focus()
  await page.keyboard.press("Control+s")
  await expect(page.getByRole("status")).toContainText("Scene saved.")
  await expect(page.getByLabel("Scene title")).toHaveValue("The revised gate crossing")
  await expect(page.getByRole("button", { name: "Save scene", exact: true })).toBeDisabled()
  expect(state.saves).toHaveLength(1)
  expect(state.saves[0].body).toContain("bell tower")
})

test("scene deletion requires confirmation and reports a recoverable failure", async ({ page }) => {
  await page.goto(route)
  await expect(page.getByLabel("Scene title")).toHaveValue("Gate Crossing")
  const state = await installSceneWrites(page)
  state.failDelete = true
  await page.getByRole("button", { name: "Delete", exact: true }).click()
  await page.getByRole("dialog").getByRole("button", { name: "Cancel", exact: true }).click()
  await expect(page.getByLabel("Scene title")).toHaveValue("Gate Crossing")
  await page.getByRole("button", { name: "Delete", exact: true }).click()
  await page.getByRole("dialog").getByRole("button", { name: "Delete scene", exact: true }).click()
  await expect(page.getByRole("alert").filter({ hasText: "Could not delete this scene" })).toBeVisible()
  state.failDelete = false
  await page.getByRole("button", { name: "Delete", exact: true }).click()
  await page.getByRole("dialog").getByRole("button", { name: "Delete scene", exact: true }).click()
  await expect(page.getByRole("status")).toContainText("Scene deleted.")
  await expect(page.getByLabel("Scene title")).not.toHaveValue("Gate Crossing")
})

test("scene navigation and new-scene actions protect unsaved changes", async ({ page }) => {
  await page.goto(route)
  await expect(page.getByLabel("Scene title")).toHaveValue("Gate Crossing")
  await page.getByLabel("Scene title").fill("Unsaved gate revision")
  await page.getByRole("button", { name: "New scene", exact: true }).click()
  await page.getByRole("dialog").getByRole("button", { name: "Keep editing" }).click()
  await expect(page.getByLabel("Scene title")).toHaveValue("Unsaved gate revision")
  await page.getByRole("link", { name: "Chapters", exact: true }).click()
  await expect(page.getByRole("dialog", { name: "Leave with unsaved scene changes?" })).toBeVisible()
  await page.getByRole("dialog").getByRole("button", { name: "Keep editing" }).click()
  await expect(page).toHaveURL(new RegExp(`${route}$`))
  await page.getByRole("button", { name: "New scene", exact: true }).click()
  await page.getByRole("dialog").getByRole("button", { name: "Discard changes" }).click()
  await expect(page.getByLabel("Scene title")).toHaveValue("")
  await expect(page.getByRole("button", { name: "Save scene", exact: true })).toBeDisabled()
})

test("scene mobile outline has keyboard tabs and search recovery", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(route)
  await expect(page.getByLabel("Scene title")).toHaveValue("Gate Crossing")
  const outline = page.getByRole("button", { name: "Outline", exact: true })
  await outline.click()
  const dialog = page.getByRole("dialog", { name: "Scene outline" })
  await expect(dialog).toBeVisible()
  await dialog.getByRole("tab", { name: "Folders", exact: true }).focus()
  await page.keyboard.press("ArrowRight")
  await expect(dialog.getByRole("tab", { name: "Scenes", exact: true })).toBeFocused()
  await expect(dialog.getByRole("tabpanel", { name: "Scenes", exact: true })).toBeVisible()
  await dialog.getByLabel("Search scenes", { exact: true }).fill("No such scene")
  await expect(dialog.getByText("No scenes match this view.")).toBeVisible()
  await dialog.getByRole("button", { name: "Clear filters" }).click()
  await expect(dialog.getByRole("button", { name: /Gate Crossing/ })).toBeVisible()
  expect(await criticalAccessibilityViolations(page, '[role="dialog"]')).toEqual([])
  await page.keyboard.press("Escape")
  await expect(outline).toBeFocused()
})

test("scene initial load errors retry and empty workspaces explain saving requirements", async ({ page }) => {
  let fail = true
  await page.route("**/api/v1/books/book-1/workspace/tree**", (request) => request.fulfill(fail ? { status: 503, json: { detail: "Try later" } } : { json: { chapters: [], scene_groups: [], structure_tree: [] } }))
  await page.goto(route)
  await expect(page.getByRole("heading", { name: "Scene workspace unavailable" })).toBeVisible()
  await expect(page.getByRole("button", { name: "New scene", exact: true })).toBeDisabled()
  fail = false
  await page.getByRole("button", { name: "Retry", exact: true }).click()
  await expect(page.getByText("Add a title and scene text to save.")).toBeVisible()
  await expect(page.getByRole("button", { name: "Save scene", exact: true })).toBeDisabled()
})

test("scene details expose labelled fields and keep changes when the panel closes", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(route)
  await expect(page.getByLabel("Scene title")).toHaveValue("Gate Crossing")
  const state = await installSceneWrites(page)
  await page.getByRole("button", { name: "Details", exact: true }).click()
  const details = page.getByRole("dialog", { name: "Scene details" })
  await details.getByLabel("Description", { exact: true }).fill("The courier arrives before curfew.")
  await details.getByLabel("POV character", { exact: true }).fill("Nora")
  const advanced = details.getByRole("button", { name: "Advanced metadata", exact: true })
  if (await advanced.getAttribute("aria-expanded") === "false") await advanced.click()
  await details.getByLabel("Tags", { exact: true }).fill("")
  await details.getByLabel("Tags", { exact: true }).pressSequentially("gate,courier,")
  await expect(details.getByLabel("Tags", { exact: true })).toHaveValue("gate, courier, ")
  await page.keyboard.press("Escape")
  await expect(page.getByRole("status")).toHaveText("Unsaved changes")
  await page.getByRole("button", { name: "Save scene", exact: true }).click()
  await expect(page.getByRole("status")).toContainText("Scene saved.")
  expect(state.saves[0]).toMatchObject({ description: "The courier arrives before curfew.", metadata: { pov: "Nora", tags: ["gate", "courier"] } })
})

test("scene extra formatting stays visible outside the mobile toolbar and closes with Escape", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(route)
  await expect(page.getByRole("textbox", { name: "Scene text", exact: true })).toBeVisible()
  const more = page.getByLabel("More formatting controls", { exact: true })
  await more.click()
  const controls = page.getByRole("region", { name: "Additional formatting controls" })
  await expect(controls).toBeVisible()
  const box = await controls.boundingBox()
  expect(box!.x).toBeGreaterThanOrEqual(0)
  expect(box!.x + box!.width).toBeLessThanOrEqual(390)
  await controls.getByLabel("Line height", { exact: true }).selectOption("2")
  await page.keyboard.press("Escape")
  await expect(controls).toHaveCount(0)
  await expect(more).toBeFocused()
})

test("a new scene saves its title and text and remains selected", async ({ page }) => {
  await page.goto(route)
  await expect(page.getByLabel("Scene title")).toHaveValue("Gate Crossing")
  const state = await installSceneWrites(page)
  await page.getByRole("button", { name: "New scene", exact: true }).click()
  await page.getByLabel("Scene title").fill("The silent observatory")
  await page.getByRole("textbox", { name: "Scene text", exact: true }).fill("Nora finds an unopened letter beside the telescope.")
  await page.getByRole("button", { name: "Save scene", exact: true }).click()
  await expect(page.getByRole("status")).toContainText("Scene saved.")
  await expect(page.getByLabel("Scene title")).toHaveValue("The silent observatory")
  await expect(page.getByRole("button", { name: "Delete", exact: true })).toBeEnabled()
  expect(state.saves[0]).toMatchObject({ title: "The silent observatory", body: "Nora finds an unopened letter beside the telescope." })
})
