import { expect, test, type Page } from "@playwright/test"

import { installMockApi } from "./support/mockApi"

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

  await expect(page.getByRole("heading", { name: /keep the manuscript coherent while you revise/i })).toBeVisible()
  await expect(page.getByRole("link", { name: /^sign in$/i })).toBeVisible()
  await expect(page.getByRole("link", { name: /^start free$/i }).first()).toBeVisible()
  await expect(page.getByText("Start with the draft you already have.")).toBeVisible()
})

test("public SEO content hubs render without auth and link into article clusters", async ({ page }) => {
  await page.goto("/blog")

  await expect(page.getByRole("heading", { name: /practical guides for fiction authors/i })).toBeVisible()
  await expect(page.getByRole("link", { name: /how to keep track of characters in a novel/i }).first()).toBeVisible()

  await page.goto("/answers/how-do-i-track-character-arcs")
  await expect(page.getByRole("heading", { name: "How do I track character arcs?" })).toBeVisible()
  await expect(page.getByRole("link", { name: /how to keep track of characters in a novel/i })).toBeVisible()

  await page.goto("/demo/gregor-samsa-character-tracker")
  await expect(page.getByRole("heading", { name: /tracking gregor samsa/i })).toBeVisible()
})

test("public forum surfaces reputation and writer profile details", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/public/forum")

  await expect(page.getByRole("heading", { name: /beta novel rankings worth opening/i })).toBeVisible()
  await expect(page.getByRole("link", { name: /back to library/i })).toBeVisible()
  await expect(page.getByText("Showing 1-12 of 12 threads")).toBeVisible()
  await page.locator("select").nth(0).selectOption("top_rated")
  await page.locator("select").nth(1).selectOption("weekly")
  await expect(page.getByText("Top Rated Weekly").first()).toBeVisible()
  await expect(page.getByText("Showing 1-12 of 12 threads")).toBeVisible()
  await page.getByRole("button", { name: "General discussion" }).click()
  await page.getByPlaceholder(/general discussion headline/i).fill("How do you raise tension without chaos?")
  await page.getByPlaceholder(/what do you want advice or discussion on/i).fill("I want craft advice on building pressure in quiet scenes.")
  await page.getByRole("button", { name: "Open general thread" }).click()
  await expect(page).toHaveURL(/\/public\/forum\/forum-post-\d+$/)

  await expect(page.getByRole("heading", { name: /how do you raise tension without chaos/i })).toBeVisible()
  await expect(page.getByRole("link", { name: /^library$/i })).toBeVisible()
  await page.getByPlaceholder(/add a thoughtful public comment/i).fill("Happy to review pacing and clarity.")
  await page.getByRole("button", { name: "Post comment" }).click()
  await expect(page.getByText("Happy to review pacing and clarity.")).toBeVisible()
  await page.getByRole("button", { name: "Reply" }).first().click()
  await page.getByPlaceholder(/reply to @author/i).fill("That is exactly the section I would start with too.")
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

  await expect(page.getByRole("heading", { name: /explore public-domain demos and creator-published originals/i })).toBeVisible()
  await expect(page.getByRole("heading", { name: "Ash Gate Sample" })).toBeVisible()
  await page.getByRole("link", { name: "Open discussion" }).click()

  await expect(page).toHaveURL(/\/public\/forum\/forum-post-1$/)
  await page.goto("/public")
  await expect(page.getByRole("link", { name: "@author" })).toBeVisible()
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

  await page.getByPlaceholder("Email").fill("reader@example.com")
  await page.getByPlaceholder("Password").fill("wrong-password")
  await page.getByRole("button", { name: /^sign in$/i }).click()

  await expect(page.getByText("Invalid email or password.")).toBeVisible()
})

test("admin route returns 404 when the request is not allowed", async ({ page }) => {
  await installMockApi(page, { admin: "none" })
  await page.goto("/admin")

  await expect(page.getByText("This page could not be found.")).toBeVisible()
})

