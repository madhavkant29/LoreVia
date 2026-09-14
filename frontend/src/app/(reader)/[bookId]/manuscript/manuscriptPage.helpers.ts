import { buildSceneOutline, countWords, formatReadingTimeLabel } from "@/lib/utils/manuscriptEditor"
import { formatIndex } from "@/lib/utils/chapterLabels"
import type {
  BookNote,
  ManuscriptAnnotation,
  ManuscriptWorkspaceTree,
  PreWritingCheck,
  SaveState,
} from "@/types/book"
import type { PlotThread, TimelineResponse } from "@/types/reader"
import type { Character } from "@/types/character"
import { textToHtml } from "./manuscriptPage.formatting"
export {
  annotationCategoryLabel,
  buildManuscriptInspectorClasses,
  buildSceneDraftStorageKey,
  buildTemplateNoteBody,
  buildTemplateOutlineBlock,
  chapterMediaSrc,
  escapeAttribute,
  escapeHtml,
  escapeHtmlAttribute,
  getSceneDropSlotLabel,
  hydrateChapterMediaHtml,
  resolveManuscriptDraftFontStack,
  textToHtml,
} from "./manuscriptPage.formatting"

export type ManuscriptBookDraft = { title: string; text: string; html: string }
export type BookDraftMap = Record<number, ManuscriptBookDraft>
export type ManuscriptChapterListItem = { number: number; title?: string | null }
export type ManuscriptIndexFormat = Parameters<typeof formatIndex>[1]
export type ManuscriptPreviewSection = {
  id: string
  eyebrow: string
  title: string
  html: string
}
export type FullBookPageMapItem = {
  chapter: number
  title: string
  words: number
  pages: number
  startPage: number
  endPage: number
}
export type ManuscriptReferenceItem = {
  id: string
  chapter: number
  title: string
  excerpt: string
  source: string
}
export type ManuscriptCharacterCardDraft = {
  arcSummary: string
  description: string
  personalityTags: string
  motivations: string
  fears: string
}
export type ManuscriptCharacterNotePayload = {
  title: string
  body: string
  folderSegments: string[]
}
export type ManuscriptChapterAutosaveState = Record<
  number,
  { status: "pending" | "saved" | "error"; updatedAt?: string }
>

export function manuscriptApproxPages(wordCount: number) {
  return Math.max(1, Math.ceil(wordCount / 500))
}

export function manuscriptReadingTime(wordCount: number) {
  return formatReadingTimeLabel(wordCount > 0 ? Math.max(1, Math.ceil(wordCount / 250)) : 0)
}

export function manuscriptGoalProgress(wordCount: number, target: number | null | undefined) {
  if (!target) return null
  return Math.min(100, Math.round((wordCount / target) * 100))
}

export function countBookDraftWords(bookDrafts: BookDraftMap) {
  return Object.values(bookDrafts).reduce((sum, draft) => sum + countWords(draft.text), 0)
}

export function buildFullBookPageMap(
  chapterListItems: ManuscriptChapterListItem[],
  bookDrafts: BookDraftMap,
): FullBookPageMapItem[] {
  const ordered = chapterListItems
    .map((chapter) => {
      const draft = bookDrafts[chapter.number]
      const words = countWords(draft?.text ?? "")
      const pages = manuscriptApproxPages(words)
      return {
        chapter: chapter.number,
        title: draft?.title || chapter.title || `Chapter ${chapter.number}`,
        words,
        pages,
      }
    })
    .sort((a, b) => a.chapter - b.chapter)

  let currentPage = 1
  return ordered.map((item) => {
    const mapped = {
      ...item,
      startPage: currentPage,
      endPage: currentPage + item.pages - 1,
    }
    currentPage += item.pages
    return mapped
  })
}

export function findChapterForPage(
  fullBookPageMap: FullBookPageMapItem[],
  page: number,
) {
  return fullBookPageMap.find((item) => page >= item.startPage && page <= item.endPage) ?? null
}

export function buildActiveChapterDisplayTitle({
  chapterTitle,
  chapterListItems,
  activeChapterNumber,
}: {
  chapterTitle: string
  chapterListItems: ManuscriptChapterListItem[]
  activeChapterNumber: number
}) {
  return chapterTitle.trim()
    || chapterListItems.find((chapter) => chapter.number === activeChapterNumber)?.title?.trim()
    || `Chapter ${activeChapterNumber}`
}

