import { expect, test, type Page, type Route } from "@playwright/test"
import { installMockApi } from "./support/mockApi"
import { criticalAccessibilityViolations } from "./support/accessibility"

const path = "/sky-of-ash--book-1/voice"
const api = "**/api/v1/intelligence/*/advisor/voice-consistency-stream"
const streamReview = (route: Route, payload: unknown) => route.fulfill({ contentType: "text/event-stream", body: `event: stage\ndata: {"message":"Reviewing the full passage..."}\n\nevent: done\ndata: ${JSON.stringify(payload)}\n\n` })
const input = (page: Page) => page.getByRole("textbox", { name: "Dialogue or chapter text for voice review" })
const run = (page: Page) => page.getByRole("button", { name: "Run voice review", exact: true })
const review = { review: { overall_verdict: "The submitted dialogue retains Nora's clipped cadence.", issues: [] }, characters_reviewed: ["Nora"], warnings: ["Only two baseline samples were available."], character_matches: [], retrieved_passages: [{ chapter_num: 2, chapter_title: "The Ember Gate", excerpt: "A baseline dialogue excerpt.", relevance: .8 }] }

test.beforeEach(async ({ page }) => {
  await installMockApi(page, { voiceConsistency: "selected-character" })
  await page.route("**/api/v1/books/book-1/scenes", (route) => route.request().method() === "POST" ? route.fulfill({ status: 201, json: { ...route.request().postDataJSON(), id: "voice-scene-1" } }) : route.fallback())
  await page.addInitScript(() => { if (!localStorage.getItem("lorevia-preferences")) localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "dark" }, version: 0 })); document.cookie = "lorevia_analytics_consent=false; Path=/; SameSite=Lax" })
})

test("voice explanation opens by hover and click in dark and light themes", async ({ page }) => {
  await page.goto(path)
  const info = page.getByRole("button", { name: "How Voice Consistency works" })
  await expect(info).toBeVisible()
  await info.hover()
  await expect(page.getByRole("tooltip")).toContainText("source-backed samples")
  await page.mouse.move(0, 0)
  await expect(page.getByRole("tooltip")).toHaveCount(0)
  await info.click()
  await expect(page.getByRole("tooltip")).toContainText("too little evidence")
  await page.evaluate(() => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "light" }, version: 0 })))
  await page.reload()
  await expect(info).toBeVisible()
  await info.click()
  await expect(page.getByRole("tooltip")).toContainText("too little evidence")
})

test("short current dialogue shows a tentative review without a match percentage", async ({ page }) => {
  await page.route(api, (route) => streamReview(route, {
    review: { status: "partial_evidence", overall_verdict: "Current passage evidence is too limited for a reliable voice match.", issues: [] },
    characters_reviewed: ["Nora"], character_matches: [], retrieved_passages: [],
    warnings: ["Nora: at least 2 excerpts and 20 words are needed for a reliable voice match."],
    coverage: { processed_ranges: [{ start: 0, end: 42 }], total_characters: 42 },
  }))
  await page.goto(path)
  await expect(run(page)).toBeEnabled()
  await run(page).click()
  await expect(page.getByRole("heading", { name: "Partial voice review" })).toBeVisible()
  await expect(page.getByText(/current passage evidence may be too limited/)).toBeVisible()
  await expect(page.getByText("No reliable match scores were available for this passage.")).toBeVisible()
  await expect(page.getByText(/% match/)).toHaveCount(0)
})