test("admin route loads the operations console for owner admins", async ({ page }) => {
  await installMockApi(page, { admin: "owner" })
  await page.goto("/admin")

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
  await expect(page.getByText("Upcoming Beta Reads")).toBeVisible()
  await expect(page.getByText("Complete reviews before the deadline.")).toBeVisible()
  await expect(page.getByText("Chapter 12 feedback - Seraphina Vale")).toBeVisible()
  await expect(page.getByRole("heading", { name: "Sky of Ash" }).first()).toBeVisible()
  await page.getByRole("button", { name: /^new project$/i }).click()
  await expect(page.getByRole("heading", { name: /upload book/i })).toBeVisible()
})

test("settings page updates the public username", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/settings")

  const usernameInput = page.locator('input[autocomplete="username"]')
  await expect(usernameInput).toHaveValue("author")
  await usernameInput.fill("storysmith")
  await page.getByRole("button", { name: /change username/i }).click()

  await expect(page.getByText("Public username updated.")).toBeVisible()
  await expect(page.getByText("@storysmith")).toBeVisible()
})

test("settings page updates promotional email preferences", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/settings")

  await expect(page.getByText("Control promotional LoreVia emails")).toBeVisible()
  await page.getByRole("button", { name: /Product updates/i }).click()

  await expect(page.getByText("Email preferences updated.")).toBeVisible()
})

test("author uploads default the manuscript byline from the public username", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/library")
  await page.getByRole("button", { name: /^new project$/i }).click()
  await page.getByRole("button", { name: /^author mode$/i }).click()

  const bylineInput = page.getByPlaceholder("Manuscript author or pen name")
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

  const dismissCookies = page.getByRole("button", { name: /not now/i })
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
  await page.goto("/book-1")

  await expect(page.getByText("Open Manuscript Editor")).toBeVisible()
  await expect(page.getByText("Know what your edit breaks before your readers do.")).toBeVisible()
  await expect(page.getByRole("button", { name: /create revision checklist/i })).toBeVisible()

  const sidebarRail = page.locator('[data-testid="author-tools-nav-rail"]')
  await expect(sidebarRail).toBeVisible()
  await sidebarRail.hover()
  await expect(sidebarRail.locator('[data-testid="author-nav-helper-overview"]')).toContainText("See progress, next steps, and the latest signals around this book.")

  const dismissCookies = page.getByRole("button", { name: /not now/i })
  if (await dismissCookies.isVisible().catch(() => false)) {
    await dismissCookies.click()
  }

  await page.getByRole("button", { name: /open manuscript editor/i }).dispatchEvent("click")

  await expect(page).toHaveURL(/\/(?:[^/]+--)?book-1\/manuscript$/)
  await expect(page.getByText("Story manuscript")).toBeVisible()
  await expect(page.getByText("Manuscript progress")).toBeVisible()
})

test("book overview shows the nav panel on mobile", async ({ page }) => {
  await installMockApi(page)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto("/book-1")

  const mobileNavPanel = page.locator('[data-testid="author-tools-nav-panel"]')
  await expect(mobileNavPanel).toBeVisible()
  await expect(mobileNavPanel.locator('[data-testid="author-nav-item-overview"]')).toContainText("Overview")
  await expect(mobileNavPanel.locator('[data-testid="author-nav-item-read"]')).toContainText("Preview Draft")
})

test("book overview keeps world-gap issue language constructive", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/book-1")

  await expect(page.getByRole("button", { name: /World Gaps.*2 review targets queued/i })).toBeVisible()
})

test("notifications surface revision digest guidance", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/notifications")

  await expect(page.getByRole("heading", { name: "Updates from your writing workspace" })).toBeVisible()
  await expect(page.getByText("Know what your edit breaks before your readers do.")).toBeVisible()
  await expect(page.getByText("2 downstream logic risks need attention first.", { exact: true })).toBeVisible()
  await expect(page.getByRole("link", { name: /open revision command center/i })).toBeVisible()
})

test("manuscript workspace loads core drafting surfaces", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/book-1/manuscript")

  await expect(page.getByRole("heading", { name: "Sky of Ash" }).first()).toBeVisible()
  await expect(page.getByPlaceholder("Search chapters")).toBeVisible()
  await expect(page.getByRole("link", { name: /open workspace/i })).toBeVisible()
  await expect(page.getByText(/^Gate Crossing$/)).toBeVisible()
})

test("manuscript workspace switches into paged preview for chapter and full-book views", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/book-1/manuscript")

  const dismissCookies = page.getByRole("button", { name: /not now/i })
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
})

