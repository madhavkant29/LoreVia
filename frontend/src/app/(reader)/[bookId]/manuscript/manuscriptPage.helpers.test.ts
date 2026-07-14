import { describe, expect, it } from "vitest"

import {
  activeManuscriptSaveState,
  annotationCategoryLabel,
  buildActiveChapterDisplayTitle,
  buildActiveChapterHeading,
  buildChapterPreviewSections,
  buildChapterRowStats,
  buildFullBookPageMap,
  buildFullBookPreviewSections,
  buildManuscriptInspectorClasses,
  buildManuscriptCharacterCardDraft,
  buildManuscriptCharacterNotePayload,
  buildManuscriptReferenceItems,
  buildRecentEventSummary,
  buildSceneDraftStorageKey,
  buildStructureVersionByChapter,
  buildDraftSurfaceSummaryLabel,
  buildTemplateNoteBody,
  buildTemplateOutlineBlock,
  countBookDraftWords,
  chapterMediaSrc,
  escapeAttribute,
  escapeHtml,
  escapeHtmlAttribute,
  filterChapterListItems,
  filterWorkspaceSceneGroups,
  findChapterForPage,
  getChapterAnnotations,
  getChapterLinkedNotes,
  getGeneralManuscriptNotes,
  getActiveChapterContextCharacters,
  getActiveThreadSummary,
  getOpenManuscriptAnnotations,
  getResolvedManuscriptAnnotations,
  getRightRailThreadItems,
  getSceneDropSlotLabel,
  getWarningSummary,
  hydrateChapterMediaHtml,
  formatManuscriptChapterHeading,
  manuscriptApproxPages,
  manuscriptAutosaveMetaLabel,
  manuscriptGoalProgress,
  manuscriptPageSummaryLabel,
  manuscriptReadingTime,
  manuscriptSaveStateLabel,
  manuscriptSaveStateTone,
  parseChapterHeadingInput,
  resolveManuscriptDraftFontStack,
  textToHtml,
} from "./manuscriptPage.helpers"
import type { ChapterData, ChapterMedia } from "@/types/reader"
import type { BookNote, ManuscriptAnnotation, ManuscriptWorkspaceTree, NovelScene, PreWritingCheck, WritingTemplate } from "@/types/book"
import type { PlotThread, TimelineResponse } from "@/types/reader"
import type { Character } from "@/types/character"

function media(overrides: Partial<ChapterMedia>): ChapterMedia {
  return {
    id: "media-1",
    chapter_id: "chapter-1",
    marker: "[[image:storm]]",
    sort_order: 1,
    content_type: "image/png",
    content_base64: "abc123",
    url: null,
    alt_text: null,
    created_at: "2026-06-01T00:00:00Z",
    ...overrides,
  } as unknown as ChapterMedia
}

function chapter(overrides: Partial<ChapterData>): ChapterData {
  return {
    id: "chapter-1",
    book_id: "book-1",
    chapter_number: 1,
    title: "Storm",
    text_content: "First paragraph\n\nSecond paragraph",
    html_content: null,
    media: [],
    ...overrides,
  } as unknown as ChapterData
}

const template = {
  title: "Scene Card",
  description: "  Track the scene purpose. ",
  content: "  - POV:\n- Stakes: ",
} as WritingTemplate

