import { expect, test, type Page } from "@playwright/test"

import { installMockApi } from "./support/mockApi"

const BOOK_ROUTE = "/sky-of-ash--book-1"
const ADMIN_TEST_SESSION_SECRET = process.env.ADMIN_E2E_TEST_SECRET ?? "codex-e2e-admin-secret"
const E2E_APP_ORIGIN = process.env.E2E_APP_ORIGIN ?? `http://localhost:${process.env.E2E_PORT ?? "3001"}`

function watchBrowserSignals(page: Page) {
  const consoleMessages: string[] = []
  const pageErrors: string[] = []

  page.on("console", (message) => {
    consoleMessages.push(`[${message.type()}] ${message.text()}`)
  })
  page.on("pageerror", (error) => {
    pageErrors.push(String(error))
  })

  return { consoleMessages, pageErrors }
}

async function hideNonProductCaptureOverlays(page: Page) {
  await page.locator("nextjs-portal").evaluateAll((elements) => {
    for (const element of elements) {
      if (element instanceof HTMLElement) element.style.display = "none"
    }
  })
  await page.getByRole("button", { name: "Help", exact: true }).evaluateAll((elements) => {
    for (const element of elements) {
      if (element instanceof HTMLElement) element.style.display = "none"
    }
  })
}

test("marketing home page renders the core value proposition", async ({ page }) => {
  await page.goto("/")

  await expect(page.getByRole("heading", { name: /find plot holes before your readers do/i })).toBeVisible()
  await expect(page.getByRole("link", { name: /^sign in$/i })).toBeVisible()
  await expect(page.getByRole("link", { name: /^analyze my manuscript$/i }).first()).toBeVisible()
  await expect(page.getByRole("link", { name: /^see a sample finding$/i })).toBeVisible()
  await expect(page.getByRole("link", { name: /^see a sample finding$/i })).toHaveAttribute("href", "/demo/workspace")
  await expect(page.getByText("Includes a 10-day Author trial. No payment required.").first()).toBeVisible()
})

test("homepage product walkthrough renders every workspace step", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto("/")

  await expect(page.locator("[data-showcase-step]")).toHaveCount(3)
  await expect(page.getByRole("heading", { name: "From manuscript evidence to a revision decision." })).toBeVisible()
  await expect(page.locator("#features img")).toHaveCount(4)
  await expect(page.locator("#features figure button")).toHaveCount(0)
  await page.screenshot({ path: testInfo.outputPath("homepage-desktop.png"), fullPage: true })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.reload()
  await expect(page.locator("[data-showcase-step]")).toHaveCount(3)
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: testInfo.outputPath("homepage-mobile.png"), fullPage: true })
})

test("pricing and upgrade share current monthly and annual prices", async ({ page }) => {
  await installMockApi(page, { userTier: "free" })
  const checkoutPlans: string[] = []
  page.on("request", (request) => {
    if (request.url().endsWith("/api/v1/billing/checkout") && request.method() === "POST") {
      checkoutPlans.push((request.postDataJSON() as { plan: string }).plan)
    }
  })

  await page.goto("/pricing")
  const publicAuthorCard = page.locator("article").filter({
    has: page.getByRole("heading", { name: "Author", exact: true }),
  })
  const publicArchitectCard = page.locator("article").filter({
    has: page.getByRole("heading", { name: "Architect", exact: true }),
  })
  await expect(publicAuthorCard).toContainText("$19")
  await expect(publicAuthorCard).toContainText("Paid checkout charges $19 now")
  await expect(publicArchitectCard).toContainText("$39")
  await expect(publicArchitectCard).toContainText("Paid checkout charges $39 now")

  await page.getByRole("button", { name: "Yearly" }).click()
  await expect(publicAuthorCard).toContainText("$190")
  await expect(publicAuthorCard).toContainText("Save $38 with yearly billing")
  await expect(publicArchitectCard).toContainText("$390")
  await expect(publicArchitectCard).toContainText("Save $78 with yearly billing")

  await page.goto("/upgrade")
  await expect(page.getByRole("link", { name: "Return to LoreVia workspace" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Back to workspace" })).toBeVisible()
  await expect(page.locator("aside")).toHaveCount(0)
  await expect(page.getByRole("button", { name: "Help", exact: true })).toHaveCount(0)
  await expect(page.getByRole("heading", { name: "Choose the plan that matches your work" })).toBeVisible()
  const upgradeAuthorCard = page.locator("article").filter({
    has: page.getByRole("heading", { name: "Author", exact: true }),
  })
  const upgradeArchitectCard = page.locator("article").filter({
    has: page.getByRole("heading", { name: "Architect", exact: true }),
  })
  await expect(upgradeAuthorCard).toContainText("$19")
  await expect(upgradeArchitectCard).toContainText("$39")
  await upgradeAuthorCard.getByRole("button", { name: "Upgrade to Author" }).click()
  await page.getByRole("button", { name: "Pay $19.00 USD now" }).click()
  await page.getByRole("button", { name: "Cancel" }).click()
  await upgradeArchitectCard.getByRole("button", { name: "Upgrade to Architect" }).click()
  await page.getByRole("button", { name: "Pay $39.00 USD now" }).click()
  await page.getByRole("button", { name: "Cancel" }).click()
  await page.getByRole("button", { name: "Yearly" }).click()
  await expect(upgradeAuthorCard).toContainText("$190")
  await expect(upgradeArchitectCard).toContainText("$390")
  await upgradeAuthorCard.getByRole("button", { name: "Upgrade to Author" }).click()
  await page.getByRole("button", { name: "Pay $190.00 USD now" }).click()
  await page.getByRole("button", { name: "Cancel" }).click()
  await upgradeArchitectCard.getByRole("button", { name: "Upgrade to Architect" }).click()
  await page.getByRole("button", { name: "Pay $390.00 USD now" }).click()
  await page.getByRole("button", { name: "Cancel" }).click()
  await expect.poll(() => checkoutPlans).toEqual([
    "author_monthly",
    "architect_monthly",
    "author_annual",
    "architect_annual",
  ])
})

test("public pricing uses marketing navigation and one plan marker", async ({ page }, testInfo) => {
  await installMockApi(page, { session: "guest" })
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto("/pricing")

  await expect(page.getByRole("link", { name: "LoreVia home" })).toBeVisible()
  await expect(page.getByRole("link", { name: /^sign in$/i })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Choose the plan that matches your work" })).toBeVisible()
  await expect(page.locator("article")).toHaveCount(3)
  await expect(page.getByText("Recommended", { exact: true })).toHaveCount(1)
  await expect(page.getByText("Core plan", { exact: true })).toHaveCount(0)
  await expect(page.getByText("Paid plan", { exact: true })).toHaveCount(0)
  await page.screenshot({ path: testInfo.outputPath("pricing-desktop.png"), fullPage: true })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.reload()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: testInfo.outputPath("pricing-mobile.png"), fullPage: true })
})

test("comparison pages use an editorial index and one evidence matrix", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto("/compare")

  await expect(page.getByRole("heading", { name: /pick the writing workspace/i })).toBeVisible()
  const comparisonIndex = page.getByTestId("comparison-index-list")
  await expect(comparisonIndex.getByRole("link")).toHaveCount(4)
  await expect(comparisonIndex.getByText("Comparison page")).toHaveCount(0)
  await page.screenshot({ path: testInfo.outputPath("compare-index-desktop.png"), fullPage: true })

  await Promise.all([
    page.waitForURL(/\/compare\/scrivener$/, { timeout: 60_000 }),
    comparisonIndex.getByRole("link", { name: /LoreVia vs Scrivener/i }).click(),
  ])
  await expect(page.getByRole("heading", { name: "LoreVia vs Scrivener" })).toBeVisible()
  await expect(page.getByTestId("comparison-verdict")).toBeVisible()
  await expect(page.getByTestId("comparison-table").getByRole("table")).toBeVisible()
  await expect(page.getByTestId("comparison-differentiators").locator("article")).toHaveCount(3)
  await page.screenshot({ path: testInfo.outputPath("compare-detail-desktop.png"), fullPage: true })

  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByRole("heading", { name: "LoreVia vs Scrivener" })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: testInfo.outputPath("compare-detail-mobile.png"), fullPage: true })
})

test("demo catalog and case study keep source evidence ahead of promotion", async ({ page }, testInfo) => {
  await page.context().addCookies([{ name: "lorevia_analytics_consent", value: "false", domain: "localhost", path: "/" }])
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto("/demo")

  await expect(page.getByRole("heading", { name: /see how manuscript evidence becomes an editorial decision/i })).toBeVisible()
  const demoIndex = page.getByTestId("demo-index-list")
  await expect(demoIndex.locator("article")).toHaveCount(3)
  await expect(page.getByText(/SEO angle/i)).toHaveCount(0)
  await expect(page.getByText(/Why these pages matter/i)).toHaveCount(0)
  await page.screenshot({ path: testInfo.outputPath("demo-index-desktop.png"), fullPage: true })

  await Promise.all([
    page.waitForURL(/\/demo\/gregor-samsa-character-tracker$/, { timeout: 60_000 }),
    demoIndex.getByRole("link", { name: /tracking gregor samsa/i }).click(),
  ])
  await expect(page.getByRole("heading", { name: /tracking gregor samsa/i })).toBeVisible()
  await expect(page.getByTestId("demo-case-study").locator(":scope > section")).toHaveCount(3)
  await expect(page.getByText("Why this page exists")).toHaveCount(0)
  await page.screenshot({ path: testInfo.outputPath("demo-case-study-desktop.png"), fullPage: true })

  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: testInfo.outputPath("demo-case-study-mobile.png"), fullPage: true })
})

test("active trial checkout defaults to continuing free and requires charge confirmation", async ({ page }) => {
  await installMockApi(page, { userTier: "trial" })
  const checkoutBodies: Array<{
    plan: string
    confirmed_immediate_charge: boolean
    quote_token: string
  }> = []
  page.on("request", (request) => {
    if (request.url().endsWith("/api/v1/billing/checkout") && request.method() === "POST") {
      checkoutBodies.push(request.postDataJSON() as {
        plan: string
        confirmed_immediate_charge: boolean
        quote_token: string
      })
    }
  })

  await page.goto("/upgrade")
  await expect(page.getByText("Your free trial is already active.").first()).toBeVisible()
  await expect(page.getByRole("heading", { name: "Author — temporary trial access" })).toBeVisible()
  await expect(page.getByText(/there is no subscription to cancel or refund/i)).toBeVisible()
  await expect(page.getByRole("button", { name: "Continue free trial" }).first()).toBeVisible()
  const authorCard = page.locator("article").filter({
    has: page.getByRole("heading", { name: "Author", exact: true }),
  })
  await authorCard.getByRole("button", { name: "View payment details" }).click()

  const dialog = page.getByRole("dialog")
  await expect(dialog.getByText("Active — already started")).toBeVisible()
  await expect(dialog.getByText("$19.00 USD", { exact: true }).first()).toBeVisible()
  const payButton = dialog.getByRole("button", { name: "Pay $19.00 USD now" })
  await expect(payButton).toBeDisabled()
  await dialog.getByRole("checkbox").check()
  await expect(payButton).toBeEnabled()
  await payButton.click()

  await expect.poll(() => checkoutBodies).toEqual([
    {
      plan: "author_monthly",
      confirmed_immediate_charge: true,
      quote_token: "signed-quote-author_monthly",
    },
  ])
  await expect(dialog.getByRole("alert")).toContainText("Mock checkout requested for author_monthly")
})

test("paid accounts can manage their current plan and refund options from pricing or settings", async ({ page }) => {
  await installMockApi(page, { userTier: "author" })
  const portalRequest = page.waitForRequest((request) =>
    request.url().endsWith("/api/v1/billing/portal") && request.method() === "POST",
  )

  await page.goto("/upgrade")
  await expect(page.getByText("Your current plan")).toBeVisible()
  await expect(page.getByRole("heading", { name: "Author", exact: true }).first()).toBeVisible()
  await expect(page.getByText(/Next renewal/).first()).toBeVisible()
  const currentPlanSection = page.locator('[aria-labelledby="current-plan-heading"]')
  await expect(currentPlanSection.getByRole("button", { name: "Manage subscription" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Refund policy" })).toHaveAttribute("href", "/refund")
  await expect(page.getByRole("link", { name: "Request a refund" })).toHaveAttribute("href", /mailto:support@getlorevia\.com/)

  await currentPlanSection.getByRole("button", { name: "Manage subscription" }).click()
  await portalRequest
  await expect(page).toHaveURL(/\?mock_billing_portal=1$/)

  await page.goto("/settings")
  await expect(page.getByRole("button", { name: "Manage subscription" })).toBeVisible()
  await expect(page.getByText(/Next renewal/).first()).toBeVisible()
  await expect(page.getByRole("link", { name: "Refund policy" })).toHaveAttribute("href", "/refund")
  await expect(page.getByRole("link", { name: "Request a refund" })).toHaveAttribute("href", /mailto:support@getlorevia\.com/)
})

test("mobile marketing header keeps sign in and registration visible", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/")

  await expect(page.getByRole("link", { name: /^sign in$/i })).toBeVisible()
  await expect(page.getByRole("link", { name: /^start free$/i }).first()).toBeVisible()
  const hasHorizontalOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  )
  expect(hasHorizontalOverflow).toBe(false)

  await page.getByRole("link", { name: /^sign in$/i }).click()
  await expect(page).toHaveURL(/\/login$/)
})

test("support assistant answers navigation questions with a direct workspace action", async ({ page }) => {
  await installMockApi(page)
  await page.goto(BOOK_ROUTE)

  await expect(page.getByTestId("author-tools-nav-bar")).toBeVisible()
  const dismissCookies = page.getByRole("button", { name: /decline cookies/i })
  if (await dismissCookies.isVisible().catch(() => false)) {
    await dismissCookies.click()
  }
  await expect(page.getByRole("button", { name: "Help", exact: true })).toBeVisible()
  await page.getByRole("button", { name: "Help", exact: true }).click()
  const dialog = page.getByRole("dialog", { name: "LoreVia Support" })
  await expect(dialog).toBeVisible()

  await dialog.getByLabel("What do you need help with?").fill("How do I access character voice area?")
  await dialog.getByRole("button", { name: "Ask support assistant" }).click()

  await expect(dialog.getByText("Open Voice Consistency from the Writing workspace")).toBeVisible()
  await expect(dialog.getByRole("link", { name: "Open Voice Consistency" })).toHaveAttribute("href", "/book-1/voice")
  await expect(dialog).toHaveClass(/rounded-sm/)
  await expect(dialog).toHaveClass(/border-0/)
})

test("book workspace uses one stable job-based bar without the hover rail", async ({ page }, testInfo) => {
  await installMockApi(page)
  await page.goto(BOOK_ROUTE)

  const bookBar = page.getByTestId("author-tools-nav-bar")
  await expect(bookBar).toHaveCount(1)
  await expect(bookBar.getByText("Draft", { exact: true }).filter({ visible: true })).toBeVisible()
  await expect(bookBar.getByText("Story Bible", { exact: true }).filter({ visible: true })).toBeVisible()
  await expect(bookBar.getByText("Review", { exact: true }).filter({ visible: true })).toBeVisible()
  await expect(bookBar.getByText("Share", { exact: true }).filter({ visible: true })).toBeVisible()
  await expect(page.getByTestId("author-tools-nav-rail")).toHaveCount(0)

  await page.goto(`${BOOK_ROUTE}/timeline`)
  await expect(page.getByTestId("author-tools-nav-bar")).toHaveCount(1)
  await expect(page.getByRole("heading", { name: "Arc timeline" })).toBeVisible()

  await page.setViewportSize({ width: 390, height: 844 })
  await page.reload()
  await expect(page.getByTestId("author-tools-nav-bar")).toBeVisible()
  await expect(page.getByTestId("author-tools-nav-bar").getByText("Story Bible", { exact: true }).filter({ visible: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: testInfo.outputPath("book-workspace-mobile.png"), fullPage: true })
})

test("timeline uses desktop lanes and a dense mobile event list", async ({ page }) => {
  await installMockApi(page)
  await page.addInitScript(() => {
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(`${BOOK_ROUTE}/timeline`)

  await expect(page.getByRole("heading", { name: "Arc timeline" })).toBeVisible()
  await expect(page.getByText("Timeline lanes")).toBeVisible()
  await expect(page.getByText("Gregor and Grete break trust").last()).toBeVisible()
  await hideNonProductCaptureOverlays(page)
  await page.screenshot({ path: test.info().outputPath("timeline-lanes-desktop.png"), fullPage: true })

  await page.getByLabel("Show").selectOption("relationships")
  await expect(page.getByText("Family survival")).toHaveCount(0)
  await expect(page.getByText("Gregor and Grete break trust").last()).toBeVisible()

  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByText("Timeline lanes")).toBeHidden()
  await expect(page.getByText("Relationship shift").first()).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: test.info().outputPath("timeline-list-mobile.png"), fullPage: true })
})

test("plot threads use focused work queues with details on demand", async ({ page }) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  await installMockApi(page)
  await page.addInitScript(() => {
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(`${BOOK_ROUTE}/plot-threads`)

  await expect(page.getByRole("heading", { name: "Plot threads" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "Open 2" })).toHaveAttribute("aria-selected", "true")
  await expect(page.getByText("Who opened the gate?", { exact: true })).toBeVisible()
  await expect(page.getByText("Thread details")).toHaveCount(0)
  await page.screenshot({ path: test.info().outputPath("plot-threads-open-desktop.png"), fullPage: true })

  await page.getByRole("tab", { name: "Needs attention 1" }).click()
  await page.getByRole("button", { name: /The vanished map clue/ }).click()
  await expect(page.getByRole("heading", { name: "Thread details" })).toBeVisible()
  await expect(page.getByText("Return the map in chapter 6 or remove its setup.")).toBeVisible()
  await expect(page.getByLabel("Private note")).toHaveValue("Restore near the archive scene.")
  await page.screenshot({ path: test.info().outputPath("plot-threads-attention-desktop.png"), fullPage: true })

  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByRole("heading", { name: "Thread details" })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: test.info().outputPath("plot-threads-attention-mobile.png"), fullPage: true })
  expect(pageErrors).toEqual([])
  expect(consoleMessages.filter((message) => message.startsWith("[error]"))).toEqual([])
})

