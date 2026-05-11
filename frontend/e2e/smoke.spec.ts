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

test("points page shows the daily rewarded-ad counter", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/points")

  await expect(page.getByRole("heading", { name: "Points wallet" })).toBeVisible()
  await expect(page.getByText("2 / 3")).toBeVisible()
  await expect(page.getByRole("heading", { name: "2 ads left today" })).toBeVisible()
  await expect(page.getByText("Ad 1")).toBeVisible()
  await expect(page.getByText("Watched")).toBeVisible()
  await expect(page.getByText("Rewarded ad")).toBeVisible()
})

test("book overview opens the manuscript editor", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/book-1")

  await expect(page.getByText("Open Manuscript Editor")).toBeVisible()
  await expect(page.getByText("Know what your edit breaks before your readers do.")).toBeVisible()
  await expect(page.getByRole("button", { name: /create revision checklist/i })).toBeVisible()
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

test("collaboration workspace creates a story-scoped share", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/book-1/collaboration")

  await expect(page.getByRole("heading", { name: "Sky of Ash sharing" })).toBeVisible()
  await expect(page.getByText("Beta Reader")).toBeVisible()

  await page.getByPlaceholder("reader@example.com").fill("editor@example.com")
  await page.getByPlaceholder("Display name").fill("Dev Editor")
  await page.getByRole("combobox").selectOption("developmental_editor")
  await page.getByRole("button", { name: /save share/i }).click()

  await expect(page.getByText("Share saved.")).toBeVisible()
  await expect(page.getByText("Dev Editor")).toBeVisible()
})

test("reader published layout applies book typography without mobile overflow", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/book-1/chapter/2")

  await expect(page.getByRole("button", { name: "Published" })).toHaveAttribute("aria-pressed", "true")
  await expect(page.locator(".book-layout__body")).toBeVisible()

  const firstParagraph = page.locator(".book-block--paragraph").nth(0)
  const normalParagraph = page.locator(".book-block--paragraph").nth(1)
  const paragraphAfterSceneBreak = page.locator(".scene-break + .book-block--paragraph")
  const broadcastBlock = page.locator(".book-block--broadcast")
  const quoteBlock = page.locator(".book-block--quote")

  await expect(firstParagraph).toBeVisible()
  await expect(normalParagraph).toBeVisible()
  await expect(paragraphAfterSceneBreak).toBeVisible()
  await expect(broadcastBlock).toBeVisible()
  await expect(quoteBlock).toBeVisible()

  const desktopStyles = await normalParagraph.evaluate((element) => {
    const styles = window.getComputedStyle(element)
    return {
      fontFamily: styles.fontFamily,
      textAlign: styles.textAlign,
      textIndent: styles.textIndent,
      marginTop: styles.marginTop,
      marginBottom: styles.marginBottom,
    }
  })
  expect(desktopStyles.fontFamily).toContain("Georgia")
  expect(desktopStyles.textAlign).toBe("justify")
  expect(Number.parseFloat(desktopStyles.textIndent)).toBeGreaterThan(0)
  expect(desktopStyles.marginTop).toBe("0px")
  expect(desktopStyles.marginBottom).toBe("0px")

  await expect(firstParagraph).toHaveCSS("text-indent", "0px")
  await expect(paragraphAfterSceneBreak).toHaveCSS("text-indent", "0px")
  await expect(broadcastBlock).toHaveCSS("text-indent", "0px")
  await expect(quoteBlock).toHaveCSS("text-indent", "0px")

  const quoteInset = await quoteBlock.evaluate((element) => {
    const styles = window.getComputedStyle(element)
    return {
      marginLeft: Number.parseFloat(styles.marginLeft),
      paddingLeft: Number.parseFloat(styles.paddingLeft),
    }
  })
  expect(quoteInset.marginLeft).toBeGreaterThan(0)
  expect(quoteInset.paddingLeft).toBeGreaterThan(0)

  await page.setViewportSize({ width: 390, height: 800 })
  await expect(normalParagraph).toHaveCSS("text-align", "left")
  const hasHorizontalOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
  expect(hasHorizontalOverflow).toBe(false)
})
