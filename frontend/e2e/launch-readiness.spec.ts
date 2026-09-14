import { expect, test, type Page } from "@playwright/test"
import { mkdir } from "node:fs/promises"

import { installMockApi } from "./support/mockApi"

const BOOK_ROUTE = "/sky-of-ash--book-1"
const CAPTURE_AUDIT = process.env.CAPTURE_UI_AUDIT === "1"
const REQUESTED_AUTH_ROUTE_NAMES = new Set(
  (process.env.UI_AUDIT_ROUTE_NAMES ?? "")
    .split(",")
    .map((name) => name.trim())
    .filter(Boolean),
)

const authenticatedRoutes = [
  { name: "library", path: "/library" },
  { name: "settings", path: "/settings" },
  { name: "upgrade", path: "/upgrade" },
  { name: "stats", path: "/stats" },
  { name: "notifications", path: "/notifications" },
  { name: "beta-reads", path: "/beta-reads" },
  { name: "notes", path: "/notes" },
  { name: "chats", path: "/chats" },
  { name: "series", path: "/series" },
  { name: "quotes", path: "/quotes" },
  { name: "add-chapter", path: "/library/add-chapter" },
  { name: "book-overview", path: BOOK_ROUTE },
  { name: "manuscript", path: `${BOOK_ROUTE}/manuscript` },
  { name: "chapters", path: `${BOOK_ROUTE}/chapters` },
  { name: "chapter-reader", path: `${BOOK_ROUTE}/chapter/2` },
  { name: "characters", path: `${BOOK_ROUTE}/characters` },
  { name: "relationships", path: `${BOOK_ROUTE}/graph` },
  { name: "timeline", path: `${BOOK_ROUTE}/timeline` },
  { name: "plot-threads", path: `${BOOK_ROUTE}/plot-threads` },
  { name: "foreshadowing", path: `${BOOK_ROUTE}/foreshadowing` },
  { name: "world-gap", path: `${BOOK_ROUTE}/world-gap` },
  { name: "series-wiki", path: `${BOOK_ROUTE}/cross-book-wiki` },
  { name: "analysis", path: `${BOOK_ROUTE}/analysis` },
  { name: "advisor", path: `${BOOK_ROUTE}/advisor` },
  { name: "editorial-review", path: `${BOOK_ROUTE}/editorial-review` },
  { name: "voice", path: `${BOOK_ROUTE}/voice` },
  { name: "reports", path: `${BOOK_ROUTE}/reports` },
  { name: "beta-feedback", path: `${BOOK_ROUTE}/beta-feedback` },
  { name: "summaries", path: `${BOOK_ROUTE}/summaries` },
  { name: "author-loop", path: `${BOOK_ROUTE}/author-loop` },
  { name: "ai-beta-reader", path: `${BOOK_ROUTE}/ai-beta-reader` },
  { name: "ask-lorevia", path: `${BOOK_ROUTE}/ask` },
  { name: "book-notes", path: `${BOOK_ROUTE}/notes` },
  { name: "scenes", path: `${BOOK_ROUTE}/scenes` },
  { name: "search", path: `${BOOK_ROUTE}/search` },
  { name: "export", path: `${BOOK_ROUTE}/export` },
  { name: "collaboration", path: `${BOOK_ROUTE}/collaboration` },
  { name: "visibility", path: `${BOOK_ROUTE}/visibility` },
  { name: "book-compliance", path: `${BOOK_ROUTE}/compliance` },
  { name: "relationship-evolution", path: `${BOOK_ROUTE}/relationship-evolution` },
] as const

const selectedAuthenticatedRoutes = REQUESTED_AUTH_ROUTE_NAMES.size > 0
  ? authenticatedRoutes.filter((route) => REQUESTED_AUTH_ROUTE_NAMES.has(route.name))
  : authenticatedRoutes