test("voice review distinguishes compared sections from scanned sections with no attributed speech", async ({ page }) => {
  await page.route(api, (route) => streamReview(route, {
    review: { status: "partial_evidence", overall_verdict: "Only attributable dialogue was compared.", issues: [] },
    characters_reviewed: ["Nora"], character_matches: [], retrieved_passages: [], warnings: [],
    coverage: { processed_ranges: [{ start: 3200, end: 5000 }], unattributed_ranges: [{ start: 0, end: 3200 }], compared_ranges: [{ start: 4000, end: 4200 }], not_compared_ranges: [{ start: 0, end: 4000 }, { start: 4200, end: 5000 }], unattributed_quoted_ranges: [{ start: 4200, end: 4240 }], total_characters: 5000 },
    coverage_by_character: [{ character_name: "Nora", processed_ranges: [{ start: 3200, end: 5000 }], unattributed_ranges: [{ start: 0, end: 3200 }], compared_ranges: [{ start: 4000, end: 4200 }], not_compared_ranges: [{ start: 0, end: 4000 }, { start: 4200, end: 5000 }], total_characters: 5000 }],
  }))
  await page.goto(path)
  await expect(run(page)).toBeEnabled()
  await run(page).click()
  await expect(page.getByText(/1,800 of 5,000 source characters were in reviewed sections/)).toBeVisible()
  await expect(page.getByText(/3,200 characters had no attributable voice/)).toBeVisible()
  await expect(page.getByText(/Exact voice comparison: 200 characters compared with the baseline; 4,800 source characters were not voice-compared/)).toBeVisible()
  await expect(page.getByText(/40 quoted characters were not attributed to a reviewed voice/)).toBeVisible()
  await expect(page.getByText(/Nora: 1 overlapping section\(s\) compared; 1 section\(s\) had no attributable voice and were not compared/)).toBeVisible()
})

test("voice source and findings are readable at four widths and in both themes", async ({ page }, info) => {
  const errors: string[] = []; page.on("pageerror", (error) => errors.push(error.message))
  await page.goto(path); await expect(run(page)).toBeEnabled(); await run(page).click()
  await expect(page.getByRole("heading", { name: "Verdict", exact: true })).toBeVisible()
  if (await page.getByRole("button", { name: "Not now", exact: true }).isVisible()) await page.getByRole("button", { name: "Not now", exact: true }).click()
  for (const width of [1440, 1280, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 })
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
    await page.evaluate(() => window.scrollTo({ top: 0, behavior: "instant" }))
    await page.screenshot({ path: info.outputPath(`voice-${width}.png`), fullPage: true, animations: "disabled" })
  }
  expect(await criticalAccessibilityViolations(page)).toEqual([])
  await page.getByRole("button", { name: "Help", exact: true }).focus(); await page.keyboard.press("Enter")
  await expect(page.getByRole("dialog")).toBeVisible(); await page.keyboard.press("Escape")
  await page.evaluate(() => localStorage.setItem("lorevia-preferences", JSON.stringify({ state: { theme: "light" }, version: 0 })))
  page.once("dialog", (dialog) => dialog.accept()); await page.reload(); await expect(run(page)).toBeEnabled(); await run(page).click()
  await expect(page.getByRole("heading", { name: "Verdict", exact: true })).toBeVisible()
  await page.screenshot({ path: info.outputPath("voice-light.png"), fullPage: true, animations: "disabled" })
  expect(await criticalAccessibilityViolations(page)).toEqual([]); expect(errors).toEqual([])
})

test("voice drafts survive source changes, refresh, and declined discard or navigation", async ({ page }) => {
  await page.goto(path); await expect(run(page)).toBeEnabled()
  await input(page).fill("Edited chapter dialogue")
  await page.getByLabel("Chapter or passage", { exact: true }).selectOption("")
  await input(page).fill("A custom passage")
  await page.evaluate(() => window.dispatchEvent(new Event("online")))
  await expect(input(page)).toHaveValue("A custom passage")
  await page.getByLabel("Chapter or passage", { exact: true }).selectOption("2")
  await expect(input(page)).toHaveValue("Edited chapter dialogue")
  page.once("dialog", (dialog) => dialog.dismiss()); await page.getByRole("button", { name: "Discard passage edits" }).click()
  await expect(input(page)).toHaveValue("Edited chapter dialogue")
  page.once("dialog", (dialog) => dialog.dismiss()); await page.getByRole("link", { name: "Open manuscript", exact: true }).click()
  await expect(page).toHaveURL(new RegExp(`${path}$`))
  page.once("dialog", (dialog) => dialog.accept()); await page.getByRole("button", { name: "Discard passage edits" }).click()
  await expect(input(page)).toHaveValue(/Nora crossed the ember gate/)
  await page.getByLabel("Chapter or passage", { exact: true }).selectOption("")
  await expect(input(page)).toHaveValue("A custom passage")
})