test("manuscript workspace reorders chapter scenes within the sidebar", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/book-1/manuscript")

  const dismissCookies = page.getByRole("button", { name: /not now/i })
  if (await dismissCookies.isVisible().catch(() => false)) {
    await dismissCookies.click()
  }

  const sceneCards = page.locator("[data-scene-id]")
  await expect(sceneCards).toHaveCount(2)
  await expect(sceneCards.nth(0)).toHaveAttribute("data-scene-id", "scene-1")
  await expect(sceneCards.nth(1)).toHaveAttribute("data-scene-id", "scene-2")

  await page.locator('[data-scene-id="scene-2"]').scrollIntoViewIfNeeded()

  const dragHandle = page.locator('[data-scene-id="scene-2"]').getByRole("button", { name: /drag/i })
  await dragHandle.dragTo(page.locator('[data-scene-drop-slot="2:0"]'))

  await expect(sceneCards.nth(0)).toHaveAttribute("data-scene-id", "scene-2")
  await expect(sceneCards.nth(1)).toHaveAttribute("data-scene-id", "scene-1")
  await expect(page.getByText("Order saved")).toBeVisible()
})

test("manuscript workspace surfaces chapter annotations in the notes rail", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/book-1/manuscript")
  await page.getByRole("button", { name: /Chapter 2 The Ember Gate/i }).click()
  await expect(page.locator('[data-editor-key="chapter-2"]')).toBeVisible()

  const notesPane = page.locator("aside")
  await notesPane.getByRole("button", { name: /^Notes$/ }).click()
  await expect(notesPane.getByText("1 annotation anchored to this chapter.")).toBeVisible()
  await expect(notesPane.getByText("Gate imagery")).toBeVisible()
})

test("collaboration workspace creates a story-scoped share", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/book-1/collaboration")

  await expect(page.getByRole("heading", { name: "Sky of Ash sharing" })).toBeVisible()
  await expect(page.getByRole("combobox")).toHaveValue("beta_reader")
  await expect(page.getByText("Feedback-focused role for reader response.")).toBeVisible()
  await expect(page.getByText("Can edit manuscript")).toBeVisible()

  const dismissCookies = page.getByRole("button", { name: /not now/i })
  if (await dismissCookies.isVisible().catch(() => false)) {
    await dismissCookies.click()
  }

  const emailField = page.getByPlaceholder("reader@example.com")
  const nameField = page.getByPlaceholder("Display name")
  await emailField.fill("editor@example.com")
  if (await emailField.inputValue() !== "editor@example.com") {
    await emailField.fill("editor@example.com")
  }
  await expect(emailField).toHaveValue("editor@example.com")
  await nameField.fill("Dev Editor")
  await page.getByRole("combobox").selectOption("developmental_editor")
  await page.getByLabel("Can view selected chapters only").uncheck()
  await page.getByRole("button", { name: /save share/i }).click()

  await expect(page.getByText("Share saved.")).toBeVisible()
  await expect(page.getByText("Dev Editor")).toBeVisible()
  await expect(page.getByText("edit manuscript / story bible / AI scans / export / comment", { exact: true }).first()).toBeVisible()
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

  await page.goto("/book-1")
  await expect(page.getByAltText("Sky of Ash cover").first()).toBeVisible()
})

test("reader renders inline images from asset urls and base64 fallback", async ({ page }) => {
  await installMockApi(page)

  await page.goto("/book-1/chapter/2")
  await expect(page.getByAltText("Ash bridge sketch")).toBeVisible()
  await expect(page.getByText("Fallback inset")).toBeVisible()
})

test("character review surfaces unresolved relationship candidates in duplicate review mode", async ({ page }) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  await installMockApi(page)

  await page.goto("/book-1/characters")
  await expect(page.getByRole("heading", { name: "Character Bible" })).toBeVisible()
  await page.getByRole("button", { name: /^Review duplicates$/i }).click()
  await expect(page.getByText("Relationship review")).toBeVisible()
  await expect(page.getByText("Grete <-> Gregor's father")).toBeVisible()

  expect(consoleMessages.some((message) => /Maximum update depth exceeded/i.test(message))).toBe(false)
  expect(pageErrors.some((message) => /Maximum update depth exceeded/i.test(message))).toBe(false)
})