export function buildActiveChapterHeading(activeChapterNumber: number, activeChapterDisplayTitle: string) {
  return `${activeChapterNumber}. ${activeChapterDisplayTitle}`
}

export function manuscriptPageSummaryLabel({
  draftSurfaceMode,
  previewPageCount,
  approxPages,
}: {
  draftSurfaceMode: "edit" | "paged"
  previewPageCount: number
  approxPages: number
}) {
  return draftSurfaceMode === "paged"
    ? `${previewPageCount} preview page${previewPageCount === 1 ? "" : "s"}`
    : `~${approxPages} pages`
}

export function buildDraftSurfaceSummaryLabel({
  draftSurfaceMode,
  editorMode,
}: {
  draftSurfaceMode: "edit" | "paged"
  editorMode: "chapter" | "book"
}) {
  if (draftSurfaceMode === "paged") return "Paged preview"
  return editorMode === "chapter" ? "Single document" : "Full manuscript"
}

export function buildManuscriptReferenceItems({
  recallResults,
  review,
  reviewPassages,
}: {
  recallResults: Array<{ chapter_num: number; chapter_title?: string | null; summary: string; chunk_index?: number | null }>
  review: { insertion_opportunities?: Array<{ target_chapter: number; target_chapter_title?: string | null; what_to_add: string }> } | null | undefined
  reviewPassages: Array<{ chapter_num: number; chapter_title?: string | null; excerpt: string; chunk_index?: number | null }>
}): ManuscriptReferenceItem[] {
  const recallItems = recallResults.map((result, index) => ({
    id: `search-${index}`,
    chapter: result.chapter_num,
    title: result.chapter_title || `Chapter ${result.chapter_num}`,
    excerpt: result.summary,
    source: typeof result.chunk_index === "number" ? `Search · chunk ${result.chunk_index}` : "Search",
  }))
  const reviewItems = reviewPassages.map((passage, index) => ({
    id: `review-${index}`,
    chapter: passage.chapter_num,
    title: passage.chapter_title || `Chapter ${passage.chapter_num}`,
    excerpt: passage.excerpt,
    source: typeof passage.chunk_index === "number" ? `Continuity · chunk ${passage.chunk_index}` : "Continuity",
  }))
  const insertionItems = (review?.insertion_opportunities ?? []).map((item, index) => ({
    id: `insert-${index}`,
    chapter: item.target_chapter,
    title: item.target_chapter_title || `Chapter ${item.target_chapter}`,
    excerpt: item.what_to_add,
    source: "Insertion suggestion",
  }))
  return [...insertionItems, ...reviewItems, ...recallItems]
    .filter((item, index, arr) => arr.findIndex((candidate) => candidate.id === item.id) === index)
    .slice(0, 12)
}

export function buildChapterRowStats(
  chapterListItems: ManuscriptChapterListItem[],
  bookDrafts: BookDraftMap,
) {
  const stats: Record<number, { wordCount: number; sceneCount: number; readingTime: string }> = {}
  for (const chapter of chapterListItems) {
    const draftText = bookDrafts[chapter.number]?.text ?? ""
    const wordCount = countWords(draftText)
    stats[chapter.number] = {
      wordCount,
      sceneCount: buildSceneOutline(draftText).length,
      readingTime: manuscriptReadingTime(wordCount),
    }
  }
  return stats
}

export function filterChapterListItems<T extends ManuscriptChapterListItem>(
  chapterListItems: T[],
  search: string,
) {
  const query = search.trim().toLowerCase()
  if (!query) return chapterListItems
  return chapterListItems.filter((chapter) => {
    const title = chapter.title?.toLowerCase() ?? ""
    return title.includes(query) || `chapter ${chapter.number}`.includes(query)
  })
}

export function getChapterLinkedNotes(notes: BookNote[], activeChapterNumber: number) {
  return notes.filter((note) => note.chapter_number === activeChapterNumber)
}

export function getGeneralManuscriptNotes(notes: BookNote[]) {
  return notes.filter((note) => note.chapter_number === null)
}

export function getChapterAnnotations(
  annotations: ManuscriptAnnotation[],
  activeChapterNumber: number,
) {
  return annotations.filter((annotation) => annotation.chapter_number === activeChapterNumber)
}

