import { expect, test, type Page } from "@playwright/test"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"
import type { WorldBuildingDocumentDetail, WorldElement, WorldGapResult, WorldNote } from "@/types/world-building"

const path = "/sky-of-ash--book-1/world-gap"
const base = "/api/v1/intelligence/book-1/world-building"
const now = "2026-10-10T10:00:00Z"
const source = (id = "doc-1", title = "Canon source"): WorldBuildingDocumentDetail => ({ id, book_id: "book-1", title, text: "The gate opens only at dawn.", word_count: 7, is_active: true, created_at: now, updated_at: now })
const note = (id = "note-1", status = "open"): WorldNote => ({ id, book_id: "book-1", title: "Clarify the gate rule", body: "The keeper opens it at night.", note_type: "world_gap", chapter_number: 2, priority: "high", status, created_at: now, updated_at: now })
const element: WorldElement = { id: "element-1", book_id: "book-1", name: "Dawn Gate", description: "A gate governed by the first light.", source_scope: "worldbuilding", element_type: "location", dependencies: [], usage_count: 2, edited_by_author: false, is_series_canonical: false, created_at: now, updated_at: now, aliases: [], provenance: [], claims: [], chapter_numbers: [2], chapter_count: 1, summary_mentions: 1, narrative_modes: [], author_override: false, suggestions: [{ id: "suggestion-1", title: "Name the exception", description: "Explain how the keeper can open the gate after sunset." }] }
const gap: WorldGapResult = { mode: "gap_detection", generated_at: now, gap_categories: {}, priority_gaps: [], consistency_flags: [], world_documents: [source()], world_elements: [element], gap_groups: [{ key: "rules", label: "Canon rules", items: [{ id: "gap-1", category: "canon_conflict", severity: "high", title: "The gate opens after sunset", description: "The manuscript and source use different opening rules.", suggested_fix: "Explain the keeper's exception.", priority: 8, confidence: .8, provenance: {}, world_document_id: "doc-1", world_document_title: "Canon source", world_evidence: "The gate opens only at dawn.", story_evidence: "The keeper opened the gate beneath the moon.", story_chapter_number: 2 }] }] }