test("voice protects the full passage at the length boundary and saves the submitted snapshot", async ({ page }) => {
  let release!: () => void; const held = new Promise<void>((resolve) => { release = resolve }); const requests: { text: string }[] = []
  await page.route(api, async (route) => { requests.push(route.request().postDataJSON()); await held; await streamReview(route, review) })
  await page.goto(path); await expect(run(page)).toBeEnabled()
  await input(page).fill("x".repeat(12001)); await expect(run(page)).toBeDisabled()
  await expect(page.getByText(/shorten the passage before reviewing/)).toBeVisible()
  expect(requests).toEqual([])
  await input(page).fill("x".repeat(12000)); await run(page).click()
  await expect(page.getByRole("button", { name: "Reviewing...", exact: true })).toBeDisabled()
  await input(page).fill("Later edited text"); release()
  await expect(page.getByText(/The editor or character focus has changed/)).toBeVisible()
  expect(requests).toHaveLength(1); expect(requests[0].text).toHaveLength(12000)
  await page.getByText("Read the reviewed passage", { exact: true }).click()
  await expect(page.locator("details").filter({ hasText: "Read the reviewed passage" })).toContainText("x".repeat(12000))
  const saved = page.waitForRequest((request) => request.method() === "POST" && new URL(request.url()).pathname === "/api/v1/books/book-1/scenes")
  await page.getByRole("button", { name: "Save snapshot", exact: true }).click()
  const payload = (await saved).postDataJSON()
  expect(payload.body).toContain("x".repeat(12000)); expect(payload.body).not.toContain("Later edited text")
  expect(payload.body).toContain("Only two baseline samples"); expect(payload.chapter_number).toBe(2)
  await expect(page.getByText(/Saved review scene to/)).toBeVisible()
})

test("voice counts and submits every source character including surrounding whitespace", async ({ page }) => {
  const requests: { text: string }[] = []
  await page.route(api, (route) => {
    requests.push(route.request().postDataJSON())
    return streamReview(route, review)
  })
  await page.goto(path)
  await page.getByLabel("Chapter or passage", { exact: true }).selectOption("")
  const accepted = `  ${"x".repeat(11997)} `
  await input(page).fill(`${accepted}x`)
  await expect(run(page)).toBeDisabled()
  await expect(page.getByText(/12,001 \/ 12,000 characters/)).toBeVisible()

  await input(page).fill(accepted)
  await expect(run(page)).toBeEnabled()
  await run(page).click()
  await expect(page.getByText(review.review.overall_verdict, { exact: true })).toBeVisible()
  expect(requests).toHaveLength(1)
  expect(requests[0].text).toBe(accepted)
})

test("voice retains earlier results through review failure and exposes evidence", async ({ page }) => {
  let fail = false
  await page.route(api, (route) => fail ? route.fulfill({ status: 503, json: { detail: "Review temporarily unavailable." } }) : streamReview(route, review))
  await page.goto(path); await expect(run(page)).toBeEnabled(); await run(page).click()
  await expect(page.getByText(review.review.overall_verdict, { exact: true })).toBeVisible()
  await page.getByText("Manuscript evidence (1 passage)", { exact: true }).click()
  await expect(page.getByText("A baseline dialogue excerpt.", { exact: true })).toBeVisible()
  await expect(page.getByRole("link", { name: "Open chapter 2", exact: true })).toHaveAttribute("href", "/sky-of-ash--book-1/manuscript?chapter=2")
  fail = true; await input(page).fill("Another passage"); await run(page).click()
  await expect(page.getByText("Review temporarily unavailable.", { exact: true })).toBeVisible()
  await expect(page.getByText(review.review.overall_verdict, { exact: true })).toBeVisible()
  await expect(input(page)).toHaveValue("Another passage")
})

