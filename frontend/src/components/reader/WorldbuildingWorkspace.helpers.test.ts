import { describe, expect, it } from "vitest"

import type { UserStats } from "@/types/book"
import type { WikiEntry, WorldBuildingDocument, WorldElement, WorldGapResult, WorldIntegrationResult, WorldNote } from "@/types/world-building"
import {
  accentBadgeClass,
  accentDotClass,
  accentOutlineButtonClass,
  badgeClass,
  bodyTextClass,
  buildUploadLimitNote,
  countWorldDocumentWords,
  dangerButtonClass,
  eyebrowClass,
  findSelectedWorldDocument,
  formatElementType,
  getApiErrorDetail,
  getOpenGapIds,
  getSuggestionElements,
  getVisibleItems,
  getVisibleWorldElements,
  groupWorldNotesByStatus,
  inputClass,
  mutedActionClass,
  mutedTextClass,
  panelClass,
  primaryButtonClass,
  secondaryButtonClass,
  severityClass,
  softPanelClass,
  summarizeRecord,
  summarizeWikiEntryTypes,
  summarizeWorldElementTypes,
  titleTextClass,
} from "./WorldbuildingWorkspace.helpers"

function worldDocument(overrides: Partial<WorldBuildingDocument>): WorldBuildingDocument {
  return {
    id: "document-1",
    book_id: "book-1",
    title: "World Bible",
    word_count: 0,
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  }
}

function worldNote(overrides: Partial<WorldNote>): WorldNote {
  return {
    id: "note-1",
    book_id: "book-1",
    note_type: "gap",
    title: "Gap",
    body: "Body",
    priority: "medium",
    status: "open",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  }
}

function worldElement(overrides: Partial<WorldElement>): WorldElement {
  return {
    id: "element-1",
    book_id: "book-1",
    source_scope: "chapter",
    element_type: "location",
    name: "Citadel",
    dependencies: [],
    usage_count: 0,
    suggestions: [],
    edited_by_author: false,
    is_series_canonical: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    aliases: [],
    provenance: [],
    claims: [],
    chapter_numbers: [],
    chapter_count: 0,
    summary_mentions: 0,
    narrative_modes: [],
    author_override: false,
    ...overrides,
  }
}

function wikiEntry(overrides: Partial<WikiEntry>): WikiEntry {
  return {
    id: "wiki-1",
    book_id: "book-1",
    entry_type: "location",
    name: "Citadel",
    created_at: "2026-01-01T00:00:00Z",
    ...overrides,
  }
}

function userStats(overrides: Partial<UserStats["private"]>): UserStats {
  return {
    public: {
      total_books_read: 0,
      total_words_read: 0,
    },
    private: {
      total_uploads: 0,
      total_token_consumption: 0,
      total_chapters_tracked: 0,
      saved_quotes: 0,
      active_analyzed_words: 12500,
      active_word_limit: 20000,
      active_words_remaining: 7500,
      monthly_processed_words: 0,
      monthly_processed_word_limit: 0,
      monthly_processed_words_remaining: 0,
      source_storage_bytes: 1.25 * 1024 ** 3,
      source_storage_limit_bytes: 5 * 1024 ** 3,
      source_storage_remaining_bytes: 0,
      allowances_enforced: true,
      ...overrides,
    },
    writing: {
      today: { words: 0 },
      this_week: { words: 0 },
      this_month: { words: 0 },
      this_year: { words: 0 },
      last_24_hours: { words: 0 },
      last_7_days: { words: 0 },
      last_30_days: { words: 0 },
      last_year: { words: 0 },
      heatmap: [],
      entries_today: [],
    },
  }
}