async function installWorld(page: Page) {
  await installMockApi(page)
  await page.addInitScript(() => { if (!localStorage.getItem("lorevia-preferences")) localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 })); document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax" })
  const state = { documents: [source(), source("doc-2", "Second source")], notes: [note()], analysis: structuredClone(gap), elements: [structuredClone(element)], fail: new Set<string>(), calls: [] as string[], aliases: [] as { id: string; canonical_name: string; aliases: string[] }[] }
  await page.route(`**${base}/**`, async (route) => {
    const suffix = new URL(route.request().url()).pathname.slice(base.length)
    const method = route.request().method(); const call = `${method} ${suffix}`; state.calls.push(call)
    if (state.fail.has(call)) return route.fulfill({ status: 503, json: { detail: `Temporarily unavailable: ${suffix}` } })
    if (suffix === "/bootstrap") return route.fulfill({ json: { documents: state.documents, notes: state.notes, elements: state.elements, canon_overrides: state.aliases, wiki: [], stats: null, gap_analysis: state.analysis } })
    if (suffix === "/gaps") return route.fulfill({ json: state.analysis })
    if (suffix === "/elements") return route.fulfill({ json: state.elements })
    if (suffix === "/documents" && method === "GET") return route.fulfill({ json: state.documents })
    if (suffix === "/documents" && method === "POST") {
      const body = route.request().postData() ?? ""
      const text = /name="text"\r\n\r\n([\s\S]*?)\r\n--/.exec(body)?.[1] ?? "Imported reference text."
      const title = /name="title"\r\n\r\n([\s\S]*?)\r\n--/.exec(body)?.[1] ?? "Imported source"
      const created = { ...source(`doc-${state.documents.length + 1}`, title), text }
      state.documents = body.includes('name="replace_existing"\r\n\r\ntrue') ? [created] : [...state.documents, created]
      return route.fulfill({ json: [created] })
    }
    if (suffix.startsWith("/documents/")) {
      const id = suffix.split("/").at(-1); const current = state.documents.find((item) => item.id === id)
      if (method === "DELETE") { state.documents = state.documents.filter((item) => item.id !== id); return route.fulfill({ status: 204 }) }
      if (!current) return route.fulfill({ status: 404, json: { detail: "Source not found" } })
      if (method === "PATCH") Object.assign(current, route.request().postDataJSON())
      return route.fulfill({ json: current })
    }
    if (suffix === "/notes" && method === "POST") { const created = { ...note(`note-${state.notes.length + 1}`), ...route.request().postDataJSON() }; state.notes.unshift(created); return route.fulfill({ json: created }) }
    if (suffix === "/notes") return route.fulfill({ json: state.notes })
    if (suffix.startsWith("/notes/by-chapter/")) return route.fulfill({ json: state.notes.filter((item) => item.chapter_number === Number(suffix.split("/").at(-1))) })
    if (suffix.startsWith("/notes/")) {
      const id = suffix.split("/")[2]
      if (method === "DELETE") { state.notes = state.notes.filter((item) => item.id !== id); return route.fulfill({ json: { deleted: id } }) }
      const current = state.notes.find((item) => item.id === id)!
      current.status = route.request().postDataJSON().status
      return route.fulfill({ json: current })
    }
    if (suffix === "/integration") return route.fulfill({ json: { mode: "story_integration", generated_at: now, world_elements: state.elements, world_documents: state.documents, consistency_flags: [], integration_opportunities: [{ id: "opportunity-1", element_name: "The dawn rule", element_type: "rule", description: "Let the keeper explain the cost.", suggestions: ["Seed the exception earlier."], priority: 6, target_chapter: 2 }] } })
    if (suffix === "/canon-overrides") {
      if (method === "POST") { const saved = { id: "alias-1", ...route.request().postDataJSON() }; state.aliases = [saved]; return route.fulfill({ json: saved }) }
      return route.fulfill({ json: state.aliases })
    }
    if (suffix === "/wiki/generate") return route.fulfill({ json: { generated_count: 1, updated_names: ["Dawn Gate"], entries: [{ id: "wiki-1", book_id: "book-1", name: "Dawn Gate", entry_type: "place", description: "An opening bound to daylight.", first_mention: 2, created_at: now }] } })
    if (suffix === "/wiki") return route.fulfill({ json: [] })
    if (suffix === "/query") return route.fulfill({ json: { mode: route.request().postDataJSON().mode, answer: "The keeper needs a stated exception.", citations: Array.from({ length: 5 }, (_, i) => ({ name: `Source ${i + 1}`, excerpt: `Evidence ${i + 1}` })), suggestions: [{ title: "Clarify the cost", description: "The keeper must give up a memory." }], logic_alerts: [], simulation_steps: ["The gate closes", "The keeper pays"] } })
    return route.fallback()
  })
  await page.route("**/api/v1/intelligence/element-1/world-building/accept-suggestion", (route) => {
    const call = "POST /accept-suggestion"; state.calls.push(call)
    if (state.fail.has(call)) return route.fulfill({ status: 503, json: { detail: "Could not update suggestion" } })
    state.elements[0].suggestions = []; state.analysis.world_elements[0].suggestions = []
    return route.fulfill({ json: { accepted: "suggestion-1", remaining: 0 } })
  })
  return state
}