describe("manuscript page helpers", () => {
  it("escapes HTML text and attributes consistently", () => {
    expect(escapeHtml("<Mira & Jon>")).toBe("&lt;Mira &amp; Jon&gt;")
    expect(escapeAttribute('Mira "Storm"')).toBe("Mira &quot;Storm&quot;")
    expect(escapeHtmlAttribute('x<&"')).toBe("x&lt;&amp;&quot;")
  })

  it("converts plain text and embedded media into safe chapter HTML", () => {
    expect(textToHtml("")).toBe("<p></p>")
    expect(textToHtml("One\nline\n\nTwo")).toBe("<p>One<br>line</p><p>Two</p>")
    expect(chapterMediaSrc(media({ url: "https://cdn.example/storm.png" }))).toBe("https://cdn.example/storm.png")
    expect(chapterMediaSrc(media({ url: null }))).toBe("data:image/png;base64,abc123")

    const html = hydrateChapterMediaHtml(
      chapter({
        html_content: "<p>Before [[image:storm]] after</p>",
        media: [media({ marker: "[[image:storm]]", url: 'https://cdn.example/storm&"x.png' })],
      })
    )

    expect(html).toContain('<img src="https://cdn.example/storm&amp;&quot;x.png"')
    expect(html).toContain('alt="[[image:storm]]"')
    expect(html).not.toContain("Before [[image:storm]] after")
  })

  it("derives manuscript editor labels and storage keys", () => {
    expect(resolveManuscriptDraftFontStack("sans")).toContain("Space Grotesk")
    expect(resolveManuscriptDraftFontStack("times")).toContain("Times New Roman")
    expect(getSceneDropSlotLabel(0, 3)).toBe("Drop at start")
    expect(getSceneDropSlotLabel(2, 5)).toBe("Drop at position 3")
    expect(getSceneDropSlotLabel(5, 5)).toBe("Drop at end")
    expect(buildSceneDraftStorageKey("book-1", { id: "scene-1" } as NovelScene, 2)).toContain("scene-1")
    expect(buildSceneDraftStorageKey("book-1", null, 2)).toContain("new:2")
  })

  it("derives manuscript inspector classes for dark and light themes", () => {
    const dark = buildManuscriptInspectorClasses(true)
    const light = buildManuscriptInspectorClasses(false)

    expect(dark.rail).toContain("bg-[#0b0f11]")
    expect(dark.secondaryButton).toContain("text-slate-200")
    expect(light.rail).toContain("bg-white")
    expect(light.secondaryButton).toContain("text-stone-700")
    expect(dark.primaryButton).toBe(light.primaryButton)
  })

  it("builds reusable template text and annotation labels", () => {
    expect(buildTemplateNoteBody(template)).toBe("# Scene Card\n\nTrack the scene purpose.\n\n- POV:\n- Stakes:")
    expect(buildTemplateOutlineBlock(template)).toContain("Purpose: Track the scene purpose.")
    expect(annotationCategoryLabel("line_edit")).toBe("Line Edit")
    expect(annotationCategoryLabel("custom_category")).toBe("custom_category")
  })

  it("derives manuscript metrics, page maps, and preview sections", () => {
    const drafts = {
      2: { title: "Second", text: "one two three", html: "<p>Second</p>" },
      1: { title: "First", text: "one ".repeat(501), html: "<p>First</p>" },
    }

    expect(countBookDraftWords(drafts)).toBe(504)
    expect(manuscriptApproxPages(0)).toBe(1)
    expect(manuscriptApproxPages(501)).toBe(2)
    expect(manuscriptReadingTime(251)).toBe("2 min read")
    expect(manuscriptGoalProgress(500, 1000)).toBe(50)
    expect(manuscriptGoalProgress(500, 0)).toBeNull()
    const pageMap = buildFullBookPageMap([{ number: 2, title: "Two" }, { number: 1, title: "One" }], drafts)
    expect(pageMap).toMatchObject([
      { chapter: 1, startPage: 1, endPage: 2 },
      { chapter: 2, startPage: 3, endPage: 3 },
    ])
    expect(findChapterForPage(pageMap, 1)?.chapter).toBe(1)
    expect(findChapterForPage(pageMap, 3)?.chapter).toBe(2)
    expect(findChapterForPage(pageMap, 99)).toBeNull()
    expect(buildActiveChapterDisplayTitle({
      chapterTitle: " Draft title ",
      chapterListItems: [{ number: 2, title: "List title" }],
      activeChapterNumber: 2,
    })).toBe("Draft title")
    expect(buildActiveChapterDisplayTitle({
      chapterTitle: " ",
      chapterListItems: [{ number: 2, title: " List title " }],
      activeChapterNumber: 2,
    })).toBe("List title")
    expect(buildActiveChapterDisplayTitle({
      chapterTitle: "",
      chapterListItems: [],
      activeChapterNumber: 5,
    })).toBe("Chapter 5")
    expect(buildActiveChapterHeading(2, "Storm")).toBe("2. Storm")
    expect(manuscriptPageSummaryLabel({
      draftSurfaceMode: "paged",
      previewPageCount: 1,
      approxPages: 5,
    })).toBe("1 preview page")
    expect(manuscriptPageSummaryLabel({
      draftSurfaceMode: "paged",
      previewPageCount: 3,
      approxPages: 5,
    })).toBe("3 preview pages")
    expect(manuscriptPageSummaryLabel({
      draftSurfaceMode: "edit",
      previewPageCount: 3,
      approxPages: 5,
    })).toBe("~5 pages")
    expect(buildDraftSurfaceSummaryLabel({ draftSurfaceMode: "paged", editorMode: "book" })).toBe("Paged preview")
    expect(buildDraftSurfaceSummaryLabel({ draftSurfaceMode: "edit", editorMode: "chapter" })).toBe("Single document")
    expect(buildDraftSurfaceSummaryLabel({ draftSurfaceMode: "edit", editorMode: "book" })).toBe("Full manuscript")
    expect(buildChapterRowStats([{ number: 2, title: "Two" }], drafts)[2]).toMatchObject({
      wordCount: 3,
      sceneCount: 1,
    })
    expect(formatManuscriptChapterHeading(3, "", "arabic")).toBe("3. Chapter 3")
    expect(buildChapterPreviewSections(4, "Storm", "<p>Body</p>", "arabic")[0]).toMatchObject({
      id: "chapter-preview-4",
      title: "Storm",
    })
    expect(buildFullBookPreviewSections({
      editorMode: "book",
      draftSurfaceMode: "paged",
      chapterListItems: [{ number: 1, title: "One" }],
      bookDrafts: drafts,
      chapterIndexFormat: "arabic",
    })[0]).toMatchObject({ id: "book-preview-1", html: "<p>First</p>" })
    expect(buildFullBookPreviewSections({
      editorMode: "chapter",
      draftSurfaceMode: "paged",
      chapterListItems: [{ number: 1, title: "One" }],
      bookDrafts: drafts,
      chapterIndexFormat: "arabic",
    })).toEqual([])
  })

  it("builds manuscript reference items and parses editable chapter headings", () => {
    expect(buildManuscriptReferenceItems({
      recallResults: [{ chapter_num: 2, chapter_title: "Two", summary: "Recall", chunk_index: 3 }],
      review: { insertion_opportunities: [{ target_chapter: 1, target_chapter_title: "One", what_to_add: "Add clue" }] },
      reviewPassages: [{ chapter_num: 4, chapter_title: null, excerpt: "Continuity", chunk_index: null }],
    })).toMatchObject([
      { id: "insert-0", source: "Insertion suggestion" },
      { id: "review-0", source: "Continuity" },
      { id: "search-0", source: "Search · chunk 3" },
    ])

    expect(parseChapterHeadingInput("", 2, "Old")).toEqual({ chapterNumber: 2, title: "Old" })
    expect(parseChapterHeadingInput("12. New title", 2, "Old")).toEqual({ chapterNumber: 12, title: "New title" })
    expect(parseChapterHeadingInput("Standalone", 2, "Old")).toEqual({ chapterNumber: 2, title: "Standalone" })
  })

  it("filters manuscript chapter lists, notes, annotations, and scene groups", () => {
    const notes = [
      { id: "note-1", chapter_number: 2, title: "Chapter note" },
      { id: "note-2", chapter_number: null, title: "General note" },
    ] as BookNote[]
    const annotations = [
      { id: "annotation-1", chapter_number: 2, status: "open" },
      { id: "annotation-2", chapter_number: 2, status: "resolved" },
      { id: "annotation-3", chapter_number: 3, status: "open" },
    ] as ManuscriptAnnotation[]
    const workspaceTree = {
      chapters: [
        { chapter_number: 1, structure_version: 3 },
        { chapter_number: 2, structure_version: 7 },
      ],
      scene_groups: [
        {
          chapter_number: 1,
          chapter_title: "One",
          scenes: [
            { id: "scene-1", title: "Arrival", description: "Gate opens", body: "Mira enters", path: "1/arrival" },
            { id: "scene-2", title: "Quiet", description: null, body: "Rest", path: "1/quiet" },
          ],
        },
        {
          chapter_number: 2,
          chapter_title: "Two",
          scenes: [
            { id: "scene-3", title: "Confrontation", description: "Argument", body: "Jon speaks", path: "2/confrontation" },
          ],
        },
      ],
      note_paths: [],
    } as unknown as ManuscriptWorkspaceTree

    expect(filterChapterListItems([{ number: 1, title: "Arrival" }, { number: 2, title: "Storm" }], "chapter 2")).toEqual([
      { number: 2, title: "Storm" },
    ])
    expect(getChapterLinkedNotes(notes, 2).map((note) => note.id)).toEqual(["note-1"])
    expect(getGeneralManuscriptNotes(notes).map((note) => note.id)).toEqual(["note-2"])
    expect(getChapterAnnotations(annotations, 2).map((annotation) => annotation.id)).toEqual(["annotation-1", "annotation-2"])
    expect(getOpenManuscriptAnnotations(getChapterAnnotations(annotations, 2)).map((annotation) => annotation.id)).toEqual(["annotation-1"])
    expect(getResolvedManuscriptAnnotations(getChapterAnnotations(annotations, 2)).map((annotation) => annotation.id)).toEqual(["annotation-2"])
    expect(filterWorkspaceSceneGroups(workspaceTree, "gate")).toMatchObject([
      { chapter_number: 1, scenes: [{ id: "scene-1" }] },
    ])
    expect(filterWorkspaceSceneGroups(workspaceTree, "")).toHaveLength(2)
    expect(buildStructureVersionByChapter(workspaceTree)).toEqual({ 1: 3, 2: 7 })
  })

  it("builds right-rail writing summaries from prewriting and fallback data", () => {
    const preWritingCheck = {
      upcoming_chapter: 4,
      active_characters: [
        { id: "character-1", name: "Mira" },
        { id: "character-2", name: "Jon" },
        { id: "character-3", name: "Sefa" },
        { id: "character-4", name: "Rin" },
        { id: "character-5", name: "Extra" },
      ],
      unresolved_threads: [
        { id: "thread-1", title: "Gate" },
        { id: "thread-2", title: "Map" },
        { id: "thread-3", title: "Debt" },
        { id: "thread-4", title: "Extra" },
      ],
      recent_events: [
        { chapter_number: 3, detail: "Mira enters" },
        { chapter_number: 2, detail: "Jon warns her" },
        { chapter_number: 1, detail: "Gate opens" },
        { chapter_number: 0, detail: "Extra" },
      ],
      alerts: [
        { kind: "continuity", title: "Check timeline" },
        { kind: "character", title: "Clarify motive" },
        { kind: "pacing", title: "Slow reveal" },
        { kind: "extra", title: "Extra" },
      ],
    } as unknown as PreWritingCheck
    const fallbackThreads = [
      { id: "thread-a", status: "open" },
      { id: "thread-b", status: "resolved" },
      { id: "thread-c", status: "open" },
    ] as PlotThread[]
    const explicitThreads = [{ id: "thread-main", status: "open" }] as PlotThread[]
    const timeline = {
      events: [
        { chapter_number: 1, title: "One", detail: "First" },
        { chapter_number: 2, title: "Two", detail: null },
        { chapter_number: 3, title: "Three", detail: "Third" },
        { chapter_number: 5, title: "Future", detail: "Ignore" },
      ],
    } as TimelineResponse

    expect(getActiveChapterContextCharacters(preWritingCheck).map((character) => character.name)).toEqual(["Mira", "Jon", "Sefa", "Rin"])
    expect(getActiveThreadSummary(preWritingCheck).map((thread) => thread.title)).toEqual(["Gate", "Map", "Debt"])
    expect(getRightRailThreadItems(explicitThreads, fallbackThreads)).toEqual(explicitThreads)
    expect(getRightRailThreadItems([], fallbackThreads).map((thread) => thread.id)).toEqual(["thread-a", "thread-c"])
    expect(buildRecentEventSummary({
      preWritingCheck,
      rightRailTimelineData: timeline,
      activeChapterNumber: 3,
    }).map((event) => event.detail)).toEqual(["Mira enters", "Jon warns her", "Gate opens"])
    expect(buildRecentEventSummary({
      preWritingCheck: null,
      rightRailTimelineData: timeline,
      activeChapterNumber: 3,
    })).toEqual([
      { chapter_number: 3, detail: "Third" },
      { chapter_number: 2, detail: "Two" },
      { chapter_number: 1, detail: "First" },
    ])
    expect(getWarningSummary(preWritingCheck).map((alert) => alert.title)).toEqual(["Check timeline", "Clarify motive", "Slow reveal"])
  })

  it("derives manuscript save labels, tones, metadata, and active save state", () => {
    const autosaveState = {
      2: { status: "pending" as const },
      3: { status: "saved" as const, updatedAt: "2026-07-05T12:34:00Z" },
      4: { status: "error" as const },
    }

    expect(manuscriptSaveStateLabel({
      chapterNumber: 1,
      saving: true,
      dirtyDrafts: [1],
      autosaveState,
    })).toBe("Saving...")
    expect(manuscriptSaveStateLabel({
      chapterNumber: 1,
      saving: false,
      dirtyDrafts: [],
      autosaveState,
    })).toBe("Saved")
    expect(manuscriptSaveStateLabel({
      chapterNumber: 2,
      saving: false,
      dirtyDrafts: [2],
      autosaveState,
    })).toBe("Autosaving...")
    expect(manuscriptSaveStateLabel({
      chapterNumber: 3,
      saving: false,
      dirtyDrafts: [3],
      autosaveState,
    })).toBe("Autosaved locally")
    expect(manuscriptSaveStateLabel({
      chapterNumber: 4,
      saving: false,
      dirtyDrafts: [4],
      autosaveState,
    })).toBe("Local save failed")
    expect(manuscriptSaveStateTone("Saved", false)).toContain("emerald")
    expect(manuscriptSaveStateTone("Local save failed", true)).toContain("rose")
    expect(manuscriptSaveStateTone("Unsaved", true)).toContain("amber")
    expect(manuscriptAutosaveMetaLabel({
      chapterNumber: 3,
      dirtyDrafts: [3],
      autosaveState,
    })).toContain("Local autosave at")
    expect(manuscriptAutosaveMetaLabel({
      chapterNumber: 3,
      dirtyDrafts: [],
      autosaveState,
    })).toBeNull()
    expect(activeManuscriptSaveState({
      saving: true,
      chapterTitleSaveState: undefined,
      activeChapterAutosaveStatus: undefined,
      dirtyDrafts: [],
      activeChapterNumber: 1,
    })).toBe("saving")
    expect(activeManuscriptSaveState({
      saving: false,
      chapterTitleSaveState: "error",
      activeChapterAutosaveStatus: undefined,
      dirtyDrafts: [],
      activeChapterNumber: 1,
    })).toBe("error")
    expect(activeManuscriptSaveState({
      saving: false,
      chapterTitleSaveState: undefined,
      activeChapterAutosaveStatus: undefined,
      dirtyDrafts: [1],
      activeChapterNumber: 1,
    })).toBe("offline_draft")
    expect(activeManuscriptSaveState({
      saving: false,
      chapterTitleSaveState: undefined,
      activeChapterAutosaveStatus: undefined,
      dirtyDrafts: [],
      activeChapterNumber: 1,
    })).toBe("saved")
  })

  it("builds manuscript character card drafts and note payloads", () => {
    const character = {
      name: "Mira",
      role: "mc",
      arc_summary: "Learns to trust the crew.",
      description: "A careful navigator.",
      personality_tags: ["guarded", "precise"],
      motivations: ["protect Sefa", "find the gate"],
      fears: ["betrayal"],
    } as Character

    expect(buildManuscriptCharacterCardDraft(character)).toEqual({
      arcSummary: "Learns to trust the crew.",
      description: "A careful navigator.",
      personalityTags: "guarded, precise",
      motivations: "protect Sefa, find the gate",
      fears: "betrayal",
    })
    expect(buildManuscriptCharacterNotePayload(character)).toEqual({
      title: "Mira",
      body: "**Mira** (mc)\n\nArc: Learns to trust the crew.\n\nPersonality: guarded, precise\n\nMotivations: protect Sefa; find the gate",
      folderSegments: ["Characters", "Mira"],
    })
  })
})
