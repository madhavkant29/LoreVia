import { expect, test } from "@playwright/test"

import { criticalAccessibilityViolations } from "./support/accessibility"

test("homepage navigation and reading layout work across screen sizes", async ({ page }, testInfo) => {
  for (const viewport of [
    { name: "desktop", width: 1440, height: 900 },
    { name: "laptop", width: 1280, height: 800 },
    { name: "tablet", width: 768, height: 1024 },
    { name: "mobile", width: 390, height: 844 },
  ] as const) {
    await page.setViewportSize(viewport)
    await page.goto("/")

    await expect(page.getByRole("heading", { level: 1, name: "Find plot holes before your readers do." })).toBeVisible()
    const demoPlayer = page.getByTitle("LoreVia product demonstration")
    await expect(demoPlayer).toBeVisible()
    await expect(demoPlayer).toHaveAttribute("src", "https://www.youtube-nocookie.com/embed/LVwVqo5X4LA")
    await expect(page.getByRole("link", { name: "Watch on YouTube" })).toHaveAttribute("href", "https://youtu.be/LVwVqo5X4LA")
    expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
    expect(await criticalAccessibilityViolations(page), `accessibility violations at ${viewport.name}`).toEqual([])

    if (viewport.width < 1024) {
      const menuButton = page.getByRole("button", { name: "Open navigation menu" })
      await expect(menuButton).toBeVisible()
      await menuButton.focus()
      await page.keyboard.press("Enter")
      const mobileNavigation = page.getByRole("navigation", { name: "Mobile primary navigation" })
      await expect(mobileNavigation).toBeVisible()
      await expect(mobileNavigation.getByRole("link", { name: "Pricing" })).toHaveAttribute("href", "/#pricing")
      await expect(mobileNavigation.getByRole("link", { name: "Resources" })).toHaveAttribute("href", "/blog")
      await expect(page.getByRole("button", { name: "Close navigation menu" })).toHaveAttribute("aria-expanded", "true")

      if (viewport.name === "mobile") {
        await page.screenshot({ path: testInfo.outputPath("homepage-mobile-menu.png") })
        await page.keyboard.press("Escape")
        await expect(page.getByRole("button", { name: "Open navigation menu" })).toBeFocused()
        await expect(mobileNavigation).toBeHidden()
        await page.getByRole("button", { name: "Open navigation menu" }).click()
        await mobileNavigation.getByRole("link", { name: "How it works" }).click()
        await expect(page).toHaveURL(/\/#workflow$/)
        await expect(mobileNavigation).toBeHidden()
      }
    } else {
      await expect(page.getByRole("navigation", { name: "Primary navigation" })).toBeVisible()
      await expect(page.getByRole("button", { name: /navigation menu/i })).toHaveCount(0)
    }

    if (viewport.name === "desktop" || viewport.name === "mobile") {
      await page.screenshot({ path: testInfo.outputPath(`homepage-${viewport.name}-viewport.png`) })
    }
  }
})

test("homepage FAQs expand as readable native disclosures", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/#faq")

  const question = page.getByText("Is my manuscript private?", { exact: true })
  await question.click()
  await expect(page.getByText("Yes. LoreVia is built for private draft work, revision, and author-controlled sharing rather than public posting.")).toBeVisible()
})