test("setup and payoff uses a compact evidence ledger", async ({ page }) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  await installMockApi(page)
  await page.addInitScript(() => {
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(`${BOOK_ROUTE}/foreshadowing`)

  await expect(page.getByRole("heading", { name: "Setup and payoff" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "All setups 3" })).toHaveAttribute("aria-selected", "true")
  await expect(page.getByText("The gate key is warm before the alarm sounds.")).toBeVisible()
  await expect(page.getByText("No linked payoff yet")).toBeVisible()
  await page.screenshot({ path: test.info().outputPath("setup-payoff-ledger-desktop.png"), fullPage: true })

  await page.getByRole("tab", { name: "Unlinked 1" }).click()
  await expect(page.getByText("A silver bell rings beneath the river.")).toBeVisible()
  await expect(page.getByText("The gate key is warm before the alarm sounds.")).toHaveCount(0)

  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: test.info().outputPath("setup-payoff-unresolved-mobile.png"), fullPage: true })
  expect(pageErrors).toEqual([])
  expect(consoleMessages.filter((message) => message.startsWith("[error]"))).toEqual([])
})

test("world gaps prioritize evidence and defer source editing", async ({ page }) => {
  test.setTimeout(120_000)
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  await installMockApi(page)
  await page.addInitScript(() => {
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
  const documentBodyRequests: string[] = []
  page.on("request", (request) => {
    if (request.url().includes("/world-building/documents/world-doc-1")) documentBodyRequests.push(request.url())
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(`${BOOK_ROUTE}/world-gap`)

  await expect(page.getByRole("heading", { name: "World gaps" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "Review gaps" })).toHaveAttribute("aria-selected", "true")
  await expect(page.getByText("Northreach needs a clearer canon note")).toBeVisible()
  await expect(page.getByText("Northreach is a desert capital.")).toHaveCount(0)
  await page.getByRole("button", { name: /Northreach needs a clearer canon note.*Review evidence/ }).click()
  await expect(page.getByText("Northreach is a desert capital.")).toBeVisible()
  expect(documentBodyRequests).toHaveLength(0)
  await page.screenshot({ path: test.info().outputPath("world-gaps-evidence-desktop.png"), fullPage: true })

  await page.getByRole("tab", { name: "Canon sources" }).click()
  await expect(page.getByText("Core World Notes", { exact: true }).first()).toBeVisible()
  await expect.poll(() => documentBodyRequests.length).toBeGreaterThan(0)

  await page.getByRole("tab", { name: "Review gaps" }).click()
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByText("Manuscript evidence").first()).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: test.info().outputPath("world-gaps-evidence-mobile.png"), fullPage: true })
  expect(pageErrors).toEqual([])
  expect(consoleMessages.filter((message) => message.startsWith("[error]"))).toEqual([])
})

test("series wiki uses a reference list and selected detail", async ({ page }) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  await installMockApi(page, { seriesBooks: true })
  await page.addInitScript(() => {
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(`${BOOK_ROUTE}/cross-book-wiki`)

  await expect(page.getByRole("heading", { name: "Series wiki" })).toBeVisible()
  await expect(page.getByText("Nora Vale", { exact: true }).first()).toBeVisible()
  const desktopDetail = page.getByLabel("Selected series reference")
  await expect(desktopDetail.getByRole("heading", { name: "Nora Vale ↔ Nora Veyl" })).toBeVisible()
  await expect(desktopDetail.getByRole("link", { name: "Open connected book" })).toHaveAttribute("href", "/book-2")
  await page.screenshot({ path: test.info().outputPath("series-wiki-list-detail-desktop.png"), fullPage: true })

  await page.getByLabel("Reference type").selectOption("wiki")
  await expect(page.getByText("Glass Road", { exact: true }).first()).toBeVisible()
  await expect(page.getByText("Kael Arden", { exact: true })).toHaveCount(0)

  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByRole("heading", { name: "Glass Road ↔ The Glassway" })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: test.info().outputPath("series-wiki-reference-mobile.png"), fullPage: true })
  expect(pageErrors).toEqual([])
  expect(consoleMessages.filter((message) => message.startsWith("[error]"))).toEqual([])
})

test("draft outline and notes stay compact and defer secondary note data", async ({ page }, testInfo) => {
  await installMockApi(page)
  await page.context().addCookies([{ name: "lorevia_analytics_consent", value: "false", domain: "localhost", path: "/" }])
  const inspectorRequests: string[] = []
  page.on("request", (request) => {
    if (request.url().includes("/workspace/tree") || request.url().includes("/notes/vault/relations")) {
      inspectorRequests.push(request.url())
    }
  })

  await page.goto(`${BOOK_ROUTE}/chapters`)
  await expect(page.getByRole("heading", { name: "Chapters", exact: true, level: 1 })).toBeVisible()
  await expect(page.locator("article").filter({ hasText: "The Ember Gate" })).toContainText("Processed · Marked as read · Indexed and ready")
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: testInfo.outputPath("chapter-outline-desktop.png"), fullPage: true })

  await page.goto(`${BOOK_ROUTE}/notes`)
  await expect(page.getByRole("heading", { name: "Notes", exact: true })).toBeVisible()
  const detailsButton = page.getByRole("button", { name: "Details", exact: true })
  await expect(detailsButton).toBeVisible()
  await expect(detailsButton).toBeEnabled()
  expect(inspectorRequests).toHaveLength(0)

  await detailsButton.click()
  await expect.poll(() => inspectorRequests.length).toBeGreaterThan(0)
  await page.getByRole("button", { name: /Chapter-linked notes/ }).click()
  await expect(page.getByRole("article").getByRole("heading", { name: "Gate imagery", exact: true })).toBeVisible()
  await hideNonProductCaptureOverlays(page)
  await page.screenshot({ path: testInfo.outputPath("notes-workspace-desktop.png"), fullPage: true })

  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByRole("button", { name: "Close", exact: true })).toBeVisible()
  await page.getByRole("button", { name: "Close", exact: true }).click()
  await expect(page.getByLabel("Note details")).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: testInfo.outputPath("notes-mobile.png"), fullPage: true })
})

test("recaps stay contextual to overview and chapters and load on intent", async ({ page }) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  const recapRequests: string[] = []
  page.on("request", (request) => {
    if (request.url().includes("/api/v1/reader/book-1/summary-collection")) recapRequests.push(request.url())
  })
  await installMockApi(page)
  await page.context().addCookies([{ name: "lorevia_analytics_consent", value: "false", domain: "localhost", path: "/" }])

  await page.goto(`${BOOK_ROUTE}/chapters`)
  await expect(page.getByRole("heading", { name: "Chapters", exact: true, level: 1 })).toBeVisible()
  expect(recapRequests).toEqual([])
  await page.getByRole("button", { name: "Show chapter recaps" }).click()
  await expect(page.getByRole("button", { name: "Hide chapter recaps" })).toBeVisible()
  expect(recapRequests).toHaveLength(1)
  await page.getByText("Read chapter recap").first().click()
  await expect(page.getByText("Nora leaves the ash road and reaches the city wall.")).toBeVisible()
  await page.setViewportSize({ width: 1440, height: 1000 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: test.info().outputPath("chapter-recaps-desktop.png"), fullPage: true })

  await page.goto(BOOK_ROUTE)
  await expect(page.getByText("Manuscript recap", { exact: true }).first()).toBeVisible()
  await page.getByText("Manuscript recap", { exact: true }).first().click()
  await expect(page.getByText("Nora leaves the ash road and reaches the city wall. The ember gate opens and Nora steps into the city under watch.")).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: test.info().outputPath("manuscript-recap-mobile.png"), fullPage: true })

  await page.goto(`${BOOK_ROUTE}/summaries`)
  await expect(page).toHaveURL(new RegExp(`${BOOK_ROUTE}$`))
  expect(consoleMessages.some((message) => /Maximum update depth|ReferenceError|TypeError|Unhandled/i.test(message))).toBe(false)
  expect(pageErrors).toEqual([])
})

test("chapter reading keeps navigation and evidence tools contextual", async ({ page }, testInfo) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  const chapterRequests: string[] = []
  page.on("request", (request) => {
    if (request.url().includes("/api/v1/reader/book-1/chapter/2")) chapterRequests.push(request.url())
  })
  await installMockApi(page)
  await page.context().addCookies([{ name: "lorevia_analytics_consent", value: "false", domain: "localhost", path: "/" }])
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(`${BOOK_ROUTE}/chapter/2`)

  await expect(page.getByRole("heading", { name: "The Ember Gate", exact: true })).toBeVisible()
  await expect(page.getByText(/Nora crossed the ember gate/)).toBeVisible()
  expect(chapterRequests.length).toBeLessThanOrEqual(1)
  await expect(page.getByRole("button", { name: "Recap", exact: true })).toBeVisible()
  await expect(page.getByText("Graph", { exact: true })).toHaveCount(0)
  await expect(page.getByText("Old Style Serif", { exact: true })).toHaveCount(0)

  await page.getByRole("button", { name: "Chapter tools", exact: true }).click()
  await expect(page.getByRole("link", { name: "Ask with citations", exact: true })).toHaveAttribute("href", `${BOOK_ROUTE}/ask`)
  await expect(page.getByRole("link", { name: "Search this chapter", exact: true })).toHaveAttribute("href", `${BOOK_ROUTE}/search?chapter=2`)
  await expect(page.getByRole("link", { name: "Chapter notes", exact: true })).toHaveAttribute("href", `${BOOK_ROUTE}/notes?chapter=2`)

  await page.getByRole("button", { name: "Text", exact: true }).click()
  await expect(page.getByRole("group", { name: "Typeface" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Use Old Style Serif font" })).toBeVisible()
  const themeButton = page.getByRole("button", { name: /^(Light|Dark)$/ }).first()
  const initialThemeAction = await themeButton.textContent()
  await themeButton.click()
  await expect(page.getByRole("button", { name: initialThemeAction === "Light" ? "Dark" : "Light", exact: true })).toBeVisible()
  await hideNonProductCaptureOverlays(page)
  await page.screenshot({ path: testInfo.outputPath("chapter-reader-desktop.png"), fullPage: true })

  await page.setViewportSize({ width: 768, height: 900 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: testInfo.outputPath("chapter-reader-tablet.png"), fullPage: true })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.reload()
  await expect(page.getByRole("button", { name: "Menu", exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "Recap", exact: true }).last()).toBeVisible()
  await page.getByRole("button", { name: "Menu", exact: true }).click()
  await expect(page.getByRole("link", { name: "Search this chapter", exact: true })).toBeVisible()
  await expect(page.getByRole("link", { name: "Chapter notes", exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await hideNonProductCaptureOverlays(page)
  await page.screenshot({ path: testInfo.outputPath("chapter-reader-mobile.png"), fullPage: true })

  expect(consoleMessages.some((message) => /Maximum update depth|ReferenceError|TypeError|Unhandled/i.test(message))).toBe(false)
  expect(pageErrors).toEqual([])
})

test("scene workspace keeps outline and details on demand", async ({ page }, testInfo) => {
  await installMockApi(page)
  await page.context().addCookies([{ name: "lorevia_analytics_consent", value: "false", domain: "localhost", path: "/" }])
  await page.goto(`${BOOK_ROUTE}/scenes`)

  await expect(page.getByRole("heading", { name: "Scenes", exact: true })).toBeVisible()
  await expect(page.getByLabel("Scene title")).toHaveValue("Gate Crossing")
  await expect(page.getByText("Nora crosses into the city.", { exact: true })).toBeVisible()
  const outlineButton = page.getByRole("button", { name: "Outline", exact: true })
  const detailsButton = page.getByRole("button", { name: "Details", exact: true })
  await expect(outlineButton).toHaveAttribute("aria-pressed", "false")
  await expect(detailsButton).toHaveAttribute("aria-pressed", "false")
  await page.screenshot({ path: testInfo.outputPath("scenes-focused-desktop.png"), fullPage: true })

  await outlineButton.click()
  await expect(page.getByLabel("Search scenes")).toBeVisible()
  await outlineButton.click()
  await detailsButton.click()
  await expect(page.getByRole("heading", { name: "Metadata", exact: true })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath("scenes-details-desktop.png"), fullPage: true })
  await detailsButton.click()

  await page.setViewportSize({ width: 390, height: 844 })
  await page.reload()
  await expect(page.getByLabel("Scene title")).toHaveValue("Gate Crossing")
  await page.getByRole("button", { name: "Outline", exact: true }).click()
  await expect(page.getByText("Scene outline", { exact: true })).toBeVisible()
  await page.getByRole("dialog", { name: "Scene outline" }).getByRole("button", { name: "Close", exact: true }).click()
  await page.getByRole("button", { name: "Details", exact: true }).click()
  await expect(page.getByText("Scene details", { exact: true }).first()).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath("scenes-details-mobile.png"), fullPage: true })
  await page.getByRole("dialog", { name: "Scene details" }).getByRole("button", { name: "Close", exact: true }).click()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: testInfo.outputPath("scenes-focused-mobile.png"), fullPage: true })
})

test("interactive demo reviews findings without API calls or mobile overflow", async ({ page }, testInfo) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  const apiRequests: string[] = []
  page.on("request", (request) => {
    if (request.url().includes("/api/")) apiRequests.push(request.url())
  })
  await page.goto("/demo/workspace")

  await expect(page.getByRole("heading", { name: "Review Dracula continuity findings" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Chapter context" })).toHaveCount(0)
  await expect(page.getByRole("heading", { name: "Revision plan" })).toHaveCount(0)
  const desktopOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
  expect(desktopOverflow).toBe(false)
  await page.screenshot({ path: testInfo.outputPath("demo-workspace-desktop.png"), fullPage: true })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.reload()
  await expect(page.getByText("0/3 reviewed")).toBeVisible()
  await page.getByRole("button", { name: "Add to revision plan" }).click()
  await expect(page.getByText("1/3 reviewed")).toBeVisible()
  await expect(page.getByRole("heading", { name: "Revision plan" })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath("demo-workspace-mobile.png"), fullPage: true })
  await page.getByRole("button", { name: "Reset demo" }).click()
  await expect(page.getByText("0/3 reviewed")).toBeVisible()

  const hasHorizontalOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
  expect(hasHorizontalOverflow).toBe(false)
  expect(apiRequests).toEqual([])
  expect(pageErrors).toEqual([])
  expect(consoleMessages.filter((message) => message.startsWith("[error]"))).toEqual([])
})

test("editorial hubs and articles work without auth on desktop and mobile", async ({ page, context }, testInfo) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  const apiRequests: string[] = []
  page.on("request", (request) => {
    if (request.url().includes("/api/")) apiRequests.push(request.url())
  })
  await context.grantPermissions(["clipboard-read", "clipboard-write"])
  await page.goto("/blog")

  await expect(page.getByRole("heading", { name: /notes on the difficult work of keeping a story whole/i })).toBeVisible()
  await expect(page.getByRole("link", { name: /how to build a scene list that actually helps you revise/i }).first()).toBeVisible()
  const hubHero = page.locator(".editorial-feature img")
  await expect(hubHero).toBeVisible()
  expect(await hubHero.evaluate((image: HTMLImageElement) => image.naturalWidth)).toBeGreaterThan(0)
  await expect(page.locator(".editorial-latest-grid .editorial-story-card__image")).toHaveCount(4)
  await expect(page.locator(".editorial-topics img")).toHaveCount(0)
  await page.screenshot({ path: testInfo.outputPath("blog-index-desktop.png"), fullPage: true })

  await page.goto("/blog/how-to-build-a-scene-list-for-novel-revision")
  await expect(page.getByRole("heading", { name: /how to build a scene list that actually helps you revise/i })).toBeVisible()
  await expect(page.getByRole("navigation", { name: "Article sections" }).first()).toBeVisible()
  await page.getByRole("button", { name: "Copy article link" }).click()
  await expect(page.locator('p[aria-live="polite"]')).toHaveText("Link copied")
  await page.getByRole("button", { name: "Switch to dark mode" }).click()
  await expect(page.locator("html")).toHaveClass(/dark/)
  await page.screenshot({ path: testInfo.outputPath("blog-article-desktop.png"), fullPage: true })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/answers")
  await expect(page.getByRole("heading", { name: /start with the question on your desk/i })).toBeVisible()
  await page.getByRole("searchbox", { name: "Search answers" }).fill("character arcs")
  await expect(page.getByRole("link", { name: /how do i track character arcs/i })).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath("answers-index-mobile.png"), fullPage: true })

  await page.goto("/answers/how-do-i-track-character-arcs")
  await expect(page.getByRole("heading", { name: /how do i track character arcs/i })).toBeVisible()
  await expect(page.getByText("Short answer", { exact: true })).toBeVisible()
  await expect(page.locator(".editorial-hero")).toHaveCount(0)
  await expect(page.locator(".editorial-mobile-toc")).toBeVisible()
  await page.locator(".editorial-mobile-toc summary").click()
  await expect(page.locator('.editorial-mobile-toc a[href="#define-the-starting-logic"]')).toBeVisible()
  const mobileOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
  expect(mobileOverflow).toBe(false)
  await page.screenshot({ path: testInfo.outputPath("answer-article-mobile.png"), fullPage: true })

  await page.goto("/demo/gregor-samsa-character-tracker")
  await expect(page.getByRole("heading", { name: /tracking gregor samsa/i })).toBeVisible()
  expect(apiRequests).toEqual([])
  expect(pageErrors).toEqual([])
  expect(consoleMessages.filter((message) => message.startsWith("[error]"))).toEqual([])
})

test("public forum surfaces reputation and writer profile details", async ({ page }, testInfo) => {
  await installMockApi(page)
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto("/public/forum")

  await expect(page.getByRole("heading", { name: /beta novel rankings worth opening/i })).toBeVisible()
  await expect(page.getByRole("link", { name: /back to public library/i })).toBeVisible()
  await expect(page.getByText("Showing 1-12 of 12 threads")).toBeVisible()
  await page.locator("select").nth(0).selectOption("top_rated")
  await page.locator("select").nth(1).selectOption("weekly")
  await expect(page.getByText("Top Rated Weekly").first()).toBeVisible()
  await expect(page.getByText("Showing 1-12 of 12 threads")).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: testInfo.outputPath("public-forum-desktop.png"), fullPage: true })
  await page.getByRole("button", { name: "General discussion" }).click()
  await page.getByLabel(/general discussion headline/i).fill("How do you raise tension without chaos?")
  await page.getByLabel(/discussion body/i).fill("I want craft advice on building pressure in quiet scenes.")
  await page.getByRole("button", { name: "Open general thread" }).click()
  await expect(page).toHaveURL(/\/public\/forum\/forum-post-\d+$/)

  // The new mock post only exists in the browser process; use a seeded post for
  // the server-rendered thread interaction that follows.
  await page.goto("/public/forum/forum-post-1")
  await expect(page.getByRole("heading", { name: /looking for sharp beta readers/i })).toBeVisible()
  await expect(page.getByRole("link", { name: /^library$/i })).toBeVisible()
  await page.getByLabel(/public comment/i).fill("Happy to review pacing and clarity.")
  await page.getByRole("button", { name: "Post comment" }).click()
  await expect(page.getByText("Happy to review pacing and clarity.")).toBeVisible()
  await page.getByRole("button", { name: "Reply" }).first().click()
  await page.getByLabel(/^reply to @/i).fill("That is exactly the section I would start with too.")
  await page.getByRole("button", { name: "Post reply" }).click()
  await expect(page.getByText("That is exactly the section I would start with too.")).toBeVisible()
  await expect(page.getByRole("link", { name: "@author" }).first()).toBeVisible()
  await page.screenshot({ path: testInfo.outputPath("public-forum-thread-desktop.png"), fullPage: true })
  await page.goto("/public/writers/author")

  await expect(page.getByRole("heading", { name: "@author", exact: true })).toBeVisible()
  await expect(page.getByText(/public forum status: public/i)).toBeVisible()
  await expect(page.getByRole("button", { name: /Posts \(2\)/i })).toBeVisible()
  await expect(page.getByRole("button", { name: /Comments \(1\)/i })).toBeVisible()
  await page.getByRole("button", { name: /Comments \(1\)/i }).click()
  await expect(page.getByText(/how do you keep second acts from flattening out/i)).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: testInfo.outputPath("public-writer-mobile.png"), fullPage: true })
})