test("world gap workspace surfaces consistency flags and the coverage watchlist", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/book-1/world-gap")

  await expect(page.getByRole("heading", { name: "Grouped inconsistencies and cleanup notes" })).toBeVisible()
  await expect(page.getByText("Consistency flags")).toBeVisible()
  await expect(page.getByText("Conflicting definition for Northreach")).toBeVisible()
  await expect(page.getByText("Coverage watchlist")).toBeVisible()
  await expect(page.getByText("Northreach needs a clearer canon note")).toBeVisible()
})

test("advisor continuity scan shows metadata and proactive audit cards", async ({ page }) => {
  await installMockApi(page)
  await page.goto("/book-1/advisor")

  const dismissCookies = page.getByRole("button", { name: /not now/i })
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
  await page.goto("/book-1/voice")

  await expect(page.getByRole("heading", { name: /sky of ash voice consistency/i })).toBeVisible()
  await expect(page.getByRole("heading", { name: "The Ember Gate" })).toBeVisible()
  await expect(page.locator("textarea")).toContainText("Nora crossed the ember gate")

  await page.getByRole("button", { name: /run voice review/i }).click()

  await expect(page.getByRole("heading", { name: "Character voice consistency" })).toBeVisible()
  await expect(page.getByText("Reviewed: Nora Vale")).toBeVisible()
  await expect(page.getByText("Nora sounds more formal than her baseline")).toBeVisible()

  expect(consoleMessages.some((message) => /Maximum update depth exceeded/i.test(message))).toBe(false)
  expect(pageErrors.some((message) => /Maximum update depth exceeded/i.test(message))).toBe(false)
})

test("voice consistency surfaces backend errors instead of failing silently", async ({ page }) => {
  await installMockApi(page)
  await page.route("**/api/v1/intelligence/book-1/advisor/voice-consistency", async (route) => {
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Voice review is temporarily unavailable." }),
    })
  })

  await page.goto("/book-1/voice")
  await expect(page.getByRole("heading", { name: /sky of ash voice consistency/i })).toBeVisible()

  await page.getByRole("button", { name: /run voice review/i }).click()

  await expect(page.getByText("Voice review is temporarily unavailable.")).toBeVisible()
})

test("character bible exposes manual merge without duplicate-key warnings", async ({ page }) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  await installMockApi(page)
  await page.goto("/book-1/characters")

  await expect(page.getByRole("heading", { name: "Character Bible" })).toBeVisible()
  await expect(page.getByRole("button", { name: /^Review duplicates$/i })).toBeVisible()

  await page.getByRole("button", { name: /^Review duplicates$/i }).click()
  await expect(page.getByRole("button", { name: /^start manual merge$/i }).first()).toBeVisible()
  await page.getByRole("button", { name: /^start manual merge$/i }).first().click()

  await expect(page.getByRole("heading", { name: "Manual merge" })).toBeVisible()

  expect(consoleMessages.some((message) => /same key|Keys should be unique/i.test(message))).toBe(false)
  expect(pageErrors.some((message) => /same key|Keys should be unique/i.test(message))).toBe(false)
})

test("character bible can add a manual character", async ({ page }) => {
  const { consoleMessages, pageErrors } = watchBrowserSignals(page)
  await installMockApi(page)
  await page.goto("/book-1/characters")

  await expect(page.getByRole("heading", { name: "Character Bible" })).toBeVisible()
  await page.getByRole("button", { name: /^add character$/i }).first().click()

  await expect(page.getByRole("heading", { name: "New character" })).toBeVisible()
  await page.getByLabel("Name").fill("Aunt Dahlia")
  await page.getByLabel("First chapter").fill("2")
  await page.getByLabel("Description").fill("A precise aunt with a sharp memory.")
  await page.getByRole("button", { name: /^create character$/i }).click()

  await expect(page.getByRole("heading", { name: "Aunt Dahlia" })).toBeVisible()
  await expect(page.getByText("A precise aunt with a sharp memory.")).toBeVisible()

  expect(consoleMessages.some((message) => /Maximum update depth exceeded/i.test(message))).toBe(false)
  expect(pageErrors.some((message) => /Maximum update depth exceeded/i.test(message))).toBe(false)
})
