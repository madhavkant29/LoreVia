import { expect, test } from "@playwright/test"
import { installMockApi } from "./support/mockApi"

test("temporary session failure keeps the user signed in and recovers on retry", async ({ page }) => {
  await installMockApi(page)
  await page.addInitScript(() => {
    sessionStorage.setItem("lorevia-auth-user", JSON.stringify({
      id: "user-1", email: "author@example.com", username: "Author", tier: "architect",
    }))
  })
  let unavailable = true
  await page.route("**/api/v1/auth/session", async (route) => {
    if (unavailable) {
      await route.fulfill({ status: 503, json: { detail: "Temporarily unavailable" } })
      return
    }
    await route.fallback()
  })

  await page.goto("/library")
  const retry = page.getByRole("button", { name: "Retry session check" })
  await expect(retry).toBeVisible()
  expect(new URL(page.url()).pathname).toBe("/library")
  expect(await page.evaluate(() => sessionStorage.getItem("lorevia-auth-user"))).not.toBeNull()

  unavailable = false
  await retry.click()
  await expect(retry).not.toBeVisible()
  expect(new URL(page.url()).pathname).toBe("/library")
})