export function getOpenManuscriptAnnotations(annotations: ManuscriptAnnotation[]) {
  return annotations.filter((annotation) => annotation.status !== "resolved")
}

export function getResolvedManuscriptAnnotations(annotations: ManuscriptAnnotation[]) {
  return annotations.filter((annotation) => annotation.status === "resolved")
}

export function filterWorkspaceSceneGroups(
  workspaceTree: ManuscriptWorkspaceTree | null | undefined,
  search: string,
) {
  if (!workspaceTree) return []
  const query = search.trim().toLowerCase()
  if (!query) return workspaceTree.scene_groups
  return workspaceTree.scene_groups
    .map((group) => ({
      ...group,
      scenes: group.scenes.filter((scene) =>
        [scene.title, scene.description ?? "", scene.body ?? "", scene.path].some((value) =>
          value.toLowerCase().includes(query)
        )
      ),
    }))
    .filter((group) => group.scenes.length > 0)
}

export function buildStructureVersionByChapter(
  workspaceTree: ManuscriptWorkspaceTree | null | undefined,
) {
  const next: Record<number, number> = {}
  for (const chapter of workspaceTree?.chapters ?? []) {
    next[chapter.chapter_number] = chapter.structure_version
  }
  return next
}

export function getActiveChapterContextCharacters(preWritingCheck: PreWritingCheck | null | undefined) {
  return (preWritingCheck?.active_characters ?? []).slice(0, 4)
}

export function getActiveThreadSummary(preWritingCheck: PreWritingCheck | null | undefined) {
  return preWritingCheck?.unresolved_threads.slice(0, 3) ?? []
}

export function getRightRailThreadItems(
  plotThreads: PlotThread[],
  rightRailPlotThreads: PlotThread[],
) {
  return plotThreads.length
    ? plotThreads
    : rightRailPlotThreads.filter((thread) => thread.status !== "resolved").slice(0, 8)
}

export function buildRecentEventSummary({
  preWritingCheck,
  rightRailTimelineData,
  activeChapterNumber,
}: {
  preWritingCheck: PreWritingCheck | null | undefined
  rightRailTimelineData: TimelineResponse | null | undefined
  activeChapterNumber: number
}) {
  if (preWritingCheck?.recent_events.length) {
    return preWritingCheck.recent_events.slice(0, 3)
  }
  return (rightRailTimelineData?.events ?? [])
    .filter((event) => event.chapter_number <= activeChapterNumber)
    .slice(-3)
    .reverse()
    .map((event) => ({
      chapter_number: event.chapter_number,
      detail: event.detail || event.title,
    }))
}

export function getWarningSummary(preWritingCheck: PreWritingCheck | null | undefined) {
  return preWritingCheck?.alerts.slice(0, 3) ?? []
}

export function manuscriptSaveStateLabel({
  chapterNumber,
  saving,
  dirtyDrafts,
  autosaveState,
}: {
  chapterNumber: number
  saving: boolean
  dirtyDrafts: number[]
  autosaveState: ManuscriptChapterAutosaveState
}) {
  if (saving) return "Saving..."
  if (!dirtyDrafts.includes(chapterNumber)) return "Saved"

  const chapterAutosave = autosaveState[chapterNumber]
  if (chapterAutosave?.status === "pending") return "Autosaving..."
  if (chapterAutosave?.status === "saved") return "Autosaved locally"
  if (chapterAutosave?.status === "error") return "Local save failed"
  return "Unsaved"
}

export function manuscriptSaveStateTone(label: string, isDark: boolean) {
  if (label === "Saved") {
    return isDark ? "bg-emerald-500/10 text-emerald-200" : "bg-emerald-100 text-emerald-800"
  }
  if (label === "Local save failed") {
    return isDark ? "bg-rose-500/10 text-rose-200" : "bg-rose-100 text-rose-800"
  }
  return isDark ? "bg-amber-500/10 text-amber-200" : "bg-amber-100 text-amber-800"
}

export function manuscriptAutosaveMetaLabel({
  chapterNumber,
  dirtyDrafts,
  autosaveState,
}: {
  chapterNumber: number
  dirtyDrafts: number[]
  autosaveState: ManuscriptChapterAutosaveState
}) {
  const chapterAutosave = autosaveState[chapterNumber]
  if (!dirtyDrafts.includes(chapterNumber) || chapterAutosave?.status !== "saved" || !chapterAutosave.updatedAt) {
    return null
  }
  return `Local autosave at ${new Date(chapterAutosave.updatedAt).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`
}

