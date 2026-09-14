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

test("marketing home page renders the core value proposition", async ({ page }) => {
  await page.goto("/")

  await expect(page.getByRole("heading", { name: /find plot holes before your readers do/i })).toBeVisible()
  await expect(page.getByRole("link", { name: /^sign in$/i })).toBeVisible()
  await expect(page.getByRole("link", { name: /^analyze my manuscript$/i }).first()).toBeVisible()
  await expect(page.getByRole("link", { name: /^see a sample finding$/i })).toBeVisible()
  await expect(page.getByRole("link", { name: /^see a sample finding$/i })).toHaveAttribute("href", "/demo/workspace")
  await expect(page.getByText("Includes a 10-day Author trial. No payment required.").first()).toBeVisible()
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
  await expect(page.getByRole("button", { name: "Manage billing / cancel subscription" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Refund policy" })).toHaveAttribute("href", "/refund")
  await expect(page.getByRole("link", { name: "Request a refund" })).toHaveAttribute("href", /mailto:support@getlorevia\.com/)

  await page.getByRole("button", { name: "Manage billing / cancel subscription" }).click()
  await portalRequest
  await expect(page).toHaveURL(/\?mock_billing_portal=1$/)

  await page.goto("/settings")
  await expect(page.getByRole("button", { name: "Manage billing / cancel subscription" })).toBeVisible()
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

test("interactive demo reviews findings without API calls or mobile overflow", async ({ page }) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  const apiRequests: string[] = []
  page.on("request", (request) => {
    if (request.url().includes("/api/")) apiRequests.push(request.url())
  })
  await page.goto("/demo/workspace")

  await expect(page.getByRole("heading", { name: "Review Dracula continuity findings" })).toBeVisible()
  const desktopOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
  expect(desktopOverflow).toBe(false)

  await page.setViewportSize({ width: 390, height: 844 })
  await page.reload()
  await expect(page.getByText("0/3 reviewed")).toBeVisible()
  await page.getByRole("button", { name: "Add to revision plan" }).click()
  await expect(page.getByText("1/3 reviewed")).toBeVisible()
  await expect(page.getByRole("heading", { name: "Revision plan" })).toBeVisible()
  await page.getByRole("button", { name: "Reset demo" }).click()
  await expect(page.getByText("0/3 reviewed")).toBeVisible()

  const hasHorizontalOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
  expect(hasHorizontalOverflow).toBe(false)
  expect(apiRequests).toEqual([])
  expect(pageErrors).toEqual([])
  expect(consoleMessages.filter((message) => message.startsWith("[error]"))).toEqual([])
})

test("editorial hubs and articles work without auth on desktop and mobile", async ({ page, context }) => {
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

  await page.goto("/blog/how-to-build-a-scene-list-for-novel-revision")
  await expect(page.getByRole("heading", { name: /how to build a scene list that actually helps you revise/i })).toBeVisible()
  await expect(page.getByRole("navigation", { name: "Article sections" }).first()).toBeVisible()
  await page.getByRole("button", { name: "Copy article link" }).click()
  await expect(page.locator('p[aria-live="polite"]')).toHaveText("Link copied")
  await page.getByRole("button", { name: "Switch to dark mode" }).click()
  await expect(page.locator("html")).toHaveClass(/dark/)

  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/answers")
  await expect(page.getByRole("heading", { name: /start with the question on your desk/i })).toBeVisible()
  await page.getByRole("searchbox", { name: "Search answers" }).fill("character arcs")
  await expect(page.getByRole("link", { name: /how do i track character arcs/i })).toBeVisible()

  await page.goto("/answers/how-do-i-track-character-arcs")
  await expect(page.getByRole("heading", { name: /how do i track character arcs/i })).toBeVisible()
  await expect(page.getByText("Short answer", { exact: true })).toBeVisible()
  await expect(page.locator(".editorial-mobile-toc")).toBeVisible()
  await page.locator(".editorial-mobile-toc summary").click()
  await expect(page.locator('.editorial-mobile-toc a[href="#define-the-starting-logic"]')).toBeVisible()
  const mobileOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
  expect(mobileOverflow).toBe(false)

  await page.goto("/demo/gregor-samsa-character-tracker")
  await expect(page.getByRole("heading", { name: /tracking gregor samsa/i })).toBeVisible()
  expect(apiRequests).toEqual([])
  expect(pageErrors).toEqual([])
  expect(consoleMessages.filter((message) => message.startsWith("[error]"))).toEqual([])
})

test("public forum surfaces reputation and writer profile details", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/public/forum")

  await expect(page.getByRole("heading", { name: /beta novel rankings worth opening/i })).toBeVisible()
  await expect(page.getByRole("link", { name: /back to public library/i })).toBeVisible()
  await expect(page.getByText("Showing 1-12 of 12 threads")).toBeVisible()
  await page.locator("select").nth(0).selectOption("top_rated")
  await page.locator("select").nth(1).selectOption("weekly")
  await expect(page.getByText("Top Rated Weekly").first()).toBeVisible()
  await expect(page.getByText("Showing 1-12 of 12 threads")).toBeVisible()
  await page.getByRole("button", { name: "General discussion" }).click()
  await page.getByLabel(/general discussion headline/i).fill("How do you raise tension without chaos?")
  await page.getByLabel(/discussion body/i).fill("I want craft advice on building pressure in quiet scenes.")
  await page.getByRole("button", { name: "Open general thread" }).click()
  await expect(page).toHaveURL(/\/public\/forum\/forum-post-\d+$/)

  await expect(page.getByRole("heading", { name: /how do you raise tension without chaos/i })).toBeVisible()
  await expect(page.getByRole("link", { name: /^library$/i })).toBeVisible()
  await page.getByLabel(/public comment/i).fill("Happy to review pacing and clarity.")
  await page.getByRole("button", { name: "Post comment" }).click()
  await expect(page.getByText("Happy to review pacing and clarity.")).toBeVisible()
  await page.getByRole("button", { name: "Reply" }).first().click()
  await page.getByLabel(/reply to @author/i).fill("That is exactly the section I would start with too.")
  await page.getByRole("button", { name: "Post reply" }).click()
  await expect(page.getByText("That is exactly the section I would start with too.")).toBeVisible()
  await expect(page.getByRole("link", { name: "@author" }).first()).toBeVisible()
  await page.goto("/public/writers/author")

  await expect(page.getByRole("heading", { name: "@author", exact: true })).toBeVisible()
  await expect(page.getByText(/public forum status: public/i)).toBeVisible()
  await expect(page.getByRole("button", { name: /Posts \(2\)/i })).toBeVisible()
  await expect(page.getByRole("button", { name: /Comments \(1\)/i })).toBeVisible()
  await page.getByRole("button", { name: /Comments \(1\)/i }).click()
  await expect(page.getByText(/how do you keep second acts from flattening out/i)).toBeVisible()
})

test("public uploads support ranking and window selection", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/public/uploads")

  await expect(page.getByRole("heading", { name: /browse creator-published books from lorevia authors/i })).toBeVisible()
  await page.getByLabel("Rank by").selectOption("top_rated")
  await page.getByLabel("Window").selectOption("weekly")
  await expect(page.getByText("Top Rated Weekly").first()).toBeVisible()
  await expect(page.getByRole("heading", { name: "Ash Gate Sample" })).toBeVisible()
  await page.getByLabel("Search creator-published books").fill("ash")
  await expect(page.getByRole("heading", { name: "Ash Gate Sample" })).toBeVisible()
  await expect(page.getByText(/mock ranking feed for local smoke coverage/i).first()).toBeVisible()
})

test("public library cross-links safe samples and writer trust", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/public")

  await expect(page.getByRole("heading", { name: /published work for focused reading/i })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Ash Gate Sample" })).toBeVisible()
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
})

test("login surfaces an invalid-credentials error", async ({ page }) => {
  await installMockApi(page, { session: "guest", login: "unauthorized" })
  await page.goto("/login")

  await page.getByLabel("Email", { exact: true }).fill("reader@example.com")
  await page.getByLabel("Password", { exact: true }).fill("wrong-password")
  await page.getByRole("button", { name: /^sign in$/i }).click()

  await expect(page.getByText("Invalid email or password.")).toBeVisible()
})

test("auth redirects protect private pages and skip login for active sessions", async ({ page }) => {
  await page.goto("/library")
  await expect(page).toHaveURL(/\/login\?next=%2Flibrary$/)

  await installMockApi(page)
  await page.goto("/login")
  await expect(page).toHaveURL(/\/library$/)
  await expect(page.getByRole("heading", { name: "Library" })).toBeVisible()
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

test("admin route loads the operations console for owner admins", async ({ page }) => {
  await installMockApi(page, { admin: "owner" })
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
  await page.goto(`/admin?e2e=${Date.now()}`)

  await expect(page.getByRole("heading", { name: "Operations Console" })).toBeVisible()
  await expect(page.getByText("Billing setup")).toBeVisible()
  await expect(page.getByRole("heading", { name: "Moderation" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Refunds" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Admin Access" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Audit" })).toBeVisible()
})

test("library renders a mocked project and opens the upload modal", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/library")

  await expect(page.getByRole("heading", { name: "Library" })).toBeVisible()
  await expect(page.getByTestId("first-manuscript-hero")).toHaveCount(0)
  await page.keyboard.press("Control+K")
  await expect(page.getByRole("dialog", { name: "Command palette" })).toBeVisible()
  await page.getByLabel("Search commands").fill("manuscript")
  await expect(page.getByRole("option", { name: /manuscript editor: sky of ash/i })).toBeVisible()
  await page.keyboard.press("Escape")

  await expect(page.getByRole("heading", { name: "Sky of Ash" }).first()).toBeVisible()
  await page.getByRole("button", { name: /^new project$/i }).click()
  await expect(page.getByRole("dialog", { name: "Upload manuscript" })).toBeVisible()
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
  const mobileActions = page.getByRole("navigation", { name: "Primary actions" })
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
  await page.getByRole("button", { name: /change username/i }).click()

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
  await expect(page.getByRole("link", { name: "Manage preferences" })).toHaveAttribute("href", "/settings#emails")
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

test("beta reads page shows active and missed assignments without reader analysis tools", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/beta-reads")

  await expect(page.getByRole("heading", { name: "Upcoming Beta Reads" })).toBeVisible()
  await expect(page.getByText("Track assigned beta reads, deadlines, and review requirements from one place.")).toBeVisible()
  await expect(page.getByText("Chapter 12 feedback")).toBeVisible()
  await expect(page.getByText("The Lost Heir")).toBeVisible()
  await expect(page.getByRole("button", { name: /^submit feedback$/i }).first()).toBeVisible()
  await expect(page.getByText(/story health|continuity scan|plot analysis|character analysis|ai story advisor/i)).toHaveCount(0)

  await page.getByRole("button", { name: "Missed" }).click()
  await expect(page.getByText("Act two beta read")).toBeVisible()
  await expect(page.getByText("Counted toward your consecutive missed beta reads")).toBeVisible()
})

test("stats page shows the writing dashboard and todays entries", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/stats")

  const dismissCookies = page.getByRole("button", { name: /decline cookies/i })
  await dismissCookies.click({ timeout: 5000 }).catch(() => {})

  await expect(page.getByRole("heading", { name: "Writing momentum, not just account totals." })).toBeVisible()
  await page.getByText("This Week", { exact: true }).first().scrollIntoViewIfNeeded()
  await expect(page.getByText("1,202 words")).toBeVisible()
  await expect(page.getByText(/2,565/).first()).toBeVisible()
  await expect(page.getByText("Chapter XXXVI")).toBeVisible()
  await expect(page.getByText("+763 words")).toBeVisible()
  await expect(page.getByText("Heatmap of saved writing")).toBeVisible()
})

test("book overview opens the manuscript editor", async ({ page }) => {
  await installMockApi(page)
  await page.goto(BOOK_ROUTE)

  await expect(page.getByText("Open Manuscript Editor")).toBeVisible()
  await expect(page.getByText("Your author command center.")).toBeVisible()
  await expect(page.getByRole("button", { name: /create revision checklist/i })).toBeVisible()

  const sidebarRail = page.locator('[data-testid="author-tools-nav-rail"]')
  await expect(sidebarRail).toBeVisible()
  await sidebarRail.hover()
  await expect(sidebarRail.locator('[data-testid="author-nav-helper-overview"]')).toContainText("See progress, next steps, and the latest signals around this book.")
  await sidebarRail.getByRole("button", { name: "Show advanced tools" }).click()
  await expect(sidebarRail.locator('[data-testid="author-nav-item-scenes"]')).toContainText("Scene Workspace")
  await expect(sidebarRail.locator('[data-testid="author-nav-item-notes"]')).toContainText("Notes Workspace")
  await expect.poll(async () => {
    return sidebarRail.evaluate((rail) => {
      const scenes = rail.querySelector('[data-testid="author-nav-item-scenes"]')
      const notes = rail.querySelector('[data-testid="author-nav-item-notes"]')
      return Boolean(scenes && notes && scenes.compareDocumentPosition(notes) & Node.DOCUMENT_POSITION_FOLLOWING)
    })
  }).toBe(true)

  const dismissCookies = page.getByRole("button", { name: /decline cookies/i })
  if (await dismissCookies.isVisible().catch(() => false)) {
    await dismissCookies.click()
  }

  await page.getByRole("button", { name: /open manuscript editor/i }).click()

  await expect(page).toHaveURL(/\/(?:[^/]+--)?book-1\/manuscript$/, { timeout: 15000 })
  await expect(page.getByText("Story manuscript")).toBeVisible()
  await expect(page.getByText("Manuscript progress")).toBeVisible()
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
  await installMockApi(page)
  await page.goto(`${BOOK_ROUTE}/export`)

  const novelCard = page.getByTestId("novel-export-card")
  await expect(novelCard.getByText("Novel export")).toBeVisible()
  await expect(novelCard.getByLabel("Preface")).toHaveValue("A short note before the ash gates open.")
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
})

test("book overview shows the nav panel on mobile", async ({ page }) => {
  await installMockApi(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto(BOOK_ROUTE)

  const mobileNavPanel = page.locator('[data-testid="author-tools-nav-panel"]')
  await expect(mobileNavPanel).toBeVisible()
  await expect(mobileNavPanel.locator('[data-testid="author-nav-item-overview"]')).toContainText("Overview")
  await expect(mobileNavPanel.locator('[data-testid="author-nav-item-read"]')).toContainText("Preview Draft")
})

test("book overview keeps world-gap issue language constructive", async ({ page }) => {
  await installMockApi(page)
  await page.goto(BOOK_ROUTE)

  await expect(page.getByRole("button", { name: /World Gaps.*2 issues detected/i })).toBeVisible()
})

test("notifications surface revision digest guidance", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/notifications")

  await expect(page.getByRole("heading", { name: "Updates from your writing workspace" })).toBeVisible()
  await expect(page.getByText("Know what your edit breaks before your readers do.")).toBeVisible()
  await expect(page.getByText("2 downstream logic risks need attention first.", { exact: true })).toBeVisible()
  await expect(page.getByRole("link", { name: /open revision command center/i })).toBeVisible()
  await expect(page.getByRole("button", { name: /toggle notifications, 1 unread/i })).toBeVisible()

  await page.getByRole("button", { name: "Mark read" }).click()

  await expect(page.getByRole("button", { name: "Toggle notifications" })).toBeVisible()
  await expect(page.getByRole("button", { name: /toggle notifications, 1 unread/i })).toHaveCount(0)
  await expect(page.getByRole("button", { name: "Mark read" })).toHaveCount(0)
})

test("manuscript workspace loads core drafting surfaces", async ({ page }) => {
  await installMockApi(page)
  await page.goto(`${BOOK_ROUTE}/manuscript`)

  await expect(page.getByRole("heading", { name: "Sky of Ash" }).first()).toBeVisible()
  await expect(page.getByLabel("Search chapters")).toBeVisible()
  await expect(page.getByRole("link", { name: /open workspace/i })).toBeVisible()
  const workspaceModes = page.getByRole("tablist", { name: "Manuscript workspace modes" })
  await expect(workspaceModes.getByRole("tab", { name: "Write" })).toBeVisible()
  await expect(workspaceModes.getByRole("tab", { name: "Plan" })).toBeVisible()
  await expect(workspaceModes.getByRole("tab", { name: "Analysis" })).toBeVisible()
  await expect(workspaceModes.getByRole("tab", { name: "Characters" })).toHaveCount(0)
  await expect(page.getByText(/^Gate Crossing$/)).toBeVisible()
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

test("manuscript scene metadata insertion requires confirmation", async ({ page }) => {
  await installMockApi(page)
  await page.goto(`${BOOK_ROUTE}/manuscript`)

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

  await expect(page.getByRole("button", { name: "Processing 53% ~3min left" })).toBeDisabled()
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

  const autoReprocessToggle = page.getByLabel("Auto reprocess edits")
  await expect(autoReprocessToggle).toBeChecked()
  await autoReprocessToggle.click()
  await expect(autoReprocessToggle).not.toBeChecked()
  await expect(page.getByText("Turning this off stops LoreVia from reprocessing saved edits automatically. To update story memory, open each edited chapter and click Reprocess. This adds extra steps, but can reduce token usage.")).toBeVisible()

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
  await installMockApi(page)
  await page.goto(`${BOOK_ROUTE}/collaboration`)

  await expect(page.getByRole("heading", { name: /collaborators$/i })).toBeVisible()
  await expect(page.getByRole("combobox")).toHaveValue("beta_reader")
  await expect(page.getByText("Feedback-focused role for reader response.")).toBeVisible()
  await expect(page.getByText("Can edit manuscript")).toBeVisible()

  const dismissCookies = page.getByRole("button", { name: /decline cookies/i })
  if (await dismissCookies.isVisible().catch(() => false)) {
    await dismissCookies.click()
  }

  const emailField = page.getByLabel("Email", { exact: true })
  const nameField = page.getByLabel("Display name", { exact: true })
  await nameField.fill("Dev Editor")
  await page.getByLabel("Role", { exact: true }).selectOption("developmental_editor")
  await expect(page.getByText("Structure, continuity, and arc partner.")).toBeVisible()
  const selectedChaptersOnly = page.getByLabel("Can view selected chapters only")
  await selectedChaptersOnly.uncheck()
  await expect(selectedChaptersOnly).not.toBeChecked()
  await expect(emailField).toBeEnabled()
  await emailField.fill("editor@example.com")
  await expect(emailField).toHaveValue("editor@example.com")
  await expect(page.getByRole("button", { name: /save share/i })).toBeEnabled()
  
  // Wait for the save request to complete
  const savePromise = page.waitForResponse(response => 
    response.url().includes('/collaborators') && response.request().method() === 'POST'
  )
  await page.getByRole("button", { name: /save share/i }).click()
  await savePromise

  await expect(page.getByText("Share saved.")).toBeVisible({ timeout: 15000 })
  await expect(page.getByText("Dev Editor")).toBeVisible()
  await expect(page.getByText("edit manuscript / story bible / AI scans / export / comment", { exact: true }).first()).toBeVisible()
})

test("reader published layout applies book typography without mobile overflow", async ({ page }) => {
  await installMockApi(page)
  await page.goto(`${BOOK_ROUTE}/chapter/2`)

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
  await page.getByRole("button", { name: /^Review duplicates$/i }).click()
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
  const characterBibleShell = page.locator("xpath=//div[contains(@class, 'bg-[#11191a]') and contains(@class, 'text-slate-100')]").first()
  await expect(characterBibleShell).toBeVisible()
})

test("world gap workspace surfaces consistency flags and the coverage watchlist", async ({ page }) => {
  await installMockApi(page)
  await page.goto(`${BOOK_ROUTE}/world-gap`)

  await expect(page.getByRole("heading", { name: "Grouped inconsistencies and cleanup notes" })).toBeVisible()
  await expect(page.getByText("Consistency flags")).toBeVisible()
  await expect(page.getByText("Conflicting definition for Northreach")).toBeVisible()
  await expect(page.getByText("Coverage watchlist")).toBeVisible()
  await expect(page.getByText("Northreach needs a clearer canon note")).toBeVisible()
})

test("advisor continuity scan shows metadata and proactive audit cards", async ({ page }) => {
  await installMockApi(page)
  await page.goto(`${BOOK_ROUTE}/advisor`)

  const dismissCookies = page.getByRole("button", { name: /decline cookies/i })
  if (await dismissCookies.isVisible().catch(() => false)) {
    await dismissCookies.click()
  }

  await page.locator("#advisor-tab-scan").click()

  await expect(page.getByText("Data sources:")).toBeVisible()
  await expect(page.getByText("Proactive audit added")).toBeVisible()
  await expect(page.getByText('Unresolved thread: "Who opened the gate?"')).toBeVisible()
  await expect(page.getByText("The gate mystery is still carrying the highest proactive risk in the current draft.")).toBeVisible()
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

  await expect(page.getByRole("heading", { name: "Character voice consistency" })).toBeVisible()
  await expect(page.getByText("Reviewed: Nora Vale")).toBeVisible({ timeout: 15000 })
  await expect(page.getByText("Nora sounds more formal than her baseline")).toBeVisible()

  expect(consoleMessages.some((message) => /Maximum update depth exceeded/i.test(message))).toBe(false)
  expect(pageErrors.some((message) => /Maximum update depth exceeded/i.test(message))).toBe(false)
})

test("AI Beta Reader runs chapter and manuscript checks and bridges results into revision work", async ({ page }) => {
  await installMockApi(page)
  await page.goto(`${BOOK_ROUTE}/analysis`)

  await page.getByRole("link", { name: /AI Beta Reader/i }).click()
  await expect(page.getByRole("heading", { name: /Sky of Ash AI Beta Reader/i })).toBeVisible()
  await page.getByRole("button", { name: "Run again" }).click()
  await expect(page.getByText("Reading manuscript batch 2 of 2...")).toBeVisible()
  await expect(page.getByText("Report complete.")).toBeVisible({ timeout: 15000 })

  await page.getByRole("tab", { name: "Overused Language" }).click()
  await expect(page.getByRole("heading", { name: "“silver gate”" })).toBeVisible()
  await expect(page.getByRole("link", { name: "Open chapter 2" })).toHaveAttribute(
    "href",
    /ai_beta_finding=term-silver-gate/,
  )

  await page.getByRole("tab", { name: "Character Voices" }).click()
  await expect(page.getByRole("heading", { name: "Gregor" })).toBeVisible()
  await expect(page.getByText("42%", { exact: false }).first()).toBeVisible()

  await page.getByRole("tab", { name: "Revision Priorities" }).click()
  await page.getByRole("button", { name: "Save note" }).click()
  await expect(page.getByText(/Saved finding to AI Beta Reader/i)).toBeVisible()
  await page.getByRole("button", { name: "Create revision task" }).click()
  await expect(page.getByText("Revision task created in the revision board.")).toBeVisible()
  await page.getByRole("button", { name: "Create revision task" }).click()
  await expect(page.getByText("That revision task already exists.")).toBeVisible()

  await page.getByRole("radio", { name: "Full manuscript" }).click()
  await page.getByRole("button", { name: "Run again" }).click()
  await expect(page.getByText("Report complete.")).toBeVisible({ timeout: 15000 })
})

test("AI Beta Reader preserves and marks reports stale after manuscript changes", async ({ page }) => {
  await installMockApi(page, { betaReaderStale: true })
  await page.goto(`${BOOK_ROUTE}/ai-beta-reader`)

  await expect(page.getByText("This report is from an earlier manuscript version.", { exact: false })).toBeVisible()
  await expect(page.getByRole("link", { name: "Human Beta Feedback" })).toHaveAttribute("href", `${BOOK_ROUTE}/beta-feedback`)
  await expect(page.getByRole("link", { name: "Voice Consistency" })).toHaveAttribute("href", `${BOOK_ROUTE}/voice`)
})

test("voice consistency can target a selected character", async ({ page }) => {
  await installMockApi(page, { voiceConsistency: "selected-character" })
  await page.goto(`${BOOK_ROUTE}/voice`)

  await expect(page.getByRole("heading", { name: /sky of ash voice consistency/i })).toBeVisible()
  await expect(page.locator("textarea")).toContainText("Nora crossed the ember gate")
  await page.locator('label:has-text("Character focus") select').selectOption({ label: "Gregor" })
  await expect(page.getByText("Focused review: Gregor")).toBeVisible()
  await page.getByRole("button", { name: /run voice review/i }).click()

  // Wait for the loading state to complete
  await expect(page.getByRole("button", { name: /run voice review/i })).toBeVisible({ timeout: 15000 })

  await expect(page.getByText("Reviewed: Gregor")).toBeVisible({ timeout: 15000 })
  await expect(page.getByText("Gregor slips into abstract explanation")).toBeVisible()
  await expect(page.getByText("74% match")).toBeVisible()
  await expect(page.getByText("Closest alternate voice: Grete (38% match)")).toBeVisible()
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

test("character bible exposes manual merge without duplicate-key warnings", async ({ page }) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  await installMockApi(page)
  await page.goto(`${BOOK_ROUTE}/characters`)

  await expect(page.getByRole("heading", { name: "Character Bible" })).toBeVisible()
  await expect(page.getByRole("button", { name: /^Review duplicates$/i })).toBeVisible()

  await page.getByRole("button", { name: /^Review duplicates$/i }).click()

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
  await page.goto(`${BOOK_ROUTE}/graph`)

  const dismissCookies = page.getByRole("button", { name: /decline cookies/i })
  if (await dismissCookies.isVisible().catch(() => false)) {
    await dismissCookies.click()
  }

  await expect(page.getByRole("heading", { name: "Relationship graph", exact: true })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Read the map", exact: true })).toBeVisible()

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
  await expect(page.getByRole("button", { name: /center node/i })).toBeVisible()
  await expect(page.getByText("Protect his family")).toBeVisible()

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

  expect(consoleMessages.some((message) => /Maximum update depth exceeded/i.test(message))).toBe(false)
  expect(pageErrors.some((message) => /Maximum update depth exceeded/i.test(message))).toBe(false)
})

test("character bible repair workspace renders preview controls without overflow", async ({ page }) => {
  await installMockApi(page)
  await page.goto(`${BOOK_ROUTE}/characters`)

  const repairWorkspaceButton = page.getByRole("button", { name: /^repair workspace$/i })
  await expect(repairWorkspaceButton).toBeVisible()
  await expect(repairWorkspaceButton).toBeEnabled()
  await repairWorkspaceButton.click()

  await expect(repairWorkspaceButton).toHaveAttribute("aria-pressed", "true", { timeout: 15000 })
  await expect(page.getByRole("heading", { name: "Book reprocess preview" })).toBeVisible({ timeout: 15000 })
  await expect(page.getByText("Repair controls")).toBeVisible()
  await expect(page.getByRole("button", { name: /^refresh preview$/i })).toBeVisible()
  await expect(page.getByRole("button", { name: /^apply repair plan$/i })).toBeVisible()
  await expect(page.getByText("Protected skips and chapter refreshes")).toBeVisible()

  const hasHorizontalOverflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
  expect(hasHorizontalOverflow).toBe(false)
})