test("alternate voice similarity is shown as a clue rather than speaker proof", async ({ page }) => {
  await page.route(api, (route) => streamReview(route, {
    ...review,
    character_matches: [{
      character_name: "Nora",
      match_score: 42,
      baseline_sample_size: 4,
      baseline_word_count: 82,
      sample_dialogue_count: 2,
      strongest_signals: [],
      closest_other_character: "Mara",
      closest_other_score: 86,
    }],
  }))
  await page.goto(path)
  await expect(run(page)).toBeEnabled()
  await run(page).click()
  await expect(page.getByText(/Closest alternate voice: Mara/)).toContainText(
    "supporting evidence, not proof of speaker identity",
  )
})

test("pronoun-attributed voice review remains visibly tentative", async ({ page }) => {
  await page.route(api, (route) => streamReview(route, {
    review: { status: "partial_evidence", overall_verdict: "Speaker attribution is tentative.", issues: [] },
    characters_reviewed: ["Gregor"], character_matches: [], retrieved_passages: [],
    baseline_evidence: [{ character_name: "Gregor", sample_count: 3, word_count: 75, chapters: [1, 2], attribution_confidence: "contextual" }],
    warnings: ["Gregor: some dialogue was linked through a nearby pronoun."],
    coverage: { total_characters: 120, processed_ranges: [{ start: 0, end: 120 }] },
  }))
  await page.goto(path)
  await expect(run(page)).toBeEnabled()
  await run(page).click()
  await expect(page.getByRole("heading", { name: "Partial voice review" })).toBeVisible()
  await expect(page.getByText(/Current passage attribution: contextual/)).toBeVisible()
  await expect(page.getByText(/not a complete verdict/)).toBeVisible()
  await expect(page.getByText(/No supported character voice issues were found/)).toHaveCount(0)
})

test("first-person narrator baseline with uncertain identity stays a partial review", async ({ page }) => {
  await page.route(api, (route) => streamReview(route, {
    voice_mode: "first_person_narration",
    review: { status: "partial_evidence", overall_verdict: "Narrator attribution in the baseline is tentative.", issues: [] },
    characters_reviewed: ["Gregor"], character_matches: [], retrieved_passages: [],
    baseline_evidence: [{ character_name: "Gregor", sample_count: 3, word_count: 135, chapters: [1, 2], baseline_attribution_confidence: "unverified_narrator", attribution_confidence: "user_selected_narrator" }],
    warnings: ["Gregor: baseline chapters do not independently identify this narrator."],
    coverage: { total_characters: 120, processed_ranges: [{ start: 0, end: 120 }] },
  }))
  await page.goto(path)
  await page.getByLabel("Character focus").selectOption("char-gregor")
  await page.getByLabel("Voice to review").selectOption("first_person_narration")
  await expect(run(page)).toBeEnabled()
  await run(page).click()
  await expect(page.getByRole("heading", { name: "Partial voice review" })).toBeVisible()
  await expect(page.getByText(/Baseline attribution: unverified narrator/)).toBeVisible()
  await expect(page.getByText(/Current passage attribution: user selected narrator/)).toBeVisible()
  await expect(page.getByText("No reliable match scores were available for this passage.")).toBeVisible()
  await expect(page.getByText(/% match/)).toHaveCount(0)
})

