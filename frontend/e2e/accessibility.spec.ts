import { expect, test } from "@playwright/test"

import { criticalAccessibilityViolations } from "./support/accessibility"
import { installMockApi } from "./support/mockApi"

const BOOK_ROUTE = "/sky-of-ash--book-1"

test("critical public and authenticated routes have no serious accessibility violations", async ({ page }) => {
  test.setTimeout(120_000)

  await installMockApi(page, { session: "guest" })
  await page.goto("/login")
  await expect(page.getByRole("heading", { name: /^sign in$/i })).toBeVisible()
  expect(await criticalAccessibilityViolations(page)).toEqual([])

  await installMockApi(page)
  for (const path of ["/library", "/upgrade", BOOK_ROUTE, `${BOOK_ROUTE}/manuscript`]) {
    await page.goto(path)
    await expect(page.locator("h1, h2").filter({ visible: true }).first()).toBeVisible()
    expect(await criticalAccessibilityViolations(page), `accessibility violations on ${path}`).toEqual([])
  }
})

test("critical dialogs are labelled, focus-contained, and keyboard dismissible", async ({ page }) => {
  test.setTimeout(120_000)
  await installMockApi(page)

  await page.goto("/library")
  await page.getByRole("button", { name: /^new project$/i }).first().click()
  const uploadDialog = page.getByRole("dialog", { name: "Upload manuscript" })
  await expect(uploadDialog).toBeVisible()
  await expect(uploadDialog.locator(":focus")).toHaveCount(1)
  expect(await criticalAccessibilityViolations(page, '[role="dialog"]')).toEqual([])
  await page.keyboard.press("Escape")
  await expect(uploadDialog).toHaveCount(0)

  await page.goto("/upgrade")
  const authorCard = page.locator("article").filter({
    has: page.getByRole("heading", { name: "Author", exact: true }),
  })
  await authorCard.getByRole("button", { name: "Upgrade to Author" }).click()
  const billingDialog = page.getByRole("dialog")
  await expect(billingDialog).toBeVisible()
  await expect(billingDialog.locator(":focus")).toHaveCount(1)
  expect(await criticalAccessibilityViolations(page, '[role="dialog"]')).toEqual([])
  await page.keyboard.press("Escape")
  await expect(billingDialog).toHaveCount(0)

  await page.goto(`${BOOK_ROUTE}/manuscript`)
  await page.getByRole("button", { name: "Reprocess manuscript" }).click()
  const reprocessDialog = page.getByRole("dialog", { name: "Reprocess manuscript?" })
  await expect(reprocessDialog).toBeVisible()
  await expect(reprocessDialog.locator(":focus")).toHaveCount(1)
  expect(await criticalAccessibilityViolations(page, '[role="dialog"]')).toEqual([])
  await page.keyboard.press("Escape")
  await expect(reprocessDialog).toHaveCount(0)
})