describe("WorldbuildingWorkspace helpers", () => {
  it("extracts API error detail only from axios-style errors", () => {
    expect(getApiErrorDetail({ isAxiosError: true, response: { data: { detail: "No quota left" } } })).toBe("No quota left")
    expect(getApiErrorDetail({ isAxiosError: true, response: { data: { detail: ["bad"] } } })).toBeNull()
    expect(getApiErrorDetail(new Error("plain"))).toBeNull()
  })

  it("summarizes records by preferred text fields or compact key/value fallback", () => {
    expect(summarizeRecord("Already summarized")).toBe("Already summarized")
    expect(summarizeRecord({ title: "  Canon conflict  ", reason: "ignored" })).toBe("Canon conflict")
    expect(summarizeRecord({ chapter_title: "", source_scope: "chapter", confidence: 0.82, empty: "" })).toBe(
      "source scope: chapter - confidence: 0.82"
    )
  })

  it("formats element and severity labels", () => {
    expect(formatElementType("magic_system")).toBe("magic system")
    expect(formatElementType("")).toBe("element")
    expect(severityClass("critical", true)).toContain("text-rose")
    expect(severityClass("high", false)).toContain("text-amber")
    expect(severityClass("low", true)).toContain("text-slate")
  })

  it("returns stable light and dark UI classes", () => {
    expect(panelClass(true)).toContain("bg-[#0a1322]")
    expect(softPanelClass(false)).toContain("bg-stone-50")
    expect(eyebrowClass(true)).toContain("uppercase")
    expect(titleTextClass(false)).toContain("text-stone-950")
    expect(bodyTextClass(true)).toContain("text-slate-300")
    expect(mutedTextClass(false)).toContain("text-stone-500")
    expect(inputClass(true)).toContain("focus:border-sky")
    expect(secondaryButtonClass(false)).toContain("hover:bg-stone")
    expect(primaryButtonClass("violet")).toContain("bg-[#6d28d9]")
    expect(accentOutlineButtonClass("amber", true)).toContain("text-amber")
    expect(dangerButtonClass(false)).toContain("text-rose")
    expect(mutedActionClass(true, "teal")).toContain("opacity-80")
    expect(badgeClass(false)).toContain("rounded-full")
    expect(accentBadgeClass("blue", true)).toContain("text-sky")
    expect(accentDotClass("violet", false)).toBe("bg-violet-500")
  })

  it("derives document and note state without mutating source arrays", () => {
    const documents = [
      worldDocument({ id: "one", word_count: 900 }),
      worldDocument({ id: "two", word_count: null }),
      worldDocument({ id: "three", word_count: 100 }),
    ]
    const notes = [
      worldNote({ id: "open-linked", status: "open", linked_gap_id: "gap-1" }),
      worldNote({ id: "addressed-linked", status: "addressed", linked_gap_id: "gap-2" }),
      worldNote({ id: "open-unlinked", status: "open", linked_gap_id: null }),
    ]

    expect(findSelectedWorldDocument(documents, "two")?.id).toBe("two")
    expect(findSelectedWorldDocument(documents, "missing")).toBeNull()
    expect(countWorldDocumentWords(documents)).toBe(1000)
    expect([...getOpenGapIds(notes)]).toEqual(["gap-1"])
    expect(groupWorldNotesByStatus(notes).open.map((note) => note.id)).toEqual(["open-linked", "open-unlinked"])
    expect(groupWorldNotesByStatus(notes).addressed.map((note) => note.id)).toEqual(["addressed-linked"])
  })

  it("summarizes wiki and extracted element types with fallback buckets", () => {
    expect(summarizeWikiEntryTypes([wikiEntry({ entry_type: "location" }), wikiEntry({ entry_type: "location" }), wikiEntry({ entry_type: "" })])).toEqual({
      location: 2,
      entry: 1,
    })
    expect(
      summarizeWorldElementTypes([
        worldElement({ element_type: "culture" }),
        worldElement({ element_type: "culture" }),
        worldElement({ element_type: "" }),
      ])
    ).toEqual({
      culture: 2,
      element: 1,
    })
  })

  it("prefers integration suggestions and sorts visible elements by source, usage, and name", () => {
    const analysisElement = worldElement({ id: "analysis", suggestions: [{ title: "Use later" }] })
    const integrationElement = worldElement({ id: "integration", suggestions: [{ title: "Use now" }] })
    const integration = {
      world_elements: [integrationElement, worldElement({ id: "ignored", suggestions: [] })],
    } as WorldIntegrationResult
    const analysis = {
      world_elements: [analysisElement],
    } as WorldGapResult

    expect(getSuggestionElements(integration, analysis).map((element) => element.id)).toEqual(["integration"])
    expect(getSuggestionElements(null, analysis).map((element) => element.id)).toEqual(["analysis"])

    const visible = getVisibleWorldElements([
      worldElement({ id: "low", source_scope: "chapter", usage_count: 10, name: "Zeta" }),
      worldElement({ id: "alpha", source_scope: "worldbuilding", usage_count: 1, name: "Alpha" }),
      worldElement({ id: "beta", source_scope: "worldbuilding", usage_count: 1, name: "Beta" }),
      worldElement({ id: "high", source_scope: "chapter", usage_count: 12, name: "High" }),
    ])

    expect(visible.map((element) => element.id)).toEqual(["alpha", "beta", "high", "low"])
  })

  it("limits visible item lists and formats upload limit status", () => {
    expect(getVisibleItems(["a", "b", "c"], false, 2)).toEqual(["a", "b"])
    expect(getVisibleItems(["a", "b", "c"], true, 2)).toEqual(["a", "b", "c"])
    expect(buildUploadLimitNote(null)).toBeNull()
    expect(buildUploadLimitNote(userStats({}))).toBe("12,500/20,000 active words · 1.3/5 GB source storage.")
    expect(buildUploadLimitNote(userStats({ allowances_enforced: false }))).toBe(
      "12,500/20,000 active words · 1.3/5 GB source storage (reporting only)."
    )
  })
})