test("first-person auto-detect sends no guessed narrator and explains insufficient identity", async ({ page }) => {
  const requests: Record<string, unknown>[] = []
  await page.route(api, (route) => {
    requests.push(route.request().postDataJSON())
    return streamReview(route, {
      voice_mode: "first_person_narration",
      review: { status: "insufficient_evidence", overall_verdict: "The narrator could not be identified.", issues: [] },
      characters_reviewed: [], characters_detected: [], character_matches: [], retrieved_passages: [],
      warnings: ["The passage does not unambiguously name its first-person narrator. Select the narrator to review this voice; no identity was guessed."],
      coverage: { total_characters: 52, processed_ranges: [], unattributed_ranges: [{ start: 0, end: 52 }] },
    })
  })
  await page.goto(path)
  await page.getByLabel("Voice to review").selectOption("first_person_narration")
  await expect(run(page)).toBeEnabled()
  await run(page).click()
  await expect(page.getByText(/no identity was guessed/)).toBeVisible()
  expect(requests).toHaveLength(1)
  expect(requests[0].voice_mode).toBe("first_person_narration")
  expect(requests[0]).not.toHaveProperty("character_id")
})

test("voice query failures offer independent retries without replacing custom drafts", async ({ page }) => {
  let bookFailed = true; let chaptersFailed = true; let charactersFailed = true
  await page.route((url) => url.pathname === "/api/v1/books/book-1", (route) => bookFailed ? route.fulfill({ status: 503, json: { detail: "Unavailable" } }) : route.fallback())
  await page.route((url) => url.pathname === "/api/v1/reader/book-1/chapters", (route) => chaptersFailed ? route.fulfill({ status: 503, json: { detail: "Unavailable" } }) : route.fallback())
  await page.route((url) => url.pathname === "/api/v1/books/book-1/characters", (route) => charactersFailed ? route.fulfill({ status: 503, json: { detail: "Unavailable" } }) : route.fallback())
  await page.goto(path); await input(page).fill("Keep this custom draft")
  await expect(page.getByRole("button", { name: "Retry book context" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Retry chapter list" })).toBeVisible()
  await expect(page.getByRole("button", { name: "Retry characters" })).toBeVisible()
  await expect(run(page)).toBeDisabled()
  bookFailed = false; await page.getByRole("button", { name: "Retry book context" }).click()
  await expect(run(page)).toBeEnabled()
  chaptersFailed = false; await page.getByRole("button", { name: "Retry chapter list" }).click()
  charactersFailed = false; await page.getByRole("button", { name: "Retry characters" }).click()
  await expect(page.getByLabel("Chapter or passage", { exact: true })).toHaveValue("")
  await expect(input(page)).toHaveValue("Keep this custom draft")
  await expect(page.getByLabel("Character focus", { exact: true }).locator('option[value="char-gregor"]')).toHaveCount(1)
})

test("voice chapter loading and errors do not masquerade as an empty passage", async ({ page }) => {
  let release!: () => void; const held = new Promise<void>((resolve) => { release = resolve }); let fail = true
  await page.route((url) => url.pathname === "/api/v1/reader/book-1/chapter/2", async (route) => { if (!fail) return route.fallback(); await held; await route.fulfill({ status: 503, json: { detail: "Unavailable" } }) })
  await page.goto(path); await expect(page.getByText("Loading chapter text...", { exact: true })).toBeVisible()
  await expect(run(page)).toBeDisabled(); release()
  await expect(page.getByRole("button", { name: "Retry chapter text" })).toBeVisible()
  fail = false; await page.getByRole("button", { name: "Retry chapter text" }).click()
  await expect(input(page)).toHaveValue(/Nora crossed the ember gate/); await expect(run(page)).toBeEnabled()
})

test("voice note and scene saves recover visibly and serialize writes", async ({ page }) => {
  await page.route(api, (route) => streamReview(route, review))
  let fail = true; let writes = 0; let release!: () => void; const held = new Promise<void>((resolve) => { release = resolve })
  await page.route((url) => url.pathname === "/api/v1/books/book-1/notes/vault", async (route) => {
    if (route.request().method() !== "PUT") return route.fallback()
    writes++
    if (fail) return route.fulfill({ status: 503, json: { detail: "Save temporarily unavailable." } })
    await held; return route.fallback()
  })
  await page.goto(path); await expect(run(page)).toBeEnabled(); await run(page).click()
  await page.getByRole("button", { name: "Save review note", exact: true }).click()
  await expect(page.getByText(/Check Notes before trying again/)).toBeVisible()
  fail = false; await page.getByRole("button", { name: "Save review note", exact: true }).click()
  await expect(page.getByRole("button", { name: "Save snapshot", exact: true })).toBeDisabled()
  await expect(page.getByRole("button", { name: "Save review note", exact: true })).toBeDisabled()
  release(); await expect(page.getByText(/Saved voice note to/)).toBeVisible(); expect(writes).toBe(2)
  let sceneFailed = true
  await page.route((url) => url.pathname === "/api/v1/books/book-1/workspace/tree", (route) => sceneFailed ? route.fulfill({ status: 503, json: { detail: "Scene list unavailable." } }) : route.fallback())
  await page.getByRole("button", { name: "Save snapshot", exact: true }).click()
  await expect(page.getByText(/Check Scenes before trying again/)).toBeVisible()
  await expect(page.getByText(review.review.overall_verdict, { exact: true })).toBeVisible()
  sceneFailed = false; await page.getByRole("button", { name: "Save snapshot", exact: true }).click()
  await expect(page.getByText(/Saved review scene to/)).toBeVisible()
})

test("voice empty choices and long evidence stay usable on mobile", async ({ page }, info) => {
  await page.route((url) => url.pathname === "/api/v1/reader/book-1/chapters", (route) => route.fulfill({ json: { chapters: [], current_chapter: null } }))
  await page.route((url) => url.pathname === "/api/v1/books/book-1/characters", (route) => route.fulfill({ json: [] }))
  await page.route(api, (route) => streamReview(route, { ...review, review: { overall_verdict: "LongWord".repeat(100), issues: [] }, retrieved_passages: [{ chapter_num: 99, excerpt: "LongExcerpt".repeat(100), chapter_title: "Unavailable chapter", relevance: 0 }] }))
  await page.setViewportSize({ width: 390, height: 1000 }); await page.goto(path)
  await expect(page.getByText(/No chapters yet/)).toBeVisible()
  await expect(page.getByText(/No character choices yet/)).toBeVisible()
  await input(page).fill("   "); await expect(run(page)).toBeDisabled()
  await input(page).fill("Original dialogue"); await run(page).click()
  await page.getByText("Manuscript evidence (1 passage)", { exact: true }).click()
  await expect(page.getByText(/This chapter is not available/)).toBeVisible()
  await expect(page.getByRole("link", { name: "Open chapter 99" })).toHaveCount(0)
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  await page.screenshot({ path: info.outputPath("voice-long-mobile.png"), fullPage: true, animations: "disabled" })
  expect(await criticalAccessibilityViolations(page)).toEqual([])
})

test("voice finding notes keep the reviewed character after a focus change", async ({ page }) => {
  await page.goto(path); await expect(run(page)).toBeEnabled()
  await page.getByLabel("Character focus", { exact: true }).selectOption("char-gregor")
  await run(page).click(); await expect(page.getByText("Reviewed voices: Gregor", { exact: true })).toBeVisible()
  await page.getByLabel("Character focus", { exact: true }).selectOption("char-grete")
  await expect(page.getByText(/The editor or character focus has changed/)).toBeVisible()
  await page.getByText("If this change is intentional", { exact: true }).focus(); await page.keyboard.press("Enter")
  await expect(page.locator("details[open]")).toContainText("Gregor")
  const saved = page.waitForRequest((request) => request.method() === "PUT" && new URL(request.url()).pathname === "/api/v1/books/book-1/notes/vault")
  await page.getByRole("button", { name: "Save note: Gregor slips into abstract explanation" }).click()
  const content = (await saved).postDataJSON().content as string
  expect(content).toContain("Character focus: Gregor"); expect(content).toContain("Chapter 2")
  expect(content).toContain("Gregor slips into abstract explanation")
  await expect(page.getByText(/Saved voice note to/)).toBeVisible()
  await page.getByRole("link", { name: "View review", exact: true }).click()
  await expect(page.getByRole("heading", { name: "Character voice", exact: true })).toBeFocused()
})

test("voice finding decisions persist across repeat reviews and failed saves remain actionable", async ({ page }) => {
  const findingKey = "a".repeat(64)
  let saved = false
  let failSave = true
  const issue = {
    finding_key: findingKey,
    character_name: "Gregor",
    classification: "possible",
    severity: "moderate",
    title: "Gregor changes register",
    description: "His new line is more colloquial than the cited baseline.",
    submitted_excerpt: "No way, dude.",
    baseline_excerpt: "I shall return before dawn.",
    baseline_chapter_number: 1,
    confidence: 0.7,
    revision_direction: "Check whether the register shift is deliberate.",
    intentionality_prompt: "Is this a deliberate response to fear?",
  }
  await page.route(api, (route) => streamReview(route, {
    review: { status: "complete", overall_verdict: "One possible shift.", issues: saved ? [] : [issue] },
    characters_reviewed: ["Gregor"],
    warnings: [], character_matches: [], retrieved_passages: [],
    suppressed_findings: saved ? [{ ...issue, decision: "intentional" }] : [],
    coverage: { total_characters: 24, processed_ranges: [{ start: 0, end: 24 }] },
  }))
  await page.route(`**/api/v1/intelligence/*/advisor/voice-decisions/${findingKey}`, (route) => {
    if (failSave) return route.fulfill({ status: 503, json: { detail: "Decision save unavailable." } })
    saved = true
    return route.fulfill({ json: { finding_key: findingKey, decision: "intentional", note: null } })
  })

  await page.goto(path)
  await expect(run(page)).toBeEnabled()
  await page.getByLabel("Character focus", { exact: true }).selectOption("char-gregor")
  await run(page).click()
  await expect(page.getByText(issue.title)).toBeVisible()
  const savedNote = page.waitForRequest((request) => request.method() === "PUT" && new URL(request.url()).pathname === "/api/v1/books/book-1/notes/vault")
  await page.getByRole("button", { name: `Save note: ${issue.title}` }).click()
  const noteContent = (await savedNote).postDataJSON().content as string
  expect(noteContent).toContain("**Submitted excerpt:** No way, dude.")
  expect(noteContent).toContain("**Baseline excerpt (chapter 1):** I shall return before dawn.")
  const savedSnapshot = page.waitForRequest((request) => request.method() === "POST" && new URL(request.url()).pathname === "/api/v1/books/book-1/scenes")
  await page.getByRole("button", { name: "Save snapshot", exact: true }).click()
  const snapshotBody = (await savedSnapshot).postDataJSON().body as string
  expect(snapshotBody).toContain("**Submitted excerpt:** No way, dude.")
  expect(snapshotBody).toContain("**Baseline excerpt (chapter 1):** I shall return before dawn.")
  await page.getByRole("button", { name: "Mark intentional" }).click()
  await expect(page.getByText("Decision save unavailable.")).toBeVisible()
  await expect(page.getByText(issue.title)).toBeVisible()

  failSave = false
  await page.getByRole("button", { name: "Mark intentional" }).click()
  await expect(page.getByText(/All findings from this review have recorded decisions/)).toBeVisible()
  await expect(page.getByText("One possible shift.", { exact: true })).toHaveCount(0)
  const decidedNote = page.waitForRequest((request) => request.method() === "PUT" && new URL(request.url()).pathname === "/api/v1/books/book-1/notes/vault")
  await page.getByRole("button", { name: "Save review note", exact: true }).click()
  const decidedContent = (await decidedNote).postDataJSON().content as string
  expect(decidedContent).toContain("**Review decision:** intentional")
  expect(decidedContent).toContain("**Baseline excerpt (chapter 1):** I shall return before dawn.")
  expect(decidedContent).not.toContain("No voice issues were flagged")
  await run(page).click()
  await expect(page.getByText(/Previously reviewed findings \(1\)/)).toBeVisible()
  await expect(page.getByRole("button", { name: "Mark intentional" })).toHaveCount(0)
})