test("worldbuilding views stay readable across four widths and both themes", async ({ page }, info) => {
  await installWorld(page); const errors: string[] = []; page.on("pageerror", (error) => errors.push(error.message))
  await page.goto(path); await expect(page.getByText("The gate opens after sunset", { exact: true })).toBeVisible()
  await page.getByRole("button", { name: /The gate opens after sunset.*Review evidence/ }).click()
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 }); expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
    await page.screenshot({ path: info.outputPath(`world-${width}.png`), fullPage: true, animations: "disabled" })
  }
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.getByRole("tab", { name: "Review gaps", exact: true }).focus(); await page.keyboard.press("ArrowRight")
  await expect(page.getByRole("tab", { name: "Canon sources", exact: true })).toBeFocused()
  await expect(page.getByLabel("Worldbuilding manuscript", { exact: true })).toHaveValue("The gate opens only at dawn.")
  await page.getByText("Import reference files", { exact: true }).click()
  await page.screenshot({ path: info.outputPath("world-sources-mobile.png"), fullPage: true, animations: "disabled" })
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.getByRole("tab", { name: "Canon tools", exact: true }).click()
  await page.screenshot({ path: info.outputPath("world-tools-mobile.png"), fullPage: true, animations: "disabled" })
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.getByRole("button", { name: "Help", exact: true }).click(); await expect(page.getByRole("dialog")).toBeVisible(); await page.keyboard.press("Escape")
  await page.evaluate(() => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "light" }, version: 0 })))
  await page.reload(); await page.getByRole("tab", { name: "Canon tools", exact: true }).click()
  await page.screenshot({ path: info.outputPath("world-tools-light.png"), fullPage: true, animations: "disabled" })
  expect(await criticalAccessibilityViolations(page)).toEqual([]); expect(errors).toEqual([])
})

test("worldbuilding source drafts survive tabs, declined replacement and failed saves", async ({ page }) => {
  const state = await installWorld(page); await page.goto(path)
  await page.getByRole("tab", { name: "Canon sources", exact: true }).click()
  const input = page.getByLabel("Worldbuilding manuscript", { exact: true }); await expect(input).toHaveValue("The gate opens only at dawn.")
  await input.fill("Keep this source revision")
  await page.getByRole("tab", { name: "Review gaps", exact: true }).click(); await page.getByRole("tab", { name: "Canon sources", exact: true }).click()
  await expect(input).toHaveValue("Keep this source revision")
  page.once("dialog", (dialog) => dialog.dismiss()); await page.getByRole("button", { name: /Second source.*words/ }).click(); await expect(input).toHaveValue("Keep this source revision")
  state.fail.add("PATCH /documents/doc-1"); await page.getByRole("button", { name: "Save document", exact: true }).click()
  await expect(page.getByRole("status").filter({ hasText: "Your draft is retained" })).toBeVisible(); await expect(input).toHaveValue("Keep this source revision")
  state.fail.clear(); await page.getByRole("button", { name: "Save document", exact: true }).click(); await expect(page.getByText("Saved Canon source.", { exact: true })).toBeVisible()
  await expect(input).toHaveValue("Keep this source revision")
  await page.getByRole("button", { name: "New blank document", exact: true }).click(); await input.fill("New canon text")
  await page.getByLabel("Document title", { exact: true }).fill("New source")
  await page.getByRole("tab", { name: "Review gaps", exact: true }).click(); await page.getByRole("tab", { name: "Canon sources", exact: true }).click()
  await expect(page.getByRole("button", { name: "Create document", exact: true })).toBeEnabled()
  state.fail.add("GET /gaps")
  await page.getByRole("button", { name: "Create document", exact: true }).click(); await expect(page.getByText("Created New source.", { exact: true })).toBeVisible()
  expect(state.documents.find((item) => item.title === "New source")?.text).toBe("New canon text")
  await page.getByRole("tab", { name: "Review gaps", exact: true }).click()
  await expect(page.getByText(/This comparison uses earlier/)).toBeVisible()
})