test("public uploads support ranking and window selection", async ({ page }, testInfo) => {
  await installMockApi(page)
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto("/public/uploads")

  await expect(page.getByRole("heading", { name: /browse creator-published books from lorevia authors/i })).toBeVisible()
  await page.getByLabel("Rank by").selectOption("top_rated")
  await page.getByLabel("Window").selectOption("weekly")
  await expect(page.getByText("Top Rated Weekly").first()).toBeVisible()
  await expect(page.getByRole("heading", { name: "Ash Gate Sample" })).toBeVisible()
  await page.getByLabel("Search creator-published books").fill("ash")
  await expect(page.getByRole("heading", { name: "Ash Gate Sample" })).toBeVisible()
  await expect(page.getByText(/mock ranking feed for local smoke coverage/i).first()).toBeVisible()
  await expect(page.getByTestId("creator-upload-list").locator("article")).toHaveCount(1)
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: testInfo.outputPath("public-uploads-desktop.png"), fullPage: true })
  await page.goto("/public/analytics")
  await expect(page.getByRole("heading", { name: /see how creator-published books are surfacing/i })).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: testInfo.outputPath("public-upload-analytics-mobile.png"), fullPage: true })
})

test("public library cross-links safe samples and writer trust", async ({ page }, testInfo) => {
  await installMockApi(page)
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto("/public")

  await expect(page.getByRole("heading", { name: /published work for focused reading/i })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Ash Gate Sample" })).toBeVisible()
  await expect(page.getByTestId("public-book-list").locator("article")).toHaveCount(1)
  await page.screenshot({ path: testInfo.outputPath("public-library-desktop.png"), fullPage: true })
  const ashGateCard = page
    .locator("article")
    .filter({ has: page.getByRole("heading", { name: "Ash Gate Sample" }) })
    .first()
  await ashGateCard.getByRole("link", { name: "Discussion", exact: true }).click()

  await expect(page).toHaveURL(/\/public\/forum\/forum-post-1$/)
  await page.goto("/public")
  await expect(ashGateCard.getByRole("link", { name: "@author" })).toBeVisible()
  await page.goto("/public/writers/author")

  await expect(page).toHaveURL(/\/public\/writers\/author$/)
  await expect(page.getByRole("heading", { name: "@author", exact: true })).toBeVisible()
  await page.getByRole("link", { name: "Open forum discussion" }).click()

  await expect(page).toHaveURL(/\/public\/forum\/forum-post-1$/)
  await page.goto("/public/writers/author")
  await page.getByRole("link", { name: "Read public sample" }).click()

  await expect(page).toHaveURL(/\/public\/public-book-1$/)
  await expect(page.getByRole("heading", { name: "Ash Gate Sample" })).toBeVisible()
  await expect(page.getByRole("link", { name: "@author" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Start reading" })).toBeVisible()
  await expect(page.getByTestId("public-book-activity")).not.toHaveAttribute("open", "")
  await page.screenshot({ path: testInfo.outputPath("public-book-desktop.png"), fullPage: true })

  await page.getByRole("link", { name: "Start reading" }).click()
  await expect(page).toHaveURL(/\/public\/public-book-1\/chapter\/1$/)
  await expect(page.getByRole("heading", { name: "The Gate Opens" })).toBeVisible()
  await expect(page.getByTestId("public-chapter-reader")).toContainText("Ash Gate Sample")
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: testInfo.outputPath("public-chapter-mobile.png"), fullPage: true })
})

test("login surfaces an invalid-credentials error", async ({ page }, testInfo) => {
  await installMockApi(page, { session: "guest", login: "unauthorized" })
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto("/login")

  await page.getByLabel("Email", { exact: true }).fill("reader@example.com")
  await page.getByLabel("Password", { exact: true }).fill("wrong-password")
  await page.getByRole("button", { name: /^sign in$/i }).click()

  await expect(page.getByText("Invalid email or password.")).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: testInfo.outputPath("login-error-desktop.png"), fullPage: true })
  await page.goto("/register")
  await expect(page.getByRole("heading", { name: "Create account" })).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: testInfo.outputPath("register-mobile.png"), fullPage: true })
  await page.goto("/forgot-password")
  await expect(page.getByRole("heading", { name: "Reset your password" })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
})

test("auth redirects protect private pages and skip login for active sessions", async ({ page }) => {
  await page.goto("/library")
  await expect(page).toHaveURL(/\/login\?next=%2Flibrary$/)

  await installMockApi(page)
  await page.goto("/login")
  await expect(page).toHaveURL(/\/library$/)
  await expect(page.getByRole("heading", { name: "Library" })).toBeVisible()
})

test("checkout and confirmation keep a focused transaction shell", async ({ page }, testInfo) => {
  await installMockApi(page, { session: "guest" })
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto("/checkout")

  await expect(page.getByRole("heading", { name: "Complete your secure checkout." })).toBeVisible()
  await expect(page.getByRole("navigation")).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: testInfo.outputPath("checkout-desktop.png"), fullPage: true })

  await page.goto("/checkout/success")
  await expect(page.getByRole("heading", { name: "Your subscription checkout is complete." })).toBeVisible()
  await expect(page.getByText(/missing transaction reference/i)).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: testInfo.outputPath("checkout-success-mobile.png"), fullPage: true })
})

test("legal and contact pages use a restrained prose shell", async ({ page }, testInfo) => {
  await installMockApi(page, { session: "guest" })
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto("/contact")

  await expect(page.getByRole("heading", { name: "We're here to help." })).toBeVisible()
  await expect(page.getByText("This page is operational, not decorative.")).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: testInfo.outputPath("contact-desktop.png"), fullPage: true })

  await page.goto("/privacy")
  await expect(page.getByRole("heading", { name: "Privacy Policy" })).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: testInfo.outputPath("privacy-mobile.png"), fullPage: true })
})

test("system states present one clear recovery action", async ({ page }, testInfo) => {
  await installMockApi(page, { session: "guest" })
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto("/status")

  await expect(page.getByRole("heading", { name: "No active incident is posted." })).toBeVisible()
  await expect(page.getByRole("link", { name: "Contact support" })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: testInfo.outputPath("status-desktop.png"), fullPage: true })

  await page.goto("/offline")
  await expect(page.getByRole("heading", { name: "You are offline." })).toBeVisible()
  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: testInfo.outputPath("offline-mobile.png"), fullPage: true })

  await page.goto("/unsubscribe")
  await expect(page.getByRole("heading", { name: "We could not unsubscribe you" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Manage preferences" })).toBeVisible()
})

test("admin route returns 404 when the request is not allowed", async ({ page }) => {
  await installMockApi(page, { admin: "none" })
  await page.goto("/")
  const response = await page.evaluate(async () => {
    const result = await fetch("/api/v1/admin/session")
    return { status: result.status, body: await result.json() }
  })

  expect(response.status).toBe(403)
  expect(response.body).toEqual({ detail: "Admin only" })

  await page.goto("/admin")

  await expect(page.getByText("This page could not be found.")).toBeVisible()
})

test("admin session accepts owner admins in the E2E mock", async ({ page }) => {
  await installMockApi(page, { admin: "owner" })
  await page.goto("/")
  const response = await page.evaluate(async () => {
    const result = await fetch("/api/v1/admin/session")
    return { status: result.status, body: await result.json() }
  })

  expect(response.status).toBe(200)
  expect(response.body).toMatchObject({
    is_admin: true,
    is_owner: true,
    requires_step_up: false,
  })
  expect(response.body.scopes).toEqual(["moderation_admin", "billing_admin", "super_admin"])
})

test("admin route loads scoped table-first work areas for owner admins", async ({ page }, testInfo) => {
  await installMockApi(page, { admin: "owner" })
  const adminRequests: string[] = []
  page.on("request", (request) => {
    const pathname = new URL(request.url()).pathname
    if (pathname.startsWith("/api/v1/admin/") && request.method() === "GET") adminRequests.push(pathname)
  })
  await page.route("**/api/v1/admin/session", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      headers: {
        "access-control-allow-credentials": "true",
        "access-control-allow-origin": E2E_APP_ORIGIN,
      },
      body: JSON.stringify({
        is_admin: true,
        scopes: ["moderation_admin", "billing_admin", "super_admin"],
        is_owner: true,
        requires_step_up: false,
        session_expires_at: null,
      }),
    })
  })
  await page.goto("/")
  const response = await page.evaluate(async () => {
    const result = await fetch("/api/v1/admin/session")
    return { status: result.status, body: await result.json() }
  })

  expect(response.status).toBe(200)
  expect(response.body).toMatchObject({
    is_admin: true,
    is_owner: true,
    requires_step_up: false,
  })
  expect(response.body.scopes).toEqual(["moderation_admin", "billing_admin", "super_admin"])

  await page.setExtraHTTPHeaders({
    "x-lorevia-admin-test-session": `owner:${ADMIN_TEST_SESSION_SECRET}`,
  })
  await page.evaluate((value) => {
    document.cookie = `lorevia_admin_test_session=${encodeURIComponent(value)}; Path=/; SameSite=Lax`
  }, `owner:${ADMIN_TEST_SESSION_SECRET}`)
  await page.context().addCookies([
    {
      name: "lorevia_admin_test_session",
      value: `owner:${ADMIN_TEST_SESSION_SECRET}`,
      url: E2E_APP_ORIGIN,
      sameSite: "Lax",
    },
  ])
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto(`/admin?e2e=${Date.now()}`)

  await expect(page.getByRole("heading", { name: "Operations Console" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Platform Overview" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Moderation" })).toHaveCount(0)
  await expect.poll(() => adminRequests).toContain("/api/v1/admin/metrics")
  expect(adminRequests).not.toContain("/api/v1/admin/billing/status")
  expect(adminRequests).not.toContain("/api/v1/admin/public-shares/pending")
  await page.screenshot({ path: testInfo.outputPath("admin-overview-desktop.png"), fullPage: true })

  await page.getByRole("button", { name: "Moderation", exact: true }).click()
  await expect(page.getByRole("heading", { name: "Moderation" })).toBeVisible()
  await expect(page.getByRole("table")).toHaveCount(2)
  await expect.poll(() => adminRequests).toContain("/api/v1/admin/public-shares/pending")
  expect(adminRequests).not.toContain("/api/v1/admin/billing/status")
  await page.screenshot({ path: testInfo.outputPath("admin-moderation-desktop.png"), fullPage: true })

  await page.getByRole("button", { name: "Billing", exact: true }).click()
  await expect(page.getByRole("heading", { name: "Refunds" })).toBeVisible()
  await expect(page.getByText(/Billing configuration/)).toBeVisible()

  await page.getByRole("button", { name: "Reliability", exact: true }).click()
  await expect(page.getByRole("heading", { name: "Rate Limits" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Reliability and Unit Economics" })).toBeVisible()

  await page.getByRole("button", { name: "Access & audit", exact: true }).click()
  await expect(page.getByRole("heading", { name: "Admin Access" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Audit" })).toBeVisible()
  await expect(page.getByRole("table")).toHaveCount(2)

  await page.setViewportSize({ width: 390, height: 844 })
  await page.evaluate(() => window.scrollTo(0, 0))
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: testInfo.outputPath("admin-access-mobile.png"), fullPage: true })
})

test("library renders a mocked project and opens the upload modal", async ({ page }) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  await installMockApi(page)
  await page.addInitScript(() => {
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
  await page.goto("/library")

  await expect(page.getByRole("heading", { name: "Library" })).toBeVisible()
  await expect(page.getByTestId("first-manuscript-hero")).toHaveCount(0)
  await expect(page.getByRole("searchbox", { name: "Search projects" })).toBeVisible()
  await expect(page.getByText("Next best action")).toHaveCount(0)
  await expect(page.getByText("Recent activity")).toHaveCount(0)
  await expect(page.getByRole("link", { name: "Open Sky of Ash" })).toBeVisible()
  await page.screenshot({ path: test.info().outputPath("library-desktop.png"), fullPage: true })
  await page.keyboard.press("Control+K")
  await expect(page.getByRole("dialog", { name: "Command palette" })).toBeVisible()
  await page.getByLabel("Search commands").fill("manuscript")
  await expect(page.getByRole("option", { name: /manuscript editor: sky of ash/i })).toBeVisible()
  await page.keyboard.press("Escape")

  await page.getByRole("button", { name: /^new project$/i }).click()
  await expect(page.getByRole("dialog", { name: "Upload manuscript" })).toBeVisible()
  await page.getByRole("button", { name: "Close upload modal" }).click()

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/library")
  await expect(page.getByRole("heading", { name: "Library" })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: test.info().outputPath("library-mobile.png"), fullPage: true })
  expect(consoleMessages.some((message) => /Maximum update depth|ReferenceError|TypeError|Unhandled/i.test(message))).toBe(false)
  expect(pageErrors).toEqual([])
})

test("warned prose outline corrections are sent with the exact upload", async ({ page }) => {
  await installMockApi(page)
  await page.route("**/api/v1/books/upload/preview", async (route) => {
    await route.fulfill({ json: {
      detected_language: "en", language_confidence: 1, title: "Harbor", author: "",
      source_sha256: "source-hash", content_sha256: "content-hash", parser_version: "prose-structure-2", block_count: 3,
      sections: [
        { id: "part-1", type: "part", title: "Part I", number: 1, start_block: 0, end_block: 0, include_in_analysis: false, word_count: 0, source_location: "line 1" },
        { id: "note-1", type: "notes", title: "Author's Note", number: null, start_block: 0, end_block: 1, include_in_analysis: false, word_count: 8, source_location: "line 2", opening_excerpt: "A note from the author.", closing_excerpt: "A note from the author." },
        { id: "unknown-1", type: "unknown", title: "Unclassified passage", number: null, start_block: 1, end_block: 2, include_in_analysis: true, word_count: 12, source_location: "line 4", opening_excerpt: "The harbor lamp went dark.", closing_excerpt: "The harbor lamp went dark.", warnings: ["The section type is uncertain."] },
        { id: "chapter-1", type: "chapter", title: "Chapter 1", number: 1, parent_id: "part-1", start_block: 2, end_block: 3, include_in_analysis: true, word_count: 15, source_location: "line 6", opening_excerpt: "Mara returned home.", closing_excerpt: "Mara returned home." },
      ],
      chapter_count: 1, toc_detected: false, front_matter_count: 1, confidence: 0.7,
      warnings: [{ severity: "warning", section_id: "unknown-1", message: "The section type is uncertain." }],
      total_words: 35, source_size_bytes: 80, allowance_allowed: true,
      projected_active_words: 35, active_word_limit: 100000, projected_monthly_processed_words: 27,
      monthly_processed_word_limit: 100000, projected_source_storage_bytes: 80, source_storage_limit_bytes: 1000000,
    } })
  })
  let submitted = ""
  await page.route("**/api/v1/books/upload", async (route) => {
    submitted = route.request().postData() ?? ""
    await route.fulfill({ status: 202, json: { book_id: "book-1", status: "processing" } })
  })
  await page.goto("/library")
  await page.getByRole("button", { name: /^new project$/i }).first().click()
  const dialog = page.getByRole("dialog", { name: "Upload manuscript" })
  await dialog.getByRole("button", { name: /^author mode$/i }).click()
  await dialog.locator('input[type="file"]').first().setInputFiles({
    name: "harbor.txt", mimeType: "text/plain", buffer: Buffer.from("Author's Note\nA note from the author.\nChapter 1\nMara returned home."),
  })
  await dialog.getByRole("button", { name: "Preview structure" }).click()
  await expect(dialog.getByText("Review uncertain boundaries")).toBeVisible()
  await expect(dialog.getByText("Unclassified passage")).toBeVisible()
  await dialog.getByRole("button", { name: "Edit structure" }).click()
  await dialog.getByRole("textbox", { name: "Section 3 title" }).fill("Harbor interlude")
  await dialog.getByRole("button", { name: "Save changes" }).click()
  await dialog.getByLabel("Title", { exact: true }).fill("Harbor")
  await dialog.getByRole("button", { name: "Confirm & Import" }).click()
  await expect.poll(() => submitted).toContain("Harbor interlude")
  expect(submitted).toContain("structure_plan")
  expect(submitted).toContain("source-hash")

  await page.route("**/api/v1/reader/book-1/chapters", async (route) => {
    await route.fulfill({ json: {
      read_upto: 0, current_chapter: 0,
      chapters: [
        { number: 1, title: "Chapter 1", chapter_kind: "chapter", printed_label: "Chapter 1", parent_part_id: "part-one", parent_part_title: "Part I", processed: true, intelligence_available: true, read: false, tags: [] },
        { number: 2, title: "Chapter 1", chapter_kind: "chapter", printed_label: "Chapter 1", parent_part_id: "part-two", parent_part_title: "Part II", processed: true, intelligence_available: true, read: false, tags: [] },
      ],
    } })
  })
  await page.goto(`${BOOK_ROUTE}/chapters`)
  await expect(page.getByRole("heading", { name: "Part I", exact: true })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Part II", exact: true })).toBeVisible()
  await page.getByRole("button", { name: "Open chapter 2: Chapter 1" }).click()
  await expect(page).toHaveURL(/\/chapter\/2$/, { timeout: 30_000 })
})

test("account notes and quotes use compact searchable rows", async ({ page }) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  await installMockApi(page)
  await page.addInitScript(() => {
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })

  await page.goto("/notes")
  await expect(page.getByRole("heading", { name: "Notes", exact: true })).toBeVisible()
  await expect(page.getByText("Gate oath continuity")).toBeVisible()
  await expect(page.getByText("Visible notes")).toHaveCount(0)
  await page.getByRole("searchbox", { name: "Search notes" }).fill("silver key")
  await expect(page.getByText("Gate oath continuity")).toBeVisible()
  await page.screenshot({ path: test.info().outputPath("account-notes-desktop.png"), fullPage: true })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/quotes")
  await expect(page.getByRole("heading", { name: "Quotes", exact: true })).toBeVisible()
  await expect(page.getByText("The gate remembers every oath.")).toBeVisible()
  await expect(page.getByText("Visible quotes")).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: test.info().outputPath("account-quotes-mobile.png"), fullPage: true })

  expect(consoleMessages.some((message) => /Maximum update depth|ReferenceError|TypeError|Unhandled/i.test(message))).toBe(false)
  expect(pageErrors).toEqual([])
})

