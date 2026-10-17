import { expect, test } from "@playwright/test"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"

test.beforeEach(async ({ page }) => {
  await installMockApi(page)
  await page.addInitScript(() => { localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 })); document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax" })
})

test("settings remains readable across four viewport widths", async ({ page }, info) => {
  await page.goto("/settings")
  await expect(page.getByLabel("Public username", { exact: true })).toHaveValue("author")
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    if (width < 1024) await expect.poll(() => page.locator("aside").first().evaluate((element) => element.getBoundingClientRect().right)).toBeLessThanOrEqual(0)
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
    await page.screenshot({ path: info.outputPath(`settings-${width}.png`), animations: "disabled" })
  }
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.getByRole("button", { name: "Help", exact: true }).focus(); await page.keyboard.press("Enter")
  await expect(page.getByRole("dialog")).toBeVisible(); await page.keyboard.press("Escape")
  await expect(page.getByRole("button", { name: "Help", exact: true })).toBeFocused()
  await page.getByLabel("Jump to settings section").selectOption("goals")
  await expect.poll(() => page.locator("#goals").evaluate((el) => el.getBoundingClientRect().top)).toBeLessThan(180)
  await page.screenshot({ path: info.outputPath("settings-goals-mobile.png"), animations: "disabled" })
  await page.getByRole("button", { name: "Toggle theme", exact: true }).click()
  await expect(page.locator(".settings-surface")).toHaveClass(/settings-surface--light/)
  await page.screenshot({ path: info.outputPath("settings-goals-light.png"), animations: "disabled" })
  expect(await criticalAccessibilityViolations(page)).toEqual([])
})

test("settings search has a clear recovery and preserves hidden unsaved fields", async ({ page }) => {
  await page.goto("/settings")
  await page.getByLabel("Public username", { exact: true }).fill("new_handle")
  await page.getByRole("searchbox", { name: "Search settings" }).fill("not-a-setting")
  await expect(page.getByRole("heading", { name: "No matching settings" })).toBeVisible()
  await expect(page.getByText(/Unsaved changes: public username/)).toBeVisible()
  await page.getByRole("button", { name: "Clear search", exact: true }).click()
  await expect(page.getByLabel("Public username", { exact: true })).toHaveValue("new_handle")
  page.once("dialog", (dialog) => dialog.dismiss())
  await page.getByRole("link", { name: "Open Home", exact: true }).click()
  await expect(page).toHaveURL(/\/settings$/)
  await page.getByRole("button", { name: "Discard username change" }).click()
  await expect(page.getByLabel("Public username", { exact: true })).toHaveValue("author")
  await page.getByRole("searchbox", { name: "Search settings" }).fill("marketing")
  await expect(page.locator(".settings-panel")).toHaveCount(1)
  await expect(page.getByRole("heading", { name: "LoreVia emails" })).toBeVisible()
})

test("settings resource failures retry independently without inventing billing or email choices", async ({ page }) => {
  let fail = true
  for (const endpoint of ["billing/subscription", "email/preferences"]) await page.route(`**/api/v1/${endpoint}`, (route) => fail ? route.fulfill({ status: 503, json: {} }) : route.fallback())
  await page.goto("/settings")
  await expect(page.getByRole("button", { name: "Retry billing details" })).toBeVisible()
  await expect(page.getByText(/renewal and payment status are unverified/)).toBeVisible()
  await expect(page.getByRole("button", { name: /Product updates/ })).toHaveCount(0)
  fail = false
  await page.getByRole("button", { name: "Retry billing details" }).click()
  await expect(page.getByText(/Your subscription renews automatically/)).toBeVisible()
  await page.getByRole("button", { name: "Retry email preferences" }).click()
  await expect(page.getByRole("button", { name: /Product updates/ })).toHaveAttribute("aria-pressed", "true")
})

test("daily goals keep invalid and failed input and save the exact valid value", async ({ page }) => {
  let fail = true
  await page.route("**/api/v1/auth/me/daily-word-goal", (route) => {
    expect(route.request().postDataJSON()).toEqual({ daily_word_goal: 2500 })
    return fail ? route.fulfill({ status: 503, json: {} }) : route.fulfill({ json: { ...profile, daily_word_goal: 2500 } })
  })
  await page.goto("/settings")
  await expect(page.getByLabel("Words per day", { exact: true })).toHaveValue("1200")
  const profile = await page.evaluate(() => JSON.parse(sessionStorage.getItem("lorevia-auth-user") || "{}"))
  await page.getByRole("searchbox", { name: "Search settings" }).fill("daily")
  for (const value of ["", "-1", "1.5", "1000001"]) {
    await page.getByLabel("Words per day", { exact: true }).fill(value)
    await expect(page.getByRole("button", { name: "Save daily goal", exact: true })).toBeDisabled()
    await expect(page.getByLabel("Words per day", { exact: true })).toHaveValue(value)
  }
  await page.getByLabel("Words per day", { exact: true }).fill("2500")
  await page.getByRole("button", { name: "Save daily goal", exact: true }).click()
  await expect(page.getByText("We could not save the daily goal right now.")).toBeVisible()
  await expect(page.getByLabel("Words per day", { exact: true })).toHaveValue("2500")
  fail = false; await page.getByRole("button", { name: "Save daily goal", exact: true }).click()
  await expect(page.getByText("Daily goal updated.")).toBeVisible()
  await expect(page.getByRole("button", { name: "Save daily goal", exact: true })).toBeDisabled()
  await expect(page.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "0")
})