export function activeManuscriptSaveState({
  saving,
  chapterTitleSaveState,
  activeChapterAutosaveStatus,
  dirtyDrafts,
  activeChapterNumber,
}: {
  saving: boolean
  chapterTitleSaveState: SaveState | undefined
  activeChapterAutosaveStatus: ManuscriptChapterAutosaveState[number]["status"] | undefined
  dirtyDrafts: number[]
  activeChapterNumber: number
}): SaveState {
  if (saving) return "saving"
  if (chapterTitleSaveState === "error") return "error"
  if (activeChapterAutosaveStatus === "error") return "error"
  if (dirtyDrafts.includes(activeChapterNumber)) return "offline_draft"
  return "saved"
}

export function formatManuscriptChapterHeading(
  chapterNumber: number,
  title: string,
  chapterIndexFormat: ManuscriptIndexFormat,
) {
  return `${chapterNumber}. ${title.trim() || `Chapter ${formatIndex(chapterNumber, chapterIndexFormat)}`}`
}

export function buildChapterPreviewSections(
  activeChapterNumber: number,
  activeChapterDisplayTitle: string,
  html: string,
  chapterIndexFormat: ManuscriptIndexFormat,
): ManuscriptPreviewSection[] {
  return [
    {
      id: `chapter-preview-${activeChapterNumber}`,
      eyebrow: `Chapter ${formatIndex(activeChapterNumber, chapterIndexFormat)}`,
      title: activeChapterDisplayTitle,
      html,
    },
  ]
}

export function buildFullBookPreviewSections({
  editorMode,
  draftSurfaceMode,
  chapterListItems,
  bookDrafts,
  chapterIndexFormat,
}: {
  editorMode: "chapter" | "book"
  draftSurfaceMode: "edit" | "paged"
  chapterListItems: ManuscriptChapterListItem[]
  bookDrafts: BookDraftMap
  chapterIndexFormat: ManuscriptIndexFormat
}): ManuscriptPreviewSection[] {
  if (editorMode !== "book" || draftSurfaceMode !== "paged") return []
  return chapterListItems.map((chapter) => {
    const draft = bookDrafts[chapter.number] ?? {
      title: chapter.title || `Chapter ${chapter.number}`,
      text: "",
      html: textToHtml(""),
    }
    return {
      id: `book-preview-${chapter.number}`,
      eyebrow: `Chapter ${formatIndex(chapter.number, chapterIndexFormat)}`,
      title: draft.title || chapter.title || `Chapter ${chapter.number}`,
      html: draft.html,
    }
  })
}

export function parseChapterHeadingInput(
  value: string,
  fallbackNumber: number,
  fallbackTitle: string,
) {
  const trimmed = value.trim()
  if (!trimmed) {
    return { chapterNumber: fallbackNumber, title: fallbackTitle.trim() || `Chapter ${fallbackNumber}` }
  }

  const matched = trimmed.match(/^(\d+)\.\s*(.+)$/)
  if (!matched) {
    return { chapterNumber: fallbackNumber, title: trimmed }
  }

  return {
    chapterNumber: Number.parseInt(matched[1], 10) || fallbackNumber,
    title: matched[2].trim() || fallbackTitle.trim() || `Chapter ${fallbackNumber}`,
  }
}

export function buildManuscriptCharacterCardDraft(character: Character): ManuscriptCharacterCardDraft {
  return {
    arcSummary: character.arc_summary ?? "",
    description: character.description ?? "",
    personalityTags: (character.personality_tags ?? []).join(", "),
    motivations: (character.motivations ?? []).join(", "),
    fears: (character.fears ?? []).join(", "),
  }
}

export function buildManuscriptCharacterNotePayload(character: Character): ManuscriptCharacterNotePayload {
  return {
    title: character.name,
    body: [
      `**${character.name}** (${character.role ?? "background"})`,
      character.arc_summary ? `\nArc: ${character.arc_summary}` : "",
      character.personality_tags?.length ? `\nPersonality: ${character.personality_tags.join(", ")}` : "",
      character.motivations?.length ? `\nMotivations: ${character.motivations.join("; ")}` : "",
    ].filter(Boolean).join("\n"),
    folderSegments: ["Characters", character.name],
  }
}