const publicRoutes = [
  { name: "home", path: "/" },
  { name: "login", path: "/login" },
  { name: "register", path: "/register" },
  { name: "forgot-password", path: "/forgot-password" },
  { name: "pricing", path: "/pricing" },
  { name: "demo", path: "/demo" },
  { name: "demo-workspace", path: "/demo/workspace" },
  { name: "demo-character", path: "/demo/gregor-samsa-character-tracker" },
  { name: "blog", path: "/blog" },
  { name: "blog-article", path: "/blog/how-to-build-a-scene-list-for-novel-revision" },
  { name: "answers", path: "/answers" },
  { name: "answer", path: "/answers/how-do-i-track-character-arcs" },
  { name: "compare", path: "/compare" },
  { name: "comparison", path: "/compare/scrivener" },
  { name: "public-library", path: "/public" },
  { name: "public-uploads", path: "/public/uploads" },
  { name: "public-analytics", path: "/public/analytics" },
  { name: "public-forum", path: "/public/forum" },
  { name: "public-post", path: "/public/forum/forum-post-1" },
  { name: "public-writer", path: "/public/writers/author" },
  { name: "public-book", path: "/public/public-book-1" },
  { name: "public-chapter", path: "/public/public-book-1/chapter/1" },
  { name: "contact", path: "/contact" },
  { name: "status", path: "/status" },
  { name: "privacy", path: "/privacy" },
  { name: "terms", path: "/terms" },
  { name: "refund", path: "/refund" },
  { name: "copyright", path: "/copyright" },
  { name: "compliance", path: "/compliance" },
  { name: "eula", path: "/eula" },
  { name: "font-notice", path: "/font-notice" },
] as const

test("authenticated launch surfaces avoid clipping, duplicate ids, and fixed-layer collisions", async ({ page }) => {
  test.setTimeout(600_000)
  await installMockApi(page)
  if (CAPTURE_AUDIT) await mkdir("test-results/ui-audit", { recursive: true })
  const violations: string[] = []

  for (const viewport of [
    { name: "desktop", width: 1440, height: 900 },
    { name: "mobile", width: 390, height: 844 },
  ] as const) {
    await page.setViewportSize(viewport)
    for (const route of selectedAuthenticatedRoutes) {
      await page.goto(route.path)
      await expect(page.locator("body")).toBeVisible()
      await page.locator("h1, h2").filter({ visible: true }).first().waitFor({ state: "visible", timeout: 15_000 })
      await page.waitForTimeout(100)

      const audit = await collectLayoutAudit(page)
      collectViolations(violations, route.path, viewport.name, audit)

      if (CAPTURE_AUDIT && ["library", "book-overview", "manuscript", "characters"].includes(route.name)) {
        await page.screenshot({
          path: `test-results/ui-audit/${route.name}-${viewport.name}.png`,
          fullPage: false,
        })
      }
    }
  }

  expect(violations).toEqual([])
})

test("public launch surfaces avoid clipping, unnamed fields, and fixed-layer collisions", async ({ page }) => {
  test.setTimeout(480_000)
  await installMockApi(page, { session: "guest" })
  const violations: string[] = []

  for (const viewport of [
    { name: "desktop", width: 1440, height: 900 },
    { name: "mobile", width: 390, height: 844 },
  ] as const) {
    await page.setViewportSize(viewport)
    for (const route of publicRoutes) {
      await page.goto(route.path)
      await expect(page.locator("body")).toBeVisible()
      await page.locator("h1, h2").filter({ visible: true }).first().waitFor({ state: "visible", timeout: 15_000 })
      await page.waitForTimeout(100)

      const audit = await collectLayoutAudit(page)
      collectViolations(violations, route.path, viewport.name, audit)
    }
  }

  expect(violations).toEqual([])
})

function collectViolations(
  violations: string[],
  path: string,
  viewport: string,
  audit: Awaited<ReturnType<typeof collectLayoutAudit>>,
) {
  if (audit.horizontalOverflow) violations.push(`${path} has horizontal document overflow at ${viewport}: ${JSON.stringify(audit.overflowingElements)}`)
  if (audit.duplicateIds.length > 0) violations.push(`${path} has duplicate DOM ids at ${viewport}: ${JSON.stringify(audit.duplicateIds)}`)
  if (audit.clippedControls.length > 0) violations.push(`${path} clips interactive controls at ${viewport}: ${JSON.stringify(audit.clippedControls)}`)
  if (audit.unlabelledFields.length > 0) violations.push(`${path} has unnamed form fields at ${viewport}: ${JSON.stringify(audit.unlabelledFields)}`)
  if (audit.fixedCollisions.length > 0) violations.push(`${path} has overlapping fixed controls at ${viewport}: ${JSON.stringify(audit.fixedCollisions)}`)
}

