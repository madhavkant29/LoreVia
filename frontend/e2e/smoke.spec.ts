import { expect, test } from "@playwright/test"

import { installMockApi } from "./support/mockApi"

test("marketing home page renders the core value proposition", async ({ page }) => {
  await page.goto("/")

  await expect(page.getByRole("heading", { name: /never lose track of your story again/i })).toBeVisible()
  await expect(page.getByRole("link", { name: /^sign in$/i })).toBeVisible()
  await expect(page.getByText("Start with one chapter. See what LoreVia remembers.")).toBeVisible()
})

test("login surfaces an invalid-credentials error", async ({ page }) => {
  await installMockApi(page, { session: "guest", login: "unauthorized" })
  await page.goto("/login")

  await page.getByPlaceholder("Email").fill("reader@example.com")
  await page.getByPlaceholder("Password").fill("wrong-password")
  await page.getByRole("button", { name: /^sign in$/i }).click()

  await expect(page.getByText("Invalid email or password.")).toBeVisible()
})

test("library renders a mocked project and opens the upload modal", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/library")

  await expect(page.getByRole("heading", { name: "Library" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Sky of Ash" }).first()).toBeVisible()
  await page.getByRole("button", { name: /^new project$/i }).click()
  await expect(page.getByRole("heading", { name: /upload book/i })).toBeVisible()
})

test("book overview opens the manuscript editor", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/book-1")

  await expect(page.getByText("Open Manuscript Editor")).toBeVisible()
  await page.getByRole("button", { name: /open manuscript editor/i }).click()

  await expect(page).toHaveURL(/\/(?:[^/]+--)?book-1\/manuscript$/)
  await expect(page.getByText("Story manuscript")).toBeVisible()
  await expect(page.getByText("Manuscript progress")).toBeVisible()
})

test("manuscript workspace loads core drafting surfaces", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/book-1/manuscript")

  await expect(page.getByRole("heading", { name: "Sky of Ash" }).first()).toBeVisible()
  await expect(page.getByPlaceholder("Search chapters")).toBeVisible()
  await expect(page.getByRole("link", { name: /open workspace/i })).toBeVisible()
  await expect(page.getByText(/^Gate Crossing$/)).toBeVisible()
})