test("username validation, failure recovery, and pending saves preserve other drafts", async ({ page }) => {
  let fail = true
  let release: (() => void) | undefined
  const waiting = new Promise<void>((resolve) => { release = resolve })
  await page.route("**/api/v1/auth/me/username?*", async (route) => {
    if (fail) return route.fulfill({ status: 409, json: {} })
    await waiting; await route.fallback()
  })
  await page.goto("/settings")
  await page.getByLabel("Public username", { exact: true }).fill("bad name")
  await expect(page.getByRole("button", { name: "Change username", exact: true })).toBeDisabled()
  await page.getByLabel("Public username", { exact: true }).fill("storysmith")
  await page.getByRole("button", { name: "Change username", exact: true }).click()
  await expect(page.getByText(/We could not save that username/)).toBeVisible()
  await expect(page.getByLabel("Public username", { exact: true })).toHaveValue("storysmith")
  await page.getByLabel("Words per day", { exact: true }).fill("2200")
  fail = false; await page.getByRole("button", { name: "Change username", exact: true }).click()
  await expect(page.getByLabel("Public username", { exact: true })).toBeDisabled()
  await expect(page.getByRole("button", { name: "Save daily goal", exact: true })).toBeDisabled()
  release?.()
  await expect(page.getByText("Public username updated.")).toBeVisible()
  await expect(page.getByLabel("Words per day", { exact: true })).toHaveValue("2200")
})

test("reading and messaging saves expose failures and confirm only successful changes", async ({ page }) => {
  let fail = true
  await page.route("**/api/v1/auth/me/reading-mode?*", (route) => fail ? route.fulfill({ status: 503, json: {} }) : route.fulfill({ json: { ...profile, reading_mode: "speed" } }))
  await page.route("**/api/v1/auth/me/messaging-permission", (route) => fail ? route.fulfill({ status: 503, json: {} }) : route.fulfill({ json: { ...profile, reading_mode: "speed", messaging_permission: "friends_only" } }))
  await page.goto("/settings")
  await expect(page.getByLabel("Public username", { exact: true })).toHaveValue("author")
  const profile = await page.evaluate(() => JSON.parse(sessionStorage.getItem("lorevia-auth-user") || "{}"))
  await page.getByRole("button", { name: /^Speed/ }).click()
  await expect(page.getByText(/Reading mode could not be saved/)).toBeVisible()
  await expect(page.getByRole("button", { name: /^Analyst/ })).toHaveAttribute("aria-pressed", "true")
  fail = false; await page.getByRole("button", { name: /^Speed/ }).click()
  await expect(page.getByText("Reading mode updated.")).toBeVisible()
  await expect(page.getByRole("button", { name: /^Speed/ })).toHaveAttribute("aria-pressed", "true")
  fail = true; await page.getByRole("button", { name: /^Friends only/ }).click()
  await expect(page.getByText(/We could not save your messaging privacy/)).toBeVisible()
  await expect(page.getByRole("button", { name: /^Anyone can/ })).toHaveAttribute("aria-pressed", "true")
  fail = false; await page.getByRole("button", { name: /^Friends only/ }).click()
  await expect(page.getByText("Messaging privacy updated.")).toBeVisible()
  await expect(page.getByRole("button", { name: /^Friends only/ })).toHaveAttribute("aria-pressed", "true")
})