test("worldbuilding loading and refresh failures retain context and distinguish stale comparisons", async ({ page }) => {
  const state = await installWorld(page); state.fail.add("GET /bootstrap"); await page.goto(path)
  await expect(page.getByRole("button", { name: "Retry worldbuilding workspace" })).toBeVisible()
  await expect(page.getByText("No world documents yet.", { exact: true })).toHaveCount(0)
  state.fail.clear(); await page.getByRole("button", { name: "Retry worldbuilding workspace" }).click()
  await expect(page.getByText("The gate opens after sunset", { exact: true })).toBeVisible()
  state.fail.add("GET /gaps"); await page.getByRole("button", { name: "Refresh comparison", exact: true }).click()
  await expect(page.getByRole("button", { name: "Retry comparison", exact: true })).toBeVisible()
  await expect(page.getByText("The gate opens after sunset", { exact: true })).toBeVisible()
  state.fail.clear(); state.analysis.is_stale = true; state.analysis.refresh_job_id = "refresh-1"
  await page.getByRole("button", { name: "Retry comparison", exact: true }).click(); await expect(page.getByText(/This comparison uses earlier/)).toBeVisible()
  state.fail.add("GET /documents/doc-1"); await page.getByRole("tab", { name: "Canon sources", exact: true }).click()
  await expect(page.getByRole("button", { name: "Retry source content", exact: true })).toBeVisible()
  await expect(page.getByRole("button", { name: "Save document", exact: true })).toHaveCount(0)
  state.fail.clear(); await page.getByRole("button", { name: "Retry source content", exact: true }).click()
  await expect(page.getByLabel("Worldbuilding manuscript", { exact: true })).toHaveValue("The gate opens only at dawn.")
})

test("worldbuilding cleanup filters and mutations retain failures and update the visible scope", async ({ page }) => {
  const state = await installWorld(page); await page.goto(path)
  await page.getByLabel("Chapter number filter", { exact: true }).fill("1.5"); await page.getByRole("button", { name: "Filter by chapter", exact: true }).click()
  await expect(page.getByText("Enter a whole chapter number of 1 or higher.", { exact: true })).toBeVisible()
  await page.getByLabel("Chapter number filter", { exact: true }).fill("2"); state.fail.add("GET /notes/by-chapter/2")
  await page.getByRole("button", { name: "Filter by chapter", exact: true }).click(); await expect(page.getByText(/previous results are retained/)).toBeVisible()
  state.fail.clear(); await page.getByRole("button", { name: "Filter by chapter", exact: true }).click(); await expect(page.getByText("Showing chapter 2 cleanup notes.", { exact: true })).toBeVisible()
  state.fail.add("PATCH /notes/note-1/status"); await page.getByRole("button", { name: "Resolve: Clarify the gate rule", exact: true }).click()
  await expect(page.getByText(/previous status is retained/)).toBeVisible(); await expect(page.getByRole("button", { name: "Resolve: Clarify the gate rule", exact: true })).toBeEnabled()
  state.fail.clear(); await page.getByRole("button", { name: "Resolve: Clarify the gate rule", exact: true }).click()
  await expect(page.getByText("No open world gap notes right now.", { exact: true })).toBeVisible()
  await page.getByText(/Addressed Notes/).click(); await page.getByRole("button", { name: "Reopen: Clarify the gate rule", exact: true }).click()
  await expect(page.getByRole("button", { name: "Resolve: Clarify the gate rule", exact: true })).toBeVisible()
  page.once("dialog", (dialog) => dialog.dismiss()); await page.getByRole("button", { name: "Delete: Clarify the gate rule", exact: true }).click(); expect(state.notes).toHaveLength(1)
  page.once("dialog", (dialog) => dialog.accept()); await page.getByRole("button", { name: "Delete: Clarify the gate rule", exact: true }).click(); await expect(page.getByText("Deleted the cleanup note.", { exact: true })).toBeVisible()
})

test("worldbuilding evidence saves recover and resolved findings do not create duplicate notes", async ({ page }) => {
  const state = await installWorld(page); await page.goto(path)
  await page.getByRole("button", { name: /The gate opens after sunset.*Review evidence/ }).click()
  await expect(page.getByRole("link", { name: "Open chapter 2", exact: true })).toHaveAttribute("href", "/sky-of-ash--book-1/manuscript?chapter=2")
  state.fail.add("POST /notes"); await page.getByRole("button", { name: "Add to cleanup", exact: true }).click()
  await expect(page.getByText(/Refresh cleanup notes before retrying/)).toBeVisible()
  state.fail.clear(); await page.getByRole("button", { name: "Add to cleanup", exact: true }).click()
  await expect(page.getByRole("button", { name: "Saved to cleanup", exact: true })).toBeDisabled()
  await page.getByRole("button", { name: "Resolve: The gate opens after sunset", exact: true }).click()
  await expect(page.getByRole("button", { name: "Saved to cleanup", exact: true })).toBeDisabled()
  expect(state.calls.filter((call) => call === "POST /notes")).toHaveLength(2)
})