test("writing stats keeps one trend, one progress summary, and a compact breakdown", async ({ page }) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  await installMockApi(page)
  await page.addInitScript(() => {
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
  await page.goto("/stats")

  await expect(page.getByRole("heading", { name: "Writing progress" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Heatmap of saved writing" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Progress summary" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Breakdown" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Entries today" })).toHaveCount(0)
  await page.screenshot({ path: test.info().outputPath("writing-stats-desktop.png"), fullPage: true })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/stats")
  await expect(page.getByRole("heading", { name: "Writing progress" })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: test.info().outputPath("writing-stats-mobile.png"), fullPage: true })

  expect(consoleMessages.some((message) => /Maximum update depth|ReferenceError|TypeError|Unhandled|Hydration failed/i.test(message))).toBe(false)
  expect(pageErrors).toEqual([])
})

test("series management uses one selected detail and a contextual Ask workspace", async ({ page }) => {
  const requestedSeriesAnalysis: string[] = []
  await installMockApi(page, { seriesBooks: true })
  page.on("request", (request) => {
    if (request.url().includes("/world-building/series-analysis")) requestedSeriesAnalysis.push(request.url())
  })

  await page.goto("/series")
  await page.getByRole("button", { name: /decline cookies|not now/i }).click({ timeout: 5000 }).catch(() => {})
  await expect(page.getByRole("heading", { name: "Series management" })).toBeVisible()
  await expect(page.getByRole("complementary", { name: "Series list" })).toContainText("Ash Cycle")
  await expect(page.getByRole("complementary", { name: "Series list" })).toContainText("North Road")
  await expect(page.getByRole("region", { name: "Selected series details" })).toContainText("Sky of Ash")
  await expect(page.getByRole("region", { name: "Selected series details" })).toContainText("Embers Beyond the Gate")
  expect(requestedSeriesAnalysis).toHaveLength(0)

  await page.getByRole("button", { name: "World analysis" }).click()
  await expect(page.getByText("Ash Gate")).toBeVisible()
  expect(requestedSeriesAnalysis).toHaveLength(1)
  await page.screenshot({ path: test.info().outputPath("series-master-detail-desktop.png"), fullPage: true })

  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByRole("combobox", { name: "Selected series" })).toBeVisible()
  await expect(page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).resolves.toBe(true)
  await page.screenshot({ path: test.info().outputPath("series-master-detail-mobile.png"), fullPage: true })

  await page.getByRole("link", { name: "Ask about this series" }).click()
  await expect(page.getByRole("heading", { name: "Ask about Ash Cycle" })).toBeVisible()
  await expect(page.getByText("Series Ask · 2 projects")).toBeVisible()
  await page.getByText("Suggested questions", { exact: true }).click()
  await page.getByRole("button", { name: "Which character changes most across the series?" }).click()
  await expect(page.getByText(/Nora changes most across the series/)).toBeVisible()
  await expect(page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).resolves.toBe(true)
  await page.screenshot({ path: test.info().outputPath("series-ask-mobile.png"), fullPage: true })
})

test("messages uses a deferred two-pane conversation layout with mobile drill-in", async ({ page }) => {
  const messageRequests: string[] = []
  await installMockApi(page)
  await page.addInitScript(() => {
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
  page.on("request", (request) => {
    if (request.url().includes("/social/conversations/conversation-1/messages/page")) messageRequests.push(request.url())
  })

  await page.goto("/chats")
  await expect(page.getByRole("heading", { name: "Messages" })).toBeVisible()
  await expect(page.getByRole("button", { name: /@theo/i })).toBeVisible()
  await expect(page.getByText(/select a conversation to read and reply/i)).toBeVisible()
  expect(messageRequests).toHaveLength(0)

  await page.getByRole("button", { name: /@theo/i }).click()
  await expect(page.getByText("Can you read chapter two?", { exact: true }).last()).toBeVisible()
  await expect.poll(() => messageRequests.length).toBe(1)
  await page.getByRole("textbox", { name: "Message", exact: true }).fill("I’ll send line notes after dinner.")
  await page.getByRole("button", { name: "Send", exact: true }).click()
  await expect(page.getByText("I’ll send line notes after dinner.")).toBeVisible()
  await page.screenshot({ path: test.info().outputPath("messages-two-pane-desktop.png"), fullPage: true })

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/chats")
  await expect(page.getByRole("button", { name: /@theo/i })).toBeVisible()
  await expect(page.getByText(/select a conversation to read and reply/i)).toBeHidden()
  await page.screenshot({ path: test.info().outputPath("messages-list-mobile.png"), fullPage: true })
  await page.getByRole("button", { name: /@theo/i }).click()
  await expect(page.getByRole("button", { name: "Back", exact: true })).toBeVisible()
  await expect(page.getByText("Can you read chapter two?", { exact: true }).last()).toBeVisible()
  await expect(page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).resolves.toBe(true)
  await page.screenshot({ path: test.info().outputPath("messages-thread-mobile.png"), fullPage: true })
})

test("notifications uses chronological rows with restrained unread emphasis", async ({ page }) => {
  const revisionRequests: string[] = []
  await installMockApi(page)
  await page.addInitScript(() => {
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
  page.on("request", (request) => {
    if (request.url().includes("/revision-intelligence")) revisionRequests.push(request.url())
  })

  await page.goto("/notifications")
  await expect(page.getByRole("heading", { name: "Notifications" })).toBeVisible()
  await expect(page.getByText("1 unread update")).toBeVisible()
  await expect(page.getByRole("heading", { name: "2 revision risks surfaced in Sky of Ash" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Sky of Ash is ready" })).toBeVisible()
  await expect(page.locator('span[aria-label="Unread"]')).toHaveCount(1)
  expect(revisionRequests).toHaveLength(0)

  await page.getByRole("button", { name: "View details" }).first().click()
  await expect(page.getByRole("heading", { name: "Revision Details" })).toBeVisible()
  await expect(page.getByText("Chapter 2 assumption may break later payoff").last()).toBeVisible()
  await expect.poll(() => revisionRequests.length).toBe(1)
  await page.screenshot({ path: test.info().outputPath("notifications-rows-desktop.png"), fullPage: true })

  await page.getByRole("button", { name: "Mark read", exact: true }).click()
  await expect(page.getByText("You’re up to date")).toBeVisible()
  await page.setViewportSize({ width: 390, height: 844 })
  await page.evaluate(() => {
    document.documentElement.scrollLeft = 0
    document.body.scrollLeft = 0
    window.scrollTo(0, 0)
  })
  await expect(page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).resolves.toBe(true)
  await page.screenshot({ path: test.info().outputPath("notifications-rows-mobile.png"), fullPage: true })
})

test("help stays clear of profile and mobile actions while support input keeps question marks", async ({ page }) => {
  await installMockApi(page)
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto("/library")

  const help = page.getByRole("button", { name: "Help", exact: true })
  const profile = page.getByRole("link", { name: "Open author public profile" })
  await expect(help).toBeVisible()
  await expect(profile).toBeVisible()

  const desktopBoxes = await Promise.all([help.boundingBox(), profile.boundingBox()])
  expect(desktopBoxes[0]).not.toBeNull()
  expect(desktopBoxes[1]).not.toBeNull()
  expect(rectanglesOverlap(desktopBoxes[0]!, desktopBoxes[1]!)).toBe(false)

  await help.click()
  const supportInput = page.getByLabel("What do you need help with?")
  await supportInput.pressSequentially("Can I save this chapter?")
  await expect(supportInput).toHaveValue("Can I save this chapter?")
  await expect(page.getByRole("dialog", { name: "LoreVia Support" })).toBeVisible()

  await page.getByRole("button", { name: "Close" }).last().click()
  await page.setViewportSize({ width: 390, height: 844 })
  await page.reload()
  const mobileHelp = page.getByRole("button", { name: "Help", exact: true })
  const mobileActions = page.getByRole("button", { name: "Open navigation" })
  await expect(mobileHelp).toBeVisible()
  await expect(mobileActions).toBeVisible()
  const mobileBoxes = await Promise.all([mobileHelp.boundingBox(), mobileActions.boundingBox()])
  expect(mobileBoxes[0]).not.toBeNull()
  expect(mobileBoxes[1]).not.toBeNull()
  expect(rectanglesOverlap(mobileBoxes[0]!, mobileBoxes[1]!)).toBe(false)
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
})

function rectanglesOverlap(
  first: { x: number; y: number; width: number; height: number },
  second: { x: number; y: number; width: number; height: number },
) {
  return first.x < second.x + second.width
    && first.x + first.width > second.x
    && first.y < second.y + second.height
    && first.y + first.height > second.y
}

test("settings page updates the public username", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/settings")

  const usernameInput = page.locator('input[autocomplete="username"]')
  await expect(usernameInput).toHaveValue("author")
  await usernameInput.fill("storysmith")
  const changeUsernameButton = page.getByRole("button", { name: /change username/i })
  await changeUsernameButton.focus()
  await page.keyboard.press("Enter")

  await expect(page.getByText("Public username updated.")).toBeVisible()
  await expect(page.locator("#identity").getByText("@storysmith")).toBeVisible()
})

test("settings page updates promotional email preferences", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/settings")

  await expect(page.getByText("LoreVia emails")).toBeVisible()
  await page.getByRole("button", { name: /Product updates/i }).click()

  await expect(page.getByText("Email preferences updated.")).toBeVisible()
  await page.getByRole("button", { name: "Unsubscribe from promotional emails" }).click()
  await expect(page.getByRole("button", { name: "Promotional emails unsubscribed" })).toBeVisible()
})

test("email unsubscribe link suppresses promotional email", async ({ page }) => {
  await installMockApi(page, { session: "guest" })
  await page.goto("/unsubscribe?token=mock-unsubscribe-token")

  await expect(page.getByRole("heading", { name: "You are unsubscribed" })).toBeVisible()
  await expect(page.getByText("author@getlorevia.com")).toBeVisible()
  await expect(page.getByText(/product updates or marketing emails/i)).toBeVisible()
  await expect(page.getByRole("link", { name: "Return to LoreVia" })).toHaveAttribute("href", "/")
})

test("settings data export triggers a download request", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/settings")

  await page.locator("#danger").scrollIntoViewIfNeeded()
  const downloadPromise = page.waitForEvent("download")
  await page.getByRole("button", { name: "Export my data" }).click()
  const download = await downloadPromise

  expect(download.suggestedFilename()).toBe("lorevia-data-export.zip")
})

test("settings account deletion requires confirmation and redirects to login", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/settings")

  await page.locator("#danger").scrollIntoViewIfNeeded()
  await expect(page.getByRole("button", { name: "Delete account" })).toBeDisabled()
  await page.getByLabel("Type DELETE MY ACCOUNT").fill("DELETE MY ACCOUNT")
  await page.getByLabel("Current password").fill("StrongPass123!@#")
  const dismissCookies = page.getByRole("button", { name: /decline cookies/i })
  if (await dismissCookies.isVisible().catch(() => false)) {
    await dismissCookies.click()
  }
  await page.getByRole("button", { name: "Delete account" }).click()

  await expect(page).toHaveURL(/\/login$/)
})

test("settings sidebar follows the current section while scrolling", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/settings")

  await expect(page.getByRole("link", { name: "Account" })).toHaveAttribute("aria-current", "location")
  await expect(page.getByText(/Security, password reset, verification, and billing emails/i)).toBeVisible()
  await page.locator("#session").evaluate((section) => {
    const targetTop = section.getBoundingClientRect().top + window.scrollY - 96
    window.scrollTo({ top: targetTop, behavior: "instant" })
  })
  await page.waitForFunction(() => {
    const rect = document.getElementById("session")?.getBoundingClientRect()
    return Boolean(rect && rect.top > 0 && rect.top < 180)
  })
  await page.evaluate(() => window.dispatchEvent(new Event("scroll")))
  await expect(page.getByRole("link", { name: "Session" })).toHaveAttribute("aria-current", "location")
})

test("settings uses one scannable form surface with explicit workspace controls", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/settings")

  await expect(page.getByRole("heading", { name: "Settings", exact: true })).toBeVisible()
  await expect(page.getByPlaceholder(/Search account, visibility/i)).toBeVisible()
  await expect(page.locator(".settings-summary-grid")).toHaveCount(0)
  await expect(page.locator(".settings-stack")).toHaveCount(1)
  await expect(page.locator("#workspace").getByRole("button", { name: "Hide from workspace" }).first()).toBeVisible()

  await page.setViewportSize({ width: 390, height: 844 })
  await page.evaluate(() => {
    document.documentElement.scrollLeft = 0
    document.body.scrollLeft = 0
    window.scrollTo(0, 0)
  })
  await expect(page.getByRole("navigation", { name: "Settings sections" })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
})

test("library permanent book deletion requires confirmation and removes the project", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/library")

  await expect(page.getByRole("heading", { name: "Sky of Ash" }).first()).toBeVisible()
  await page.locator('button[aria-label="Open actions for Sky of Ash"]').first().click()
  await page.getByRole("button", { name: "Delete permanently", exact: true }).click()
  const deleteDialog = page.getByRole("dialog", { name: "Delete Sky of Ash permanently?" })
  await deleteDialog.getByLabel("Confirmation phrase").fill("DELETE BOOK")
  await deleteDialog.getByRole("button", { name: "Delete permanently" }).click()

  await expect(page.getByRole("heading", { name: "Sky of Ash" })).toHaveCount(0)
})

test("author uploads default the manuscript byline from the public username", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/library")
  await page.getByRole("button", { name: /^new project$/i }).first().click()
  await page.getByRole("button", { name: /^author mode$/i }).click()

  const bylineInput = page.getByLabel("Manuscript author or pen name")
  await expect(bylineInput).toHaveValue("author")
  await expect(page.getByText("This name appears on this manuscript only.")).toBeVisible()
  await expect(page.getByText("different pen name or byline")).toBeVisible()
})