test("email and data action failures retain confirmed state and support retry", async ({ page }) => {
  let fail = true
  await page.route("**/api/v1/email/preferences", (route) => route.request().method() === "POST" && fail ? route.fulfill({ status: 503, json: {} }) : route.fallback())
  await page.route("**/api/v1/auth/me/data-export", (route) => fail ? route.fulfill({ status: 503, json: {} }) : route.fallback())
  await page.route("**/api/v1/auth/me", (route) => route.request().method() === "DELETE" ? route.fulfill({ status: 403, json: {} }) : route.fallback())
  await page.goto("/settings")
  await page.getByRole("button", { name: /^Product updates/ }).click()
  await expect(page.getByText("We could not save your email preferences right now.")).toBeVisible()
  await expect(page.getByRole("button", { name: /^Product updates/ })).toHaveAttribute("aria-pressed", "true")
  await page.getByRole("button", { name: "Export my data", exact: true }).click()
  await expect(page.getByText(/We could not prepare your export/)).toBeVisible()
  fail = false
  await page.getByRole("button", { name: /^Product updates/ }).click()
  await expect(page.getByRole("button", { name: /^Product updates/ })).toHaveAttribute("aria-pressed", "false")
  const download = page.waitForEvent("download")
  await page.getByRole("button", { name: "Export my data", exact: true }).click()
  expect((await download).suggestedFilename()).toBe("lorevia-data-export.zip")
  await expect(page.getByRole("button", { name: "Delete account", exact: true })).toBeDisabled()
  await page.getByLabel("Type DELETE MY ACCOUNT").fill("DELETE MY ACCOUNT")
  await page.getByLabel("Current password").fill("local-dummy-password")
  await page.getByRole("button", { name: "Delete account", exact: true }).click()
  await expect(page.getByText(/We could not delete your account/)).toBeVisible()
  await expect(page.getByLabel("Type DELETE MY ACCOUNT")).toHaveValue("DELETE MY ACCOUNT")
  await expect(page).toHaveURL(/\/settings$/)
})

test("analytics controls update the remembered choice and notify the runtime", async ({ page }) => {
  await page.goto("/settings")
  await page.getByRole("searchbox", { name: "Search settings" }).fill("analytics")
  await page.getByRole("button", { name: "Allow analytics", exact: true }).click()
  await expect(page.getByText("Current choice: Allowed.", { exact: true })).toBeVisible()
  await page.evaluate(() => {
    window.addEventListener("lorevia:analytics-consent-changed", () => { document.documentElement.dataset.consentNotified = "true" })
  })
  await page.getByRole("button", { name: "Withdraw analytics", exact: true }).click()
  await expect(page.getByText("Current choice: Withdrawn.", { exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.dataset.consentNotified)).toBe("true")
  expect(await page.evaluate(() => document.cookie.includes("lorevia_analytics_consent=false"))).toBe(true)
  expect(await page.evaluate(() => window.__loreviaPosthog === undefined)).toBe(true)
})

test("workspace controls preserve local changes on sync failure and restore hidden tools", async ({ page }, info) => {
  let fail = true
  const preference = { schema_version: 1, revision: 1, complexity_mode: "standard", dashboard_visibility: {} as Record<string, string>, dashboard_order: [], public_tool_visibility: {}, density: "comfortable", reader_toolbar_density: "standard", locked_tool_presentation: "compact", default_workspace_shell: "author", mobile_actions: [], guidance_dismissals: { library: "old" } as Record<string, string>, recommendation_snoozes: {}, updated_at: null }
  await page.route("**/api/v1/auth/me/ui-preferences", async (route) => {
    if (route.request().method() === "PATCH") {
      if (fail) return route.fulfill({ status: 503, json: {} })
      for (const operation of route.request().postDataJSON().operations) {
        if (operation.path.startsWith("/dashboard_visibility/")) preference.dashboard_visibility[operation.path.split("/")[2]] = operation.value
        if (operation.path === "/complexity_mode") preference.complexity_mode = operation.value
        if (operation.path === "/guidance_dismissals") preference.guidance_dismissals = operation.value
      }
      preference.revision++
    }
    await route.fulfill({ json: preference })
  })
  await page.goto("/settings")
  await page.getByRole("searchbox", { name: "Search settings" }).fill("workspace visibility")
  const notes = page.locator(".settings-tool-row").filter({ has: page.getByText("Notes", { exact: true }) })
  await notes.getByRole("button", { name: "Hide from workspace", exact: true }).click()
  await expect(notes.getByText("Hidden from workspace navigation")).toBeVisible()
  await expect(page.getByText("Saved on this device; sync pending")).toBeVisible()
  fail = false; await page.locator("#workspace").getByRole("button", { name: "Retry", exact: true }).click()
  await expect(page.getByText("Saved on this device; sync pending")).toHaveCount(0)
  await page.getByRole("button", { name: "Show all hidden tools" }).click()
  await expect(notes.getByText("Visible in workspace navigation")).toBeVisible()
  await page.getByRole("button", { name: /^Power Expose/ }).click()
  await expect(page.getByRole("button", { name: /^Power Expose/ })).toHaveAttribute("aria-pressed", "true")
  await page.getByRole("button", { name: "Restart onboarding" }).click()
  await expect(page.getByText("Onboarding tips and guidance will appear again where available.")).toBeVisible()
  await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }))
  await page.screenshot({ path: info.outputPath("settings-workspace-desktop.png"), fullPage: true, animations: "disabled" })
  await page.setViewportSize({ width: 390, height: 1000 })
  await page.screenshot({ path: info.outputPath("settings-workspace-mobile.png"), fullPage: true, animations: "disabled" })
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.getByRole("searchbox", { name: "Search settings" }).fill("delete")
  await page.screenshot({ path: info.outputPath("settings-data-mobile.png"), fullPage: true, animations: "disabled" })
})