test("worldbuilding canon tools retain failed drafts and show the complete submitted query evidence", async ({ page }) => {
  const state = await installWorld(page); await page.goto(path); await page.getByRole("tab", { name: "Canon tools", exact: true }).click()
  await page.getByLabel("Canonical name", { exact: true }).fill("Dawn Gate"); await page.getByLabel("Aliases", { exact: true }).fill("Sun Gate, Gate")
  state.fail.add("POST /canon-overrides"); await page.getByRole("button", { name: "Save override", exact: true }).click()
  await expect(page.getByText(/Your entries are retained/)).toBeVisible(); await expect(page.getByLabel("Canonical name", { exact: true })).toHaveValue("Dawn Gate")
  state.fail.clear(); await page.getByRole("button", { name: "Save override", exact: true }).click(); await expect(page.getByLabel("Canonical name", { exact: true })).toHaveValue("")
  state.fail.add("GET /integration"); await page.getByRole("button", { name: "Refresh opportunities", exact: true }).first().click(); await expect(page.getByText(/previous result is retained/)).toBeVisible()
  state.fail.clear(); await page.getByRole("button", { name: "Refresh opportunities", exact: true }).first().click(); await expect(page.getByText("Let the keeper explain the cost.", { exact: true })).toBeVisible()
  state.fail.add("POST /wiki/generate"); await page.getByRole("button", { name: "Generate wiki", exact: true }).first().click(); await expect(page.getByText(/Existing entries are retained/)).toBeVisible()
  state.fail.clear(); await page.getByRole("button", { name: "Generate wiki", exact: true }).first().click(); await expect(page.getByText("An opening bound to daylight.", { exact: true })).toBeVisible()
  await page.getByLabel("Query the canon", { exact: true }).fill("Can the keeper open it at night?")
  state.fail.add("POST /query"); await page.getByRole("button", { name: "Run simulation", exact: true }).click(); await expect(page.getByText(/question and any previous answer are retained/)).toBeVisible()
  state.fail.clear(); await page.getByRole("button", { name: "Run simulation", exact: true }).click()
  await expect(page.getByText("Evidence 5", { exact: false })).toBeVisible(); await expect(page.getByText("The keeper must give up a memory.", { exact: false })).toBeVisible()
  await page.getByLabel("Query the canon", { exact: true }).fill("A different question"); await expect(page.getByText(/editor now contains a different question/)).toBeVisible()
})

test("worldbuilding imports and deletes require intentional source replacement and recover", async ({ page }) => {
  const state = await installWorld(page); await page.goto(path); await page.getByRole("tab", { name: "Canon sources", exact: true }).click()
  await expect(page.getByLabel("Worldbuilding manuscript", { exact: true })).toHaveValue("The gate opens only at dawn.")
  await page.getByText("Import reference files", { exact: true }).click()
  await page.getByLabel("Upload world corpus files", { exact: true }).setInputFiles({ name: "canon.txt", mimeType: "text/plain", buffer: Buffer.from("The gate opens at dawn.") })
  await page.getByRole("checkbox", { name: /Replace active world corpus/ }).check()
  page.once("dialog", (dialog) => dialog.dismiss()); await page.getByRole("button", { name: "Replace corpus", exact: true }).click(); expect(state.calls.filter((call) => call === "POST /documents")).toHaveLength(0)
  state.fail.add("POST /documents"); page.once("dialog", (dialog) => dialog.accept()); await page.getByRole("button", { name: "Replace corpus", exact: true }).click()
  await expect(page.getByText(/selected files are retained/)).toBeVisible(); await expect(page.getByText("1 file selected", { exact: true })).toBeVisible()
  state.fail.clear(); page.once("dialog", (dialog) => dialog.accept()); await page.getByRole("button", { name: "Replace corpus", exact: true }).click()
  await expect(page.getByText("Replaced the active world corpus and loaded the new documents.", { exact: true })).toBeVisible(); expect(state.documents).toHaveLength(1)
  await expect(page.getByLabel("Worldbuilding manuscript", { exact: true })).toHaveValue("Imported reference text.")
  page.once("dialog", (dialog) => dialog.dismiss()); await page.getByRole("button", { name: "Delete document", exact: true }).click(); expect(state.documents).toHaveLength(1)
  state.fail.add(`DELETE /documents/${state.documents[0].id}`)
  page.once("dialog", (dialog) => dialog.accept()); await page.getByRole("button", { name: "Delete document", exact: true }).click()
  await expect(page.getByRole("status").filter({ hasText: "Temporarily unavailable" })).toBeVisible()
  await expect(page.getByLabel("Worldbuilding manuscript", { exact: true })).toHaveValue("Imported reference text.")
  state.fail.clear()
  page.once("dialog", (dialog) => dialog.accept()); await page.getByRole("button", { name: "Delete document", exact: true }).click(); await expect(page.getByRole("button", { name: "Create document", exact: true })).toBeDisabled()
  expect(state.documents).toHaveLength(0)
})