test("beta reads separates assigned, in-progress, and completed work without eager detail requests", async ({ page }) => {
  const detailRequests: string[] = []
  await installMockApi(page)
  page.on("request", (request) => {
    if (/\/api\/v1\/beta-reads\/beta-[^/]+$/.test(new URL(request.url()).pathname)) detailRequests.push(request.url())
  })
  await page.addInitScript(() => {
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
  await page.goto("/beta-reads")

  await expect(page.getByRole("heading", { name: "Reading assignments" })).toBeVisible()
  await expect(page.getByRole("tab", { name: "In progress" })).toHaveAttribute("aria-selected", "true")
  await expect(page.getByText("Chapter 12 feedback")).toBeVisible()
  await expect(page.getByText("The Lost Heir")).toBeVisible()
  expect(detailRequests).toHaveLength(0)

  await page.getByRole("button", { name: "View details" }).first().click()
  await expect(page.getByRole("heading", { name: "Author questions" })).toBeVisible()
  await expect.poll(() => detailRequests.length).toBe(1)
  await expect(page.getByText(/story health|continuity scan|plot analysis|character analysis|ai story advisor/i)).toHaveCount(0)
  await page.screenshot({ path: test.info().outputPath("beta-reads-in-progress-desktop.png"), fullPage: true })

  await page.getByRole("tab", { name: "Assigned" }).click()
  await expect(page.getByText("Skyward Hollow")).toBeVisible()
  await expect(page.getByText("Review Chapter 3")).toBeVisible()

  await page.getByRole("tab", { name: "Completed" }).click()
  await expect(page.getByText("The Glass Orchard")).toBeVisible()
  await expect(page.getByText("Act two beta read")).toBeVisible()
  await page.getByRole("button", { name: "View details" }).last().click()
  await expect(page.getByText(/missed 2 beta reads in a row/i)).toBeVisible()

  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByRole("tab", { name: "Completed" })).toBeVisible()
  await expect(page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).resolves.toBe(true)
  await page.screenshot({ path: test.info().outputPath("beta-reads-completed-mobile.png"), fullPage: true })
})

test("stats page shows one writing trend, progress summary, and compact breakdown", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/stats")

  const dismissCookies = page.getByRole("button", { name: /decline cookies|not now/i })
  await dismissCookies.click({ timeout: 5000 }).catch(() => {})

  await expect(page.getByRole("heading", { name: "Writing progress" })).toBeVisible()
  await expect(page.getByText("Heatmap of saved writing")).toBeVisible()
  await expect(page.getByRole("heading", { name: "Progress summary" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Breakdown" })).toBeVisible()
  await expect(page.getByText("This Week", { exact: true })).toBeVisible()
  await expect(page.getByText("Upload units used")).toBeVisible()
})

test("book overview opens the manuscript editor", async ({ page }) => {
  await installMockApi(page)
  await page.goto(BOOK_ROUTE)

  await expect(page.getByText("Open Manuscript Editor")).toBeVisible()
  await expect(page.getByRole("heading", { name: "Book overview" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Revision pressure at a glance." })).toBeVisible()
  await expect(page.getByRole("button", { name: "Create checklist" })).toBeVisible()

  const workspaceBar = page.locator('[data-testid="author-tools-nav-bar"]')
  await expect(workspaceBar).toBeVisible()
  await expect(workspaceBar.getByRole("link", { name: "Scene Workspace" })).toBeVisible()
  await expect(workspaceBar.getByRole("link", { name: "Notes Workspace" })).toBeVisible()

  const dismissCookies = page.getByRole("button", { name: /decline cookies/i })
  if (await dismissCookies.isVisible().catch(() => false)) {
    await dismissCookies.click()
  }

  await page.getByRole("button", { name: /open manuscript editor/i }).click()

  await expect(page).toHaveURL(/\/(?:[^/]+--)?book-1\/manuscript$/, { timeout: 15000 })
  await expect(page.getByRole("tab", { name: "Write" })).toHaveAttribute("aria-selected", "true")
  await expect(page.getByRole("textbox", { name: "Chapter title" })).toBeVisible()
})

test("analysis-complete overview starts with the supportive first read before critique", async ({ page }) => {
  await installMockApi(page, { activationPending: true, firstImpression: "running" })
  await page.goto(BOOK_ROUTE)

  await expect(page.getByTestId("activation-experience")).toBeVisible()
  await expect(page.getByRole("heading", { name: "What’s Working" })).toBeVisible({ timeout: 15000 })
  await expect(page.getByRole("heading", { name: "The Story LoreVia Is Seeing" })).toBeVisible()
  await expect(page.getByTestId("continuity-inbox")).toBeVisible()
  await expect(page.getByRole("heading", { name: "Evidence-backed continuity review" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Turn the read into a revision path" })).toBeVisible()
  await expect(page.getByText("Ash-dark fantasy with intimate stakes")).toBeVisible()
  await expect(page.getByText("Full coverage: all 3 requested chapters were analyzed.")).toBeVisible()
  await expect(page.getByText(/Nora and Kael's gate exchange gives the central relationship immediate pressure/i)).toBeVisible()
  await expect(page.getByRole("heading", { name: "1 findings need review" })).toBeVisible()
  const ordered = await page.evaluate(() => {
    const whatsWorking = document.querySelector('[data-testid="whats-working-section"]')
    const understanding = document.querySelector('[data-testid="story-understanding-section"]')
    const critique = document.querySelector('[data-testid="existing-analysis"]')
    const improve = document.querySelector('[data-testid="improve-section"]')
    if (!whatsWorking || !understanding || !critique || !improve) return false
    return Boolean(
      whatsWorking.compareDocumentPosition(understanding) & Node.DOCUMENT_POSITION_FOLLOWING
      && understanding.compareDocumentPosition(critique) & Node.DOCUMENT_POSITION_FOLLOWING
      && critique.compareDocumentPosition(improve) & Node.DOCUMENT_POSITION_FOLLOWING,
    )
  })
  expect(ordered).toBe(true)
  await page.getByRole("button", { name: /Nora may use gate knowledge before learning it/i }).click()
  await expect(page.getByText(/pressed her cut palm to the gate/)).toBeVisible()
  await expect(page.getByText(/Kael finally told Nora/)).toBeVisible()
  await page.getByRole("button", { name: "Accept", exact: true }).click()
  await expect(page.getByText("Marked accepted")).toBeVisible()
})

test("cached first-read reports open the activation experience without blocking", async ({ page }) => {
  await installMockApi(page, { activationPending: true, firstImpression: "cached" })
  await page.goto(BOOK_ROUTE)

  await expect(page.getByRole("heading", { name: "What’s Working" })).toBeVisible()
  await expect(page.getByText("Your first read is underway.")).toHaveCount(0)
  await expect(page.getByTestId("continuity-inbox")).toBeVisible()
})

test("failed first-read reports expose retry and existing-analysis paths", async ({ page }) => {
  await installMockApi(page, { activationPending: true, firstImpression: "failed" })
  await page.goto(BOOK_ROUTE)

  await expect(page.getByText("The first read paused")).toBeVisible()
  await expect(page.getByRole("button", { name: "Continue to existing analysis" })).toBeVisible()
  await page.getByRole("button", { name: "Continue to existing analysis" }).click()
  await expect(page.getByTestId("continuity-inbox")).toBeVisible()

  await page.getByRole("button", { name: "Retry first read" }).click()
  await expect(page.getByRole("heading", { name: "What’s Working" })).toBeVisible({ timeout: 15000 })
})

test("verified-clean continuity can complete first-read activation", async ({ page }) => {
  await installMockApi(page, { activationPending: true, activationClean: true, firstImpression: "complete" })
  const workspaceUpdates: unknown[] = []
  page.on("request", (request) => {
    if (request.url().includes("/api/v1/books/book-1/writer-workspace") && request.method() === "PUT") {
      workspaceUpdates.push(request.postDataJSON())
    }
  })
  await page.goto(BOOK_ROUTE)

  await expect(page.getByRole("heading", { name: "What’s Working" })).toBeVisible()
  await expect(page.getByTestId("continuity-inbox-clean")).toBeVisible()
  await expect(page.getByText("No supported continuity conflicts found.")).toBeVisible()
  await expect.poll(() =>
    workspaceUpdates.some((update) => (
      typeof update === "object"
      && update !== null
      && (update as { activation?: { completion_action?: string } }).activation?.completion_action === "verified_clean_scan"
    )),
  ).toBe(true)
})

test("other author projects use existing activation analysis without first read", async ({ page }) => {
  const firstImpressionRequests: string[] = []
  await installMockApi(page, { activationPending: true, workType: "other" })
  page.on("request", (request) => {
    if (request.url().includes("/advisor/first-impression")) {
      firstImpressionRequests.push(request.url())
    }
  })

  await page.goto(BOOK_ROUTE)

  await expect(page.getByTestId("activation-experience")).toBeVisible()
  await expect(page.getByRole("heading", { name: /We analyzed 3 chapters in Sky of Ash/i })).toBeVisible()
  await expect(page.getByTestId("supportive-first-read")).toHaveCount(0)
  expect(firstImpressionRequests).toHaveLength(0)
})

test("zero-project authors see first-read upload as the primary library action", async ({ page }) => {
  await installMockApi(page, { zeroProjects: true })
  await page.goto("/library")

  await expect(page.getByTestId("first-manuscript-hero")).toBeVisible()
  await expect(page.getByRole("heading", { name: "Upload your manuscript for a first read" })).toBeVisible()
  await expect(page.getByText("LoreVia begins with what is working")).toBeVisible()
  await page.getByRole("button", { name: "Upload manuscript" }).click()
  await expect(page.getByRole("dialog", { name: "Upload manuscript" })).toBeVisible()
  await expect(page.getByText("what is working first, then evidence-backed revision opportunities")).toBeVisible()
  await expect(page.getByRole("button", { name: /^Author mode$/ })).toHaveAttribute("aria-pressed", "true")
})

test("expired free owners are redirected away from author-only book routes", async ({ page }) => {
  await installMockApi(page, { userTier: "free" })
  await page.goto(`${BOOK_ROUTE}/manuscript`)

  await expect(page).toHaveURL(new RegExp(`${BOOK_ROUTE}$`))
  await expect(page.getByText("Manuscript Editor requires Author")).toBeVisible()
  await expect(page.getByRole("link", { name: "Upgrade to Author" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Compare plans" })).toBeVisible()
  await expect(page.getByText("Open Manuscript Editor")).toHaveCount(0)
})

test("export studio saves a novel preface and downloads a novel export", async ({ page }) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  const writerWorkspaceRequests: string[] = []
  page.on("request", (request) => {
    if (request.url().includes("/api/v1/books/book-1/writer-workspace") && request.method() === "GET") {
      writerWorkspaceRequests.push(request.url())
    }
  })
  await installMockApi(page)
  await page.addInitScript(() => {
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
  await page.goto(`${BOOK_ROUTE}/export`)

  await expect(page.getByRole("heading", { name: "Files & Export" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Export a manuscript" })).toBeVisible()
  expect(writerWorkspaceRequests).toEqual([])
  await hideNonProductCaptureOverlays(page)
  await page.screenshot({ path: test.info().outputPath("files-export-desktop.png"), fullPage: true })

  await page.getByRole("tab", { name: /Reader edition Publication files/ }).click()
  const novelCard = page.getByTestId("novel-export-card")
  await expect(novelCard.getByText("Novel export")).toBeVisible()
  await expect.poll(() => writerWorkspaceRequests.length).toBe(1)
  await expect(novelCard.getByLabel("Preface")).toHaveValue("A short note before the ash gates open.")
  await novelCard.getByText("Publishing details", { exact: true }).click()
  await novelCard.getByLabel("Preface").fill("A new preface for early readers.")
  await novelCard.getByLabel("Dedication").fill("For the first readers.")
  await novelCard.getByLabel("Publisher").fill("LoreVia Press")
  await novelCard.getByLabel("Export first 2 chapters only").check()
  await novelCard.getByRole("button", { name: "Save novel settings" }).click()
  await expect(page.getByText("Saved novel export settings.")).toBeVisible()
  await novelCard.getByRole("button", { name: "EPUB" }).click()

  const downloadPromise = page.waitForEvent("download")
  await novelCard.getByRole("button", { name: "Export novel" }).click()
  const download = await downloadPromise

  expect(download.suggestedFilename()).toBe("Sky-of-Ash-novel-preview.epub")
  await expect(page.getByText("Downloaded first 2-chapter sample as EPUB.")).toBeVisible()

  await novelCard.getByText("Publishing details", { exact: true }).click()
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: test.info().outputPath("files-export-mobile.png"), fullPage: true })

  expect(consoleMessages.some((message) => /Maximum update depth|ReferenceError|TypeError|Unhandled/i.test(message))).toBe(false)
  expect(pageErrors).toEqual([])
})

test("access and visibility separates sharing status from navigation recovery", async ({ page }) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  await installMockApi(page)
  await page.addInitScript(() => {
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
  await page.goto(`${BOOK_ROUTE}/visibility`)

  await expect(page.getByRole("heading", { name: "Access & Visibility" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Private workspace" })).toBeVisible()
  await expect(page.getByText("Not public", { exact: true })).toBeVisible()
  await expect(page.getByRole("link", { name: "Manage collaborators" })).toBeVisible()
  await expect(page.getByText("Hidden and visible tools")).toHaveCount(0)
  await page.screenshot({ path: test.info().outputPath("access-visibility-desktop.png"), fullPage: true })

  await page.getByText("Advanced: workspace navigation", { exact: true }).click()
  await expect(page.getByText("Hidden and visible tools")).toBeVisible()
  await expect(page.getByText("This does not change who can access the book.")).toBeVisible()

  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: test.info().outputPath("access-visibility-mobile.png"), fullPage: true })

  expect(consoleMessages.some((message) => /Maximum update depth|ReferenceError|TypeError|Unhandled/i.test(message))).toBe(false)
  expect(pageErrors).toEqual([])
})

test("book compliance opens the global legal context", async ({ page }) => {
  await installMockApi(page)
  await page.goto(`${BOOK_ROUTE}/compliance`)

  await expect(page).toHaveURL(/\/compliance$/)
  await expect(page.getByRole("heading", { name: "Security & Compliance" })).toBeVisible()
})

test("book overview shows the nav panel on mobile", async ({ page }) => {
  await installMockApi(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(BOOK_ROUTE)

  const mobileNav = page.getByRole("navigation", { name: "Book workspace" })
  await expect(mobileNav).toBeVisible()
  await expect(mobileNav.getByRole("link", { name: "Overview" })).toBeVisible()
  await expect(mobileNav.getByRole("link", { name: "Preview Draft" })).toBeVisible()
})

test("book overview keeps world-gap issue language constructive", async ({ page }) => {
  await installMockApi(page)
  await page.goto(BOOK_ROUTE)

  await expect(page.getByRole("button", { name: /World Gaps.*2 issues detected/i })).toBeVisible()
})

test("notifications surface revision digest guidance", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/notifications")

  await expect(page.getByRole("heading", { name: "Notifications" })).toBeVisible()
  await expect(page.getByText("1 unread update")).toBeVisible()
  await expect(page.getByRole("heading", { name: "2 revision risks surfaced in Sky of Ash" })).toBeVisible()
  await expect(page.getByText(/2 downstream logic risks need attention first\. Top issue:/)).toBeVisible()
  const revisionNotification = page.getByRole("article").filter({ has: page.getByRole("heading", { name: "2 revision risks surfaced in Sky of Ash" }) })
  await revisionNotification.getByRole("button", { name: "View details" }).click()
  await expect(page.getByRole("heading", { name: "Revision Details" })).toBeVisible()
  await expect(page.getByText("2 downstream logic risks need attention first.", { exact: true })).toBeVisible()
  await expect(revisionNotification.getByRole("link", { name: "Open", exact: true })).toHaveAttribute("href", "/book-1")
  await expect(page.getByRole("button", { name: /toggle notifications, 1 unread/i })).toBeVisible()

  await page.getByRole("button", { name: "Mark read" }).click()

  await expect(page.getByRole("button", { name: "Toggle notifications" })).toBeVisible()
  await expect(page.getByRole("button", { name: /toggle notifications, 1 unread/i })).toHaveCount(0)
  await expect(page.getByRole("button", { name: "Mark read" })).toHaveCount(0)
})

test("manuscript workspace loads core drafting surfaces", async ({ page }) => {
  await installMockApi(page)
  await page.goto(`${BOOK_ROUTE}/manuscript`)

  await expect(page.getByRole("button", { name: /Sky of Ash/ }).first()).toBeVisible()
  await expect(page.getByLabel("Search chapters")).toHaveCount(0)
  await expect(page.getByRole("tablist", { name: "Writing context panels" })).toHaveCount(0)
  await page.getByRole("button", { name: "Outline", exact: true }).click()
  await expect(page.getByLabel("Search chapters")).toBeVisible()
  await expect(page.getByRole("link", { name: /open workspace/i })).toBeVisible()
  const workspaceModes = page.getByRole("tablist", { name: "Manuscript workspace modes" })
  await expect(workspaceModes.getByRole("tab", { name: "Write" })).toBeVisible()
  await expect(workspaceModes.getByRole("tab", { name: "Plan" })).toBeVisible()
  await expect(workspaceModes.getByRole("tab", { name: "Analysis" })).toBeVisible()
  await expect(workspaceModes.getByRole("tab", { name: "Characters" })).toHaveCount(0)
  await expect(page.getByText(/^Gate Crossing$/)).toBeVisible()
  await page.getByRole("button", { name: "Inspector", exact: true }).click()
  const writingContextPanels = page.getByRole("tablist", { name: "Writing context panels" })
  await expect(writingContextPanels.getByRole("tab", { name: "Context" })).toBeVisible()
  await expect(page.getByText("Who opened the gate?", { exact: true })).toBeVisible()
  await expect(page.getByText("Ch. 2: Nora enters the city and hears the bells.")).toBeVisible()
  await expect(page.getByRole("link", { name: /view all threads/i })).toBeVisible()
  await expect(page.getByRole("link", { name: /view all timeline events/i })).toBeVisible()
  await workspaceModes.getByRole("tab", { name: "Plan" }).click()
  await expect(page.getByRole("spinbutton", { name: "Chapter target words" })).toHaveValue("2500")
  await expect(page.getByRole("spinbutton", { name: "Book target words" })).toHaveValue("90000")
  await expect(page.getByRole("spinbutton", { name: "Session target words" })).toHaveValue("800")
  await expect(page.getByText("No manual chapter snapshots yet.")).toBeVisible()
  await page.getByRole("button", { name: "Use template" }).first().click()
  await expect(page.getByRole("heading", { name: "Use or customize template" })).toBeVisible()
  await expect(page.getByRole("radio", { name: /chapter note/i })).toBeChecked()
  await expect(page.getByRole("radio", { name: /corkboard card/i })).toBeVisible()
  await expect(page.getByRole("radio", { name: /draft outline block/i })).toBeVisible()
  await page.getByRole("button", { name: "Close" }).click()
  await workspaceModes.getByRole("tab", { name: "Analysis" }).click()
  const analysisPanels = page.getByRole("tablist", { name: "Analysis workspace panels" })
  await expect(analysisPanels.getByRole("tab", { name: "Insights" })).toBeVisible()
  await expect(analysisPanels.getByRole("tab", { name: "Characters" })).toBeVisible()
})

test("manuscript keeps outline and inspector contextual on desktop and mobile", async ({ page }, testInfo) => {
  await installMockApi(page)
  await page.context().addCookies([{ name: "lorevia_analytics_consent", value: "false", domain: "localhost", path: "/" }])
  await page.goto(`${BOOK_ROUTE}/manuscript`)

  const outlineButton = page.getByRole("button", { name: "Outline", exact: true })
  const inspectorButton = page.getByRole("button", { name: "Inspector", exact: true })
  await expect(outlineButton).toHaveAttribute("aria-pressed", "false")
  await expect(inspectorButton).toHaveAttribute("aria-pressed", "false")
  await page.screenshot({ path: testInfo.outputPath("manuscript-focused-desktop.png"), fullPage: true })
  await inspectorButton.click()
  await expect(page.getByRole("tablist", { name: "Writing context panels" })).toBeVisible()
  await hideNonProductCaptureOverlays(page)
  await page.screenshot({ path: testInfo.outputPath("manuscript-inspector-desktop.png"), fullPage: true })
  await inspectorButton.click()

  await page.setViewportSize({ width: 390, height: 844 })
  await page.reload()
  await page.getByRole("button", { name: "Outline", exact: true }).click()
  await expect(page.getByText("Manuscript outline", { exact: true })).toBeVisible()
  await page.getByText("Manuscript outline", { exact: true }).locator("..").getByRole("button", { name: "Close" }).click()
  await page.getByRole("button", { name: "Inspector", exact: true }).click()
  await expect(page.getByText("Writing inspector", { exact: true })).toBeVisible()
  await page.getByText("Writing inspector", { exact: true }).locator("..").getByRole("button", { name: "Close" }).click()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: testInfo.outputPath("manuscript-focused-mobile.png"), fullPage: true })
})

test("manuscript scene metadata insertion requires confirmation", async ({ page }) => {
  await installMockApi(page)
  await page.goto(`${BOOK_ROUTE}/manuscript`)
  await page.getByRole("button", { name: "Outline", exact: true }).click()

  const insertMetadata = page.getByLabel("Insert metadata")
  await expect(insertMetadata).not.toBeChecked()

  await insertMetadata.click()
  const cancelDialog = page.getByRole("dialog", { name: "Insert scene metadata?" })
  await expect(cancelDialog).toBeVisible()
  await cancelDialog.getByRole("button", { name: "Cancel" }).click()
  await expect(insertMetadata).not.toBeChecked()

  await insertMetadata.click()
  const confirmDialog = page.getByRole("dialog", { name: "Insert scene metadata?" })
  await expect(confirmDialog).toBeVisible()
  await confirmDialog.getByRole("button", { name: "Insert metadata" }).click()
  await expect(insertMetadata).toBeChecked()
})

test("manuscript workspace removes a chapter from the editor rail", async ({ page }) => {
  await installMockApi(page)
  const deleteRequests: string[] = []
  page.on("request", (request) => {
    if (request.url().includes("/api/v1/books/book-1/chapters/2") && request.method() === "DELETE") {
      deleteRequests.push(request.url())
    }
  })

  await page.goto(`${BOOK_ROUTE}/manuscript`)
  await page.getByRole("button", { name: "Outline", exact: true }).click()
  const removeChapterButton = page.getByRole("button", { name: "Remove Chapter 2" })
  await expect(removeChapterButton).toBeVisible()

  await removeChapterButton.click()
  const editorConfirmDialog = page.getByRole("dialog", { name: "Remove Chapter 2?" })
  await expect(editorConfirmDialog).toBeVisible()
  await editorConfirmDialog.getByRole("button", { name: "Remove chapter", exact: true }).click()

  await expect(page.getByRole("button", { name: "Remove Chapter 2" })).toHaveCount(0)
  await expect(page.getByText(/^Gate Crossing$/)).toHaveCount(0)
  await expect(page.locator('input[value="3. River of Glass"]')).toBeVisible()
  expect(deleteRequests).toHaveLength(1)
})

test("chapter navigator removes a chapter after confirmation", async ({ page }) => {
  await installMockApi(page)
  const deleteRequests: string[] = []
  page.on("request", (request) => {
    if (request.url().includes("/api/v1/books/book-1/chapters/2") && request.method() === "DELETE") {
      deleteRequests.push(request.url())
    }
  })

  await page.goto(`${BOOK_ROUTE}/chapters`)
  const chapterRow = page.locator("article").filter({ hasText: "The Ember Gate" })
  await expect(chapterRow).toContainText("The Ember Gate")
  await chapterRow.scrollIntoViewIfNeeded()

  await chapterRow.getByRole("button", { name: "Remove" }).click()
  const cancelDialog = page.getByRole("dialog", { name: "Remove Chapter 2?" })
  await expect(cancelDialog).toBeVisible()
  await cancelDialog.getByRole("button", { name: "Cancel" }).click()
  await expect(chapterRow).toContainText("The Ember Gate")
  expect(deleteRequests).toHaveLength(0)

  await chapterRow.getByRole("button", { name: "Remove" }).click()
  const confirmDialog = page.getByRole("dialog", { name: "Remove Chapter 2?" })
  await expect(confirmDialog).toBeVisible()
  await confirmDialog.getByRole("button", { name: "Remove chapter", exact: true }).click()
  await expect(page.getByRole("status")).toContainText("Chapter 2 removed.")
  await expect(chapterRow).toHaveCount(0)
  await expect(page.locator("article").filter({ hasText: "River of Glass" })).toContainText("River of Glass")
  expect(deleteRequests).toHaveLength(1)
})

test("manuscript reprocess requires confirmation before consuming an upload", async ({ page }) => {
  await installMockApi(page)
  const reprocessRequests: string[] = []
  page.on("request", (request) => {
    if (request.url().includes("/manuscript/reprocess") && request.method() === "POST") {
      reprocessRequests.push(request.postData() ?? "")
    }
  })
  await page.goto(`${BOOK_ROUTE}/manuscript`)

  await page.getByRole("button", { name: "Reprocess manuscript" }).click()
  await expect(page.getByRole("heading", { name: "Reprocess manuscript?" })).toBeVisible()
  await expect(page.getByText(/full word count is reserved first/)).toBeVisible()
  await page.getByRole("button", { name: "Cancel" }).click()
  await expect(page.getByRole("heading", { name: "Reprocess manuscript?" })).toHaveCount(0)
  expect(reprocessRequests).toHaveLength(0)

  await page.getByRole("button", { name: "Reprocess manuscript" }).click()
  await page.getByRole("button", { name: "Reserve words and reprocess" }).click()
  await expect(page.getByText("Reprocessing started for 3 chapters. 31,500 processed words are reserved and will settle chapter by chapter.").first()).toBeVisible()
  expect(reprocessRequests).toHaveLength(1)
  expect(JSON.parse(reprocessRequests[0] ?? "{}")).toEqual({ confirm_upload_charge: true })
})

test("manuscript processing state refreshes back into a reprocess action", async ({ page }) => {
  await installMockApi(page, { manuscriptProcessing: "refresh-after-two-book-reads" })

  await page.goto(`${BOOK_ROUTE}/manuscript`)

  await expect(page.getByRole("button", { name: "Reprocess manuscript" })).toBeEnabled({ timeout: 8000 })
})

test("allowance-paused manuscript continues from its checkpoint", async ({ page }) => {
  await installMockApi(page, { manuscriptProcessing: "allowance-paused" })
  const continueRequests: string[] = []
  page.on("request", (request) => {
    if (request.url().includes("/processing/continue") && request.method() === "POST") {
      continueRequests.push(request.url())
    }
  })

  await page.goto(`${BOOK_ROUTE}/manuscript`)

  const continueButton = page.getByRole("button", { name: "Continue processing" }).first()
  await expect(continueButton).toBeVisible()
  await continueButton.click()
  await expect(page.getByText("Processing continuation started.")).toBeVisible()
  expect(continueRequests).toHaveLength(1)
})

test("token-paused manuscript shows automatic resume without a continue action", async ({ page }) => {
  await installMockApi(page, { manuscriptProcessing: "token-auto-paused" })

  await page.goto(`${BOOK_ROUTE}/manuscript`)

  await expect(page.getByText(/Reprocessing will resume automatically around/).first()).toBeVisible()
  await expect(page.getByText(/2\/4 chapters complete/).first()).toBeVisible()
  await expect(page.getByRole("button", { name: "Continue processing" })).toHaveCount(0)
})

test("manual chapter reprocess marks saved edits pending and starts without upload charge", async ({ page }) => {
  await installMockApi(page)
  const reprocessRequests: string[] = []
  const firstImpressionRequests: string[] = []
  page.on("request", (request) => {
    if (request.url().includes("/manuscript/chapters/1/reprocess") && request.method() === "POST") {
      reprocessRequests.push(request.url())
    }
    if (request.url().includes("/advisor/first-impression")) {
      firstImpressionRequests.push(request.url())
    }
  })

  await page.goto(`${BOOK_ROUTE}/manuscript`)

  const manuscriptHeader = page.getByRole("banner").filter({ has: page.getByTestId("manuscript-home-link") })
  await manuscriptHeader.getByText("More", { exact: true }).click()
  const autoReprocessToggle = page.getByLabel("Auto reprocess edits")
  await expect(autoReprocessToggle).toBeChecked()
  await autoReprocessToggle.click()
  await expect(autoReprocessToggle).not.toBeChecked()
  await manuscriptHeader.getByText("More", { exact: true }).click()
  await expect(page.getByText("Turning this off stops LoreVia from reprocessing saved edits automatically. To update story memory, open each edited chapter and click Reprocess. This adds extra steps, but can reduce token usage.")).toBeVisible()

  await page.getByRole("button", { name: "Outline", exact: true }).click()
  await page.getByRole("button", { name: /Chapter 1 Ashfall/ }).click()
  await page.locator('[contenteditable="true"]').first().fill("A new sentence for the saved chapter.")
  await page.getByRole("button", { name: "Save now" }).click()
  await expect(page.getByText("Needs reprocess")).toBeVisible()

  await page.getByRole("button", { name: "Reprocess chapter" }).click()
  await expect(page.getByText("Chapter 1 reprocessing started. This uses tokens, not a book upload.")).toBeVisible()
  await expect(page.getByText("Needs reprocess")).toHaveCount(0)
  expect(reprocessRequests).toHaveLength(1)
  expect(firstImpressionRequests).toHaveLength(0)
})

test("manuscript workspace switches into paged preview for chapter and full-book views", async ({ page }) => {
  await installMockApi(page)
  await page.goto(`${BOOK_ROUTE}/manuscript`)

  const dismissCookies = page.getByRole("button", { name: /decline cookies/i })
  if (await dismissCookies.isVisible().catch(() => false)) {
    await dismissCookies.click()
  }

  const pagedPreviewToggle = page.getByRole("button", { name: "Paged preview" })
  await pagedPreviewToggle.click()
  await expect(pagedPreviewToggle).toHaveAttribute("aria-pressed", "true")
  await expect(page.getByText("Read-only paged preview")).toBeVisible()

  const previewShell = page.locator('[data-testid="manuscript-paged-preview-shell"]')
  await expect(previewShell).toBeVisible()
  await expect.poll(async () => {
    const raw = await previewShell.getAttribute("data-preview-page-count")
    return Number(raw ?? "0")
  }).toBeGreaterThan(0)

  await page.getByRole("button", { name: "Full book" }).click()
  await expect(page.getByText("Read-only paged preview")).toBeVisible()
  await expect(page.getByText("Page 1 of")).toBeVisible()
  await expect.poll(async () => {
    const raw = await previewShell.getAttribute("data-preview-page-count")
    return Number(raw ?? "0")
  }).toBeGreaterThan(1)
  await expect.poll(async () => {
    return previewShell.evaluate((node) => Math.round(node.getBoundingClientRect().width))
  }).toBeLessThanOrEqual(830)
  await expect.poll(async () => {
    return previewShell.evaluate((node) => window.getComputedStyle(node).backgroundColor)
  }).not.toBe("rgb(5, 7, 10)")

  await previewShell.evaluate((node) => {
    const pointerId = 1
    node.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, pointerId, button: 0, clientX: 700 }))
    node.dispatchEvent(new PointerEvent("pointermove", { bubbles: true, pointerId, button: 0, clientX: 120 }))
    node.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, pointerId, button: 0, clientX: 120 }))
  })

  await expect(page.getByText("Page 2 of")).toBeVisible()
})

test("manuscript workspace reorders chapter scenes within the sidebar", async ({ page }) => {
  await installMockApi(page)
  await page.goto(`${BOOK_ROUTE}/manuscript`)

  const dismissCookies = page.getByRole("button", { name: /decline cookies/i })
  if (await dismissCookies.isVisible().catch(() => false)) {
    await dismissCookies.click()
  }

  await page.getByRole("button", { name: "Outline", exact: true }).click()
  const sceneCards = page.locator("[data-scene-id]")
  await expect(sceneCards).toHaveCount(2)
  const firstSceneCopy = page.getByTestId("scene-copy-scene-1")
  await expect(firstSceneCopy).toBeVisible()
  await expect.poll(async () => {
    return firstSceneCopy.evaluate((node) => Math.round(node.getBoundingClientRect().width))
  }).toBeGreaterThanOrEqual(220)
  await expect(sceneCards.nth(0)).toHaveAttribute("data-scene-id", "scene-1")
  await expect(sceneCards.nth(1)).toHaveAttribute("data-scene-id", "scene-2")

  const moveSceneUp = page.getByTestId("move-scene-scene-2-up")
  await moveSceneUp.scrollIntoViewIfNeeded()
  await expect(moveSceneUp).toBeEnabled()

  const reorderResponse = page.waitForResponse((response) =>
    response.request().method() === "PATCH" &&
    response.url().includes("/books/book-1/chapters/2/scenes/order") &&
    response.status() === 200
  )
  await moveSceneUp.click()
  await reorderResponse

  await expect(sceneCards.nth(0)).toHaveAttribute("data-scene-id", "scene-2")
  await expect(sceneCards.nth(1)).toHaveAttribute("data-scene-id", "scene-1")
  await expect(page.getByText("Order saved")).toBeVisible()
})

test("manuscript workspace surfaces chapter annotations in the notes rail", async ({ page }) => {
  await installMockApi(page)
  await page.goto(`${BOOK_ROUTE}/manuscript`)
  await page.getByRole("button", { name: "Outline", exact: true }).click()
  await page.getByRole("button", { name: /Chapter 2 The Ember Gate/i }).click()
  await expect(page.locator('[data-editor-key="chapter-2"]')).toBeVisible()

  await page.getByTitle("Open notes").click()
  await expect(page.getByText("New note")).toBeVisible()
  await expect(page.getByText("Notes workspace", { exact: true })).toBeVisible()
  await expect(page.getByText("Manual Editor/Chapter 2/Gate imagery.md")).toBeVisible()
  await expect(page.getByText("1 annotation anchored to this chapter.")).toBeVisible()
  await expect(page.getByText("Gate imagery", { exact: true })).toHaveCount(2)
  await page.getByPlaceholder("Chapter 2 note title").fill("Rail smoke note")
  await page.getByPlaceholder("Capture a beat, fix, continuity concern, or draft thought...").fill("Remember the gate-bell echo before the bridge.")
  await page.getByRole("button", { name: "Save note" }).click()
  await expect(page.getByRole("status")).toContainText("Saved to manuscript notes and the notes workspace.")
  await expect(page.getByText("Rail smoke note").first()).toBeVisible()
})

test("collaboration workspace creates a story-scoped share", async ({ page }) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  const activityRequests: string[] = []
  page.on("request", (request) => {
    if (/\/collaborators\/[^/]+\/activity/.test(request.url())) activityRequests.push(request.url())
  })
  await installMockApi(page)
  await page.addInitScript(() => {
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
  await page.goto(`${BOOK_ROUTE}/collaboration`)

  await expect(page.getByRole("heading", { name: "Collaborators" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "People with access" })).toBeVisible()
  expect(activityRequests).toEqual([])

  const dismissCookies = page.getByRole("button", { name: /decline cookies/i })
  if (await dismissCookies.isVisible().catch(() => false)) {
    await dismissCookies.click()
  }

  await page.getByRole("button", { name: "Invite collaborator" }).click()
  await expect(page.getByRole("combobox", { name: "Role", exact: true })).toHaveValue("commenter")
  await expect(page.getByText("Can read and leave notes without editing.")).toBeVisible()

  const emailField = page.getByLabel("Email", { exact: true })
  const nameField = page.getByLabel(/^Display name/)
  await nameField.fill("Dev Editor")
  await page.getByRole("combobox", { name: "Role" }).selectOption("developmental_editor")
  await expect(page.getByText("Can edit structure, continuity, and story arcs.")).toBeVisible()
  await page.getByText("Advanced permissions and scope").click()
  const selectedChaptersOnly = page.getByLabel("Limit to selected chapters")
  await expect(selectedChaptersOnly).not.toBeChecked()
  await expect(emailField).toBeEnabled()
  await emailField.fill("editor@example.com")
  await expect(emailField).toHaveValue("editor@example.com")
  await expect(page.getByRole("button", { name: "Grant access", exact: true })).toBeEnabled()
  
  // Wait for the save request to complete
  const savePromise = page.waitForResponse(response => 
    response.url().includes('/collaborators') && response.request().method() === 'POST'
  )
  await page.getByRole("button", { name: "Grant access", exact: true }).click()
  await savePromise

  await expect(page.getByText("Access granted.")).toBeVisible({ timeout: 15000 })
  await expect(page.getByText("Dev Editor")).toBeVisible()
  await expect(page.getByText("Edit · Story bible · Reviews · Export · Comments", { exact: true }).first()).toBeVisible()
  await page.screenshot({ path: test.info().outputPath("collaborators-desktop.png"), fullPage: true })

  await page.getByRole("button", { name: "View activity" }).first().click()
  await expect(page.getByText("Recent collaboration activity")).toBeVisible()
  await expect.poll(() => activityRequests.length).toBeGreaterThan(0)

  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: test.info().outputPath("collaborators-mobile.png"), fullPage: true })

  expect(consoleMessages.some((message) => /Maximum update depth|ReferenceError|TypeError|Unhandled/i.test(message))).toBe(false)
  expect(pageErrors).toEqual([])
})

test("beta feedback shows assignments before intent-loaded responses", async ({ page }) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  const detailRequests: string[] = []
  const readerQueueRequests: string[] = []
  page.on("request", (request) => {
    const url = request.url()
    if (/\/books\/[^/]+\/beta-reads\/[^/?]+$/.test(url)) detailRequests.push(url)
    if (/\/api\/v1\/beta-reads(?:\?|$)/.test(url)) readerQueueRequests.push(url)
  })
  await installMockApi(page)
  await page.addInitScript(() => {
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
  await page.goto(`${BOOK_ROUTE}/beta-feedback`)

  await expect(page.getByRole("heading", { name: "Beta feedback" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Assignments" })).toBeVisible()
  await expect(page.getByRole("button", { name: "New assignment" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Create beta read" })).toHaveCount(0)
  expect(detailRequests).toEqual([])
  expect(readerQueueRequests).toEqual([])

  await page.getByRole("button", { name: /reader@example.com chapter 12 feedback/i }).click()
  await expect(page.getByText("Selected assignment")).toBeVisible()
  await expect(page.getByRole("heading", { name: "Responses" })).toBeVisible()
  await expect(page.getByText("The setup is strong, but the reveal takes one paragraph too long.")).toBeVisible()
  expect(detailRequests.length).toBeGreaterThan(0)
  await page.screenshot({ path: test.info().outputPath("beta-feedback-desktop.png"), fullPage: true })

  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: test.info().outputPath("beta-feedback-mobile.png"), fullPage: true })

  expect(consoleMessages.some((message) => /Maximum update depth|ReferenceError|TypeError|Unhandled/i.test(message))).toBe(false)
  expect(pageErrors).toEqual([])
})

test("reader published layout applies book typography without mobile overflow", async ({ page }) => {
  await installMockApi(page)
  await page.goto(`${BOOK_ROUTE}/chapter/2`)

  await page.getByRole("button", { name: "Text", exact: true }).click()
  await expect(page.getByRole("button", { name: "Use published reading mode" })).toHaveAttribute("aria-pressed", "true")
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
  await expect(page.getByText("Keep the road language consistent with the later bridge beat.")).toBeVisible({ timeout: 10000 })
  await expect(page.getByText("Madhav")).toBeVisible()

  await expect(normalParagraph).toHaveCSS("font-family", /Georgia|Times New Roman|serif/i)
  await expect(normalParagraph).toHaveCSS("text-align", "justify")
  await expect(normalParagraph).toHaveCSS("margin-top", "0px")
  await expect(normalParagraph).toHaveCSS("margin-bottom", "0px")
  const desktopTextIndent = await normalParagraph.evaluate((element) => Number.parseFloat(window.getComputedStyle(element).textIndent || "0"))
  expect(desktopTextIndent).toBeGreaterThan(0)

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

  await page.getByRole("button", { name: "sans" }).click()
  await expect(normalParagraph).toHaveCSS("font-family", /Space Grotesk|Avenir Next|Segoe UI Variable Text|sans-serif/i)

  await page.getByRole("button", { name: "mono" }).click()
  await expect(normalParagraph).toHaveCSS("font-family", /SFMono-Regular|Consolas|Liberation Mono|Menlo|monospace/i)

  await page.setViewportSize({ width: 390, height: 800 })
  await expect(normalParagraph).toHaveCSS("text-align", "left")
  const hasHorizontalOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
  expect(hasHorizontalOverflow).toBe(false)
})

test("book overview renders the shared book cover asset", async ({ page }) => {
  await installMockApi(page)

  await page.goto(BOOK_ROUTE)
  await expect(page.getByAltText("Sky of Ash cover").first()).toBeVisible()
})

test("reader renders inline images from asset urls and base64 fallback", async ({ page }) => {
  await installMockApi(page)

  await page.goto(`${BOOK_ROUTE}/chapter/2`)
  await expect(page.getByAltText("Ash bridge sketch")).toBeVisible()
  await expect(page.getByText("Fallback inset")).toBeVisible()
})

test("character review surfaces unresolved relationship candidates in duplicate review mode", async ({ page }) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  await installMockApi(page)

  await page.goto(`${BOOK_ROUTE}/characters`)
  await expect(page.getByRole("heading", { name: "Character Bible" })).toBeVisible()
  await page.getByRole("button", { name: "Open menu" }).first().click()
  await page.getByRole("button", { name: "Review duplicate suggestions" }).click()
  await expect(page.getByText("Relationship review")).toBeVisible()
  await expect(page.getByText("Grete <-> Gregor's father")).toBeVisible()

  expect(consoleMessages.some((message) => /Maximum update depth exceeded/i.test(message))).toBe(false)
  expect(pageErrors.some((message) => /Maximum update depth exceeded/i.test(message))).toBe(false)
})

test("character bible follows the persisted dark theme", async ({ page }) => {
  await installMockApi(page)
  await page.addInitScript(() => {
    window.localStorage.setItem(
      "lorevia-preferences",
      JSON.stringify({
        state: {
          theme: "dark",
          timelineCollapsedSections: { characters: true, plotThreads: true, relationships: true },
        },
        version: 0,
      }),
    )
  })

  await page.goto(`${BOOK_ROUTE}/characters`)

  await expect(page.getByRole("heading", { name: "Character Bible" })).toBeVisible()
  const characterBibleShell = page.locator("[data-character-workspace]")
  await expect(characterBibleShell).toHaveClass(/bg-\[#11191a\]/)
})

test("character bible keeps the roster compact and details on demand", async ({ page }) => {
  await installMockApi(page)
  await page.addInitScript(() => {
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto(`${BOOK_ROUTE}/characters`)
  const dismissCookies = page.getByRole("button", { name: /decline cookies|not now/i })
  if (await dismissCookies.isVisible().catch(() => false)) await dismissCookies.click()

  await expect(page.getByRole("heading", { name: "Character Bible" })).toBeVisible()
  await expect(page.getByText("Gregor", { exact: true }).first()).toBeVisible()
  const detailsButton = page.getByRole("button", { name: "Details", exact: true })
  await expect(detailsButton).toHaveAttribute("aria-expanded", "false")
  await page.screenshot({ path: test.info().outputPath("characters-profile-desktop.png"), fullPage: true })

  await detailsButton.click()
  await expect(detailsButton).toHaveAttribute("aria-expanded", "true")
  await expect(page.getByRole("tab", { name: "Insights" })).toBeVisible()
  await hideNonProductCaptureOverlays(page)
  await page.screenshot({ path: test.info().outputPath("characters-details-desktop.png"), fullPage: true })
  await detailsButton.click()

  await page.setViewportSize({ width: 390, height: 844 })
  const castButton = page.getByRole("button", { name: "Cast", exact: true })
  await expect(castButton).toBeVisible()
  await castButton.click()
  await expect(page.getByText("Character roster", { exact: true })).toBeVisible()
  await page.screenshot({ path: test.info().outputPath("characters-roster-mobile.png"), fullPage: true })
  await page.getByRole("button", { name: "Close", exact: true }).click()

  await detailsButton.click()
  await expect(page.getByText("Character details", { exact: true })).toBeVisible()
  await page.screenshot({ path: test.info().outputPath("characters-details-mobile.png"), fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
})

test("world gap workspace surfaces consistency flags and the coverage watchlist", async ({ page }) => {
  await installMockApi(page)
  await page.goto(`${BOOK_ROUTE}/world-gap`)

  await expect(page.getByRole("heading", { name: "World gaps" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Canon conflicts" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Source consistency" })).toBeVisible()
  await expect(page.getByText("Conflicting definition for Northreach")).toBeVisible()
  await expect(page.getByRole("heading", { name: "Coverage watchlist" })).toBeVisible()
  await expect(page.getByText("Northreach needs a clearer canon note")).toBeVisible()
})

test("story advisor keeps the question flow quiet and presents checks as evidence rows", async ({ page }) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  await installMockApi(page)
  await page.goto(`${BOOK_ROUTE}/advisor`)

  await expect(page.locator("#advisor-tab-scan")).toBeVisible()
  const dismissCookies = page.getByRole("button", { name: /decline cookies/i })
  if (await dismissCookies.waitFor({ state: "visible", timeout: 5000 }).then(() => true).catch(() => false)) {
    await dismissCookies.click()
  }

  await expect(page.getByText("Ask the manuscript", { exact: true })).toBeVisible()
  await expect(page.getByText("What aspect of your story feels unsolved right now?", { exact: true })).toBeVisible()
  await expect(page.getByText("Retrieved Passages", { exact: true })).toHaveCount(0)
  await expect(page.getByText("Response Types", { exact: true })).toHaveCount(0)
  await page.screenshot({ path: test.info().outputPath("advisor-ask-desktop.png"), fullPage: true })

  await page.locator("#advisor-tab-scan").click()

  await expect(page.getByText(/Evidence sources: characters, character_states, plot_threads/)).toBeVisible()
  await expect(page.getByText(/1 heuristic finding · Proactive audit included/)).toBeVisible()
  await expect(page.getByText('Unresolved thread: "Who opened the gate?"')).toBeVisible()
  await expect(page.getByText("The gate mystery is still carrying the highest proactive risk in the current draft.")).toBeVisible()
  await expect(page.getByText("Warnings", { exact: true })).toBeVisible()
  await page.screenshot({ path: test.info().outputPath("advisor-checks-desktop.png"), fullPage: true })

  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByText('Unresolved thread: "Who opened the gate?"')).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: test.info().outputPath("advisor-checks-mobile.png"), fullPage: true })

  expect(consoleMessages.some((message) => /Maximum update depth|ReferenceError|TypeError|Unhandled/i.test(message))).toBe(false)
  expect(pageErrors).toEqual([])
})

test("author Ask route resolves into the Story Advisor question mode", async ({ page }) => {
  await installMockApi(page)
  await page.goto(`${BOOK_ROUTE}/ask`)

  await expect(page).toHaveURL(new RegExp(`${BOOK_ROUTE}/advisor\\?mode=ask$`))
  await expect(page.getByText("Ask the manuscript", { exact: true })).toBeVisible()
  await expect(page.getByText("Ask about the story", { exact: true })).toHaveCount(0)
})

test("reader Ask stays spoiler-scoped and uses a quiet question workspace", async ({ page }) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  await installMockApi(page, { bookMode: "reader" })
  await page.goto(`${BOOK_ROUTE}/ask`)

  const dismissCookies = page.getByRole("button", { name: /decline cookies/i })
  if (await dismissCookies.waitFor({ state: "visible", timeout: 5000 }).then(() => true).catch(() => false)) {
    await dismissCookies.click()
  }

  await expect(page.getByRole("heading", { name: "Ask about the story" })).toBeVisible()
  await expect(page.getByText("Up to Chapter 2", { exact: true })).toBeVisible()
  await expect(page.getByText("Suggested questions", { exact: true })).toBeVisible()
  await expect(page.getByLabel("Ask LoreVia a grounded question about the story")).toBeVisible()
  await expect(page.getByText("Natural Language Query", { exact: true })).toHaveCount(0)
  await page.screenshot({ path: test.info().outputPath("reader-ask-desktop.png"), fullPage: true })

  await page.getByText("Suggested questions", { exact: true }).click()
  await page.getByRole("button", { name: "Use question: When did this character last appear?" }).click()
  await page.getByRole("button", { name: "Ask", exact: true }).click()
  await expect(page.getByText("Nora last appears at the end of Chapter 2, where she leaves the ember gate with Kael.")).toBeVisible()
  await expect(page.getByRole("heading", { name: "Sources" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Jump to chapter 2" })).toHaveAttribute("href", `${BOOK_ROUTE}/chapter/2`)
  await hideNonProductCaptureOverlays(page)
  await page.screenshot({ path: test.info().outputPath("reader-ask-answer-desktop.png"), fullPage: true })

  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByRole("heading", { name: "Ask about the story" })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: test.info().outputPath("reader-ask-mobile.png"), fullPage: true })

  expect(consoleMessages.some((message) => /Maximum update depth|ReferenceError|TypeError|Unhandled/i.test(message))).toBe(false)
  expect(pageErrors).toEqual([])
})

test("editorial review keeps source, session runs, and findings in one workspace", async ({ page }) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  const editorialRequests: string[] = []
  page.on("request", (request) => {
    if (request.url().includes("editorial-review-stream")) editorialRequests.push(request.url())
  })
  await installMockApi(page)
  await page.goto(`${BOOK_ROUTE}/editorial-review`)

  const dismissCookies = page.getByRole("button", { name: /decline cookies/i })
  if (await dismissCookies.waitFor({ state: "visible", timeout: 5000 }).then(() => true).catch(() => false)) {
    await dismissCookies.click()
  }

  await expect(page.getByRole("heading", { name: "Editorial review", exact: true })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Passage" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Runs this session" })).toBeVisible()
  await expect(page.getByText("Manuscript import", { exact: true })).toHaveCount(0)
  expect(editorialRequests).toEqual([])

  await page.getByLabel("Chapter number").fill("1")
  await page.getByLabel("Passage text").fill("The gate opened, Nora ran. She spoke the blood oath before Kael could stop her.")
  await page.getByRole("button", { name: "Run review" }).click()

  await expect(page.getByText("The scene has a strong conflict turn, but Nora's gate knowledge needs earlier support.")).toBeVisible()
  await expect(page.getByText("Gate knowledge arrives after Nora uses it", { exact: true })).toBeVisible()
  await expect(page.getByText("Seed the oath before the gate", { exact: true })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Cross-referenced passages" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Chapter 1" })).toHaveAttribute("aria-pressed", "true")
  expect(editorialRequests).toHaveLength(1)
  await hideNonProductCaptureOverlays(page)
  await page.screenshot({ path: test.info().outputPath("editorial-review-desktop.png"), fullPage: true })

  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByText("Seed the oath before the gate", { exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: test.info().outputPath("editorial-review-mobile.png"), fullPage: true })

  expect(consoleMessages.some((message) => /Maximum update depth|ReferenceError|TypeError|Unhandled/i.test(message))).toBe(false)
  expect(pageErrors).toEqual([])
})

test("voice consistency runs without the max-depth console loop", async ({ page }) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  await installMockApi(page)
  await page.goto(`${BOOK_ROUTE}/voice`)

  await expect(page.getByRole("heading", { name: /sky of ash voice consistency/i })).toBeVisible()
  await expect(page.getByRole("heading", { name: "The Ember Gate" })).toBeVisible()
  await expect(page.locator("textarea")).toContainText("Nora crossed the ember gate")

  await page.getByRole("button", { name: /run voice review/i }).click()

  // Wait for the loading state to complete by checking the button text changes back
  await expect(page.getByRole("button", { name: /run voice review/i })).toBeVisible({ timeout: 15000 })

  await expect(page.getByRole("heading", { name: "Verdict" })).toBeVisible()
  await expect(page.getByText("Reviewed: Nora Vale")).toBeVisible({ timeout: 15000 })
  await expect(page.getByText("Nora sounds more formal than her baseline")).toBeVisible()

  expect(consoleMessages.some((message) => /Maximum update depth exceeded/i.test(message))).toBe(false)
  expect(pageErrors.some((message) => /Maximum update depth exceeded/i.test(message))).toBe(false)
})

test("findings overview surfaces live evidence without loading every review tool", async ({ page }) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  const reviewApiRequests: string[] = []
  page.on("request", (request) => {
    const url = request.url()
    if (/advisor|ai-beta-reader|voice-consistency/.test(url)) reviewApiRequests.push(url)
  })
  await installMockApi(page, { activationPending: true })
  await page.goto(`${BOOK_ROUTE}/analysis`)

  const dismissCookies = page.getByRole("button", { name: /decline cookies/i })
  if (await dismissCookies.waitFor({ state: "visible", timeout: 5000 }).then(() => true).catch(() => false)) {
    await dismissCookies.click()
  }

  await expect(page.getByRole("heading", { name: "Findings", exact: true })).toBeVisible()
  await expect(page.getByText("Nora may use gate knowledge before learning it", { exact: true })).toBeVisible()
  await expect(page.getByRole("link", { name: "Chapter 1" })).toHaveAttribute("href", `${BOOK_ROUTE}/chapter/1`)
  await expect(page.getByRole("heading", { name: "Manuscript review" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Structure and canon" })).toBeVisible()
  expect(reviewApiRequests).toEqual([])
  await page.screenshot({ path: test.info().outputPath("findings-desktop.png"), fullPage: true })

  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByText("Nora may use gate knowledge before learning it", { exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: test.info().outputPath("findings-mobile.png"), fullPage: true })

  expect(consoleMessages.some((message) => /Maximum update depth|ReferenceError|TypeError|Unhandled/i.test(message))).toBe(false)
  expect(pageErrors).toEqual([])
})

test("chapter reports live inside Findings and suppress empty evidence groups", async ({ page }) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  const continuityRequests: string[] = []
  page.on("request", (request) => {
    if (request.url().includes("continuity-findings")) continuityRequests.push(request.url())
  })
  await installMockApi(page, { chapterReports: true })
  await page.goto(`${BOOK_ROUTE}/reports`)

  await expect(page).toHaveURL(new RegExp(`${BOOK_ROUTE}/analysis\\?view=chapters$`))
  const dismissCookies = page.getByRole("button", { name: /decline cookies/i })
  if (await dismissCookies.waitFor({ state: "visible", timeout: 5000 }).then(() => true).catch(() => false)) {
    await dismissCookies.click()
  }

  await expect(page.getByRole("tab", { name: "Chapter reports" })).toHaveAttribute("aria-selected", "true")
  await expect(page.getByRole("heading", { name: "Chapter 1 — Ashfall" })).toBeVisible()
  await expect(page.getByText("Nora and Kael move from suspicion to a reluctant alliance.")).toBeVisible()
  await expect(page.getByText("Nora appears to know the gate rule before Chapter 2 explains how she learned it.")).toBeVisible()
  expect(continuityRequests).toEqual([])
  await page.screenshot({ path: test.info().outputPath("chapter-reports-desktop.png"), fullPage: true })

  await page.getByLabel("Filter chapter reports").selectOption("2")
  await expect(page.getByRole("heading", { name: "Chapter 2 — The Ember Gate" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Chapter 1 — Ashfall" })).toHaveCount(0)
  await expect(page.getByText("Threads resolved", { exact: true })).toBeVisible()
  await expect(page.getByText("New characters", { exact: true })).toHaveCount(0)

  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: test.info().outputPath("chapter-reports-mobile.png"), fullPage: true })

  expect(consoleMessages.some((message) => /Maximum update depth|ReferenceError|TypeError|Unhandled/i.test(message))).toBe(false)
  expect(pageErrors).toEqual([])
})

test("revision workflow resumes by step and loads each work area on intent", async ({ page }) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  const secondaryRequests: string[] = []
  page.on("request", (request) => {
    const url = request.url()
    if (/characters|story-health|chapter-reports|revision-intelligence|writer-workspace|beta-reads|revision-rounds/.test(url)) {
      secondaryRequests.push(url)
    }
  })
  await installMockApi(page, { activationPending: true, chapterReports: true })
  await page.goto(`${BOOK_ROUTE}/author-loop`)

  const dismissCookies = page.getByRole("button", { name: /decline cookies/i })
  if (await dismissCookies.waitFor({ state: "visible", timeout: 5000 }).then(() => true).catch(() => false)) {
    await dismissCookies.click()
  }

  await expect(page.getByRole("heading", { name: "Revision workflow" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Current manuscript" })).toBeVisible()
  expect(secondaryRequests).toEqual([])

  await page.getByRole("button", { name: /2 of 6 characters/i }).click()
  await expect(page.getByRole("heading", { name: "Character review" })).toBeVisible()
  await expect(page.getByText("Gregor", { exact: true }).first()).toBeVisible()
  expect(secondaryRequests.some((url) => url.includes("/characters"))).toBe(true)

  await page.getByRole("button", { name: /4 of 6 revision queue/i }).click()
  await expect(page.getByRole("heading", { name: "Revision queue", level: 2 })).toBeVisible()
  await expect(page.getByText("Chapter 2 assumption may break later payoff", { exact: true })).toBeVisible()
  expect(secondaryRequests.some((url) => url.includes("revision-intelligence"))).toBe(true)
  expect(secondaryRequests.some((url) => url.includes("writer-workspace"))).toBe(true)
  await page.screenshot({ path: test.info().outputPath("revision-workflow-desktop.png"), fullPage: true })

  await expect.poll(() => page.evaluate(() => window.localStorage.getItem("lorevia:author-loop:sky-of-ash--book-1:step"))).toBe("issues")

  await page.getByRole("button", { name: /6 of 6 reader feedback/i }).click()
  await expect(page.getByRole("heading", { name: "Reader feedback", level: 2 })).toBeVisible()
  await expect(page.getByLabel("Reader assignment")).toBeVisible()

  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: test.info().outputPath("revision-workflow-mobile.png"), fullPage: true })

  expect(consoleMessages.some((message) => /Maximum update depth|ReferenceError|TypeError|Unhandled/i.test(message))).toBe(false)
  expect(pageErrors).toEqual([])
})

test("AI Beta Reader runs chapter and manuscript checks and bridges results into revision work", async ({ page }) => {
  test.setTimeout(120_000)
  const apiRequests: string[] = []
  const consoleMessages: string[] = []
  const pageErrors: string[] = []
  page.on("request", (request) => {
    if (/\/api\/.*(?:chapters|characters|ai-beta-reader)/.test(request.url())) apiRequests.push(request.url())
  })
  page.on("console", (message) => {
    if (message.type() === "error") consoleMessages.push(message.text())
  })
  page.on("pageerror", (error) => pageErrors.push(error.message))
  await installMockApi(page)
  await page.goto(`${BOOK_ROUTE}/analysis`)

  await page.locator(`a[href="${BOOK_ROUTE}/ai-beta-reader"]`).filter({ hasText: "Check reader experience" }).click()
  await expect(page.getByRole("heading", { name: /Sky of Ash AI Beta Reader/i })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Reader report" })).toBeVisible()
  expect(apiRequests.some((url) => /\/chapters(?:\?|$)/.test(url))).toBe(false)
  expect(apiRequests.some((url) => /\/characters(?:\?|$)/.test(url))).toBe(false)
  await page.getByRole("button", { name: "New run" }).click()
  await expect(page.getByRole("heading", { name: "Configure a reader pass" })).toBeVisible()
  await page.setViewportSize({ width: 1440, height: 1000 })
  const configureOverflow = await page.evaluate(() => {
    const viewportWidth = document.documentElement.clientWidth
    const elements = Array.from(document.querySelectorAll<HTMLElement>("body *"))
      .map((element) => {
        const rect = element.getBoundingClientRect()
        return {
          className: element.className,
          right: Math.round(rect.right),
          tag: element.tagName.toLowerCase(),
          text: element.innerText?.slice(0, 80) ?? "",
          width: Math.round(rect.width),
        }
      })
      .filter((element) => element.right > viewportWidth + 1)
      .slice(0, 10)
    return {
      documentWidth: document.documentElement.scrollWidth,
      elements,
      viewportWidth,
    }
  })
  expect(configureOverflow.documentWidth, JSON.stringify(configureOverflow.elements)).toBeLessThanOrEqual(configureOverflow.viewportWidth)
  await page.screenshot({ path: test.info().outputPath("ai-beta-reader-configure.png"), fullPage: true })
  await page.getByRole("button", { name: "Run reader pass" }).click()
  await expect(page.getByText("Reading manuscript batch 2 of 2...")).toBeVisible()
  await page.screenshot({ path: test.info().outputPath("ai-beta-reader-running.png"), fullPage: true })
  await expect(page.getByRole("heading", { name: "Reader report" })).toBeVisible({ timeout: 15000 })

  await page.getByRole("tab", { name: "Overused language" }).click()
  await expect(page.getByRole("heading", { name: "“silver gate”" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Open chapter 2" })).toHaveAttribute(
    "href",
    /ai_beta_finding=term-silver-gate/,
  )

  await page.getByRole("tab", { name: "Character voices" }).click()
  await expect(page.getByRole("heading", { name: "Gregor" })).toBeVisible()
  await expect(page.getByText("42%", { exact: false }).first()).toBeVisible()

  await page.getByRole("tab", { name: "Revision priorities" }).click()
  await page.getByRole("button", { name: "Save note" }).click()
  await expect(page.getByText(/Saved finding to AI Beta Reader/i)).toBeVisible()
  await page.getByRole("button", { name: "Create revision task" }).click()
  await expect(page.getByText("Revision task created in the revision board.")).toBeVisible()
  await page.getByRole("button", { name: "Create revision task" }).click()
  await expect(page.getByText("That revision task already exists.")).toBeVisible()

  await page.getByRole("button", { name: "New run" }).click()
  await page.getByRole("radio", { name: /Full manuscript/ }).click()
  await page.getByRole("button", { name: "Run reader pass" }).click()
  await expect(page.getByRole("heading", { name: "Reader report" })).toBeVisible({ timeout: 15000 })

  await page.setViewportSize({ width: 1440, height: 1000 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: test.info().outputPath("ai-beta-reader-desktop.png"), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: test.info().outputPath("ai-beta-reader-mobile.png"), fullPage: true })
  expect(consoleMessages.some((message) => /Maximum update depth|ReferenceError|TypeError|Unhandled/i.test(message))).toBe(false)
  expect(pageErrors).toEqual([])
})

test("AI Beta Reader preserves and marks reports stale after manuscript changes", async ({ page }) => {
  await installMockApi(page, { betaReaderStale: true })
  await page.goto(`${BOOK_ROUTE}/ai-beta-reader`)

  await expect(page.getByText("This report is from an earlier manuscript version.", { exact: false })).toBeVisible()
  await expect(page.locator(`a.app-button-secondary[href="${BOOK_ROUTE}/beta-feedback"]`)).toHaveText("Human Beta Feedback")
  await expect(page.locator(`a.app-button-secondary[href="${BOOK_ROUTE}/voice"]`)).toHaveText("Voice Consistency")
})

test("voice consistency can target a selected character", async ({ page }) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  const workspaceTreeRequests: string[] = []
  page.on("request", (request) => {
    if (request.url().includes("/api/v1/books/book-1/workspace/tree")) workspaceTreeRequests.push(request.url())
  })
  await installMockApi(page, { voiceConsistency: "selected-character" })
  await page.goto(`${BOOK_ROUTE}/voice`)

  await expect(page.getByRole("heading", { name: /sky of ash voice consistency/i })).toBeVisible()
  await expect(page.locator("textarea")).toContainText("Nora crossed the ember gate")
  await page.getByLabel("Character focus", { exact: true }).selectOption({ label: "Gregor" })
  await expect(page.getByText("Focused review: Gregor")).toBeVisible()
  await page.getByRole("button", { name: /run voice review/i }).click()

  // Wait for the loading state to complete
  await expect(page.getByRole("button", { name: /run voice review/i })).toBeVisible({ timeout: 15000 })

  await expect(page.getByText("Reviewed: Gregor")).toBeVisible({ timeout: 15000 })
  await expect(page.getByText("Gregor slips into abstract explanation")).toBeVisible()
  await expect(page.getByText("74% match")).toBeVisible()
  await expect(page.getByText("Closest alternate voice: Grete (38% match)")).toBeVisible()
  expect(workspaceTreeRequests).toEqual([])

  await page.setViewportSize({ width: 1440, height: 1000 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: test.info().outputPath("voice-consistency-desktop.png"), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await expect(page.getByRole("heading", { name: "Character voice" })).toBeVisible()
  await page.screenshot({ path: test.info().outputPath("voice-consistency-mobile.png"), fullPage: true })
  expect(consoleMessages.some((message) => /Maximum update depth|ReferenceError|TypeError|Unhandled/i.test(message))).toBe(false)
  expect(pageErrors).toEqual([])
})

test("voice consistency warns when selected-character attribution is weak", async ({ page }) => {
  await installMockApi(page, { voiceConsistency: "weak-attribution" })
  await page.goto(`${BOOK_ROUTE}/voice`)

  await expect(page.getByRole("heading", { name: /sky of ash voice consistency/i })).toBeVisible()
  await expect(page.locator("textarea")).toContainText("Nora crossed the ember gate")
  await page.locator("select").nth(1).selectOption("char-grete")
  await expect(page.getByText("Focused review: Grete")).toBeVisible()
  await page.getByRole("button", { name: /run voice review/i }).click()

  // Wait for the loading state to complete
  await expect(page.getByRole("button", { name: /run voice review/i })).toBeVisible({ timeout: 15000 })

  await expect(page.getByText("Reviewed: Grete")).toBeVisible({ timeout: 15000 })
  await expect(page.getByText("Dialogue could not be confidently attributed to Grete; the review used the full submitted passage instead.")).toBeVisible()
})

test("voice consistency surfaces backend errors instead of failing silently", async ({ page }) => {
  await installMockApi(page, { voiceConsistency: "backend-error" })

  await page.goto(`${BOOK_ROUTE}/voice`)
  await expect(page.getByRole("heading", { name: /sky of ash voice consistency/i })).toBeVisible()
  await expect(page.locator("textarea")).toContainText("Nora crossed the ember gate")
  await expect(page.getByRole("button", { name: /run voice review/i })).toBeEnabled()

  await page.getByRole("button", { name: /run voice review/i }).click()

  // Wait for the loading state to complete
  await expect(page.getByRole("button", { name: /run voice review/i })).toBeVisible({ timeout: 15000 })

  await expect(page.getByText("Voice review is temporarily unavailable.")).toBeVisible({ timeout: 15000 })
})

test("book search stays behind the global search affordance and returns flat evidence", async ({ page }) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  const searchRequests: string[] = []
  page.on("request", (request) => {
    if (/\/api\/v1\/reader\/book-1\/(?:search|thematic-search)/.test(request.url())) searchRequests.push(request.url())
  })
  await installMockApi(page)
  await page.goto(`${BOOK_ROUTE}/analysis`)

  await page.getByRole("link", { name: "Search this book" }).click()
  await expect(page.getByRole("heading", { name: "Search the manuscript" })).toBeVisible()
  expect(searchRequests).toEqual([])
  await page.getByLabel("Search manuscript").fill("the gatekeeper warning")
  await page.getByRole("button", { name: "Search manuscript" }).click()
  await expect(page.getByRole("heading", { name: "Chapter 2 — The Ember Gate" })).toBeVisible()
  await expect(page.getByText("Match 1", { exact: true })).toBeVisible()
  await expect(page.getByRole("link", { name: "Open chapter 2" })).toHaveAttribute("href", `${BOOK_ROUTE}/manuscript?chapter=2`)

  await page.getByRole("tab", { name: "Themes" }).click()
  await page.getByLabel("Search manuscript").fill("inherited obligation")
  await page.getByRole("button", { name: "Search manuscript" }).click()
  await expect(page.getByText("The ash road returns as a warning about inherited obligation.")).toBeVisible()

  await page.getByRole("button", { name: "More" }).click()
  await expect(page.getByText("Search Passages", { exact: true })).toHaveCount(0)
  await page.getByRole("button", { name: "More" }).click()

  await page.setViewportSize({ width: 1440, height: 1000 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: test.info().outputPath("book-search-desktop.png"), fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: test.info().outputPath("book-search-mobile.png"), fullPage: true })
  expect(searchRequests).toHaveLength(2)
  expect(consoleMessages.some((message) => /Maximum update depth|ReferenceError|TypeError|Unhandled/i.test(message))).toBe(false)
  expect(pageErrors).toEqual([])
})

test("character bible exposes manual merge without duplicate-key warnings", async ({ page }) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  await installMockApi(page)
  await page.goto(`${BOOK_ROUTE}/characters`)

  await expect(page.getByRole("heading", { name: "Character Bible" })).toBeVisible()
  await page.getByRole("button", { name: "Open menu" }).first().click()
  await page.getByRole("button", { name: "Review duplicate suggestions" }).click()

  const startManualMergeButton = page.getByRole("button", { name: /^start manual merge$/i }).first()
  const beginManualMergeButton = page.getByRole("button", { name: /^begin manual merge$/i }).first()
  if (await startManualMergeButton.isVisible().catch(() => false)) {
    await startManualMergeButton.click()
  } else {
    await expect(beginManualMergeButton).toBeVisible()
    await beginManualMergeButton.click()
  }

  await expect(page.getByRole("heading", { name: "Manual merge" })).toBeVisible()

  expect(consoleMessages.some((message) => /same key|Keys should be unique/i.test(message))).toBe(false)
  expect(pageErrors.some((message) => /same key|Keys should be unique/i.test(message))).toBe(false)
})

test("character bible can add a manual character", async ({ page }) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  await installMockApi(page)
  await page.goto(`${BOOK_ROUTE}/characters`)

  await expect(page.getByRole("heading", { name: "Character Bible" })).toBeVisible()
  const addCharacterButton = page.getByRole("button", { name: /^add character$/i }).first()
  await expect(addCharacterButton).toBeVisible()
  await expect(addCharacterButton).toBeEnabled()
  await addCharacterButton.click()

  await expect(addCharacterButton).toHaveAttribute("aria-pressed", "true", { timeout: 15000 })
  await expect(page.getByRole("heading", { name: "New character" })).toBeVisible({ timeout: 15000 })
  await page.getByLabel("Name").fill("Aunt Dahlia")
  await page.getByLabel("First chapter").fill("2")
  await page.getByLabel("Description").fill("A precise aunt with a sharp memory.")
  const dismissCookies = page.getByRole("button", { name: /decline cookies/i })
  if (await dismissCookies.isVisible().catch(() => false)) {
    await dismissCookies.click()
  }
  await page.getByRole("button", { name: /^create character$/i }).click()

  await expect(page.getByRole("heading", { name: "Aunt Dahlia" })).toBeVisible()
  await expect(page.getByText("A precise aunt with a sharp memory.")).toBeVisible()

  expect(consoleMessages.some((message) => /Maximum update depth exceeded/i.test(message))).toBe(false)
  expect(pageErrors.some((message) => /Maximum update depth exceeded/i.test(message))).toBe(false)
})

test("character bible review queue workspace renders candidate controls without overflow", async ({ page }) => {
  await installMockApi(page)
  await page.goto(`${BOOK_ROUTE}/characters`)

  const reviewQueueButton = page.getByRole("button", { name: /^review queue$/i })
  await expect(reviewQueueButton).toBeVisible()
  await reviewQueueButton.click()

  await expect(page.getByRole("heading", { name: "Grounded review workspace" })).toBeVisible({ timeout: 15000 })
  await expect(page.getByText("Candidate summary")).toBeVisible()
  await expect(page.getByRole("heading", { name: "Gregor's sister" })).toBeVisible()
  await expect(page.getByRole("button", { name: /^promote candidate$/i })).toBeVisible()
  await expect(page.getByRole("button", { name: /^attach to selected character$/i })).toBeVisible()
  await expect(page.getByRole("button", { name: /^reject candidate$/i })).toBeVisible()

  const hasHorizontalOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
  expect(hasHorizontalOverflow).toBe(false)
})

test("character bible exposes held candidates when no visible profiles were saved", async ({ page }) => {
  await installMockApi(page, { characterBible: "review-only" })
  await page.goto(`${BOOK_ROUTE}/characters`)

  await expect(page.getByText("LoreVia held 2 extracted items for review instead of adding them automatically.")).toBeVisible({ timeout: 15000 })
  const reviewHeldCandidatesButton = page.getByRole("button", { name: /^review held candidates$/i })
  await expect(reviewHeldCandidatesButton).toBeVisible()
  await reviewHeldCandidatesButton.click()

  await expect(page.getByRole("heading", { name: "Grounded review workspace" })).toBeVisible({ timeout: 15000 })
  await expect(page.getByRole("heading", { name: "Gregor's sister" })).toBeVisible()
  await expect(page.getByRole("button", { name: /^promote candidate$/i })).toBeVisible()
})

test("relationship graph inspector responds to node and edge selection", async ({ page }) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  await installMockApi(page)
  await page.addInitScript(() => {
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
  await page.goto(`${BOOK_ROUTE}/graph`)

  const dismissCookies = page.getByRole("button", { name: /decline cookies/i })
  if (await dismissCookies.isVisible().catch(() => false)) {
    await dismissCookies.click()
  }

  await expect(page.getByRole("heading", { name: "Relationships", exact: true })).toBeVisible()
  await expect(page.getByText("Graph details", { exact: true })).toHaveCount(0)
  await expect(page.getByRole("button", { name: /arrange mode/i })).toBeVisible()
  await page.screenshot({ path: test.info().outputPath("relationship-graph-canvas-desktop.png"), fullPage: true })

  await page.waitForFunction(() => {
    const graph = (window as Window & {
      __LOREVIA_RELATIONSHIP_GRAPH__?: { selectNode?: (id: string) => void }
    }).__LOREVIA_RELATIONSHIP_GRAPH__
    return typeof graph?.selectNode === "function"
  })

  await page.evaluate(() => {
    const graph = (window as Window & {
      __LOREVIA_RELATIONSHIP_GRAPH__?: { selectNode: (id: string) => void }
    }).__LOREVIA_RELATIONSHIP_GRAPH__
    graph?.selectNode("char-gregor")
  })

  await expect(page.getByRole("heading", { name: "Gregor", exact: true })).toBeVisible()
  await expect(page.getByText("Graph details", { exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: /center node/i })).toBeVisible()
  await expect(page.getByText("Protect his family")).toBeVisible()
  await hideNonProductCaptureOverlays(page)
  await page.screenshot({ path: test.info().outputPath("relationship-graph-node-desktop.png"), fullPage: true })

  await page.evaluate(() => {
    const graph = (window as Window & {
      __LOREVIA_RELATIONSHIP_GRAPH__?: { selectEdge: (id: string) => void }
    }).__LOREVIA_RELATIONSHIP_GRAPH__
    graph?.selectEdge("edge-gregor-grete-1")
  })

  await expect(page.getByRole("heading", { name: /family/i })).toBeVisible()
  await expect(page.getByText("Gregor -> Grete")).toBeVisible()
  await expect(page.getByText("Shared facets")).toBeVisible()
  await expect(page.getByText("Gregor to Grete")).toBeVisible()
  await expect(page.getByRole("textbox", { name: "Relationship note" })).toHaveValue("Sibling bond under pressure.")
  await expect(page.getByRole("button", { name: /save correction/i })).toBeVisible()

  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByRole("dialog", { name: "Graph details" })).toBeVisible()
  await page.screenshot({ path: test.info().outputPath("relationship-graph-edge-mobile.png"), fullPage: true })
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)

  expect(consoleMessages.some((message) => /Maximum update depth exceeded/i.test(message))).toBe(false)
  expect(pageErrors.some((message) => /Maximum update depth exceeded/i.test(message))).toBe(false)
})

test("relationship evolution is a dense local graph view", async ({ page }) => {
  await installMockApi(page)
  await page.addInitScript(() => {
    document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax"
  })
  await page.setViewportSize({ width: 1440, height: 900 })
  await page.goto(`${BOOK_ROUTE}/graph?view=evolution`)

  await expect(page.getByRole("link", { name: "Evolution", exact: true })).toHaveAttribute("aria-current", "page")
  await expect(page.getByRole("heading", { name: "Gregor ↔ Grete" })).toBeVisible()
  await expect(page.getByText("Their trust breaks under the family's mounting pressure.")).toBeVisible()
  await page.screenshot({ path: test.info().outputPath("relationship-evolution-desktop.png"), fullPage: true })

  await page.setViewportSize({ width: 390, height: 844 })
  await expect(page.getByRole("heading", { name: "Gregor ↔ Mr. Samsa" })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)).toBe(false)
  await page.screenshot({ path: test.info().outputPath("relationship-evolution-mobile.png"), fullPage: true })

  await page.goto(`${BOOK_ROUTE}/relationship-evolution`)
  await expect(page).toHaveURL(new RegExp(`${BOOK_ROUTE}/graph\\?view=evolution$`))
})

test("character bible repair workspace renders preview controls without overflow", async ({ page }) => {
  await installMockApi(page)
  await page.goto(`${BOOK_ROUTE}/characters`)

  await page.getByRole("button", { name: "Open menu" }).first().click()
  const repairWorkspaceButton = page.getByRole("button", { name: /^open repair workspace$/i })
  await expect(repairWorkspaceButton).toBeEnabled()
  await repairWorkspaceButton.click()
  await expect(page.getByRole("heading", { name: "Book reprocess preview" })).toBeVisible({ timeout: 15000 })
  await expect(page.getByText("Repair controls")).toBeVisible()
  await expect(page.getByRole("button", { name: /^refresh preview$/i })).toBeVisible()
  await expect(page.getByRole("button", { name: /^apply repair plan$/i })).toBeVisible()
  await expect(page.getByText("Protected skips and chapter refreshes")).toBeVisible()

  const hasHorizontalOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
  expect(hasHorizontalOverflow).toBe(false)
})