async function collectLayoutAudit(page: Page) {
  return page.evaluate(() => {
    type Box = { label: string; x: number; y: number; width: number; height: number }
    const viewportWidth = document.documentElement.clientWidth
    const visible = (element: Element) => {
      const rect = element.getBoundingClientRect()
      const style = window.getComputedStyle(element)
      return rect.width > 0
        && rect.height > 0
        && style.display !== "none"
        && style.visibility !== "hidden"
        && Number(style.opacity || "1") > 0.05
        && element.getAttribute("aria-hidden") !== "true"
        && !element.closest("[inert]")
    }
    const labelFor = (element: Element) => (
      element.getAttribute("aria-label")
      || element.getAttribute("title")
      || element.textContent
      || element.tagName
    ).trim().replace(/\s+/g, " ").slice(0, 80)
    const boxFor = (element: Element): Box => {
      const rect = element.getBoundingClientRect()
      return {
        label: labelFor(element),
        x: Math.round(rect.x),
        y: Math.round(rect.y),
        width: Math.round(rect.width),
        height: Math.round(rect.height),
      }
    }
    const isInsideHorizontalScroller = (element: Element) => {
      let ancestor = element.parentElement
      while (ancestor && ancestor !== document.body) {
        const style = window.getComputedStyle(ancestor)
        if (
          (style.overflowX === "auto" || style.overflowX === "scroll")
          && ancestor.scrollWidth > ancestor.clientWidth + 1
        ) return true
        ancestor = ancestor.parentElement
      }
      return false
    }

    const ids = Array.from(document.querySelectorAll<HTMLElement>("body [id]:not(script):not(style)"))
      .map((element) => element.id)
      .filter(Boolean)
    const duplicateIds = [...new Set(ids.filter((id, index) => ids.indexOf(id) !== index))]

    const clippedControls = Array.from(document.querySelectorAll("a[href], button, input, select, textarea, [role='button']"))
      .filter(visible)
      .filter((element) => !isInsideHorizontalScroller(element))
      .map(boxFor)
      .filter((box) => box.x < -1 || box.x + box.width > viewportWidth + 1)

    const unlabelledFields = Array.from(document.querySelectorAll<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>("input:not([type='hidden']), textarea, select"))
      .filter(visible)
      .filter((element) => (
        element.labels?.length === 0
        && !element.getAttribute("aria-label")
        && !element.getAttribute("aria-labelledby")
        && !element.getAttribute("title")
      ))
      .map(boxFor)

    const fixedElements = Array.from(document.querySelectorAll("body *"))
      .filter((element) => {
        if (!visible(element)) return false
        const style = window.getComputedStyle(element)
        const rect = element.getBoundingClientRect()
        return style.position === "fixed"
          && style.pointerEvents !== "none"
          && rect.width >= 20
          && rect.height >= 20
          && rect.bottom > 0
          && rect.top < window.innerHeight
          && rect.right > 0
          && rect.left < window.innerWidth
      })

    const fixedCollisions: Array<{ first: Box; second: Box }> = []
    fixedElements.forEach((first, index) => {
      fixedElements.slice(index + 1).forEach((second) => {
        if (first.contains(second) || second.contains(first)) return
        const left = first.getBoundingClientRect()
        const right = second.getBoundingClientRect()
        const overlapWidth = Math.min(left.right, right.right) - Math.max(left.left, right.left)
        const overlapHeight = Math.min(left.bottom, right.bottom) - Math.max(left.top, right.top)
        if (overlapWidth > 8 && overlapHeight > 8) {
          fixedCollisions.push({ first: boxFor(first), second: boxFor(second) })
        }
      })
    })

    const overflowingElements = document.documentElement.scrollWidth > viewportWidth + 1
      ? Array.from(document.querySelectorAll("body *"))
          .filter(visible)
          .filter((element) => !isInsideHorizontalScroller(element))
          .map(boxFor)
          .filter((box) => box.x < -1 || box.x + box.width > viewportWidth + 1)
          .sort((first, second) => second.width - first.width)
          .slice(0, 12)
      : []

    return {
      horizontalOverflow: document.documentElement.scrollWidth > viewportWidth + 1,
      overflowingElements,
      duplicateIds,
      clippedControls,
      unlabelledFields,
      fixedCollisions,
    }
  })
}