test("worldbuilding exposes every lore fact and retains failed implementation decisions", async ({ page }) => {
  const state = await installWorld(page)
  state.elements = Array.from({ length: 25 }, (_, index) => ({ ...structuredClone(element), id: `element-${index + 1}`, name: `Lore fact ${index + 1}`, suggestions: index ? [] : element.suggestions }))
  state.analysis.world_elements = state.elements
  await page.goto(path); await page.getByRole("tab", { name: "Canon tools", exact: true }).click()
  await page.getByRole("button", { name: "Show all 25 elements", exact: true }).click()
  await expect(page.getByRole("heading", { name: "Lore fact 25", exact: true })).toBeVisible()
  await page.getByRole("button", { name: "Show fewer elements", exact: true }).click()
  await expect(page.getByRole("heading", { name: "Lore fact 25", exact: true })).toHaveCount(0)
  state.fail.add("POST /accept-suggestion")
  await page.getByRole("button", { name: "Mark implemented", exact: true }).click()
  await expect(page.getByText(/The suggestion is retained/)).toBeVisible()
  await expect(page.getByText(/Explain how the keeper can open the gate/)).toBeVisible()
  state.fail.clear(); await page.getByRole("button", { name: "Mark implemented", exact: true }).click()
  await expect(page.getByRole("button", { name: "Mark implemented", exact: true })).toHaveCount(0)
  expect(state.calls.filter((call) => call === "POST /accept-suggestion")).toHaveLength(2)
})

test("worldbuilding protects edits on navigation and serializes a slow source save", async ({ page }) => {
  const state = await installWorld(page)
  let release!: () => void
  const gate = new Promise<void>((resolve) => { release = resolve })
  await page.route(`**${base}/documents/doc-1`, async (route) => {
    if (route.request().method() === "PATCH") await gate
    return route.fallback()
  })
  await page.goto(path); await page.getByRole("tab", { name: "Canon sources", exact: true }).click()
  await page.getByLabel("Worldbuilding manuscript", { exact: true }).fill("Protected source draft")
  page.once("dialog", (dialog) => dialog.dismiss())
  await page.getByRole("link", { name: "Search this book", exact: true }).click()
  await expect(page).toHaveURL(new RegExp("world-gap$"))
  await page.getByRole("button", { name: "Save document", exact: true }).click()
  await expect(page.getByLabel("Worldbuilding manuscript", { exact: true })).toBeDisabled()
  await expect(page.getByRole("button", { name: "New blank document", exact: true })).toBeDisabled()
  await page.getByRole("tab", { name: "Review gaps", exact: true }).click()
  await page.getByRole("tab", { name: "Canon sources", exact: true }).click()
  await expect(page.getByLabel("Worldbuilding manuscript", { exact: true })).toBeDisabled()
  release(); await expect(page.getByText("Saved Canon source.", { exact: true })).toBeVisible()
  await expect(page.getByLabel("Worldbuilding manuscript", { exact: true })).toHaveValue("Protected source draft")
  expect(state.calls.filter((call) => call === "PATCH /documents/doc-1")).toHaveLength(1)
})
