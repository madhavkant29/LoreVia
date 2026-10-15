import { expect, test } from "@playwright/test"

import { criticalAccessibilityViolations } from "./support/accessibility"
import { installMockApi } from "./support/mockApi"

test("beta read assignments stay readable at four widths in both themes", async ({ page }, testInfo) => {
  await installMockApi(page)
  await page.goto("/")

  for (const theme of ["light", "dark"] as const) {
    await page.evaluate((nextTheme) => {
      window.localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: nextTheme }, version: 0 }))
    }, theme)

    for (const viewport of [
      { name: "desktop", width: 1440, height: 900 },
      { name: "laptop", width: 1280, height: 800 },
      { name: "tablet", width: 768, height: 1024 },
      { name: "mobile", width: 390, height: 844 },
    ] as const) {
      await page.setViewportSize(viewport)
      await page.goto("/beta-reads")

      await expect(page.getByRole("heading", { name: "Reading assignments" })).toBeVisible()
      await expect(page.getByRole("tab", { name: "In progress" })).toHaveAttribute("aria-selected", "true")
      await expect(page.getByText("Chapter 12 feedback")).toBeVisible()
      expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
      expect(await criticalAccessibilityViolations(page), `${theme} accessibility violations at ${viewport.name}`).toEqual([])

      if (viewport.name === "desktop" || viewport.name === "mobile") {
        await page.screenshot({ path: testInfo.outputPath(`beta-reads-${theme}-${viewport.name}.png`), fullPage: true })
      }
    }
  }
})
