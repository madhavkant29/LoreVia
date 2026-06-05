"use client"

import type { ReactNode } from "react"
import type { Route } from "next"
import axios from "axios"
import { useQuery } from "@tanstack/react-query"
import { startTransition, Suspense, useDeferredValue, useEffect, useMemo, useRef, useState } from "react"
import dynamic from "next/dynamic"
import Link from "next/link"
import { useParams, useRouter, useSearchParams } from "next/navigation"

import { useConfirmDialog } from "@/components/ui/ConfirmDialog"
import { Skeleton } from "@/components/ui/Skeleton"
import { ManuscriptExportMenu } from "@/components/reader/ManuscriptExportMenu"
import { ManuscriptModeSwitch } from "@/components/reader/ManuscriptModeSwitch"
import { ManuscriptSceneOrderStatus, type SceneOrderSaveState } from "@/components/reader/ManuscriptSceneOrderStatus"
import { ManuscriptVersionHistory } from "@/components/reader/ManuscriptVersionHistory"
import { ManuscriptWorkspaceSidebarHeader } from "@/components/reader/ManuscriptWorkspaceSidebarHeader"
import type { ManuscriptDraftFontFamily } from "@/components/reader/ManuscriptNonWriteWorkspace"
import type { TemplateDestination } from "@/components/reader/ManuscriptPlanWorkspace"
import { booksApi } from "@/lib/api/books"
import { deriveReprocessCta } from "@/lib/utils/editorProjectCta"
import { intelligenceApi } from "@/lib/api/intelligence"
import { asQueryKey, bookCacheKey } from "@/lib/query/cacheKeys"
import { readerApi } from "@/lib/api/reader"
import {
  buildManuscriptAutosaveKey,
  buildSceneAutosaveKey,
  buildSceneOutline,
  countWords,
  formatReadingTimeLabel,
  parseAutosaveDraft,
  parseSceneAutosaveDraft,
  serializeAutosaveDraft,
  serializeSceneAutosaveDraft,
} from "@/lib/utils/manuscriptEditor"
import {
  applyAnnotationHighlights,
  buildAnnotationSelectionAnchor,
  clearAnnotationHighlights,
  MANUSCRIPT_ANNOTATION_CATEGORIES,
  MANUSCRIPT_ANNOTATION_CATEGORY_LABELS,
  type ManuscriptSelectionAnchor,
  scrollAnnotationRangeIntoView,
} from "@/lib/utils/manuscriptAnnotations"
import { saveContextualVaultNote } from "@/lib/utils/notes"
import { htmlToPlainText, renderRichTextHtml, sanitizeRichTextHtml } from "@/lib/utils/richText"
import { moveSceneIdToIndex, reorderWorkspaceSceneTree } from "@/lib/utils/sceneWorkspace"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { capture } from "@/lib/analytics/posthog"
import type { Book, BookNote, ChapterVersion, ChapterVersionDetail, CorkboardCard, EmotionalArcOverview, ManuscriptAnnotation, ManuscriptAnnotationCategory, ManuscriptFrontMatter, ManuscriptWorkspaceTree, NovelScene, PreWritingCheck, ReadabilityMetrics, SceneVersion, SceneVersionDetail, WriterWorkspace, WritingTemplate } from "@/types/book"
import type { Character } from "@/types/character"
import { AddCharacterFromSelection } from "@/components/characters/AddCharacterFromSelection"
import type { AdvisorSuggestion, EditorialReview, EditorialReviewPassage, InlineContinuityResponse, ManuscriptSynopsis } from "@/types/intelligence"
import type { ChapterListResponse, PlotThread, SearchResult } from "@/types/reader"

const WhatsTheWordPanel = dynamic(
  () => import("@/components/intelligence/WhatsTheWordPanel").then((module) => module.WhatsTheWordPanel),
  {
    loading: () => <DeferredPanelLoadingState label="Loading word finder..." />,
  }
)

const EditorToolbar = dynamic(
  () => import("@/components/editor/SharedRichTextEditor").then((module) => module.EditorToolbar),
)

const RichTextEditor = dynamic(
  () => import("@/components/editor/SharedRichTextEditor").then((module) => module.RichTextEditor),
)

const ManuscriptPagedPreview = dynamic(
  () => import("@/components/reader/ManuscriptPagedPreview").then((module) => module.ManuscriptPagedPreview),
  {
    loading: () => <DeferredPanelLoadingState label="Preparing preview..." />,
  }
)

const ManuscriptPlanWorkspace = dynamic(
  () => import("@/components/reader/ManuscriptPlanWorkspace").then((module) => module.ManuscriptPlanWorkspace),
  {
    loading: () => <DeferredPanelLoadingState label="Loading planning workspace..." />,
  }
)

const ManuscriptNonWriteWorkspace = dynamic(
  () => import("@/components/reader/ManuscriptNonWriteWorkspace").then((module) => module.ManuscriptNonWriteWorkspace),
  {
    loading: () => <DeferredPanelLoadingState label="Loading analysis workspace..." />,
  }
)

const ManuscriptOverlayDialogs = dynamic(
  () => import("@/components/reader/ManuscriptOverlayDialogs").then((module) => module.ManuscriptOverlayDialogs),
  {
    loading: () => null,
  }
)

const ManuscriptWriteRightRail = dynamic(
  () => import("@/components/reader/ManuscriptWriteRightRail").then((module) => module.ManuscriptWriteRightRail),
  {
    loading: () => <DeferredPanelLoadingState label="Loading writing tools..." />,
  }
)

type EditorMode = "chapter" | "book"
type DraftSurfaceMode = "edit" | "paged"
type BookDraftMap = Record<number, { title: string; text: string; html: string }>
type WorkspaceTab = "write" | "plan" | "analysis"
type RightPane = "context" | "advisor" | "notes" | "arcs" | "insights" | "character"
type DraggedSceneState = { chapterNumber: number; sceneId: string }
type SceneDropTarget = { chapterNumber: number; index: number }
const WORKSPACE_TABS: Array<{ id: WorkspaceTab; label: string; title: string }> = [
  { id: "write", label: "Write", title: "Write manuscript" },
  { id: "plan", label: "Plan", title: "Plan story structure" },
  { id: "analysis", label: "Analysis", title: "Review manuscript and characters" },
]
const EMPTY_CHARACTERS: Character[] = []
const EMPTY_ANNOTATIONS: ManuscriptAnnotation[] = []
const EMPTY_NOTES: BookNote[] = []
const EMPTY_CHAPTER_VERSIONS: ChapterVersion[] = []
const SCENE_DRAG_SCENE_ID_MIME = "application/x-lorevia-scene-id"
const SCENE_DRAG_CHAPTER_MIME = "application/x-lorevia-chapter-number"

function resolveManuscriptDraftFontStack(fontFamily: ManuscriptDraftFontFamily): string {
  if (fontFamily === "georgia") return 'Georgia, "Times New Roman", serif'
  if (fontFamily === "sans") return '"Space Grotesk", "Avenir Next", "Segoe UI Variable Text", sans-serif'
  if (fontFamily === "italian-old-style") {
    return '"Iowan Old Style", "Palatino Linotype", "Book Antiqua", Palatino, Georgia, serif'
  }
  if (fontFamily === "eb-garamond") return '"EB Garamond", Garamond, "Times New Roman", Georgia, serif'
  return '"Times New Roman", Georgia, serif'
}

function getSceneDropSlotLabel(index: number, totalScenes: number) {
  if (index <= 0) return "Drop at start"
  if (index >= totalScenes) return "Drop at end"
  return `Drop at position ${index + 1}`
}

function buildSceneDraftStorageKey(bookId: string, scene?: NovelScene | null, chapterNumber?: number | null) {
  return buildSceneAutosaveKey(bookId, scene?.id ?? `new:${chapterNumber ?? "unassigned"}`)
}

function buildTemplateNoteBody(template: WritingTemplate) {
  return [
    `# ${template.title}`,
    "",
    template.description.trim(),
    "",
    template.content.trim(),
  ].filter((line) => line !== undefined && line !== null).join("\n")
}

function buildTemplateOutlineBlock(template: WritingTemplate) {
  return [
    `## Draft outline: ${template.title}`,
    "",
    template.description.trim() ? `Purpose: ${template.description.trim()}` : "",
    "",
    template.content.trim(),
  ].filter((line) => line !== undefined && line !== null).join("\n")
}

export default function ManuscriptPage() {
  return (
    <Suspense fallback={null}>
      <ManuscriptPageInner />
    </Suspense>
  )
}

function ManuscriptPageInner() {
  const { bookId } = useParams<{ bookId: string }>()
  const router = useRouter()
  const searchParams = useSearchParams()
  const confirm = useConfirmDialog()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  useEffect(() => {
    capture("author_manuscript_opened", { book_id: bookId })
  }, [bookId])

  const [book, setBook] = useState<Book | null>(null)
  const [characters, setCharacters] = useState<Character[]>([])
  const [chapterList, setChapterList] = useState<ChapterListResponse | null>(null)
  const [selectedChapter, setSelectedChapter] = useState<number | null>(null)
  const [draftChapterNumber, setDraftChapterNumber] = useState<number | null>(null)
  const [chapterTitle, setChapterTitle] = useState("")
  const [text, setText] = useState("")
  const [html, setHtml] = useState("")
  const [replaceExisting, setReplaceExisting] = useState(false)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [deletingChapterNumber, setDeletingChapterNumber] = useState<number | null>(null)
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [review, setReview] = useState<EditorialReview | null>(null)
  const [reviewPassages, setReviewPassages] = useState<EditorialReviewPassage[]>([])
  const [inlineContinuity, setInlineContinuity] = useState<InlineContinuityResponse | null>(null)
  const [suggestions, setSuggestions] = useState<AdvisorSuggestion[]>([])
  const [plotThreads, setPlotThreads] = useState<PlotThread[]>([])
  const [preWritingCheck, setPreWritingCheck] = useState<PreWritingCheck | null>(null)
  const [chapterVersions, setChapterVersions] = useState<ChapterVersion[]>([])
  const [chapterVersionDetail, setChapterVersionDetail] = useState<ChapterVersionDetail | null>(null)
  const [chapterVersionNameDraft, setChapterVersionNameDraft] = useState("")
  const [workspaceTree, setWorkspaceTree] = useState<ManuscriptWorkspaceTree | null>(null)
  const [sceneSearch, setSceneSearch] = useState("")
  const [chapterSearch, setChapterSearch] = useState("")
  const [collapsedSceneGroups, setCollapsedSceneGroups] = useState<Record<string, boolean>>({})
  const [draggedScene, setDraggedScene] = useState<DraggedSceneState | null>(null)
  const [sceneDropTarget, setSceneDropTarget] = useState<SceneDropTarget | null>(null)
  const [sceneOrderSaveState, setSceneOrderSaveState] = useState<Record<number, SceneOrderSaveState>>({})
  const [sceneEditorOpen, setSceneEditorOpen] = useState(false)
  const [editingScene, setEditingScene] = useState<NovelScene | null>(null)
  const [sceneTitleDraft, setSceneTitleDraft] = useState("")
  const [sceneDescriptionDraft, setSceneDescriptionDraft] = useState("")
  const [sceneBodyDraft, setSceneBodyDraft] = useState("")
  const [sceneHtmlDraft, setSceneHtmlDraft] = useState("<p></p>")
  const [sceneChapterDraft, setSceneChapterDraft] = useState<number | null>(null)
  const [sceneSaving, setSceneSaving] = useState(false)
  const [restoringVersionId, setRestoringVersionId] = useState<string | null>(null)
  const [sceneVersions, setSceneVersions] = useState<SceneVersion[]>([])
  const [sceneVersionDetail, setSceneVersionDetail] = useState<SceneVersionDetail | null>(null)
  const [sceneVersionNameDraft, setSceneVersionNameDraft] = useState("")
  const [restoringSceneVersionId, setRestoringSceneVersionId] = useState<string | null>(null)
  const [writerWorkspace, setWriterWorkspace] = useState<WriterWorkspace | null>(null)
  const [workspaceSaving, setWorkspaceSaving] = useState(false)
  const [readability, setReadability] = useState<ReadabilityMetrics | null>(null)
  const [readabilityLoading, setReadabilityLoading] = useState(false)
  const [emotionalArc, setEmotionalArc] = useState<EmotionalArcOverview | null>(null)
  const [logicSelectionText, setLogicSelectionText] = useState("")
  const [tighteningSelection, setTighteningSelection] = useState(false)
  const [continuityLoading, setContinuityLoading] = useState(false)
  const [recallQuery, setRecallQuery] = useState("")
  const [recallResults, setRecallResults] = useState<SearchResult[]>([])
  const [recallCharacter, setRecallCharacter] = useState<Character | null>(null)
  const [recallLoading, setRecallLoading] = useState(false)
  const [synopsis, setSynopsis] = useState<ManuscriptSynopsis | null>(null)
  const [editorMode, setEditorMode] = useState<EditorMode>("chapter")
  const [draftSurfaceMode, setDraftSurfaceMode] = useState<DraftSurfaceMode>("edit")
  const [workspaceTab, setWorkspaceTab] = useState<WorkspaceTab>("write")
  const [fontSize, setFontSize] = useState(12)
  const [fontSizeLocked, setFontSizeLocked] = useState(false)
  const [fontFamily, setFontFamily] = useState<ManuscriptDraftFontFamily>("times")
  const [lineHeight, setLineHeight] = useState(1.8)
  const [showPageGuides, setShowPageGuides] = useState(true)
  const [chapterPreviewPageCount, setChapterPreviewPageCount] = useState(1)
  const [fullBookPreviewPageCount, setFullBookPreviewPageCount] = useState(1)
  const [firstLineIndent, setFirstLineIndent] = useState(false)
  const [showLeftRail, setShowLeftRail] = useState(true)
  const [showRightRail, setShowRightRail] = useState(true)
  const [focusMode, setFocusMode] = useState(false)
  const [activeRightPane, setActiveRightPane] = useState<RightPane>("context")
  const [selectedCharCard, setSelectedCharCard] = useState<Character | null>(null)
  const [charCardEditing, setCharCardEditing] = useState(false)
  const [charCardSaving, setCharCardSaving] = useState(false)
  const [charCardDraft, setCharCardDraft] = useState<{
    arcSummary: string
    description: string
    personalityTags: string
    motivations: string
    fears: string
  }>({ arcSummary: "", description: "", personalityTags: "", motivations: "", fears: "" })
  const [showExportMenu, setShowExportMenu] = useState(false)
  const [showCompileDialog, setShowCompileDialog] = useState(false)
  const [showReprocessConfirm, setShowReprocessConfirm] = useState(false)
  const [compileFormat, setCompileFormat] = useState<"pdf" | "docx" | "epub" | "vault">("docx")
  const [includeSceneMetadataOnImport, setIncludeSceneMetadataOnImport] = useState(true)
  const [includeSceneMetadataOnExport, setIncludeSceneMetadataOnExport] = useState(true)
  const [showEditorSettings, setShowEditorSettings] = useState(false)
  const [activeEditorKey, setActiveEditorKey] = useState<string | null>(null)
  const [fullBookLoading, setFullBookLoading] = useState(false)
  const [bookDrafts, setBookDrafts] = useState<BookDraftMap>({})
  const [contentVersionByChapter, setContentVersionByChapter] = useState<Record<number, number>>({})
  const [exporting, setExporting] = useState<"pdf" | "docx" | "epub" | "vault" | null>(null)
  const [reprocessing, setReprocessing] = useState(false)
  const [jumpTarget, setJumpTarget] = useState<number | null>(null)
  const [activeFindIndex, setActiveFindIndex] = useState(0)
  const [replaceQuery, setReplaceQuery] = useState("")
  const [replaceValue, setReplaceValue] = useState("")
  const [gotoPageInput, setGotoPageInput] = useState("")
  const [showPageSetup, setShowPageSetup] = useState(false)
  const [showSearchTools, setShowSearchTools] = useState(false)
  const [notes, setNotes] = useState<BookNote[]>([])
  const [notesLoading, setNotesLoading] = useState(false)
  const [savingNote, setSavingNote] = useState(false)
  const [noteScope, setNoteScope] = useState<"chapter" | "book">("chapter")
  const [noteTitle, setNoteTitle] = useState("")
  const [noteBody, setNoteBody] = useState("")
  const [noteBodyText, setNoteBodyText] = useState("")
  const [dirtyDrafts, setDirtyDrafts] = useState<number[]>([])
  const [autosaveState, setAutosaveState] = useState<Record<number, { status: "pending" | "saved" | "error"; updatedAt?: string }>>({})
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null)
  const [editNoteTitle, setEditNoteTitle] = useState("")
  const [editNoteBody, setEditNoteBody] = useState("")
  const [editingNoteSaving, setEditingNoteSaving] = useState(false)
  const [annotations, setAnnotations] = useState<ManuscriptAnnotation[]>([])
  const [annotationsLoading, setAnnotationsLoading] = useState(false)
  const [annotationAnchor, setAnnotationAnchor] = useState<{
    quote: string
    anchorContextBefore: string | null
    anchorContextAfter: string | null
    startOffset: number
    endOffset: number
  } | null>(null)
  const [annotationDraft, setAnnotationDraft] = useState("")
  const [annotationCategory, setAnnotationCategory] = useState<ManuscriptAnnotationCategory>("general")
  const [annotationVisibility, setAnnotationVisibility] = useState<"shared" | "private">("shared")
  const [annotationActionId, setAnnotationActionId] = useState<string | null>(null)
  const [activeAnnotationId, setActiveAnnotationId] = useState<string | null>(null)
  const [newCorkboardTitle, setNewCorkboardTitle] = useState("")
  const [selectionMenu, setSelectionMenu] = useState<{ text: string; top: number; left: number } | null>(null)
  const [addCharacterOpen, setAddCharacterOpen] = useState(false)
  const [addCharacterText, setAddCharacterText] = useState("")

  useEffect(() => {
    if (loading || manuscriptReadyCapturedRef.current) return
    manuscriptReadyCapturedRef.current = true
    capture("author_manuscript_ready", {
      book_id: bookId,
      optional_panels_deferred: true,
      duration_ms:
        typeof performance !== "undefined" && manuscriptLoadStartedAtRef.current !== null
          ? Math.round(performance.now() - manuscriptLoadStartedAtRef.current)
          : null,
    })
  }, [bookId, loading])

  const chapterRefs = useRef<Record<number, HTMLDivElement | null>>({})
  const searchInputRef = useRef<HTMLInputElement | null>(null)
  const manuscriptSectionRef = useRef<HTMLDivElement | null>(null)
  const initialChapterLoadedRef = useRef<number | null>(null)
  const handledSceneIntentRef = useRef(false)
  const annotationRangesRef = useRef<Map<string, Range>>(new Map())
  const pendingAnnotationJumpIdRef = useRef<string | null>(null)
  const selectionMenuAnchorRef = useRef<ManuscriptSelectionAnchor | null>(null)
  const manuscriptReadyCapturedRef = useRef(false)
  const manuscriptLoadStartedAtRef = useRef<number | null>(typeof performance !== "undefined" ? performance.now() : null)
  const deferredChecksSeedRef = useRef<{ chapterNumber: number; text: string } | null>(null)
  const lastAutoChecksRef = useRef<Record<number, number>>({})

  const { data: charactersData = EMPTY_CHARACTERS } = useQuery<Character[]>({
    queryKey: [`manuscript:${bookId}:characters`],
    queryFn: () => booksApi.getCharacters(bookId),
    staleTime: 60_000,
  })
  const { data: writerWorkspaceData = null, refetch: refetchWriterWorkspace } = useQuery<WriterWorkspace | null>({
    queryKey: [bookCacheKey(bookId, "writer-workspace")],
    queryFn: () => booksApi.getWriterWorkspace(bookId),
    staleTime: 60_000,
  })
  const { data: emotionalArcData = null, refetch: refetchEmotionalArc } = useQuery<EmotionalArcOverview | null>({
    queryKey: [bookCacheKey(bookId, "emotional-arc")],
    queryFn: () => booksApi.getEmotionalArc(bookId),
    enabled: workspaceTab === "plan" || activeRightPane === "arcs" || activeRightPane === "insights",
    staleTime: 60_000,
  })
  const { data: synopsisData = null, refetch: refetchSynopsis } = useQuery<ManuscriptSynopsis | null>({
    queryKey: [`manuscript:${bookId}:synopsis:minimal`],
    queryFn: () => intelligenceApi.synopsis(bookId, "minimal"),
    enabled: activeRightPane === "insights",
    staleTime: 60_000,
  })
  const { data: workspaceTreeData = null, refetch: refetchWorkspaceTree } = useQuery<ManuscriptWorkspaceTree | null>({
    queryKey: [bookCacheKey(bookId, "workspace-tree")],
    queryFn: () => booksApi.getWorkspaceTree(bookId),
    staleTime: 60_000,
  })
  const annotationChapterNumber = selectedChapter ?? draftChapterNumber
  const {
    data: annotationsData = EMPTY_ANNOTATIONS,
    isFetching: annotationsQueryLoading,
  } = useQuery<ManuscriptAnnotation[]>({
    queryKey: [`manuscript:${bookId}:annotations:${annotationChapterNumber ?? "none"}`],
    queryFn: () => annotationChapterNumber === null ? Promise.resolve(EMPTY_ANNOTATIONS) : booksApi.getManuscriptAnnotations(bookId, annotationChapterNumber),
    enabled: annotationChapterNumber !== null && (workspaceTab === "write" || activeRightPane === "notes"),
    staleTime: 30_000,
  })
  const {
    data: notesData = EMPTY_NOTES,
    isFetching: notesQueryLoading,
  } = useQuery<BookNote[]>({
    queryKey: [`manuscript:${bookId}:notes`],
    queryFn: () => booksApi.getBookNotes(bookId),
    enabled: showRightRail && activeRightPane === "notes",
    staleTime: 30_000,
  })
  const { data: chapterVersionsData = EMPTY_CHAPTER_VERSIONS } = useQuery<ChapterVersion[]>({
    queryKey: selectedChapter !== null ? [`manuscript:${bookId}:chapter-versions:${selectedChapter}`] : [`manuscript:${bookId}:chapter-versions:none`],
    queryFn: async () => {
      if (selectedChapter === null) return []
      return booksApi.getChapterVersions(bookId, selectedChapter)
    },
    enabled: showLeftRail && selectedChapter !== null,
  })

  const nextChapterNumber = useMemo(() => {
    const numbers = chapterList?.chapters.map((chapter) => chapter.number) ?? []
    return numbers.length ? Math.max(...numbers) + 1 : 1
  }, [chapterList])

  const activeChapterNumber = selectedChapter ?? draftChapterNumber ?? nextChapterNumber
  const { data: preWritingCheckData = null } = useQuery<PreWritingCheck | null>({
    queryKey: [`manuscript:${bookId}:prewriting:${activeChapterNumber}`],
    queryFn: () => booksApi.getPreWritingCheck(bookId, activeChapterNumber),
    enabled: workspaceTab !== "write" && !loading && activeChapterNumber > 0,
    staleTime: 30_000,
  })
  const sceneDraftDirty = useMemo(() => {
    if (!sceneEditorOpen) return false
    const baseTitle = editingScene?.title ?? ""
    const baseDescription = editingScene?.description ?? ""
    const baseBody = editingScene?.body ?? ""
    const baseChapterNumber = editingScene?.chapter_number ?? (selectedChapter ?? null)
    return (
      sceneTitleDraft !== baseTitle
      || sceneDescriptionDraft !== baseDescription
      || sceneBodyDraft !== baseBody
      || sceneChapterDraft !== baseChapterNumber
    )
  }, [editingScene, sceneBodyDraft, sceneChapterDraft, sceneDescriptionDraft, sceneEditorOpen, sceneTitleDraft, selectedChapter])
  const hasPendingEdits = dirtyDrafts.length > 0 || sceneDraftDirty
  const reprocessCta = useMemo(
    () => deriveReprocessCta(book, hasPendingEdits),
    [book, hasPendingEdits],
  )

  const sheetStyle = {
    fontSize: `${fontSize}pt`,
    lineHeight: String(lineHeight),
    fontFamily: resolveManuscriptDraftFontStack(fontFamily),
  } as const

  const chapterWordCount = useMemo(() => countWords(text), [text])
  const chapterApproxPages = useMemo(() => Math.max(1, Math.ceil(chapterWordCount / 500)), [chapterWordCount])
  const chapterReadingTime = useMemo(() => formatReadingTimeLabel(chapterWordCount > 0 ? Math.max(1, Math.ceil(chapterWordCount / 250)) : 0), [chapterWordCount])
  const chapterSceneOutline = useMemo(() => buildSceneOutline(text), [text])
  const fullBookWordCount = useMemo(() => Object.values(bookDrafts).reduce((sum, draft) => sum + countWords(draft.text), 0), [bookDrafts])
  const fullBookApproxPages = useMemo(() => Math.max(1, Math.ceil(fullBookWordCount / 500)), [fullBookWordCount])
  const fullBookReadingTime = useMemo(() => formatReadingTimeLabel(fullBookWordCount > 0 ? Math.max(1, Math.ceil(fullBookWordCount / 250)) : 0), [fullBookWordCount])
  const chapterGoalProgress = useMemo(() => {
    const target = writerWorkspace?.word_count_goals.chapter_target ?? 0
    if (!target) return null
    return Math.min(100, Math.round((chapterWordCount / target) * 100))
  }, [chapterWordCount, writerWorkspace])
  const bookGoalProgress = useMemo(() => {
    const target = writerWorkspace?.word_count_goals.book_target ?? 0
    if (!target) return null
    return Math.min(100, Math.round((fullBookWordCount / target) * 100))
  }, [fullBookWordCount, writerWorkspace])
  const deferredChapterSearch = useDeferredValue(chapterSearch)
  const deferredSceneSearch = useDeferredValue(sceneSearch)
  const leftRailVisible = workspaceTab === "write" && !focusMode && showLeftRail
  const rightRailVisible = workspaceTab !== "plan" && !focusMode && showRightRail
  const desktopLayoutClass = leftRailVisible && rightRailVisible
    ? "xl:grid-cols-[22rem_minmax(0,1fr)_23.5rem]"
    : leftRailVisible
      ? "xl:grid-cols-[22rem_minmax(0,1fr)]"
      : rightRailVisible
        ? "xl:grid-cols-[minmax(0,1fr)_23.5rem]"
        : "xl:grid-cols-1"
  const chapterListItems = chapterList?.chapters ?? []
  const fullBookPageMap = useMemo(() => {
    const ordered = (chapterList?.chapters ?? [])
      .map((chapter) => {
        const draft = bookDrafts[chapter.number]
        const words = countWords(draft?.text ?? "")
        const pages = Math.max(1, Math.ceil(words / 500))
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
  }, [bookDrafts, chapterList])
  const fullBookReferenceItems = useMemo(() => {
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
  }, [recallResults, review, reviewPassages])
  const pagedPreviewPreset = writerWorkspace?.publishing.active_preset ?? "standard_manuscript"
  const chapterLinkedNotes = useMemo(
    () => notes.filter((note) => note.chapter_number === activeChapterNumber),
    [activeChapterNumber, notes]
  )
  const chapterManualNotes = chapterLinkedNotes
  const chapterAnnotations = useMemo(
    () => annotations.filter((annotation) => annotation.chapter_number === activeChapterNumber),
    [activeChapterNumber, annotations]
  )
  const openChapterAnnotations = useMemo(
    () => chapterAnnotations.filter((annotation) => annotation.status !== "resolved"),
    [chapterAnnotations]
  )
  const resolvedChapterAnnotations = useMemo(
    () => chapterAnnotations.filter((annotation) => annotation.status === "resolved"),
    [chapterAnnotations]
  )
  const generalNotes = useMemo(
    () => notes.filter((note) => note.chapter_number === null),
    [notes]
  )
  const filteredChapterItems = useMemo(() => {
    const query = deferredChapterSearch.trim().toLowerCase()
    if (!query) return chapterListItems
    return chapterListItems.filter((chapter) => {
      const title = chapter.title?.toLowerCase() ?? ""
      return title.includes(query) || `chapter ${chapter.number}`.includes(query)
    })
  }, [chapterListItems, deferredChapterSearch])
  const chapterRowStats = useMemo(() => {
    const stats: Record<number, { wordCount: number; sceneCount: number; readingTime: string }> = {}
    for (const chapter of chapterListItems) {
      const draftText = bookDrafts[chapter.number]?.text ?? ""
      const wordCount = countWords(draftText)
      stats[chapter.number] = {
        wordCount,
        sceneCount: buildSceneOutline(draftText).length,
        readingTime: formatReadingTimeLabel(wordCount > 0 ? Math.max(1, Math.ceil(wordCount / 250)) : 0),
      }
    }
    return stats
  }, [bookDrafts, chapterListItems])
  const activeChapterDisplayTitle = chapterTitle.trim() || chapterListItems.find((chapter) => chapter.number === activeChapterNumber)?.title?.trim() || `Chapter ${activeChapterNumber}`
  const activeChapterHeading = `${activeChapterNumber}. ${activeChapterDisplayTitle}`
  const chapterPreviewSections = useMemo(() => ([
    {
      id: `chapter-preview-${activeChapterNumber}`,
      eyebrow: `Chapter ${activeChapterNumber}`,
      title: activeChapterDisplayTitle,
      html,
    },
  ]), [activeChapterDisplayTitle, activeChapterNumber, html])
  const fullBookPreviewSections = useMemo(() => {
    if (editorMode !== "book" || draftSurfaceMode !== "paged") return []
    return (chapterList?.chapters ?? [])
      .map((chapter) => {
        const draft = bookDrafts[chapter.number] ?? { title: chapter.title || `Chapter ${chapter.number}`, text: "", html: textToHtml("") }
        return {
          id: `book-preview-${chapter.number}`,
          eyebrow: `Chapter ${chapter.number}`,
          title: draft.title || chapter.title || `Chapter ${chapter.number}`,
          html: draft.html,
        }
      })
  }, [bookDrafts, chapterList, draftSurfaceMode, editorMode])
  const chapterPageSummaryLabel = draftSurfaceMode === "paged"
    ? `${chapterPreviewPageCount} preview page${chapterPreviewPageCount === 1 ? "" : "s"}`
    : `~${chapterApproxPages} pages`
  const fullBookPageSummaryLabel = draftSurfaceMode === "paged"
    ? `${fullBookPreviewPageCount} preview page${fullBookPreviewPageCount === 1 ? "" : "s"}`
    : `~${fullBookApproxPages} pages`
  const draftSurfaceSummaryLabel = draftSurfaceMode === "paged"
    ? "Paged preview"
    : editorMode === "chapter"
      ? "Single document"
      : "Full manuscript"
  const activeChapterWordTarget = writerWorkspace?.word_count_goals.chapter_target ?? 0
  const activeChapterContextCharacters = (preWritingCheck?.active_characters ?? []).slice(0, 4)
  const activeThreadSummary = preWritingCheck?.unresolved_threads.slice(0, 3) ?? []
  const recentEventSummary = preWritingCheck?.recent_events.slice(0, 3) ?? []
  const warningSummary = preWritingCheck?.alerts.slice(0, 3) ?? []
  const arcSummaryCharacter = emotionalArc?.characters[0] ?? null
  const filteredSceneGroups = useMemo(() => {
    if (!workspaceTree) return []
    const query = deferredSceneSearch.trim().toLowerCase()
    if (!query) return workspaceTree.scene_groups
    return workspaceTree.scene_groups
      .map((group) => ({
        ...group,
        scenes: group.scenes.filter((scene) =>
          [scene.title, scene.description ?? "", scene.body, scene.path].some((value) =>
            value.toLowerCase().includes(query)
          )
        ),
      }))
      .filter((group) => group.scenes.length > 0)
  }, [deferredSceneSearch, workspaceTree])
  const structureVersionByChapter = useMemo(() => {
    const next: Record<number, number> = {}
    for (const chapter of workspaceTree?.chapters ?? []) {
      next[chapter.chapter_number] = chapter.structure_version
    }
    return next
  }, [workspaceTree])
  const manuscriptFrontMatter = writerWorkspace?.manuscript_front_matter
  const openRightPane = (pane: RightPane) => {
    setActiveRightPane(pane)
    setShowRightRail(true)
  }

  const openCharCard = (char: Character) => {
    setSelectedCharCard(char)
    setCharCardEditing(false)
    setCharCardDraft({
      arcSummary: char.arc_summary ?? "",
      description: char.description ?? "",
      personalityTags: (char.personality_tags ?? []).join(", "),
      motivations: (char.motivations ?? []).join(", "),
      fears: (char.fears ?? []).join(", "),
    })
    setActiveRightPane("character")
    setShowRightRail(true)
  }

  const saveCharCard = async () => {
    if (!selectedCharCard) return
    setCharCardSaving(true)
    try {
      const updated = await booksApi.updateCharacter(bookId, selectedCharCard.id, {
        arcSummary: charCardDraft.arcSummary.trim() || null,
        description: charCardDraft.description.trim() || null,
        personalityTags: charCardDraft.personalityTags.split(",").map(t => t.trim()).filter(Boolean),
        motivations: charCardDraft.motivations.split(",").map(t => t.trim()).filter(Boolean),
        fears: charCardDraft.fears.split(",").map(t => t.trim()).filter(Boolean),
      })
      setSelectedCharCard(updated)
      setCharacters(prev => prev.map(c => c.id === updated.id ? updated : c))
      setCharCardEditing(false)
      setStatusMessage(`Character card for ${updated.name} saved.`)
    } finally {
      setCharCardSaving(false)
    }
  }

  const saveWorkspace = async (patch: Partial<WriterWorkspace>, options?: { silent?: boolean }) => {
    setWorkspaceSaving(true)
    try {
      const updated = await booksApi.updateWriterWorkspace(bookId, patch)
      setWriterWorkspace(updated)
      if (!options?.silent) setStatusMessage("Workspace preferences saved.")
    } catch {
      if (!options?.silent) setStatusMessage("Workspace save failed. Please try again.")
    } finally {
      setWorkspaceSaving(false)
    }
  }

  const syncLocalChapterFromServer = async (chapterNumber: number) => {
    const chapterMeta = chapterList?.chapters.find((item) => item.number === chapterNumber)
    const chapter = await readerApi.getChapter(bookId, chapterNumber)
    const nextTitle = chapter.chapter_title || chapterMeta?.title || `Chapter ${chapterNumber}`
    const nextText = chapter.text_content || ""
    const nextHtml = chapter.html_content || textToHtml(nextText)
    const nextContentVersion = typeof chapter.content_version === "number" ? chapter.content_version : 1
    if (selectedChapter === chapterNumber) {
      setDraftChapterNumber(null)
      setChapterTitle(nextTitle)
      setText(nextText)
      setHtml(nextHtml)
    }
    setBookDrafts((current) => ({
      ...current,
      [chapterNumber]: {
        title: nextTitle,
        text: nextText,
        html: nextHtml,
      },
    }))
    setContentVersionByChapter((current) => ({ ...current, [chapterNumber]: nextContentVersion }))
    clearDraftDirty(chapterNumber)
  }

  const refreshChapterVersionToken = async (chapterNumber: number) => {
    const chapter = await readerApi.getChapter(bookId, chapterNumber)
    const nextContentVersion = typeof chapter.content_version === "number" ? chapter.content_version : 1
    setContentVersionByChapter((current) => ({ ...current, [chapterNumber]: nextContentVersion }))
    return nextContentVersion
  }

  const loadWorkspaceTree = async () => {
    try {
      const { data: tree } = await refetchWorkspaceTree()
      if (!tree) {
        setWorkspaceTree(null)
        return
      }
      setWorkspaceTree(tree)
      setCollapsedSceneGroups((current) => {
        const next = { ...current }
        for (const group of tree.scene_groups) {
          if (!(group.id in next)) next[group.id] = !!group.collapsed_by_default
        }
        return next
      })
    } catch {
      setWorkspaceTree(null)
    }
  }

  const resetSceneDragState = () => {
    setDraggedScene(null)
    setSceneDropTarget(null)
  }

  const reorderScenesInChapter = async (chapterNumber: number, sourceSceneId: string, destinationIndex: number) => {
    if (!workspaceTree) return
    const chapterGroup = workspaceTree.scene_groups.find((group) => group.chapter_number === chapterNumber)
    if (!chapterGroup) return

    const currentSceneIds = chapterGroup.scenes.map((scene) => scene.id)
    const nextSceneIds = moveSceneIdToIndex(currentSceneIds, sourceSceneId, destinationIndex)
    if (nextSceneIds === currentSceneIds) return

    const previousTree = workspaceTree
    const expectedStructureVersion = chapterGroup.structure_version ?? structureVersionByChapter[chapterNumber] ?? 0

    setWorkspaceTree(reorderWorkspaceSceneTree(previousTree, chapterNumber, nextSceneIds))
    setSceneOrderSaveState((current) => ({ ...current, [chapterNumber]: "saving" }))

    try {
      const reordered = await booksApi.reorderChapterScenes(bookId, chapterNumber, {
        sceneIds: nextSceneIds,
        expectedStructureVersion,
      })
      setWorkspaceTree((current) =>
        current
          ? reorderWorkspaceSceneTree(
              current,
              chapterNumber,
              reordered.scenes.map((scene) => scene.id),
              reordered.structure_version
            )
          : current
      )
      setSceneOrderSaveState((current) => ({ ...current, [chapterNumber]: "saved" }))
    } catch (error) {
      setWorkspaceTree(previousTree)
      setSceneOrderSaveState((current) => ({ ...current, [chapterNumber]: "failed" }))
      if (axios.isAxiosError(error) && error.response?.status === 409) {
        setStatusMessage("Scene order changed in another session. Refreshed the chapter order.")
        void loadWorkspaceTree()
      } else {
        setStatusMessage("Could not save scene order. Reverted.")
      }
    } finally {
      resetSceneDragState()
    }
  }

  const loadSceneVersions = async (sceneId: string) => {
    try {
      setSceneVersions(await booksApi.getSceneVersions(bookId, sceneId))
    } catch {
      setSceneVersions([])
    }
  }

  const openSceneEditor = (scene?: NovelScene | null) => {
    const nextScene = scene ?? null
    const fallbackChapterNumber = nextScene?.chapter_number ?? (selectedChapter ?? null)
    const storageKey = buildSceneDraftStorageKey(bookId, nextScene, fallbackChapterNumber)
    const recoveredDraft = typeof window === "undefined" ? null : parseSceneAutosaveDraft(window.localStorage.getItem(storageKey))

    setEditingScene(nextScene)
    setSceneTitleDraft(recoveredDraft?.title ?? nextScene?.title ?? "")
    setSceneDescriptionDraft(recoveredDraft?.description ?? nextScene?.description ?? "")
    setSceneBodyDraft(recoveredDraft?.body ?? nextScene?.body ?? "")
    setSceneHtmlDraft(nextScene?.html_body ?? textToHtml(recoveredDraft?.body ?? nextScene?.body ?? ""))
    setSceneChapterDraft(recoveredDraft?.chapterNumber ?? fallbackChapterNumber)
    setSceneVersionDetail(null)
    setSceneVersionNameDraft("")
    setSceneEditorOpen(true)

    if (nextScene?.id) {
      void loadSceneVersions(nextScene.id)
    } else {
      setSceneVersions([])
    }
    if (recoveredDraft?.updatedAt) {
      setStatusMessage(`Recovered a local autosave for scene "${recoveredDraft.title || nextScene?.title || "draft"}".`)
    }
  }

  const closeSceneEditor = async () => {
    if (sceneDraftDirty) {
      const confirmed = await confirm({
        title: "Close scene editor?",
        body: "You have unsaved scene changes. Close the editor anyway?",
        confirmLabel: "Close editor",
        tone: "danger",
      })
      if (!confirmed) return
    }
    setSceneEditorOpen(false)
    setEditingScene(null)
    setSceneTitleDraft("")
    setSceneDescriptionDraft("")
    setSceneBodyDraft("")
    setSceneHtmlDraft("<p></p>")
    setSceneChapterDraft(selectedChapter ?? null)
    setSceneVersions([])
    setSceneVersionDetail(null)
    setSceneVersionNameDraft("")
  }

  useEffect(() => {
    const shouldOpenNewScene = searchParams.get("newScene") === "1"
    if (!shouldOpenNewScene || handledSceneIntentRef.current) return

    handledSceneIntentRef.current = true
    openSceneEditor(null)
    router.replace(`/${bookId}/manuscript`)
  }, [bookId, router, searchParams])

  const saveScene = async () => {
    if (!sceneTitleDraft.trim() || !sceneBodyDraft.trim()) return
    setSceneSaving(true)
    try {
      const previousChapterNumber = editingScene?.chapter_number ?? null
      const savedScene = await booksApi.saveScene(bookId, {
        id: editingScene?.id,
        title: sceneTitleDraft.trim(),
        description: sceneDescriptionDraft.trim() || null,
        body: sceneBodyDraft,
        html_body: sceneHtmlDraft,
        chapter_number: sceneChapterDraft,
        status: sceneChapterDraft ? "assigned" : "unassigned",
        sort_order: editingScene?.sort_order,
      })
      if (typeof window !== "undefined") {
        window.localStorage.removeItem(buildSceneDraftStorageKey(bookId, editingScene, previousChapterNumber))
        window.localStorage.removeItem(buildSceneDraftStorageKey(bookId, savedScene, savedScene.chapter_number ?? previousChapterNumber))
      }
      await loadWorkspaceTree()
      const chaptersToRefresh = [...new Set([previousChapterNumber, sceneChapterDraft].filter((value): value is number => typeof value === "number" && value > 0))]
      await Promise.all(chaptersToRefresh.map(syncLocalChapterFromServer))
      await closeSceneEditor()
      setStatusMessage(editingScene ? "Scene updated." : "Scene saved.")
    } finally {
      setSceneSaving(false)
    }
  }

  const removeScene = async (scene: NovelScene) => {
    await booksApi.deleteScene(bookId, scene.id)
    await loadWorkspaceTree()
    if (typeof scene.chapter_number === "number" && scene.chapter_number > 0) {
      await syncLocalChapterFromServer(scene.chapter_number)
    }
    setStatusMessage(`Deleted scene "${scene.title}".`)
  }

  const removeChapter = async (chapterNumber: number) => {
    const confirmed = await confirm({
      title: `Remove Chapter ${chapterNumber}?`,
      body: `Remove Chapter ${chapterNumber}? This deletes its manuscript text, scenes, notes, comments, and chapter intelligence. This cannot be undone.`,
      confirmLabel: "Remove chapter",
      tone: "danger",
    })
    if (!confirmed) return

    setDeletingChapterNumber(chapterNumber)
    try {
      try {
        await booksApi.deleteChapter(bookId, chapterNumber)
      } catch (error) {
        const detail = axios.isAxiosError(error) ? (error.response?.data as { detail?: unknown } | undefined)?.detail : null
        setStatusMessage(
          typeof detail === "string" && detail.trim()
            ? `Could not remove Chapter ${chapterNumber}: ${detail}`
            : `Could not remove Chapter ${chapterNumber}.`
        )
        return
      }

      if (typeof window !== "undefined") {
        window.localStorage.removeItem(buildManuscriptAutosaveKey(bookId, chapterNumber))
      }

      let bookData: Book
      let chapters: ChapterListResponse
      let workspace: ManuscriptWorkspaceTree | null
      try {
        ;[bookData, chapters, workspace] = await Promise.all([
          booksApi.get(bookId),
          readerApi.getChapterList(bookId),
          booksApi.getWorkspaceTree(bookId).catch(() => null),
        ])
      } catch {
        setStatusMessage(`Chapter ${chapterNumber} removed. Reload the editor to refresh the chapter list.`)
        return
      }

      const nextChapterNumber =
        chapters.chapters.find((chapter) => chapter.number > chapterNumber)?.number ??
        chapters.chapters[chapters.chapters.length - 1]?.number ??
        null

      setBook(bookData)
      setChapterList(chapters)
      setWorkspaceTree(workspace)
      if (workspace) {
        setCollapsedSceneGroups((current) => {
          const next = { ...current }
          for (const group of workspace.scene_groups) {
            if (!(group.id in next)) next[group.id] = !!group.collapsed_by_default
          }
          return next
        })
      }
      setBookDrafts((current) => {
        const next = { ...current }
        delete next[chapterNumber]
        return next
      })
      setContentVersionByChapter((current) => {
        const next = { ...current }
        delete next[chapterNumber]
        return next
      })
      setAutosaveState((current) => {
        const next = { ...current }
        delete next[chapterNumber]
        return next
      })
      setDirtyDrafts((current) => current.filter((item) => item !== chapterNumber))

      if (selectedChapter === chapterNumber || draftChapterNumber === chapterNumber) {
        setSelectedChapter(nextChapterNumber)
        setDraftChapterNumber(null)
        setReplaceExisting(nextChapterNumber !== null)
        setReview(null)
        setReviewPassages([])
        if (nextChapterNumber === null) {
          setChapterTitle("")
          setText("")
          setHtml(textToHtml(""))
        }
      }

      setStatusMessage(`Chapter ${chapterNumber} removed.`)
    } finally {
      setDeletingChapterNumber(null)
    }
  }

  const insertSceneIntoDraft = async (scene: NovelScene) => {
    const insertion = await booksApi.getSceneInsertion(bookId, scene.id, activeChapterNumber, "end", includeSceneMetadataOnImport)
    const separator = text.trim() ? "\n\n***\n\n" : ""
    const nextText = `${text}${separator}${insertion.body}`.trim()
    const nextHtml = insertion.html_body || textToHtml(nextText)
    setText(nextText)
    setHtml(nextHtml)
    setBookDrafts((current) => ({
      ...current,
      [activeChapterNumber]: { title: chapterTitle, text: nextText, html: nextHtml },
    }))
    markDraftDirty(activeChapterNumber)
    setStatusMessage(`Inserted scene "${insertion.title}" into chapter ${activeChapterNumber}.`)
  }

  const createSnapshot = async () => {
    if (selectedChapter === null) return
    try {
      const note = chapterVersionNameDraft.trim() || `Manual snapshot before edits to Chapter ${selectedChapter}`
      await booksApi.createChapterSnapshot(bookId, selectedChapter, note)
      setChapterVersions(await booksApi.getChapterVersions(bookId, selectedChapter))
      setChapterVersionNameDraft("")
      setStatusMessage(`Saved a snapshot for chapter ${selectedChapter}.`)
    } catch {
      setStatusMessage("Snapshot save failed. Please try again.")
    }
  }

  const restoreSnapshot = async (versionId: string) => {
    setRestoringVersionId(versionId)
    try {
      const restored = await booksApi.restoreChapterVersion(bookId, versionId)
      setSelectedChapter(restored.chapter_number)
      setDraftChapterNumber(null)
      setChapterTitle(restored.title || `Chapter ${restored.chapter_number}`)
      setText(restored.text)
      setHtml(restored.html || textToHtml(restored.text))
      setChapterVersions(restored.versions)
      setBookDrafts((current) => ({
        ...current,
        [restored.chapter_number]: {
          title: restored.title || `Chapter ${restored.chapter_number}`,
          text: restored.text,
          html: restored.html || textToHtml(restored.text),
        },
      }))
      clearDraftDirty(restored.chapter_number)
      await runAutomaticChecks(restored.chapter_number, restored.text)
      await loadWorkspaceTree()
      setStatusMessage(`Restored chapter ${restored.chapter_number} from snapshot.`)
    } finally {
      setRestoringVersionId(null)
    }
  }

  const previewSnapshot = async (versionId: string) => {
    try {
      const detail = await booksApi.getChapterVersionDetail(bookId, versionId)
      setChapterVersionDetail(detail)
    } catch {
      setStatusMessage("Could not load that snapshot preview.")
    }
  }

  const createSceneSnapshot = async () => {
    if (!editingScene?.id) return
    try {
      const note = sceneVersionNameDraft.trim() || `Manual snapshot for scene: ${editingScene.title}`
      const versions = await booksApi.createSceneSnapshot(bookId, editingScene.id, note)
      setSceneVersions(await booksApi.getSceneVersions(bookId, editingScene.id))
      setSceneVersionNameDraft("")
      setStatusMessage(`Saved a version for scene "${versions.scene_title}".`)
    } catch {
      setStatusMessage("Scene snapshot save failed. Please try again.")
    }
  }

  const compareSceneVersion = async (versionId: string) => {
    try {
      const detail = await booksApi.getSceneVersionDetail(bookId, versionId)
      setSceneVersionDetail(detail)
    } catch {
      setStatusMessage("Could not load that scene version.")
    }
  }

  const restoreSceneSnapshot = async (versionId: string) => {
    setRestoringSceneVersionId(versionId)
    try {
      const previousChapterNumber = editingScene?.chapter_number ?? null
      const restored = await booksApi.restoreSceneVersion(bookId, versionId)
      setEditingScene(restored.scene)
      setSceneTitleDraft(restored.scene.title)
      setSceneDescriptionDraft(restored.scene.description ?? "")
      setSceneBodyDraft(restored.scene.body)
      setSceneHtmlDraft(restored.scene.html_body ?? textToHtml(restored.scene.body))
      setSceneChapterDraft(restored.scene.chapter_number ?? null)
      setSceneVersions(restored.versions)
      setSceneVersionDetail(null)
      await loadWorkspaceTree()
      const chaptersToRefresh = [...new Set([previousChapterNumber, restored.scene.chapter_number].filter((value): value is number => typeof value === "number" && value > 0))]
      await Promise.all(chaptersToRefresh.map(syncLocalChapterFromServer))
      if (typeof window !== "undefined") {
        window.localStorage.removeItem(buildSceneDraftStorageKey(bookId, restored.scene, restored.scene.chapter_number ?? previousChapterNumber))
      }
      setStatusMessage(`Restored scene "${restored.scene.title}" from version history.`)
    } finally {
      setRestoringSceneVersionId(null)
    }
  }

  const addCorkboardCard = async () => {
    if (!newCorkboardTitle.trim() || !writerWorkspace) return
    const card: CorkboardCard = {
      id: `card-${Date.now()}`,
      title: newCorkboardTitle.trim(),
      description: "",
      lane: "ideas",
      status: "planned",
      chapter_number: activeChapterNumber,
      template_id: null,
    }
    await saveWorkspace({
      corkboard_cards: [...writerWorkspace.corkboard_cards, card],
    })
    setNewCorkboardTitle("")
  }

  const updateCardLane = async (cardId: string, lane: string) => {
    if (!writerWorkspace) return
    await saveWorkspace({
      corkboard_cards: writerWorkspace.corkboard_cards.map((card) => card.id === cardId ? { ...card, lane } : card),
    }, { silent: true })
  }

  const applyTemplateToChapter = async (template: WritingTemplate, destination: TemplateDestination) => {
    if (destination === "chapter_note") {
      const saved = await booksApi.saveBookNote(bookId, {
        chapterNumber: activeChapterNumber,
        title: `Template: ${template.title}`,
        body: buildTemplateNoteBody(template),
      })
      setNotes((current) => [saved, ...current.filter((note) => note.id !== saved.id)])
      setStatusMessage(`Saved ${template.title} as a chapter note.`)
      return
    }

    if (destination === "corkboard") {
      if (!writerWorkspace) return
      const card: CorkboardCard = {
        id: `card-${Date.now()}`,
        title: template.title,
        description: buildTemplateNoteBody(template),
        lane: "ideas",
        status: "planned",
        chapter_number: activeChapterNumber,
        template_id: template.id,
      }
      await saveWorkspace({
        corkboard_cards: [...writerWorkspace.corkboard_cards, card],
      })
      setStatusMessage(`Added ${template.title} to the corkboard.`)
      return
    }

    const outlineBlock = buildTemplateOutlineBlock(template)
    const nextText = text.trim() ? `${text.trim()}\n\n${outlineBlock}` : outlineBlock
    const nextHtml = textToHtml(nextText)
    setText(nextText)
    setHtml(nextHtml)
    markDraftDirty(activeChapterNumber)
    setBookDrafts((current) => ({
      ...current,
      [activeChapterNumber]: { title: chapterTitle, text: nextText, html: nextHtml },
    }))
    setStatusMessage(`Added ${template.title} as a draft outline block in chapter ${activeChapterNumber}.`)
  }

  const saveTemplates = async (templates: WritingTemplate[]) => {
    if (!writerWorkspace) return
    await saveWorkspace({ templates })
    setStatusMessage("Template saved.")
  }

  const tightenSelectedText = async () => {
    if (editorMode !== "chapter") {
      setStatusMessage("Selected-text tightening is available in chapter view.")
      return
    }
    const editor = document.querySelector<HTMLElement>(`[data-editor-key="chapter-${activeChapterNumber}"]`)
    if (!editor) {
      setStatusMessage("Click into the chapter editor first, then select the passage you want tightened.")
      return
    }
    const selection = window.getSelection()
    const selectedText = selection?.toString().trim() ?? ""
    if (!selectedText) {
      setStatusMessage("Select the passage you want tightened first.")
      return
    }
    const cachedRange = selection && selection.rangeCount > 0 ? selection.getRangeAt(0).cloneRange() : null
    setLogicSelectionText(selectedText)
    setTighteningSelection(true)
    try {
      const payload = await intelligenceApi.proseTightenStream(
        bookId,
        selectedText,
        activeChapterNumber,
        { onStage: setStatusMessage },
      )
      if (!payload.tightened_text || payload.tightened_text === selectedText) {
        setStatusMessage("No tighter rewrite was needed for the selected passage.")
        return
      }
      if (cachedRange) {
        const liveSelection = window.getSelection()
        liveSelection?.removeAllRanges()
        liveSelection?.addRange(cachedRange)
        document.execCommand("insertText", false, payload.tightened_text)
      }
      const nextHtml = sanitizeRichTextHtml(editor.innerHTML || html)
      const nextText = htmlToPlainText(nextHtml)
      setText(nextText)
      setHtml(nextHtml)
      markDraftDirty(activeChapterNumber)
      setBookDrafts((current) => ({
        ...current,
        [activeChapterNumber]: { title: chapterTitle, text: nextText, html: nextHtml },
      }))
      setStatusMessage(payload.rationale[0] || "Tightened the selected prose.")
    } finally {
      setTighteningSelection(false)
    }
  }

  const markDraftDirty = (chapterNumber: number) => {
    setDirtyDrafts((current) => (current.includes(chapterNumber) ? current : [...current, chapterNumber]))
  }

  const clearDraftDirty = (chapterNumber: number) => {
    setDirtyDrafts((current) => current.filter((value) => value !== chapterNumber))
    setAutosaveState((current) => {
      const next = { ...current }
      delete next[chapterNumber]
      return next
    })
    if (typeof window !== "undefined") {
      window.localStorage.removeItem(buildManuscriptAutosaveKey(bookId, chapterNumber))
    }
  }

  const formatChapterHeading = (chapterNumber: number, title: string) => `${chapterNumber}. ${title.trim() || `Chapter ${chapterNumber}`}`

  const parseChapterHeading = (value: string, fallbackNumber: number, fallbackTitle: string) => {
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

  const getRecoveredDraft = (chapterNumber: number, fallbackDraft: { title: string; text: string; html: string }) => {
    if (typeof window === "undefined") {
      return { draft: fallbackDraft, recovered: false as const }
    }

    const recovered = parseAutosaveDraft(window.localStorage.getItem(buildManuscriptAutosaveKey(bookId, chapterNumber)))
    if (!recovered?.text.trim()) {
      return { draft: fallbackDraft, recovered: false as const }
    }

    return {
      draft: {
        title: recovered.title.trim() || fallbackDraft.title,
        text: recovered.text,
        html: recovered.html || fallbackDraft.html,
      },
      recovered,
    }
  }

  const loadBase = async () => {
    const [bookData, chapters] = await Promise.all([
      booksApi.get(bookId),
      readerApi.getChapterList(bookId),
    ])
    setBook(bookData)
    setChapterList(chapters)
    const initialChapterNumber = chapters.chapters.some((item) => item.number === selectedChapter)
      ? selectedChapter
      : chapters.chapters[chapters.chapters.length - 1]?.number ?? null
    if (initialChapterNumber === null) {
      setSelectedChapter(null)
      return
    }
    if (selectedChapter !== initialChapterNumber) setSelectedChapter(initialChapterNumber)

    const chapterMeta = chapters.chapters.find((item) => item.number === initialChapterNumber)
    try {
      const chapter = await readerApi.getChapter(bookId, initialChapterNumber)
      const title = chapter.chapter_title || chapterMeta?.title || `Chapter ${initialChapterNumber}`
      const chapterText = chapter.text_content || ""
      const chapterHtml = chapter.html_content || textToHtml(chapterText)
      const chapterContentVersion = typeof chapter.content_version === "number" ? chapter.content_version : 1
      const recoveredDraft = getRecoveredDraft(initialChapterNumber, {
        title,
        text: chapterText,
        html: chapterHtml,
      })
      const nextDraft = recoveredDraft.draft
      deferredChecksSeedRef.current = {
        chapterNumber: initialChapterNumber,
        text: nextDraft.text.trim(),
      }
      initialChapterLoadedRef.current = initialChapterNumber
      setDraftChapterNumber(null)
      setChapterTitle(nextDraft.title)
      setText(nextDraft.text)
      setHtml(nextDraft.html)
      setBookDrafts((current) => ({
        ...current,
        [initialChapterNumber]: {
          title: nextDraft.title,
          text: nextDraft.text,
          html: nextDraft.html,
        },
      }))
      setContentVersionByChapter((current) => ({
        ...current,
        [initialChapterNumber]: chapterContentVersion,
      }))
      if (recoveredDraft.recovered) {
        markDraftDirty(initialChapterNumber)
        setAutosaveState((current) => ({
          ...current,
          [initialChapterNumber]: {
            status: "saved",
            updatedAt: recoveredDraft.recovered.updatedAt,
          },
        }))
        setStatusMessage(`Recovered a local autosave for chapter ${initialChapterNumber}.`)
      }
    } catch {
      setChapterTitle(chapterMeta?.title || `Chapter ${initialChapterNumber}`)
      setText("")
      setHtml(textToHtml(""))
    }
  }

  const updateFrontMatter = <K extends keyof ManuscriptFrontMatter>(key: K, value: ManuscriptFrontMatter[K]) => {
    setWriterWorkspace((current) => {
      if (!current) return current
      return {
        ...current,
        manuscript_front_matter: {
          ...current.manuscript_front_matter,
          [key]: value,
        },
      }
    })
  }

  useEffect(() => {
    loadBase().finally(() => setLoading(false))
  }, [bookId])

  useEffect(() => {
    setCharacters(charactersData)
  }, [charactersData])

  useEffect(() => {
    setWriterWorkspace(writerWorkspaceData)
  }, [writerWorkspaceData])

  useEffect(() => {
    setEmotionalArc(emotionalArcData)
  }, [emotionalArcData])

  useEffect(() => {
    setSynopsis(synopsisData)
  }, [synopsisData])

  useEffect(() => {
    setWorkspaceTree(workspaceTreeData)
    if (!workspaceTreeData) return
    setCollapsedSceneGroups((current) => {
      const next = { ...current }
      for (const group of workspaceTreeData.scene_groups) {
        if (!(group.id in next)) next[group.id] = !!group.collapsed_by_default
      }
      return next
    })
  }, [workspaceTreeData])

  useEffect(() => {
    setAnnotations(annotationsData)
    setAnnotationsLoading(annotationsQueryLoading)
  }, [annotationsData, annotationsQueryLoading])

  useEffect(() => {
    if (!showRightRail || activeRightPane !== "notes") return
    setNotes(notesData)
    setNotesLoading(notesQueryLoading)
  }, [activeRightPane, notesData, notesQueryLoading, showRightRail])

  useEffect(() => {
    setPreWritingCheck(preWritingCheckData)
  }, [preWritingCheckData])

  useEffect(() => {
    setChapterVersions(chapterVersionsData)
  }, [chapterVersionsData])

  useEffect(() => {
    if (selectedChapter === null) {
      setDraftChapterNumber(nextChapterNumber)
      setChapterTitle(`Chapter ${nextChapterNumber}`)
      setText("")
      setHtml(textToHtml(""))
      setReview(null)
      setReviewPassages([])
      return
    }
    if (initialChapterLoadedRef.current === selectedChapter) {
      initialChapterLoadedRef.current = null
      return
    }
    const chapterMeta = chapterList?.chapters.find((item) => item.number === selectedChapter)
    readerApi.getChapter(bookId, selectedChapter).then((chapter) => {
      const title = chapter.chapter_title || chapterMeta?.title || `Chapter ${selectedChapter}`
      const chapterText = chapter.text_content || ""
      const chapterHtml = chapter.html_content || textToHtml(chapterText)
      const chapterContentVersion = typeof chapter.content_version === "number" ? chapter.content_version : 1
      const recoveredDraft = getRecoveredDraft(selectedChapter, {
        title,
        text: chapterText,
        html: chapterHtml,
      })
      const nextDraft = recoveredDraft.draft
      deferredChecksSeedRef.current = {
        chapterNumber: selectedChapter,
        text: nextDraft.text.trim(),
      }
      setDraftChapterNumber(null)
      setChapterTitle(nextDraft.title)
      setText(nextDraft.text)
      setHtml(nextDraft.html)
      setBookDrafts((current) => ({
        ...current,
        [selectedChapter]: {
          title: nextDraft.title,
          text: nextDraft.text,
          html: nextDraft.html,
        },
      }))
      setContentVersionByChapter((current) => ({
        ...current,
        [selectedChapter]: chapterContentVersion,
      }))
      if (recoveredDraft.recovered) {
        markDraftDirty(selectedChapter)
        setAutosaveState((current) => ({
          ...current,
          [selectedChapter]: {
            status: "saved",
            updatedAt: recoveredDraft.recovered.updatedAt,
          },
        }))
        setStatusMessage(`Recovered a local autosave for chapter ${selectedChapter}.`)
      } else {
        setStatusMessage(null)
      }
      setReview(null)
      setReviewPassages([])
    }).catch(() => {
      setChapterTitle(chapterMeta?.title || `Chapter ${selectedChapter}`)
      setText("")
      setHtml(textToHtml(""))
    })
  }, [bookId, chapterList, nextChapterNumber, selectedChapter])

  useEffect(() => {
    if (!statusMessage) return
    const handle = window.setTimeout(() => setStatusMessage(null), 3200)
    return () => window.clearTimeout(handle)
  }, [statusMessage])

  useEffect(() => {
    if (typeof window === "undefined" || dirtyDrafts.length === 0) return

    setAutosaveState((current) => {
      const next = { ...current }
      for (const chapterNumber of dirtyDrafts) {
        next[chapterNumber] = {
          ...next[chapterNumber],
          status: "pending",
        }
      }
      return next
    })

    const handle = window.setTimeout(() => {
      try {
        const updatedAt = new Date().toISOString()
        for (const chapterNumber of dirtyDrafts) {
          const draft = bookDrafts[chapterNumber]
          if (!draft) continue
          window.localStorage.setItem(
            buildManuscriptAutosaveKey(bookId, chapterNumber),
            serializeAutosaveDraft({
              title: draft.title,
              text: draft.text,
              html: draft.html,
              updatedAt,
            })
          )
        }
        setAutosaveState((current) => {
          const next = { ...current }
          for (const chapterNumber of dirtyDrafts) {
            if (!(chapterNumber in next)) continue
            next[chapterNumber] = {
              status: "saved",
              updatedAt,
            }
          }
          return next
        })
      } catch {
        setAutosaveState((current) => {
          const next = { ...current }
          for (const chapterNumber of dirtyDrafts) {
            next[chapterNumber] = {
              ...next[chapterNumber],
              status: "error",
            }
          }
          return next
        })
      }
    }, 900)

    return () => window.clearTimeout(handle)
  }, [bookDrafts, bookId, dirtyDrafts])

  useEffect(() => {
    if (typeof window === "undefined" || !sceneEditorOpen || !sceneDraftDirty) return

    const handle = window.setTimeout(() => {
      try {
        window.localStorage.setItem(
          buildSceneDraftStorageKey(bookId, editingScene, sceneChapterDraft),
          serializeSceneAutosaveDraft({
            title: sceneTitleDraft,
            description: sceneDescriptionDraft,
            body: sceneBodyDraft,
            chapterNumber: sceneChapterDraft,
            updatedAt: new Date().toISOString(),
          })
        )
      } catch {
        setStatusMessage("Local scene autosave failed.")
      }
    }, 900)

    return () => window.clearTimeout(handle)
  }, [
    bookId,
    editingScene,
    sceneBodyDraft,
    sceneChapterDraft,
    sceneDescriptionDraft,
    sceneDraftDirty,
    sceneEditorOpen,
    sceneTitleDraft,
  ])

  useEffect(() => {
    if (typeof window === "undefined" || !hasPendingEdits) return

    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ""
    }

    const handlePageHide = () => {
      const draft = bookDrafts[activeChapterNumber]
      if (!draft?.text?.trim()) return
      const formData = new FormData()
      formData.append("text", draft.text)
      formData.append("html", draft.html ?? "")
      formData.append("title", (draft.title ?? "").trim() || "")
      formData.append("chapter_number", String(activeChapterNumber))
      formData.append("replace_existing", "true")
      navigator.sendBeacon(
        `/api/v1/books/${bookId}/manuscript/import`,
        formData,
      )
    }

    window.addEventListener("beforeunload", handleBeforeUnload)
    window.addEventListener("pagehide", handlePageHide)
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload)
      window.removeEventListener("pagehide", handlePageHide)
    }
  }, [hasPendingEdits, bookDrafts, activeChapterNumber, bookId])

  useEffect(() => {
    if (!showLeftRail || selectedChapter === null) {
      setChapterVersions([])
    }
  }, [selectedChapter, showLeftRail])

  useEffect(() => {
    if (editorMode !== "book" || !chapterList?.chapters.length) return
    const missingNumbers = chapterList.chapters
      .map((chapter) => chapter.number)
      .filter((number) => !(number in bookDrafts))
    if (!missingNumbers.length) return

    setFullBookLoading(true)
    Promise.all(missingNumbers.map((number) => readerApi.getChapter(bookId, number)))
      .then((chapters) => {
        const nextDrafts: BookDraftMap = {}
        const nextContentVersions: Record<number, number> = {}
        const recoveredAutosaves: Array<{ chapterNumber: number; updatedAt: string }> = []

        for (const chapter of chapters) {
          const fallbackDraft = {
            title: chapter.chapter_title || `Chapter ${chapter.chapter_number}`,
            text: chapter.text_content || "",
            html: chapter.html_content || textToHtml(chapter.text_content || ""),
          }
          const recoveredDraft = getRecoveredDraft(chapter.chapter_number, fallbackDraft)
          nextDrafts[chapter.chapter_number] = recoveredDraft.draft
          nextContentVersions[chapter.chapter_number] = typeof chapter.content_version === "number" ? chapter.content_version : 1
          if (recoveredDraft.recovered) {
            recoveredAutosaves.push({
              chapterNumber: chapter.chapter_number,
              updatedAt: recoveredDraft.recovered.updatedAt,
            })
          }
        }

        startTransition(() => {
          setBookDrafts((current) => {
            return { ...current, ...nextDrafts }
          })
          setContentVersionByChapter((current) => {
            return { ...current, ...nextContentVersions }
          })
          if (recoveredAutosaves.length > 0) {
            setDirtyDrafts((current) => {
              const next = new Set(current)
              for (const draft of recoveredAutosaves) next.add(draft.chapterNumber)
              return Array.from(next)
            })
            setAutosaveState((current) => {
              const next = { ...current }
              for (const draft of recoveredAutosaves) {
                next[draft.chapterNumber] = {
                  status: "saved",
                  updatedAt: draft.updatedAt,
                }
              }
              return next
            })
          }
        })
      })
      .finally(() => setFullBookLoading(false))
  }, [bookDrafts, bookId, chapterList, editorMode])

  useEffect(() => {
    if (editorMode !== "book" || jumpTarget === null) return
    const handle = window.setTimeout(() => {
      const node = chapterRefs.current[jumpTarget]
      if (node) {
        node.scrollIntoView({ behavior: "smooth", block: "start" })
      }
    }, 150)
    return () => window.clearTimeout(handle)
  }, [editorMode, jumpTarget, bookDrafts])

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "f") {
        event.preventDefault()
        searchInputRef.current?.focus()
        searchInputRef.current?.select()
      }
    }
    window.addEventListener("keydown", handler)
    return () => window.removeEventListener("keydown", handler)
  }, [])

  useEffect(() => {
    if (fontSizeLocked) return

    const updateFontSize = () => {
      const width = manuscriptSectionRef.current?.clientWidth ?? window.innerWidth
      if (width <= 900) {
        setFontSize(12)
      } else if (width <= 1200) {
        setFontSize(13)
      } else if (width <= 1600) {
        setFontSize(14)
      } else {
        setFontSize(15)
      }
    }

    updateFontSize()
    window.addEventListener("resize", updateFontSize)
    return () => window.removeEventListener("resize", updateFontSize)
  }, [fontSizeLocked])

  useEffect(() => {
    const trimmed = recallQuery.trim()
    if (trimmed.length < 2) {
      setRecallResults([])
      setRecallCharacter(null)
      setRecallLoading(false)
      return
    }

    const normalized = trimmed.toLowerCase()
    const exact = characters.find((character) =>
      character.name.toLowerCase() === normalized || character.aliases.some((alias) => alias.toLowerCase() === normalized)
    ) || null
    setRecallCharacter(exact)

    const handle = window.setTimeout(() => {
      setRecallLoading(true)
      readerApi.search(bookId, trimmed, 9999)
        .then((results) => setRecallResults(results.slice(0, 6)))
        .catch(() => setRecallResults([]))
        .finally(() => setRecallLoading(false))
    }, 250)

    return () => window.clearTimeout(handle)
  }, [bookId, characters, recallQuery])

  useEffect(() => {
    setActiveFindIndex(0)
  }, [recallResults.length, recallQuery])

  useEffect(() => {
    setAnnotationAnchor(null)
    setAnnotationDraft("")
    selectionMenuAnchorRef.current = null
  }, [activeChapterNumber])

  useEffect(() => {
    if (focusMode) return
    if (workspaceTab === "write") {
      setShowLeftRail(true)
      setShowRightRail(true)
      setActiveRightPane((current) => current === "insights" ? "context" : current)
      return
    }
    if (workspaceTab === "plan") {
      setShowLeftRail(false)
      setShowRightRail(false)
      return
    }
    if (workspaceTab === "analysis") {
      setShowLeftRail(false)
      setShowRightRail(true)
      setActiveRightPane((current) => current === "character" ? "character" : "insights")
    }
  }, [focusMode, workspaceTab])

  useEffect(() => {
    if (workspaceTab !== "write" || editorMode !== "chapter" || draftSurfaceMode !== "edit") {
      setSelectionMenu(null)
      return
    }

    const syncSelectionMenu = () => {
      const selection = window.getSelection()
      const selectedText = selection?.toString().trim() ?? ""
      const editor = document.querySelector<HTMLElement>(`[data-editor-key="chapter-${activeChapterNumber}"]`)
      const anchorNode = selection?.anchorNode

      if (!selection || !selectedText || !editor || !anchorNode || !editor.contains(anchorNode) || selection.rangeCount === 0) {
        selectionMenuAnchorRef.current = null
        setSelectionMenu(null)
        return
      }

      const rect = selection.getRangeAt(0).getBoundingClientRect()
      if (!rect.width && !rect.height) {
        selectionMenuAnchorRef.current = null
        setSelectionMenu(null)
        return
      }

      const anchor = buildAnnotationSelectionAnchor(editor)
      if (!anchor) {
        selectionMenuAnchorRef.current = null
        setSelectionMenu(null)
        return
      }

      selectionMenuAnchorRef.current = anchor
      setSelectionMenu({
        text: selectedText,
        top: rect.top + window.scrollY - 56,
        left: rect.left + window.scrollX + (rect.width / 2),
      })
    }

    document.addEventListener("selectionchange", syncSelectionMenu)
    window.addEventListener("resize", syncSelectionMenu)
    window.addEventListener("scroll", syncSelectionMenu, true)

    return () => {
      document.removeEventListener("selectionchange", syncSelectionMenu)
      window.removeEventListener("resize", syncSelectionMenu)
      window.removeEventListener("scroll", syncSelectionMenu, true)
    }
  }, [activeChapterNumber, draftSurfaceMode, editorMode, workspaceTab])

  useEffect(() => {
    if (editorMode !== "chapter") {
      clearAnnotationHighlights()
      annotationRangesRef.current = new Map()
      return
    }

    const frame = window.requestAnimationFrame(() => {
      const editor = document.querySelector<HTMLElement>(`[data-editor-key="chapter-${activeChapterNumber}"]`)
      const nextRanges = applyAnnotationHighlights(editor, chapterAnnotations, activeAnnotationId)
      annotationRangesRef.current = nextRanges

      const pendingId = pendingAnnotationJumpIdRef.current
      if (!pendingId) return
      const pendingRange = nextRanges.get(pendingId)
      if (!pendingRange) return
      scrollAnnotationRangeIntoView(pendingRange)
      pendingAnnotationJumpIdRef.current = null
    })

    return () => {
      window.cancelAnimationFrame(frame)
      clearAnnotationHighlights()
      annotationRangesRef.current = new Map()
    }
  }, [activeAnnotationId, activeChapterNumber, chapterAnnotations, editorMode, html])

  useEffect(() => {
    if (!activeAnnotationId) return
    if (chapterAnnotations.some((annotation) => annotation.id === activeAnnotationId)) return
    setActiveAnnotationId(null)
  }, [activeAnnotationId, chapterAnnotations])

  useEffect(() => {
    const trimmed = text.trim()
    if (!trimmed) {
      setReadability(null)
      setInlineContinuity(null)
      setReadabilityLoading(false)
      setContinuityLoading(false)
      return
    }
    if (
      deferredChecksSeedRef.current?.chapterNumber === activeChapterNumber
      && deferredChecksSeedRef.current.text === trimmed
    ) {
      deferredChecksSeedRef.current = null
      return
    }
    const handle = window.setTimeout(() => {
      setReadabilityLoading(true)
      setContinuityLoading(true)
      booksApi.getReadability(bookId, trimmed)
        .then(setReadability)
        .catch(() => setReadability(null))
        .finally(() => setReadabilityLoading(false))
      intelligenceApi.inlineContinuity(bookId, trimmed, activeChapterNumber)
        .then(setInlineContinuity)
        .catch(() => setInlineContinuity(null))
        .finally(() => setContinuityLoading(false))
    }, 3000)
    return () => window.clearTimeout(handle)
  }, [activeChapterNumber, bookId, text])

  const runAutomaticChecks = async (chapterNum: number, content: string) => {
    const now = Date.now()
    const last = lastAutoChecksRef.current[chapterNum] ?? 0
    if (now - last < 300_000) return
    lastAutoChecksRef.current[chapterNum] = now

    const [editorial, suggestionResult, threads, synopsisResult, emotionalArcResult] = await Promise.all([
      intelligenceApi.editorialReview(bookId, content, chapterNum),
      intelligenceApi.advisorSuggestions(bookId),
      readerApi.getPlotThreads(bookId, chapterNum),
      intelligenceApi.synopsis(bookId, "minimal").catch(() => null),
      booksApi.getEmotionalArc(bookId).catch(() => null),
    ])
    setReview(editorial.review)
    setReviewPassages(editorial.retrieved_passages)
    setSuggestions(suggestionResult.suggestions.filter((item) => item.chapter_ref === null || item.chapter_ref <= chapterNum).slice(0, 6))
    setPlotThreads(threads.filter((thread) => thread.status !== "resolved").slice(0, 8))
    if (synopsisResult) setSynopsis(synopsisResult)
    if (emotionalArcResult) setEmotionalArc(emotionalArcResult)
  }

  const saveChapterDraft = async (chapterNumber: number, draft?: { title: string; text: string; html: string }) => {
    const currentDraft = draft ?? bookDrafts[chapterNumber] ?? { title: chapterTitle, text, html }
    if (!currentDraft.text.trim()) return

    try {
      const result = await booksApi.importManuscript(bookId, {
        text: currentDraft.text,
        html: currentDraft.html,
        title: currentDraft.title.trim() || undefined,
        chapterNumber,
        expectedContentVersion: contentVersionByChapter[chapterNumber],
        replaceExisting: true,
      })
      const importedChapter = result.imported_chapters[0] ?? chapterNumber
      const nextContentVersion = result.chapter_content_versions[importedChapter]
      setSelectedChapter(importedChapter)
      if (typeof nextContentVersion === "number") {
        setContentVersionByChapter((current) => ({
          ...current,
          [importedChapter]: nextContentVersion,
        }))
      }
      clearDraftDirty(chapterNumber)
      clearDraftDirty(importedChapter)
      await loadWorkspaceTree()
      await runAutomaticChecks(importedChapter, currentDraft.text)
      setStatusMessage(`Saved chapter ${importedChapter}. Continuity, synopsis, and thread context refreshed.`)
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 409) {
        await refreshChapterVersionToken(chapterNumber).catch(() => undefined)
        setStatusMessage(`Chapter ${chapterNumber} changed in another session. Your local draft is still here. Reload the latest version or save again to intentionally overwrite it.`)
        return
      }
      throw error
    }
  }

  const saveCurrentChapter = async () => {
    if (!text.trim()) return
    setSaving(true)
    setStatusMessage(null)
    try {
      const result = await booksApi.importManuscript(bookId, {
        text,
        html,
        title: chapterTitle.trim() || undefined,
        chapterNumber: activeChapterNumber,
        expectedContentVersion: selectedChapter !== null ? contentVersionByChapter[activeChapterNumber] : undefined,
        replaceExisting: replaceExisting || selectedChapter !== null,
      })
      await loadBase()
      const importedChapter = result.imported_chapters[0] ?? activeChapterNumber
      const nextContentVersion = result.chapter_content_versions[importedChapter]
      setSelectedChapter(importedChapter)
      clearDraftDirty(importedChapter)
      setBookDrafts((current) => ({
        ...current,
        [importedChapter]: { title: chapterTitle.trim() || `Chapter ${importedChapter}`, text, html },
      }))
      if (typeof nextContentVersion === "number") {
        setContentVersionByChapter((current) => ({
          ...current,
          [importedChapter]: nextContentVersion,
        }))
      }
      await loadWorkspaceTree()
      await runAutomaticChecks(importedChapter, text)
      setStatusMessage(`Saved chapter ${importedChapter}. Continuity, synopsis, and thread context refreshed.`)
    } catch (error) {
      if (axios.isAxiosError(error) && error.response?.status === 409 && selectedChapter !== null) {
        await refreshChapterVersionToken(activeChapterNumber).catch(() => undefined)
        setStatusMessage(`Chapter ${activeChapterNumber} changed in another session. Your local draft is still here. Reload the latest version or save again to intentionally overwrite it.`)
      } else {
        setStatusMessage("Save failed. Please check the chapter number and try again.")
      }
    } finally {
      setSaving(false)
    }
  }

  const confirmReprocessManuscript = async () => {
    if (!book || reprocessing) return
    setReprocessing(true)
    setStatusMessage(null)
    try {
      const result = await booksApi.reprocessManuscript(book.id)
      setShowReprocessConfirm(false)
      setStatusMessage(`Reprocessing started for ${result.chapters_queued} chapter${result.chapters_queued === 1 ? "" : "s"}. This consumed 1 book upload.`)
      await loadBase()
    } catch {
      setStatusMessage("Reprocess failed. Check your upload quota and try again.")
    } finally {
      setReprocessing(false)
    }
  }

  const handleChapterHeadingBlur = async (rawValue: string, fallbackNumber: number, fallbackTitle: string) => {
    const parsed = parseChapterHeading(rawValue, fallbackNumber, fallbackTitle)
    const currentDraft = bookDrafts[fallbackNumber] ?? { title: fallbackTitle, text, html }
    const nextDraft = { ...currentDraft, title: parsed.title }

    setChapterTitle(parsed.title)
    setDraftChapterNumber(selectedChapter === null ? parsed.chapterNumber : null)
    setBookDrafts((current) => ({
      ...current,
      [parsed.chapterNumber]: {
        ...(current[parsed.chapterNumber] ?? nextDraft),
        title: parsed.title,
        text: selectedChapter === null ? text : current[parsed.chapterNumber]?.text ?? nextDraft.text,
        html: selectedChapter === null ? html : current[parsed.chapterNumber]?.html ?? nextDraft.html,
      },
    }))
    markDraftDirty(parsed.chapterNumber)

    const draftToPersist = selectedChapter === null
      ? { title: parsed.title, text, html }
      : { title: parsed.title, text: currentDraft.text, html: currentDraft.html }

    if (!draftToPersist.text.trim()) return

    setSaving(true)
    try {
      await saveChapterDraft(parsed.chapterNumber, draftToPersist)
    } finally {
      setSaving(false)
    }
  }

  const saveFullBook = async () => {
    const draftEntries = Object.entries(bookDrafts)
      .map(([chapterNumber, draft]) => [Number(chapterNumber), draft] as const)
      .filter(([, draft]) => draft.text.trim())
      .sort((a, b) => a[0] - b[0])
    if (!draftEntries.length) return

    setSaving(true)
    setStatusMessage(null)
    try {
      // Sequential saves are intentional: each saveChapterDraft calls setSelectedChapter,
      // loadWorkspaceTree, and runAutomaticChecks which must not overlap.
      for (const [chapterNumber, draft] of draftEntries) {
        await saveChapterDraft(chapterNumber, draft)
      }
      await loadBase()
      setStatusMessage(`Saved ${draftEntries.length} chapter${draftEntries.length === 1 ? "" : "s"} from the full-book editor.`)
    } catch {
      setStatusMessage("One of the chapter saves failed. Please try again.")
    } finally {
      setSaving(false)
    }
  }

  const jumpToChapter = (chapterNum: number) => {
    setEditorMode("book")
    setSelectedChapter(chapterNum)
    setJumpTarget(chapterNum)
  }

  const jumpToSearchResult = (index: number) => {
    const result = recallResults[index]
    if (!result) return
    setActiveFindIndex(index)
    jumpToChapter(result.chapter_num)
  }

  const exportManuscript = async (format: "pdf" | "docx" | "epub" | "vault") => {
    setExporting(format)
    try {
      const preset = writerWorkspace?.publishing.active_preset ?? "standard_manuscript"
      const blob = await booksApi.exportManuscript(bookId, format, preset, includeSceneMetadataOnExport)
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      const extension = format === "vault" ? "zip" : format
      link.download = `${(book?.title || "lorevia").replace(/\s+/g, "-").toLowerCase()}-manuscript.${extension}`
      link.click()
      URL.revokeObjectURL(url)
    } finally {
      setExporting(null)
    }
  }

  const compileManuscript = async () => {
    if (!writerWorkspace) return
    await saveWorkspace({ manuscript_front_matter: writerWorkspace.manuscript_front_matter }, { silent: true })
    setShowCompileDialog(false)
    await exportManuscript(compileFormat)
  }

  const persistNote = async (payload?: {
    noteId?: string | null
    chapterNumber?: number | null
    title?: string | null
    body: string
  }) => {
    const nextBody = payload?.body ?? noteBody
    const nextText = htmlToPlainText(nextBody)
    if (!nextText.trim()) return null
    setSavingNote(true)
    try {
      const saved = await booksApi.saveBookNote(bookId, {
        noteId: payload?.noteId ?? null,
        chapterNumber: payload?.chapterNumber ?? (noteScope === "chapter" ? activeChapterNumber : null),
        title: payload?.title ?? (noteTitle.trim() || null),
        body: nextBody,
      })
      setNotes((current) => [saved, ...current.filter((note) => note.id !== saved.id)])
      setStatusMessage(`Saved note${saved.chapter_number ? ` for chapter ${saved.chapter_number}` : ""}.`)
      return saved
    } finally {
      setSavingNote(false)
    }
  }

  const saveWorkspaceVaultNote = async (payload?: {
    title?: string | null
    body: string
    folderSegments?: string[]
  }) => {
    const nextBody = payload?.body ?? noteBody
    const nextText = htmlToPlainText(nextBody).trim()
    if (!nextText) return null
    const title = payload?.title?.trim() || noteTitle.trim() || `Chapter ${activeChapterNumber} note`
    const chapterFolder = noteScope === "chapter" && activeChapterNumber ? [`Chapter ${activeChapterNumber}`] : ["Whole Book"]

    const saved = await saveContextualVaultNote({
      bookId,
      title,
      content: nextText,
      context: "manual_editor",
      folderSegments: payload?.folderSegments?.length ? payload.folderSegments : chapterFolder,
    })
    setStatusMessage(`Saved to notes workspace: ${saved.path}`)
    return saved
  }

  const saveNote = async () => {
    const saved = await persistNote()
    if (!saved) return
    setNoteTitle("")
    setNoteBody("")
    setNoteBodyText("")
  }

  const openAnnotationComposer = () => {
    if (draftSurfaceMode === "paged") {
      setStatusMessage("Switch back to Draft mode to anchor annotations to the manuscript.")
      return
    }
    const editor = document.querySelector<HTMLElement>(`[data-editor-key="chapter-${activeChapterNumber}"]`)
    if (!editor) {
      setStatusMessage("Open a chapter first, then select the passage you want to annotate.")
      return
    }
    const anchor = buildAnnotationSelectionAnchor(editor) ?? selectionMenuAnchorRef.current
    if (!anchor) {
      setStatusMessage("Select a passage first, then add an annotation.")
      return
    }
    setAnnotationAnchor(anchor)
    setAnnotationDraft("")
    setAnnotationCategory("general")
    setAnnotationVisibility("shared")
    openRightPane("notes")
  }

  const openAddCharacterFromSelection = () => {
    if (!selectionMenu?.text) {
      setStatusMessage("Select a character name in the manuscript first.")
      return
    }
    setAddCharacterText(selectionMenu.text)
    setAddCharacterOpen(true)
    setSelectionMenu(null)
  }

  const handleCharacterCreated = (character: Character) => {
    setCharacters((current) => [...current, character])
    setStatusMessage(`Character "${character.name}" added to the story bible.`)
  }

  const saveAnnotation = async () => {
    if (!annotationAnchor || !annotationDraft.trim()) return
    setAnnotationActionId("new")
    try {
      const saved = await booksApi.saveManuscriptAnnotation(bookId, {
        chapterNumber: activeChapterNumber,
        category: annotationCategory,
        visibility: annotationVisibility,
        status: "open",
        quote: annotationAnchor.quote,
        comment: annotationDraft.trim(),
        anchorContextBefore: annotationAnchor.anchorContextBefore,
        anchorContextAfter: annotationAnchor.anchorContextAfter,
        startOffset: annotationAnchor.startOffset,
        endOffset: annotationAnchor.endOffset,
      })
      setAnnotations((current) => [saved, ...current.filter((annotation) => annotation.id !== saved.id)])
      setAnnotationAnchor(null)
      setAnnotationDraft("")
      setActiveAnnotationId(saved.id)
      pendingAnnotationJumpIdRef.current = saved.id
      setStatusMessage(`Saved annotation for chapter ${activeChapterNumber}.`)
    } finally {
      setAnnotationActionId(null)
    }
  }

  const updateAnnotationStatus = async (annotation: ManuscriptAnnotation, status: "open" | "resolved") => {
    setAnnotationActionId(annotation.id)
    try {
      const updated = await booksApi.saveManuscriptAnnotation(bookId, {
        annotationId: annotation.id,
        status,
      })
      setAnnotations((current) => current.map((item) => item.id === updated.id ? updated : item))
      setStatusMessage(status === "resolved" ? "Annotation resolved." : "Annotation reopened.")
    } finally {
      setAnnotationActionId(null)
    }
  }

  const removeAnnotation = async (annotationId: string) => {
    setAnnotationActionId(annotationId)
    try {
      await booksApi.deleteManuscriptAnnotation(bookId, annotationId)
      setAnnotations((current) => current.filter((annotation) => annotation.id !== annotationId))
      if (activeAnnotationId === annotationId) {
        setActiveAnnotationId(null)
      }
    } finally {
      setAnnotationActionId(null)
    }
  }

  const jumpToAnnotation = (annotation: ManuscriptAnnotation) => {
    openRightPane("notes")
    setEditorMode("chapter")
    setDraftSurfaceMode("edit")
    setActiveAnnotationId(annotation.id)
    pendingAnnotationJumpIdRef.current = annotation.id
    if (selectedChapter !== annotation.chapter_number) {
      setSelectedChapter(annotation.chapter_number)
      return
    }
    const range = annotationRangesRef.current.get(annotation.id)
    if (range) {
      scrollAnnotationRangeIntoView(range)
      pendingAnnotationJumpIdRef.current = null
    }
  }

  const removeNote = async (noteId: string) => {
    await booksApi.deleteBookNote(bookId, noteId)
    setNotes((current) => current.filter((note) => note.id !== noteId))
  }

  const startEditingNote = (note: BookNote) => {
    setEditingNoteId(note.id)
    setEditNoteTitle(note.title || "")
    setEditNoteBody(note.body)
  }

  const cancelEditingNote = () => {
    setEditingNoteId(null)
    setEditNoteTitle("")
    setEditNoteBody("")
  }

  const saveEditedNote = async () => {
    if (!editingNoteId) return
    setEditingNoteSaving(true)
    try {
      const updated = await booksApi.saveBookNote(bookId, {
        noteId: editingNoteId,
        title: editNoteTitle.trim() || null,
        body: editNoteBody,
      })
      setNotes((current) => current.map((note) => note.id === updated.id ? updated : note))
      cancelEditingNote()
      setStatusMessage("Note updated.")
    } finally {
      setEditingNoteSaving(false)
    }
  }

  const saveContinuityIssueAsNote = async (issue: { title: string; description: string; suggestion?: string }) => {
    const noteBody = `**Continuity Issue: ${issue.title}**\n\n${issue.description}${issue.suggestion ? `\n\n**Suggestion:** ${issue.suggestion}` : ""}`
    const noteTitle = `Continuity: ${issue.title}`
    await saveWorkspaceVaultNote({
      title: noteTitle,
      body: noteBody,
      folderSegments: activeChapterNumber ? [`Chapter ${activeChapterNumber}`, "Continuity"] : ["Continuity"],
    })
  }

  const printManuscript = () => {
    window.print()
  }

  const replaceInCurrentChapter = () => {
    if (!replaceQuery) return
    const nextText = text.replace(replaceQuery, replaceValue)
    const nextHtml = textToHtml(nextText)
    setText(nextText)
    setHtml(nextHtml)
    markDraftDirty(activeChapterNumber)
    setBookDrafts((current) => ({
      ...current,
      [activeChapterNumber]: { title: chapterTitle, text: nextText, html: nextHtml },
    }))
  }

  const replaceEverywhere = () => {
    if (!replaceQuery) return
    if (editorMode === "chapter") {
      const nextText = text.split(replaceQuery).join(replaceValue)
      const nextHtml = textToHtml(nextText)
      setText(nextText)
      setHtml(nextHtml)
      markDraftDirty(activeChapterNumber)
      setBookDrafts((current) => ({
        ...current,
        [activeChapterNumber]: { title: chapterTitle, text: nextText, html: nextHtml },
      }))
      return
    }
    setBookDrafts((current) => {
      const next: BookDraftMap = { ...current }
      for (const [chapterNumber, draft] of Object.entries(current)) {
        next[Number(chapterNumber)] = {
          ...draft,
          text: draft.text.split(replaceQuery).join(replaceValue),
          html: textToHtml(draft.text.split(replaceQuery).join(replaceValue)),
        }
      }
      return next
    })
  }

  const jumpToPage = (page: number) => {
    const match = fullBookPageMap.find((item) => page >= item.startPage && page <= item.endPage)
    if (!match) return
    setGotoPageInput(String(page))
    jumpToChapter(match.chapter)
  }

  const saveStateLabel = (chapterNumber: number) => {
    if (saving) return "Saving..."
    if (!dirtyDrafts.includes(chapterNumber)) return "Saved"

    const chapterAutosave = autosaveState[chapterNumber]
    if (chapterAutosave?.status === "pending") return "Autosaving..."
    if (chapterAutosave?.status === "saved") return "Autosaved locally"
    if (chapterAutosave?.status === "error") return "Local save failed"
    return "Unsaved"
  }

  const saveStateTone = (chapterNumber: number) => {
    const label = saveStateLabel(chapterNumber)
    if (label === "Saved") {
      return isDark ? "bg-emerald-500/10 text-emerald-200" : "bg-emerald-100 text-emerald-800"
    }
    if (label === "Local save failed") {
      return isDark ? "bg-rose-500/10 text-rose-200" : "bg-rose-100 text-rose-800"
    }
    return isDark ? "bg-amber-500/10 text-amber-200" : "bg-amber-100 text-amber-800"
  }

  const autosaveMetaLabel = (chapterNumber: number) => {
    const chapterAutosave = autosaveState[chapterNumber]
    if (!dirtyDrafts.includes(chapterNumber) || chapterAutosave?.status !== "saved" || !chapterAutosave.updatedAt) return null
    return `Local autosave at ${new Date(chapterAutosave.updatedAt).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}`
  }

  const activeSaveLabel = saving ? "Saving..." : dirtyDrafts.includes(activeChapterNumber) ? "Unsaved" : "Saved"
  const inspectorRailClass = isDark
    ? "border-l border-white/[0.08] bg-[#0b0f11] text-slate-100"
    : "border-l border-stone-200 bg-white text-stone-950"
  const inspectorSectionClass = isDark
    ? "border-t border-white/[0.08] px-4 py-4 first:border-t-0"
    : "border-t border-stone-200 px-4 py-4 first:border-t-0"
  const inspectorRecordClass = isDark
    ? "rounded-md border border-white/[0.08] bg-[#111517] px-3 py-3"
    : "rounded-md border border-stone-200 bg-stone-50 px-3 py-3"
  const inspectorLabelClass = isDark
    ? "text-3xs font-semibold uppercase tracking-[0.22em] text-slate-400"
    : "text-3xs font-semibold uppercase tracking-[0.22em] text-stone-500"
  const inspectorMutedTextClass = isDark ? "text-slate-400" : "text-stone-500"
  const inspectorBodyTextClass = isDark ? "text-slate-200" : "text-stone-700"
  const inspectorInputClass = isDark
    ? "rounded-sm border border-white/[0.08] bg-black/70 text-slate-100 placeholder:text-slate-500"
    : "rounded-sm border border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"
  const inspectorSecondaryButtonClass = isDark
    ? "rounded-sm border border-white/[0.1] bg-[#111517] px-3 py-2 text-xs font-semibold text-slate-200 hover:bg-white/[0.06]"
    : "rounded-sm border border-stone-200 bg-white px-3 py-2 text-xs font-semibold text-stone-700 hover:bg-stone-50"
  const inspectorPrimaryButtonClass = "rounded-sm bg-[#1f615d] px-3 py-2 text-xs font-semibold text-white hover:bg-[#276f6a] disabled:opacity-40"
  const inspectorDangerButtonClass = isDark ? "text-xs font-semibold text-rose-300" : "text-xs font-semibold text-rose-700"
  const inspectorChipClass = isDark
    ? "rounded-sm border border-white/[0.08] bg-white/[0.05] px-2 py-0.5 text-3xs font-medium text-slate-300"
    : "rounded-sm border border-stone-200 bg-white px-2 py-0.5 text-3xs font-medium text-stone-600"

  if (loading) {
    return <ManuscriptEditorSkeleton isDark={isDark} />
  }

  return (
    <div className={`min-h-screen overflow-x-hidden ${isDark ? "bg-[#101416] text-slate-100" : "bg-[#f4f5f3] text-stone-950"}`}>
      <style jsx global>{`
        ::highlight(lorevia-annotation-open) {
          background: ${isDark ? "rgba(251, 191, 36, 0.18)" : "rgba(245, 158, 11, 0.22)"};
          color: inherit;
        }
        ::highlight(lorevia-annotation-resolved) {
          background: ${isDark ? "rgba(148, 163, 184, 0.16)" : "rgba(148, 163, 184, 0.2)"};
          color: inherit;
        }
        ::highlight(lorevia-annotation-active) {
          background: ${isDark ? "rgba(45, 212, 191, 0.26)" : "rgba(20, 184, 166, 0.24)"};
          color: inherit;
        }
      `}</style>
      {selectionMenu && workspaceTab === "write" && editorMode === "chapter" && draftSurfaceMode === "edit" ? (
        <div
          className="pointer-events-none fixed z-50 hidden -translate-x-1/2 xl:block"
          style={{ top: selectionMenu.top, left: selectionMenu.left }}
        >
          <div className={`pointer-events-auto flex items-center gap-2 rounded-sm border px-2 py-2 ${isDark ? "border-white/10 bg-[#0f1117]" : "border-stone-200 bg-white"}`}>
            <button
              type="button"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => void tightenSelectedText()}
              disabled={tighteningSelection}
              className="rounded-sm bg-[#1f615d] px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
            >
              {tighteningSelection ? "Tightening..." : "Tighten"}
            </button>
            <button
              type="button"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => openRightPane("context")}
              className={`rounded-sm px-3 py-1.5 text-xs font-medium ${isDark ? "bg-white/8 text-slate-200" : "bg-stone-100 text-stone-700"}`}
            >
              Check consistency
            </button>
            <button
              type="button"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => openAnnotationComposer()}
              className={`rounded-sm px-3 py-1.5 text-xs font-medium ${isDark ? "bg-white/8 text-slate-200" : "bg-stone-100 text-stone-700"}`}
            >
              Annotate
            </button>
            <button
              type="button"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => openAddCharacterFromSelection()}
              className={`rounded-sm px-3 py-1.5 text-xs font-medium ${isDark ? "bg-violet-700/30 text-violet-200" : "bg-violet-100 text-violet-800"}`}
            >
              Add as character
            </button>
            <Link
              href={`/${bookId}/advisor`}
              className={`rounded-sm px-3 py-1.5 text-xs font-medium ${isDark ? "bg-white/8 text-slate-200" : "bg-stone-100 text-stone-700"}`}
            >
              Ask advisor
            </Link>
          </div>
        </div>
      ) : null}
      <div className="pb-10">
        <header className={`sticky top-0 z-40 border-b ${isDark ? "border-white/10 bg-[#111416]/95" : "border-stone-200 bg-white/95"}`}>
          <div className="flex flex-col">
            <div className="flex min-h-[4.25rem] flex-col gap-4 px-4 py-3 lg:flex-row lg:items-center lg:justify-between lg:px-6">
              <div className="flex min-w-0 items-center gap-3">
                <span className={`inline-flex h-7 w-7 shrink-0 items-center justify-center ${isDark ? "text-slate-200" : "text-stone-700"}`} aria-hidden>
                  <BookOpenIcon />
                </span>
                <button
                  type="button"
                  onClick={() => router.push(`/${bookId}` as Route)}
                  className={`flex min-w-0 items-center gap-2 text-left text-base font-semibold ${isDark ? "text-white hover:text-teal-200" : "text-stone-950 hover:text-teal-700"}`}
                  title="Open project overview"
                >
                  <span className="truncate">{book?.title || "Manuscript"}</span>
                  <span className="text-xs" aria-hidden>v</span>
                </button>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <div className="flex items-center gap-2">
                  <span className={`inline-flex h-2.5 w-2.5 rounded-full ${activeSaveLabel === "Unsaved" ? "bg-teal-400" : "bg-emerald-400"}`} />
                  <p className={`text-sm font-medium ${activeSaveLabel === "Unsaved" ? isDark ? "text-teal-300" : "text-teal-700" : isDark ? "text-emerald-300" : "text-emerald-700"}`}>{activeSaveLabel}</p>
                </div>
                <ManuscriptExportMenu
                  isDark={isDark}
                  open={showExportMenu}
                  activePreset={writerWorkspace?.publishing.active_preset ?? "standard_manuscript"}
                  exporting={exporting}
                  onToggle={() => setShowExportMenu((value) => !value)}
                  onPresetChange={(nextPreset) => {
                    void saveWorkspace({
                      publishing: {
                        ...(writerWorkspace?.publishing ?? { trim_size: "6x9", include_title_page: true, mirror_margins: true }),
                        active_preset: nextPreset,
                      },
                    }, { silent: true })
                  }}
                  onPrint={() => {
                    setShowExportMenu(false)
                    printManuscript()
                  }}
                  onCompile={(format) => {
                    setCompileFormat(format)
                    setShowExportMenu(false)
                    setShowCompileDialog(true)
                  }}
                />
                <button onClick={() => setFocusMode((value) => !value)} className={`min-h-10 rounded-sm border px-4 text-sm font-medium ${focusMode ? isDark ? "border-emerald-300/40 bg-emerald-400/15 text-white" : "border-emerald-300 bg-emerald-50 text-stone-900" : isDark ? "border-white/10 bg-white/[0.03] text-slate-200 hover:bg-white/[0.06]" : "border-stone-200 bg-white text-stone-700"}`}>
                  {focusMode ? "Exit focus" : "Focus mode"}
                </button>
                {reprocessCta.visible ? (
                  <button
                    type="button"
                    disabled={reprocessCta.disabled || reprocessing}
                    title={reprocessCta.disabledReason ?? undefined}
                    onClick={() => {
                      if (reprocessing || !book) return
                      setShowReprocessConfirm(true)
                    }}
                    className={`min-h-10 rounded-sm border px-4 text-sm font-medium disabled:opacity-40 ${
                      reprocessCta.isProcessing
                        ? isDark ? "border-sky-400/30 bg-sky-500/15 text-sky-200" : "border-sky-300 bg-sky-50 text-sky-700"
                        : isDark ? "border-white/10 bg-white/[0.03] text-slate-200 hover:bg-white/[0.06]" : "border-stone-200 bg-white text-stone-700"
                    }`}
                  >
                    {reprocessCta.label}
                  </button>
                ) : null}
                <button
                  type="button"
                  onClick={() => setShowEditorSettings((value) => !value)}
                  className={`inline-flex h-10 w-10 items-center justify-center rounded-sm border text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-200 hover:bg-white/[0.06]" : "border-stone-200 bg-white text-stone-700"}`}
                  aria-label="Editor settings"
                  title="Editor settings"
                >
                  •••
                </button>
              </div>
            </div>
            <div className={`flex flex-col gap-3 border-t px-4 py-2 lg:flex-row lg:items-center lg:justify-between lg:px-6 ${isDark ? "border-white/10" : "border-stone-200"}`}>
              <div className="flex flex-wrap items-center gap-8" role="tablist" aria-label="Manuscript workspace modes">
                {WORKSPACE_TABS.map((tab) => (
                  <button
                    key={tab.id}
                    type="button"
                    role="tab"
                    aria-selected={workspaceTab === tab.id}
                    onClick={() => setWorkspaceTab(tab.id)}
                    title={tab.title}
                    className={`border-b-2 py-3 text-sm font-medium transition ${workspaceTab === tab.id ? isDark ? "border-teal-300 text-white" : "border-teal-600 text-stone-950" : isDark ? "border-transparent text-slate-400 hover:text-slate-200" : "border-transparent text-stone-500 hover:text-stone-800"}`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
              <div className="flex flex-wrap items-center gap-3 lg:ml-auto">
                <ManuscriptModeSwitch
                  isDark={isDark}
                  options={["edit", "paged"] as const}
                  selected={draftSurfaceMode}
                  onSelect={setDraftSurfaceMode}
                  renderLabel={(mode) => mode === "edit" ? "Draft" : "Paged preview"}
                />
                <ManuscriptModeSwitch
                  isDark={isDark}
                  options={["chapter", "book"] as const}
                  selected={editorMode}
                  onSelect={setEditorMode}
                  renderLabel={(mode) => mode === "chapter" ? "Chapter" : "Full book"}
                />
              </div>
            </div>
          </div>
        </header>

        {workspaceTab === "plan" ? (
          <ManuscriptPlanWorkspace
            isDark={isDark}
            editorMode={editorMode}
            writerWorkspace={writerWorkspace}
            tighteningSelection={tighteningSelection}
            onTightenSelectedText={() => void tightenSelectedText()}
            chapterWordCount={chapterWordCount}
            fullBookWordCount={fullBookWordCount}
            chapterGoalProgress={chapterGoalProgress}
            bookGoalProgress={bookGoalProgress}
            readabilityLoading={readabilityLoading}
            readability={readability}
            chapterApproxPages={chapterApproxPages}
            fullBookApproxPages={fullBookApproxPages}
            chapterVersionsCount={chapterVersions.length}
            workspaceSaving={workspaceSaving}
            onWordCountGoalChange={(field, value) => {
              setWriterWorkspace((current) => current ? { ...current, word_count_goals: { ...current.word_count_goals, [field]: value } } : current)
            }}
            onSaveGoals={() => {
              if (writerWorkspace) {
                void saveWorkspace({ word_count_goals: writerWorkspace.word_count_goals })
              }
            }}
            onApplyTemplate={applyTemplateToChapter}
            onSaveTemplates={saveTemplates}
            newCorkboardTitle={newCorkboardTitle}
            onNewCorkboardTitleChange={setNewCorkboardTitle}
            onAddCorkboardCard={() => void addCorkboardCard()}
            onUpdateCardLane={(cardId, lane) => void updateCardLane(cardId, lane)}
            emotionalArc={emotionalArc}
          />
        ) : null}
        {workspaceTab !== "plan" ? (
        <div className={`grid min-w-0 ${desktopLayoutClass}`}>
          {leftRailVisible ? (
          <aside className={`min-w-0 border-r p-5 xl:sticky xl:top-[8.25rem] xl:max-h-[calc(100vh-8.25rem)] xl:overflow-y-auto ${isDark ? "border-white/10 bg-[#11171a]" : "border-stone-200 bg-white/90"}`}>
            <ManuscriptWorkspaceSidebarHeader
              bookTitle={book?.title}
              fullBookReadingTime={fullBookReadingTime}
              fullBookWordCount={fullBookWordCount}
              isDark={isDark}
              onCreateChapter={() => {
                setSelectedChapter(null)
                setDraftChapterNumber(nextChapterNumber)
                setReplaceExisting(false)
                setChapterTitle(`Chapter ${nextChapterNumber}`)
                setText("")
                setHtml(textToHtml(""))
                setReview(null)
                setReviewPassages([])
              }}
              onCreateScene={() => openSceneEditor(null)}
            />
            <input
              type="text"
              value={chapterSearch}
              onChange={(event) => setChapterSearch(event.target.value)}
              placeholder="Search chapters"
              className={`mt-4 w-full rounded-sm border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/30 text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"}`}
            />
            <div className="mt-4">
              <p className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Chapters</p>
              <div className="mt-2 space-y-2">
              {filteredChapterItems.map((chapter) => {
                const active = selectedChapter === chapter.number || (selectedChapter === null && draftChapterNumber === chapter.number)
                const rowStats = chapterRowStats[chapter.number] ?? { wordCount: 0, sceneCount: 0, readingTime: "0 min read" }
                const rowScenes = { length: rowStats.sceneCount }
                const rowReadingTime = rowStats.readingTime
                const rowWordCount = rowStats.wordCount
                return (
                  <div
                    key={chapter.number}
                    className={`rounded-sm border px-3 py-3 text-sm transition ${active ? isDark ? "border-teal-300 bg-teal-400/10 text-white" : "border-teal-300 bg-teal-50 text-stone-900" : isDark ? "border-white/10 bg-white/[0.035] text-slate-300 hover:border-white/15 hover:bg-white/[0.07]" : "border-stone-200 bg-stone-50 text-stone-700 hover:bg-white"}`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedChapter(chapter.number)
                          setDraftChapterNumber(null)
                          setReplaceExisting(true)
                        }}
                        className="min-w-0 flex-1 text-left focus:outline-none focus:ring-2 focus:ring-sky-400/40"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <p className="font-semibold">Chapter {chapter.number}</p>
                          <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${active ? "bg-teal-300" : chapter.processed ? "bg-emerald-400" : isDark ? "bg-slate-600" : "bg-stone-300"}`} />
                        </div>
                        <p className="mt-1 line-clamp-1 text-xs opacity-75">{chapter.title || `Chapter ${chapter.number}`}</p>
                        <p className={`text-3xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{rowScenes.length} scene{rowScenes.length === 1 ? "" : "s"} - {rowReadingTime}</p>
                        <p className={`mt-2 text-3xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{rowWordCount > 0 ? `${rowWordCount.toLocaleString()} words` : "Draft ready"} - {dirtyDrafts.includes(chapter.number) ? "needs review" : "saved"}</p>
                      </button>
                      <button
                        type="button"
                        aria-label={`Remove Chapter ${chapter.number}`}
                        disabled={deletingChapterNumber === chapter.number}
                        onClick={() => void removeChapter(chapter.number)}
                        className={`shrink-0 rounded-sm px-2.5 py-1 text-3xs font-semibold transition focus:outline-none focus:ring-2 focus:ring-rose-400/40 disabled:cursor-wait disabled:opacity-60 ${isDark ? "bg-rose-500/10 text-rose-200 hover:bg-rose-500/20" : "bg-rose-50 text-rose-700 hover:bg-rose-100"}`}
                      >
                        {deletingChapterNumber === chapter.number ? "Removing" : "Remove"}
                      </button>
                    </div>
                  </div>
                )
              })}
              </div>
            </div>
            <div className="mt-4">
              <div className="flex items-center justify-between gap-3">
                <p className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Scenes / reorder</p>
                <Link
                  href={`/${bookId}/scenes`}
                  className={`rounded-sm border px-2.5 py-1 text-3xs font-semibold ${isDark ? "border-white/10 bg-white/[0.04] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}
                >
                  Open workspace
                </Link>
                <label className={`flex items-center gap-2 text-3xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                  <input
                    type="checkbox"
                    checked={includeSceneMetadataOnImport}
                    onChange={(event) => setIncludeSceneMetadataOnImport(event.target.checked)}
                    className="h-3.5 w-3.5 rounded border-stone-300"
                  />
                  Insert metadata
                </label>
              </div>
              <div className="mt-2 space-y-2">
                {filteredSceneGroups.map((group) => {
                  const collapsed = collapsedSceneGroups[group.id] ?? group.collapsed_by_default
                  const chapterSceneNumber = typeof group.chapter_number === "number" ? group.chapter_number : null
                  const isChapterSceneGroup = chapterSceneNumber !== null
                  const chapterOrderState = chapterSceneNumber !== null ? (sceneOrderSaveState[chapterSceneNumber] ?? "idle") : "idle"
                  const isDraggingWithinChapter = chapterSceneNumber !== null && draggedScene?.chapterNumber === chapterSceneNumber
                  const chapterSceneCount = group.scenes.length
                  const chapterReorderDisabled = !isChapterSceneGroup || chapterOrderState === "saving"
                  return (
                    <div
                      key={group.id}
                      style={{ contentVisibility: "auto", containIntrinsicSize: "240px" }}
                    className={`rounded-sm border p-2 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-white"}`}
                    >
                      <button
                        onClick={() => setCollapsedSceneGroups((current) => ({ ...current, [group.id]: !collapsed }))}
                        className="flex w-full items-center justify-between gap-3 rounded-sm px-2 py-2 text-left"
                      >
                        <span className={`text-xs font-semibold uppercase tracking-[0.12em] ${isDark ? "text-slate-300" : "text-stone-700"}`}>{group.label}</span>
                        <span className={`text-3xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{collapsed ? "+" : "−"}</span>
                      </button>
                      {isChapterSceneGroup ? (
                        <div className="flex flex-wrap items-center gap-2 px-2 pb-1">
                          <span className={`rounded-sm border px-2.5 py-1 text-3xs font-semibold uppercase tracking-[0.16em] ${isDark ? "border-white/10 bg-white/[0.04] text-slate-400" : "border-stone-200 bg-stone-50 text-stone-500"}`}>
                            Reorder scenes
                          </span>
                          <ManuscriptSceneOrderStatus isDark={isDark} isDragging={isDraggingWithinChapter} state={chapterOrderState} />
                        </div>
                      ) : null}
                      {!collapsed ? (
                        <div className="mt-1 space-y-2">
                          {group.scenes.map((scene, index) => {
                            const isDraggedScene = draggedScene?.sceneId === scene.id
                            const isBeforeDropTarget = chapterSceneNumber !== null && sceneDropTarget?.chapterNumber === chapterSceneNumber && sceneDropTarget.index === index

                            return (
                              <div key={scene.id} className="space-y-2">
                                {isChapterSceneGroup ? (
                                  <div
                                    data-scene-drop-slot={`${chapterSceneNumber}:${index}`}
                                    onDragOver={(event) => {
                                      if (chapterSceneNumber === null || chapterReorderDisabled || draggedScene?.chapterNumber !== chapterSceneNumber) return
                                      event.preventDefault()
                                      event.dataTransfer.dropEffect = "move"
                                      setSceneDropTarget({ chapterNumber: chapterSceneNumber, index })
                                    }}
                                    onDrop={(event) => {
                                      if (chapterSceneNumber === null || chapterReorderDisabled) return
                                      event.preventDefault()
                                      const sourceSceneId =
                                        event.dataTransfer.getData(SCENE_DRAG_SCENE_ID_MIME) ||
                                        event.dataTransfer.getData("text/plain") ||
                                        draggedScene?.sceneId
                                      const sourceChapterNumber = Number.parseInt(
                                        event.dataTransfer.getData(SCENE_DRAG_CHAPTER_MIME) || "",
                                        10
                                      )
                                      if (Number.isFinite(sourceChapterNumber) && sourceChapterNumber !== chapterSceneNumber) {
                                        resetSceneDragState()
                                        return
                                      }
                                      if (!sourceSceneId) {
                                        resetSceneDragState()
                                        return
                                      }
                                      resetSceneDragState()
                                      void reorderScenesInChapter(chapterSceneNumber, sourceSceneId, index)
                                    }}
                                    className={`overflow-hidden rounded-sm border text-center text-3xs font-semibold uppercase tracking-[0.16em] transition-all ${isDraggingWithinChapter ? "h-8 px-3" : "h-0 border-transparent px-0 opacity-0"} ${isBeforeDropTarget ? isDark ? "border-teal-400/40 bg-teal-500/15 text-teal-100" : "border-teal-300 bg-teal-50 text-teal-700" : isDark ? "border-dashed border-white/10 bg-white/[0.03] text-slate-500" : "border-dashed border-stone-200 bg-stone-50 text-stone-400"}`}
                                  >
                                    <span className="inline-flex h-full items-center">{getSceneDropSlotLabel(index, chapterSceneCount)}</span>
                                  </div>
                                ) : null}
                                <div
                                  data-scene-id={scene.id}
                                  className={`rounded-sm border px-3 py-3 transition ${isDraggedScene ? "scale-[0.99] opacity-70" : ""} ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}
                                >
                                  <div className="flex items-start justify-between gap-3">
                                    <div className="flex min-w-0 flex-1 items-start gap-3">
                                      {isChapterSceneGroup ? (
                                        <button
                                          type="button"
                                          draggable={!chapterReorderDisabled}
                                          onDragStart={(event) => {
                                            if (chapterSceneNumber === null || chapterReorderDisabled) return
                                            event.dataTransfer.effectAllowed = "move"
                                            event.dataTransfer.setData(SCENE_DRAG_SCENE_ID_MIME, scene.id)
                                            event.dataTransfer.setData(SCENE_DRAG_CHAPTER_MIME, String(chapterSceneNumber))
                                            event.dataTransfer.setData("text/plain", scene.id)
                                            setDraggedScene({ chapterNumber: chapterSceneNumber, sceneId: scene.id })
                                            setSceneDropTarget({ chapterNumber: chapterSceneNumber, index })
                                          }}
                                          onDragEnd={() => {
                                            window.setTimeout(() => {
                                              resetSceneDragState()
                                            }, 0)
                                          }}
                                          aria-label={`Drag ${scene.title} to reorder this chapter`}
                                          className={`shrink-0 rounded-sm border px-2 py-1 text-3xs font-semibold uppercase tracking-[0.16em] transition ${chapterReorderDisabled ? "cursor-not-allowed opacity-50" : "cursor-grab active:cursor-grabbing"} ${isDark ? "border-white/10 bg-white/[0.04] text-slate-300" : "border-stone-200 bg-white text-stone-600"}`}
                                        >
                                          Drag
                                        </button>
                                      ) : null}
                                      <div className="min-w-0 flex-1">
                                        <div className="flex items-center gap-2">
                                          {isChapterSceneGroup ? <span className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Scene {scene.sort_order}</span> : null}
                                          <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{scene.title}</p>
                                        </div>
                                        <p className={`mt-1 text-3xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{scene.path}</p>
                                        {scene.description ? <p className={`mt-2 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>{scene.description}</p> : null}
                                      </div>
                                    </div>
                                    <button onClick={() => void insertSceneIntoDraft(scene)} className={`rounded-sm px-2.5 py-1 text-3xs font-semibold ${isDark ? "bg-emerald-500/15 text-emerald-200" : "bg-emerald-50 text-emerald-700"}`}>Insert</button>
                                  </div>
                                  <div className="mt-3 flex flex-wrap gap-2">
                                    <button onClick={() => openSceneEditor(scene)} className={`rounded-sm px-2.5 py-1 text-3xs ${isDark ? "bg-white/10 text-slate-200" : "bg-white text-stone-700"}`}>Edit</button>
                                    <button onClick={() => void removeScene(scene)} className={`rounded-sm px-2.5 py-1 text-3xs ${isDark ? "bg-rose-500/10 text-rose-200" : "bg-rose-50 text-rose-700"}`}>Delete</button>
                                  </div>
                                </div>
                              </div>
                            )
                          })}
                          {isChapterSceneGroup ? (
                            <div
                              data-scene-drop-slot={`${chapterSceneNumber}:${chapterSceneCount}`}
                              onDragOver={(event) => {
                                if (chapterSceneNumber === null || chapterReorderDisabled || draggedScene?.chapterNumber !== chapterSceneNumber) return
                                event.preventDefault()
                                event.dataTransfer.dropEffect = "move"
                                setSceneDropTarget({ chapterNumber: chapterSceneNumber, index: chapterSceneCount })
                              }}
                              onDrop={(event) => {
                                if (chapterSceneNumber === null || chapterReorderDisabled) return
                                event.preventDefault()
                                const sourceSceneId =
                                  event.dataTransfer.getData(SCENE_DRAG_SCENE_ID_MIME) ||
                                  event.dataTransfer.getData("text/plain") ||
                                  draggedScene?.sceneId
                                const sourceChapterNumber = Number.parseInt(
                                  event.dataTransfer.getData(SCENE_DRAG_CHAPTER_MIME) || "",
                                  10
                                )
                                if (Number.isFinite(sourceChapterNumber) && sourceChapterNumber !== chapterSceneNumber) {
                                  resetSceneDragState()
                                  return
                                }
                                if (!sourceSceneId) {
                                  resetSceneDragState()
                                  return
                                }
                                resetSceneDragState()
                                void reorderScenesInChapter(chapterSceneNumber, sourceSceneId, chapterSceneCount)
                              }}
                              className={`overflow-hidden rounded-sm border text-center text-3xs font-semibold uppercase tracking-[0.16em] transition-all ${isDraggingWithinChapter ? "h-8 px-3" : "h-0 border-transparent px-0 opacity-0"} ${sceneDropTarget?.chapterNumber === chapterSceneNumber && sceneDropTarget.index === chapterSceneCount ? isDark ? "border-teal-400/40 bg-teal-500/15 text-teal-100" : "border-teal-300 bg-teal-50 text-teal-700" : isDark ? "border-dashed border-white/10 bg-white/[0.03] text-slate-500" : "border-dashed border-stone-200 bg-stone-50 text-stone-400"}`}
                            >
                              <span className="inline-flex h-full items-center">{getSceneDropSlotLabel(chapterSceneCount, chapterSceneCount)}</span>
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                    </div>
                  )
                })}
                {filteredSceneGroups.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>No scenes match this search yet.</p> : null}
              </div>
            </div>
            <div className={`mt-4 rounded-sm border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-white"}`}>
              <div className="flex items-center justify-between gap-3">
                <p className={`text-sm font-medium ${isDark ? "text-slate-300" : "text-stone-700"}`}>Manuscript progress</p>
                <span className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{bookGoalProgress ?? 0}%</span>
              </div>
              <div className={`mt-3 h-2 overflow-hidden rounded-full ${isDark ? "bg-white/10" : "bg-stone-100"}`}>
                <div className="h-full rounded-full bg-[#1f615d]" style={{ width: `${Math.max(12, bookGoalProgress ?? 18)}%` }} />
              </div>
              <p className={`mt-3 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>
                {fullBookWordCount.toLocaleString()} / {(writerWorkspace?.word_count_goals.book_target ?? fullBookWordCount).toLocaleString()} words
              </p>
            </div>
            {selectedChapter !== null ? (
              <ManuscriptVersionHistory
                chapterNumber={selectedChapter}
                chapterVersionDetail={chapterVersionDetail}
                chapterVersionNameDraft={chapterVersionNameDraft}
                chapterVersions={chapterVersions}
                currentText={text}
                isDark={isDark}
                restoringVersionId={restoringVersionId}
                onCreateSnapshot={() => void createSnapshot()}
                onPreviewSnapshot={(versionId) => void previewSnapshot(versionId)}
                onRestoreSnapshot={(versionId) => void restoreSnapshot(versionId)}
                onVersionNameChange={setChapterVersionNameDraft}
              />
            ) : null}
          </aside>
          ) : null}

          <section ref={manuscriptSectionRef} className={`min-w-0 border-r p-0 ${!leftRailVisible && !rightRailVisible ? "xl:mx-auto xl:max-w-[1040px]" : ""} ${isDark ? "border-white/10 bg-[#0b1114]" : "border-stone-200 bg-[#faf8f4]"}`}>
            {workspaceTab !== "write" ? (
              <Suspense fallback={<Skeleton variant="card" className="min-h-64" />}>
              <ManuscriptNonWriteWorkspace
                isDark={isDark}
                bookId={bookId}
                activeChapterNumber={activeChapterNumber}
                preWritingCheck={preWritingCheck}
                editorMode={editorMode}
                onEditorModeChange={setEditorMode}
                draftSurfaceMode={draftSurfaceMode}
                onDraftSurfaceModeChange={setDraftSurfaceMode}
                leftRailVisible={leftRailVisible}
                onToggleLeftRail={() => setShowLeftRail((value) => !value)}
                chapterWordCount={chapterWordCount}
                fullBookWordCount={fullBookWordCount}
                chapterPageSummaryLabel={chapterPageSummaryLabel}
                fullBookPageSummaryLabel={fullBookPageSummaryLabel}
                draftSurfaceSummaryLabel={draftSurfaceSummaryLabel}
                showPageSetup={showPageSetup}
                onTogglePageSetup={() => setShowPageSetup((value) => !value)}
                showSearchTools={showSearchTools}
                onToggleSearchTools={() => setShowSearchTools((value) => !value)}
                fontFamily={fontFamily}
                onFontFamilyChange={setFontFamily}
                fontSize={fontSize}
                onFontSizeChange={(value) => {
                  setFontSize(value)
                  setFontSizeLocked(true)
                }}
                lineHeight={lineHeight}
                onLineHeightChange={setLineHeight}
                firstLineIndent={firstLineIndent}
                onToggleFirstLineIndent={() => setFirstLineIndent((value) => !value)}
                showPageGuides={showPageGuides}
                onToggleShowPageGuides={() => setShowPageGuides((value) => !value)}
                searchInputRef={searchInputRef}
                recallQuery={recallQuery}
                onRecallQueryChange={setRecallQuery}
                replaceQuery={replaceQuery}
                onReplaceQueryChange={setReplaceQuery}
                replaceValue={replaceValue}
                onReplaceValueChange={setReplaceValue}
                onReplaceInCurrentChapter={replaceInCurrentChapter}
                onReplaceEverywhere={replaceEverywhere}
                recallCharacter={recallCharacter}
                recallLoading={recallLoading}
                recallResults={recallResults}
                activeFindIndex={activeFindIndex}
                onJumpToChapter={jumpToChapter}
                inlineContinuity={inlineContinuity}
                logicSelectionText={logicSelectionText}
                continuityLoading={continuityLoading}
              />
              </Suspense>
            ) : null}
            <WhatsTheWordPanel bookId={bookId} isDark={isDark} className="mb-4" />

            {editorMode === "chapter" ? (
              draftSurfaceMode === "paged" ? (
                <ManuscriptPagedPreview
                  sections={chapterPreviewSections}
                  preset={pagedPreviewPreset}
                  firstLineIndent={firstLineIndent}
                  lineHeight={lineHeight}
                  isDark={isDark}
                  onPageCountChange={setChapterPreviewPageCount}
                />
              ) : (
              <div className="space-y-4">
                <div className={`relative mx-auto w-full max-w-full overflow-hidden border ${isDark ? "border-white/10 bg-[#0e1218]" : "border-[#d8d0c4] bg-[#fdfcf9]"}`}>
                  {showPageGuides ? (
                    <div
                      aria-hidden
                      className={`pointer-events-none absolute inset-0 ${isDark ? "opacity-20" : "opacity-35"}`}
                      style={{
                        backgroundImage: `repeating-linear-gradient(to bottom, transparent 0, transparent calc(297mm - 1px), ${isDark ? "rgba(255,255,255,0.08)" : "rgba(15,23,42,0.08)"} calc(297mm - 1px), ${isDark ? "rgba(255,255,255,0.08)" : "rgba(15,23,42,0.08)"} 297mm)`,
                      }}
                    />
                  ) : null}
                  <div className={`border-b px-5 py-5 sm:px-7 ${isDark ? "border-white/10 bg-[#111721]" : "border-[#e6dfd4] bg-[#f7f3ed]"}`}>
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{book?.title || "Manuscript"}</p>
                        <input
                          key={`chapter-heading-${activeChapterNumber}-${chapterTitle}`}
                          type="text"
                          defaultValue={formatChapterHeading(activeChapterNumber, chapterTitle)}
                          onBlur={(event) => void handleChapterHeadingBlur(event.target.value, activeChapterNumber, chapterTitle)}
                          className={`mt-3 w-full border-0 bg-transparent font-serif text-3xl font-semibold leading-tight outline-none sm:text-4xl ${isDark ? "text-white placeholder:text-slate-600" : "text-stone-950 placeholder:text-stone-400"}`}
                        />
                        <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{chapterReadingTime} · {chapterSceneOutline.length} scene{chapterSceneOutline.length === 1 ? "" : "s"}</p>
                        <p className={`mt-2 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{chapterWordCount.toLocaleString()} words · ~{chapterApproxPages} pages</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`rounded-sm px-3 py-1.5 text-3xs font-semibold ${saveStateTone(activeChapterNumber)}`}>
                          {saveStateLabel(activeChapterNumber)}
                        </span>
                        <button
                          type="button"
                          onClick={() => setShowEditorSettings((value) => !value)}
                          className={`hidden rounded-sm border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}
                          aria-label="Editor settings"
                        >
                          ⚙
                        </button>
                        <button
                          onClick={saveCurrentChapter}
                          disabled={saving || !text.trim()}
                          className={`rounded-sm border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-100 disabled:opacity-40" : "border-stone-200 bg-white text-stone-700 disabled:opacity-40"}`}
                          aria-label="Save now"
                        >
                          Save
                        </button>
                      </div>
                    </div>
                    {showEditorSettings ? (
                      <div className={`mt-4 inline-flex items-center gap-2 rounded-sm border px-3 py-2 text-xs ${isDark ? "border-white/10 bg-black/30 text-slate-300" : "border-stone-200 bg-white text-stone-600"}`}>
                        <span>Replace existing chapter</span>
                        <button
                          type="button"
                          onClick={() => setReplaceExisting((value) => !value)}
                          className={`rounded-sm px-2.5 py-1 font-semibold ${replaceExisting || selectedChapter !== null ? isDark ? "bg-white text-slate-950" : "bg-stone-900 text-white" : isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}
                        >
                          {replaceExisting || selectedChapter !== null ? "On" : "Off"}
                        </button>
                      </div>
                    ) : null}
                    {autosaveMetaLabel(activeChapterNumber) ? <p className={`mt-3 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{autosaveMetaLabel(activeChapterNumber)}</p> : null}
                  </div>
                  <div className={`sticky top-[8.25rem] z-10 border-b px-3 py-3 transition-all duration-200 translate-y-0 opacity-100 pointer-events-auto ${isDark ? "border-white/10 bg-[#0c1118]" : "border-[#e6dfd4] bg-[#f7f3ed]"}`}>
                    <EditorToolbar editorKey={`chapter-${activeChapterNumber}`} isDark={isDark} compact characters={characters} onAddComment={() => openAnnotationComposer()} onOpenNotes={() => openRightPane("notes")} />
                  </div>
                  <RichTextEditor
                    html={html}
                    onChange={(nextHtml, nextText) => {
                      setHtml(nextHtml)
                      setText(nextText)
                      markDraftDirty(activeChapterNumber)
                      setBookDrafts((current) => ({
                        ...current,
                        [activeChapterNumber]: { title: chapterTitle, text: nextText, html: nextHtml },
                      }))
                    }}
                    onFocus={() => setActiveEditorKey(`chapter-${activeChapterNumber}`)}
                    onBlur={() => setActiveEditorKey((current) => current === `chapter-${activeChapterNumber}` ? null : current)}
                    onShortcutSave={() => void saveCurrentChapter()}
                    onShortcutComment={() => openAnnotationComposer()}
                    onShortcutNotes={() => openRightPane("notes")}
                    onCharacterClick={(characterName) => {
                      const char = characters.find((c) => c.name === characterName || c.aliases?.includes(characterName))
                      if (char) openCharCard(char)
                    }}
                    editorKey={`chapter-${activeChapterNumber}`}
                    placeholder="Write or paste the chapter here..."
                    style={{ ...sheetStyle, textIndent: firstLineIndent ? "1.5em" : "0" }}
                    className={`relative min-h-[58vh] w-full border-0 bg-transparent px-5 py-10 outline-none sm:px-[18mm] sm:py-[22mm] ${isDark ? "text-slate-100 placeholder:text-slate-500" : "text-stone-900 placeholder:text-stone-400"}`}
                    contentClassName="mx-auto w-full max-w-[780px]"
                  />
                  <div className={`flex flex-wrap items-center justify-between gap-3 border-t px-5 py-3 text-xs sm:px-7 ${isDark ? "border-white/10 bg-[#0b1016] text-slate-400" : "border-[#e6dfd4] bg-[#f7f3ed] text-stone-500"}`}>
                    <span>{chapterWordCount.toLocaleString()} words</span>
                    <span>{saveStateLabel(activeChapterNumber)}</span>
                  </div>
                </div>
              </div>
              )
            ) : draftSurfaceMode === "paged" ? (
              <div className="space-y-5">
                {fullBookLoading ? <InlineLoadingRows label="Loading full manuscript" isDark={isDark} rows={2} /> : null}
                {fullBookPreviewSections.length > 0 ? (
                  <ManuscriptPagedPreview
                    sections={fullBookPreviewSections}
                    preset={pagedPreviewPreset}
                    firstLineIndent={firstLineIndent}
                    lineHeight={lineHeight}
                    isDark={isDark}
                    onPageCountChange={setFullBookPreviewPageCount}
                  />
                ) : (
                  <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No chapter drafts are ready for full-book preview yet.</p>
                )}
              </div>
            ) : (
              <div className="space-y-5">
                {fullBookLoading ? <InlineLoadingRows label="Loading full manuscript" isDark={isDark} rows={2} /> : null}
                {(chapterList?.chapters ?? []).map((chapter) => {
                  const draft = bookDrafts[chapter.number] ?? { title: chapter.title || `Chapter ${chapter.number}`, text: "", html: textToHtml("") }
                  return (
                    <div
                      key={chapter.number}
                      ref={(node) => {
                        chapterRefs.current[chapter.number] = node
                      }}
                      style={{ contentVisibility: "auto", containIntrinsicSize: "820px" }}
                      className={`relative mx-auto w-full max-w-full overflow-hidden border ${jumpTarget === chapter.number ? isDark ? "border-teal-400/50 bg-[#0e1218]" : "border-teal-300 bg-[#fdfcf9]" : isDark ? "border-white/10 bg-[#0e1218]" : "border-[#d8d0c4] bg-[#fdfcf9]"}`}
                    >
                      {showPageGuides ? (
                        <div
                          aria-hidden
                          className={`pointer-events-none absolute inset-0 ${isDark ? "opacity-20" : "opacity-35"}`}
                          style={{
                            backgroundImage: `repeating-linear-gradient(to bottom, transparent 0, transparent calc(297mm - 1px), ${isDark ? "rgba(255,255,255,0.08)" : "rgba(15,23,42,0.08)"} calc(297mm - 1px), ${isDark ? "rgba(255,255,255,0.08)" : "rgba(15,23,42,0.08)"} 297mm)`,
                          }}
                        />
                      ) : null}
                      <div className={`border-b px-5 py-5 sm:px-7 ${isDark ? "border-white/10 bg-[#111721]" : "border-[#e6dfd4] bg-[#f7f3ed]"}`}>
                        <div className="flex items-start justify-between gap-4">
                          <div className="min-w-0 flex-1">
                            <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Chapter {chapter.number}</p>
                            <input
                              key={`book-heading-${chapter.number}-${draft.title}`}
                              type="text"
                              defaultValue={formatChapterHeading(chapter.number, draft.title)}
                              onBlur={async (event) => {
                                const parsed = parseChapterHeading(event.target.value, chapter.number, draft.title)
                                setBookDrafts((current) => ({
                                  ...current,
                                  [chapter.number]: {
                                    title: parsed.title,
                                    text: current[chapter.number]?.text ?? draft.text,
                                    html: current[chapter.number]?.html ?? draft.html,
                                  },
                                }))
                                markDraftDirty(chapter.number)
                                if (draft.text.trim()) {
                                  setSaving(true)
                                  try {
                                    await saveChapterDraft(chapter.number, { ...draft, title: parsed.title })
                                  } finally {
                                    setSaving(false)
                                  }
                                }
                              }}
                              className={`mt-3 w-full border-0 bg-transparent font-serif text-3xl font-semibold leading-tight outline-none sm:text-4xl ${isDark ? "text-white placeholder:text-slate-600" : "text-stone-950 placeholder:text-stone-400"}`}
                            />
                            <p className={`mt-2 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{countWords(draft.text).toLocaleString()} words / ~{Math.max(1, Math.ceil(countWords(draft.text) / 500))} pages</p>
                            <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{formatReadingTimeLabel(countWords(draft.text) > 0 ? Math.max(1, Math.ceil(countWords(draft.text) / 250)) : 0)} · {buildSceneOutline(draft.text).length} scene{buildSceneOutline(draft.text).length === 1 ? "" : "s"}</p>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className={`rounded-sm px-3 py-1.5 text-3xs font-semibold ${saveStateTone(chapter.number)}`}>
                              {saveStateLabel(chapter.number)}
                            </span>
                            <button
                              onClick={() => void saveChapterDraft(chapter.number, draft)}
                              disabled={saving || !draft.text.trim()}
                              className={`rounded-sm border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-100 disabled:opacity-40" : "border-stone-200 bg-white text-stone-700 disabled:opacity-40"}`}
                              aria-label={`Save chapter ${chapter.number}`}
                            >
                              Save
                            </button>
                          </div>
                        </div>
                      </div>
                      <div className={`sticky top-[8.25rem] z-10 border-b px-3 py-3 transition-all duration-200 translate-y-0 opacity-100 pointer-events-auto ${isDark ? "border-white/10 bg-[#0c1118]" : "border-[#e6dfd4] bg-[#f7f3ed]"}`}>
                        <EditorToolbar editorKey={`book-${chapter.number}`} isDark={isDark} compact characters={characters} onAddComment={() => openAnnotationComposer()} onOpenNotes={() => openRightPane("notes")} />
                      </div>
                      <RichTextEditor
                        html={draft.html}
                        onChange={(nextHtml, nextText) => {
                          markDraftDirty(chapter.number)
                          setBookDrafts((current) => ({
                            ...current,
                            [chapter.number]: {
                              title: current[chapter.number]?.title ?? draft.title,
                              text: nextText,
                              html: nextHtml,
                            },
                          }))
                        }}
                        onFocus={() => setActiveEditorKey(`book-${chapter.number}`)}
                        onBlur={() => setActiveEditorKey((current) => current === `book-${chapter.number}` ? null : current)}
                        onShortcutSave={() => void saveChapterDraft(chapter.number, draft)}
                        onShortcutComment={() => openAnnotationComposer()}
                        onShortcutNotes={() => openRightPane("notes")}
                        onCharacterClick={(characterName) => {
                          const char = characters.find((c) => c.name === characterName || c.aliases?.includes(characterName))
                          if (char) openCharCard(char)
                        }}
                        editorKey={`book-${chapter.number}`}
                        placeholder="Draft this chapter..."
                        style={{ ...sheetStyle, textIndent: firstLineIndent ? "1.5em" : "0" }}
                        className={`relative min-h-[54vh] w-full border-0 bg-transparent px-5 py-10 outline-none sm:px-[18mm] sm:py-[22mm] ${isDark ? "text-slate-100 placeholder:text-slate-500" : "text-stone-900 placeholder:text-stone-400"}`}
                        contentClassName="mx-auto w-full max-w-[780px]"
                      />
                      <div className={`flex flex-wrap items-center justify-between gap-3 border-t px-5 py-3 text-xs sm:px-7 ${isDark ? "border-white/10 bg-[#0b1016] text-slate-400" : "border-[#e6dfd4] bg-[#f7f3ed] text-stone-500"}`}>
                        <span>{countWords(draft.text).toLocaleString()} words</span>
                        <span>{saveStateLabel(chapter.number)}</span>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}

            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <p className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>
                {draftSurfaceMode === "paged"
                  ? "Paged preview is read-only. Switch back to Draft mode to edit text, tighten selections, or anchor annotations."
                  : editorMode === "chapter"
                  ? "Save runs continuity review and refreshes unresolved plot-thread context immediately after ingest."
                  : "Full-book mode lets continuity findings and search hits jump straight to the right chapter card."}
              </p>
              {editorMode === "book" ? (
                <button
                  onClick={saveFullBook}
                  disabled={saving || Object.values(bookDrafts).every((draft) => !draft.text.trim())}
                  className={`rounded-sm border px-4 py-2 text-sm font-medium ${isDark ? "border-white/10 bg-white/5 text-slate-100 disabled:opacity-40" : "border-stone-200 bg-white text-stone-700 disabled:opacity-40"}`}
                >
                  {saving ? "Saving..." : "Save all chapters"}
                </button>
              ) : null}
            </div>
            {statusMessage ? <p role="status" className={`mt-3 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{statusMessage}</p> : null}
          </section>

          {workspaceTab === "write" && rightRailVisible ? (
            <Suspense fallback={<Skeleton variant="card" className="min-h-96 rounded-md" />}>
            <ManuscriptWriteRightRail
              isDark={isDark}
              bookId={bookId}
              activeRightPane={activeRightPane}
              onOpenRightPane={openRightPane}
              selectedCharCard={selectedCharCard}
              onClearSelectedCharCard={() => {
                setSelectedCharCard(null)
                setActiveRightPane("context")
              }}
              activeChapterContextCharacters={activeChapterContextCharacters}
              characters={characters}
              onOpenCharCard={openCharCard}
              activeThreadSummary={activeThreadSummary}
              plotThreads={plotThreads}
              recentEventSummary={recentEventSummary}
              warningSummary={warningSummary}
              review={review}
              onTightenSelectedText={() => void tightenSelectedText()}
              suggestions={suggestions}
              chapterAnnotationsCount={chapterAnnotations.length}
              chapterManualNotes={chapterManualNotes}
              generalNotes={generalNotes}
              activeChapterNumber={activeChapterNumber}
              arcSummaryCharacter={arcSummaryCharacter}
            />
            </Suspense>
          ) : null}

          {workspaceTab !== "write" && rightRailVisible ? (
          <aside className={inspectorRailClass}>
            <div className={`border-b p-2 ${isDark ? "border-white/[0.08]" : "border-stone-200"}`}>
              <div className="grid grid-cols-2 gap-1" role="tablist" aria-label="Analysis workspace panels">
                {([
                  ["insights", "Insights"],
                  ["character", "Characters"],
                ] as const).map(([pane, label]) => (
                  <button
                    key={pane}
                    type="button"
                    role="tab"
                    aria-selected={activeRightPane === pane}
                    onClick={() => setActiveRightPane(pane)}
                    className={`rounded-sm border-b-2 px-3 py-2.5 text-sm font-semibold transition ${
                      activeRightPane === pane
                        ? isDark
                          ? "border-teal-300 bg-white/[0.04] text-white"
                          : "border-teal-600 bg-stone-100 text-stone-950"
                        : isDark
                          ? "border-transparent text-slate-300 hover:bg-white/[0.04]"
                          : "border-transparent text-stone-600 hover:bg-stone-50"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {/* ── Character Card pane ──────────────────────────── */}
            {activeRightPane === "character" ? (
              <div className={inspectorSectionClass}>
                {/* Header: browse list or card header */}
                {selectedCharCard ? (
                  <>
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <button
                          onClick={() => setSelectedCharCard(null)}
                          className={`mb-1 ${inspectorLabelClass} transition hover:text-teal-300`}
                        >
                          ← All characters
                        </button>
                        <p className={`text-base font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{selectedCharCard.name}</p>
                        {selectedCharCard.aliases.length > 0 && (
                          <p className={`text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>aka {selectedCharCard.aliases.join(", ")}</p>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        {charCardEditing ? (
                          <>
                            <button
                              onClick={saveCharCard}
                              disabled={charCardSaving}
                              className={inspectorPrimaryButtonClass}
                            >
                              {charCardSaving ? "Saving…" : "Save"}
                            </button>
                            <button
                              onClick={() => setCharCardEditing(false)}
                              className={inspectorSecondaryButtonClass}
                            >
                              Cancel
                            </button>
                          </>
                        ) : (
                          <button
                            onClick={() => setCharCardEditing(true)}
                            className={inspectorSecondaryButtonClass}
                          >
                            Edit card
                          </button>
                        )}
                      </div>
                    </div>

                    <div className="mt-4 space-y-4">
                      {/* Role + First chapter badges */}
                      <div className="flex flex-wrap gap-2">
                        {selectedCharCard.role && (
                          <span className={inspectorChipClass}>{selectedCharCard.role === "mc" ? "Main" : selectedCharCard.role === "sc" ? "Supporting" : "Background"}</span>
                        )}
                        <span className={inspectorChipClass}>
                          Ch. {selectedCharCard.first_chapter}{selectedCharCard.last_seen_chapter ? ` to ${selectedCharCard.last_seen_chapter}` : ""}
                        </span>
                        {selectedCharCard.archetype && (
                          <span className={inspectorChipClass}>{selectedCharCard.archetype}</span>
                        )}
                        {selectedCharCard.character_type === "gag" && (
                          <span className={`rounded-sm border px-2 py-0.5 text-3xs font-semibold ${isDark ? "border-amber-400/20 bg-amber-500/10 text-amber-300" : "border-amber-200 bg-amber-50 text-amber-700"}`}>🎭 Gag</span>
                        )}
                      </div>

                      {/* Description */}
                      <div>
                        <p className={`mb-1 text-3xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Description</p>
                        {charCardEditing ? (
                          <textarea
                            rows={3}
                            value={charCardDraft.description}
                            onChange={e => setCharCardDraft(d => ({ ...d, description: e.target.value }))}
                            className={`w-full resize-none rounded-sm border px-3 py-2 text-sm leading-6 outline-none ${isDark ? "border-white/10 bg-black/30 text-slate-200" : "border-stone-200 bg-stone-50 text-stone-800"}`}
                          />
                        ) : (
                          <p className={`text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{selectedCharCard.description || <span className="opacity-40">No description yet.</span>}</p>
                        )}
                      </div>

                      {/* Arc summary */}
                      <div>
                        <p className={`mb-1 text-3xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Arc summary</p>
                        {charCardEditing ? (
                          <textarea
                            rows={4}
                            value={charCardDraft.arcSummary}
                            onChange={e => setCharCardDraft(d => ({ ...d, arcSummary: e.target.value }))}
                            className={`w-full resize-none rounded-sm border px-3 py-2 text-sm leading-6 outline-none ${isDark ? "border-white/10 bg-black/30 text-slate-200" : "border-stone-200 bg-stone-50 text-stone-800"}`}
                          />
                        ) : (
                          <p className={`text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{selectedCharCard.arc_summary || <span className="opacity-40">No arc summary yet.</span>}</p>
                        )}
                      </div>

                      {/* Personality tags */}
                      <div>
                        <p className={`mb-1 text-3xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Personality</p>
                        {charCardEditing ? (
                          <input
                            value={charCardDraft.personalityTags}
                            onChange={e => setCharCardDraft(d => ({ ...d, personalityTags: e.target.value }))}
                            placeholder="Comma-separated traits"
                            className={`w-full rounded-sm border px-3 py-2 text-sm outline-none ${isDark ? "border-white/10 bg-black/30 text-slate-200 placeholder:text-slate-600" : "border-stone-200 bg-stone-50 text-stone-800"}`}
                          />
                        ) : (
                          <div className="flex flex-wrap gap-1.5">
                            {(selectedCharCard.personality_tags ?? []).length > 0 ? selectedCharCard.personality_tags.map(tag => (
                              <span key={tag} className={inspectorChipClass}>{tag}</span>
                            )) : <span className={`text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>None recorded.</span>}
                          </div>
                        )}
                      </div>

                      {/* Motivations */}
                      <div>
                        <p className={`mb-1 text-3xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Motivations</p>
                        {charCardEditing ? (
                          <input
                            value={charCardDraft.motivations}
                            onChange={e => setCharCardDraft(d => ({ ...d, motivations: e.target.value }))}
                            placeholder="Comma-separated"
                            className={`w-full rounded-sm border px-3 py-2 text-sm outline-none ${isDark ? "border-white/10 bg-black/30 text-slate-200 placeholder:text-slate-600" : "border-stone-200 bg-stone-50 text-stone-800"}`}
                          />
                        ) : (
                          <ul className="space-y-1">
                            {(selectedCharCard.motivations ?? []).length > 0 ? selectedCharCard.motivations.map(m => (
                              <li key={m} className={`text-sm leading-5 ${isDark ? "text-slate-300" : "text-stone-600"}`}>· {m}</li>
                            )) : <li className={`text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>None recorded.</li>}
                          </ul>
                        )}
                      </div>

                      {/* Fears */}
                      <div>
                        <p className={`mb-1 text-3xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Fears</p>
                        {charCardEditing ? (
                          <input
                            value={charCardDraft.fears}
                            onChange={e => setCharCardDraft(d => ({ ...d, fears: e.target.value }))}
                            placeholder="Comma-separated"
                            className={`w-full rounded-sm border px-3 py-2 text-sm outline-none ${isDark ? "border-white/10 bg-black/30 text-slate-200 placeholder:text-slate-600" : "border-stone-200 bg-stone-50 text-stone-800"}`}
                          />
                        ) : (
                          <ul className="space-y-1">
                            {(selectedCharCard.fears ?? []).length > 0 ? selectedCharCard.fears.map(f => (
                              <li key={f} className={`text-sm leading-5 ${isDark ? "text-slate-300" : "text-stone-600"}`}>· {f}</li>
                            )) : <li className={`text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>None recorded.</li>}
                          </ul>
                        )}
                      </div>

                      {/* Growth events */}
                      {(selectedCharCard.growth_events ?? []).length > 0 && (
                        <div>
                          <p className={`mb-1 text-3xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Growth events</p>
                          <div className="space-y-2">
                            {selectedCharCard.growth_events!
                              .slice()
                              .sort((left, right) => (right.chapter_number ?? right.chapter ?? 0) - (left.chapter_number ?? left.chapter ?? 0))
                              .map((ev, i) => (
                              <div key={i} className={`rounded-sm border px-3 py-2 text-xs ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
                                {(ev.chapter_number ?? ev.chapter) ? (
                                  <span className={`font-semibold ${isDark ? "text-teal-300" : "text-teal-700"}`}>
                                    Ch. {ev.chapter_number ?? ev.chapter} ·{" "}
                                  </span>
                                ) : null}
                                <span className={isDark ? "text-slate-300" : "text-stone-700"}>{ev.event_title || ev.event || "Untitled event"}</span>
                                {(ev.description || ev.impact) ? (
                                  <p className={`mt-1 leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>{ev.description || ev.impact}</p>
                                ) : null}
                                <div className="mt-2 flex flex-wrap gap-1.5">
                                  {typeof ev.impact_score === "number" ? (
                                    <span className={inspectorChipClass}>
                                      impact {ev.impact_score}/10
                                    </span>
                                  ) : null}
                                  {ev.growth_direction ? (
                                    <span className={`${inspectorChipClass} capitalize`}>
                                      {ev.growth_direction}
                                    </span>
                                  ) : null}
                                  {typeof ev.growth_magnitude === "number" ? (
                                    <span className={inspectorChipClass}>
                                      growth {ev.growth_magnitude}/10
                                    </span>
                                  ) : null}
                                  {ev.is_major ? (
                                    <span className={`rounded-sm border px-2 py-0.5 ${isDark ? "border-amber-400/20 bg-amber-500/10 text-amber-300" : "border-amber-200 bg-amber-50 text-amber-700"}`}>
                                      major
                                    </span>
                                  ) : null}
                                </div>
                                {ev.accomplishments?.length ? (
                                  <p className={`mt-2 leading-5 ${isDark ? "text-slate-500" : "text-stone-500"}`}>
                                    Accomplishments: {ev.accomplishments.join(", ")}
                                  </p>
                                ) : null}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Save to notes */}
                      <button
                        onClick={() => {
                          void saveWorkspaceVaultNote({
                            title: selectedCharCard.name,
                            body: [
                              `**${selectedCharCard.name}** (${selectedCharCard.role ?? "background"})`,
                              selectedCharCard.arc_summary ? `\nArc: ${selectedCharCard.arc_summary}` : "",
                              selectedCharCard.personality_tags?.length ? `\nPersonality: ${selectedCharCard.personality_tags.join(", ")}` : "",
                              selectedCharCard.motivations?.length ? `\nMotivations: ${selectedCharCard.motivations.join("; ")}` : "",
                            ].filter(Boolean).join("\n"),
                            folderSegments: ["Characters", selectedCharCard.name],
                          }).catch(() => setStatusMessage("Could not save note."))
                        }}
                        className={`${inspectorSecondaryButtonClass} w-full`}
                      >
                        Save as note
                      </button>
                    </div>
                  </>
                ) : (
                  /* Browse list */
                  <div>
                    <p className={inspectorLabelClass}>Characters</p>
                    <p className={`mt-1 text-xs ${inspectorMutedTextClass}`}>Click a name to open their card.</p>
                    <div className="mt-3 space-y-2">
                      {characters.length === 0 ? (
                        <p className={`text-sm ${inspectorMutedTextClass}`}>No characters extracted yet.</p>
                      ) : characters.map(char => (
                        <button
                          key={char.id}
                          onClick={() => openCharCard(char)}
                          className={`${inspectorRecordClass} w-full text-left transition hover:border-teal-400/40`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{char.name}</p>
                            {char.role && (
                              <span className={inspectorChipClass}>{char.role}</span>
                            )}
                          </div>
                          {char.arc_summary && (
                            <p className={`mt-1 line-clamp-2 text-xs ${inspectorMutedTextClass}`}>{char.arc_summary}</p>
                          )}
                          {char.personality_tags && char.personality_tags.length > 0 && (
                            <div className="mt-2 flex flex-wrap gap-1">
                              {char.personality_tags.slice(0, 3).map(t => (
                                <span key={t} className={inspectorChipClass}>{t}</span>
                              ))}
                            </div>
                          )}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : null}

            {activeRightPane === "insights" ? (
              <>
            {editorMode === "book" ? (
              <>
                <div className={inspectorSectionClass}>
                  <div className="flex items-center justify-between gap-3">
                    <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Page navigator</p>
                    <span className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{fullBookPageSummaryLabel}</span>
                  </div>
                  {draftSurfaceMode === "paged" ? <p className={`mt-2 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Chapter jump targets still use draft-length estimates while paged preview is on.</p> : null}
                  <div className="mt-3 flex gap-2">
                    <input
                      type="number"
                      min={1}
                      max={Math.max(1, fullBookApproxPages)}
                      value={gotoPageInput}
                      onChange={(event) => setGotoPageInput(event.target.value)}
                      placeholder="Page #"
                      className={`w-full rounded-sm border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"}`}
                    />
                    <button
                      onClick={() => {
                        const page = parseInt(gotoPageInput)
                        if (!Number.isNaN(page)) jumpToPage(page)
                      }}
                      className={`rounded-sm px-3 py-2 text-sm font-medium ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}
                    >
                      Go
                    </button>
                  </div>
                  <div className="mt-3 max-h-64 space-y-2 overflow-y-auto pr-1">
                    {fullBookPageMap.map((item) => (
                      <button
                        key={`page-${item.chapter}`}
                        onClick={() => jumpToPage(item.startPage)}
                        className={`block w-full rounded-md border px-3 py-3 text-left text-sm ${jumpTarget === item.chapter ? isDark ? "border-teal-400/30 bg-teal-500/10 text-slate-100" : "border-teal-300 bg-teal-50 text-stone-900" : isDark ? "border-white/10 bg-white/[0.03] text-slate-200 hover:bg-white/[0.07]" : "border-stone-200 bg-stone-50 text-stone-700 hover:bg-stone-100"}`}
                      >
                        <p className="font-semibold">Pages {item.startPage}{item.endPage > item.startPage ? ` to ${item.endPage}` : ""}</p>
                        <p className="mt-1 text-xs opacity-75">Chapter {item.chapter} · {item.title}</p>
                      </button>
                    ))}
                  </div>
                </div>

                <div className={inspectorSectionClass}>
                  <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>References</p>
                  <div className="mt-3 max-h-72 space-y-2 overflow-y-auto pr-1">
                    {fullBookReferenceItems.length > 0 ? fullBookReferenceItems.map((item) => {
                      const pageRef = fullBookPageMap.find((entry) => entry.chapter === item.chapter)
                      return (
                        <button
                          key={item.id}
                          onClick={() => jumpToChapter(item.chapter)}
                          className={`block w-full rounded-md border px-3 py-3 text-left text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-200 hover:bg-white/[0.07]" : "border-stone-200 bg-stone-50 text-stone-700 hover:bg-stone-100"}`}
                        >
                          <div className="flex items-center justify-between gap-3">
                            <p className="font-semibold">Page {pageRef?.startPage ?? "?"}</p>
                            <span className={`text-3xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{item.source}</span>
                          </div>
                          <p className="mt-1 text-xs opacity-75">Chapter {item.chapter} · {item.title}</p>
                          <p className="mt-2 text-xs opacity-80">{item.excerpt}</p>
                        </button>
                      )
                    }) : <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Search hits, continuity passages, and insertion references will appear here.</p>}
                  </div>
                </div>
              </>
            ) : null}

            {synopsis ? (
              <div className={inspectorSectionClass}>
                  <p className={inspectorLabelClass}>Synopsis generator</p>
                <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{synopsis.synopsis}</p>
                {synopsis.focus_points.length > 0 ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {synopsis.focus_points.map((point) => (
                      <span key={point} className={inspectorChipClass}>{point}</span>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}

            <div className={inspectorSectionClass}>
              <div className="flex items-center justify-between gap-3">
                <p className={inspectorLabelClass}>Continuity check</p>
                <Link href={`/${bookId}/reports`} className={inspectorSecondaryButtonClass}>Report history</Link>
              </div>
              {review ? (
                <div className="mt-3 space-y-3">
                  <p className={`text-sm font-medium ${isDark ? "text-white" : "text-stone-900"}`}>{review.overall_verdict}</p>
                  {review.continuity_issues.length > 0 ? review.continuity_issues.map((issue, index) => (
                    <div key={`${issue.title}-${index}`} className={`rounded-md border px-3 py-3 text-sm ${isDark ? "border-amber-500/20 bg-amber-500/10 text-slate-200" : "border-amber-200 bg-amber-50 text-stone-700"}`}>
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1">
                          <p className="font-semibold">{issue.title}</p>
                          <p className="mt-1 text-xs leading-5 opacity-80">{issue.description}</p>
                          {issue.suggestion ? <p className="mt-2 text-xs font-medium opacity-90">{issue.suggestion}</p> : null}
                        </div>
                        <button
                          onClick={() => void saveContinuityIssueAsNote(issue)}
                          className={`${inspectorSecondaryButtonClass} shrink-0 px-2 py-1 text-3xs`}
                        >
                          Save as note
                        </button>
                      </div>
                    </div>
                  )) : (
                    <p className={`text-sm ${isDark ? "text-teal-300" : "text-teal-700"}`}>No continuity issues found in the latest save.</p>
                  )}
                  {review.insertion_opportunities.length > 0 ? (
                    <div className="space-y-2">
                      <p className={inspectorLabelClass}>Insertion opportunities</p>
                      {review.insertion_opportunities.map((item, index) => (
                        <div key={`${item.title}-${index}`} className={`${inspectorRecordClass} text-sm`}>
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="font-semibold">{item.title}</p>
                              <p className="mt-1 text-xs opacity-75">Chapter {item.target_chapter}{item.target_chapter_title ? ` - ${item.target_chapter_title}` : ""}</p>
                            </div>
                            <button onClick={() => jumpToChapter(item.target_chapter)} className={`${inspectorSecondaryButtonClass} px-2 py-1 text-3xs`}>
                              Jump there
                            </button>
                          </div>
                          <p className="mt-2 text-xs leading-5 opacity-80">{item.problem}</p>
                          <p className="mt-2 text-xs font-medium opacity-95">Add: {item.what_to_add}</p>
                          <p className="mt-2 text-xs opacity-80">{item.why_here}</p>
                          {item.anchor_excerpt ? <p className="mt-2 text-xs opacity-70">Anchor: “{item.anchor_excerpt}”</p> : null}
                        </div>
                      ))}
                    </div>
                  ) : null}
                  <button
                    onClick={async () => {
                      const blob = await intelligenceApi.continuityReport(bookId, text || bookDrafts[activeChapterNumber]?.text || "", "pdf", activeChapterNumber)
                      const url = URL.createObjectURL(blob)
                      const link = document.createElement("a")
                      link.href = url
                      link.download = `${(book?.title || "lorevia").replace(/\s+/g, "-").toLowerCase()}-continuity-report.pdf`
                      link.click()
                      URL.revokeObjectURL(url)
                    }}
                    className={inspectorSecondaryButtonClass}
                  >
                    Download continuity report
                  </button>
                </div>
              ) : (
                <p className={`mt-3 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Save a chapter to run checks.</p>
              )}
            </div>

            <div className={inspectorSectionClass}>
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className={inspectorLabelClass}>Character voice consistency</p>
                  <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Voice checks moved into a dedicated workspace so notes and scene snapshots stay shared across the app.</p>
                </div>
                <Link href={`/${bookId}/voice` as Route} className={inspectorSecondaryButtonClass}>
                  Open voice workspace
                </Link>
              </div>
            </div>

            <div className={inspectorSectionClass}>
              <div className="flex items-center justify-between gap-3">
                <p className={inspectorLabelClass}>Open threads</p>
                <Link href={`/${bookId}/plot-threads`} className={inspectorSecondaryButtonClass}>Dashboard</Link>
              </div>
              <div className="mt-3 space-y-2">
                {plotThreads.length > 0 ? plotThreads.map((thread) => (
                  <div key={thread.id} className={`rounded-md border px-3 py-3 text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-200" : "border-stone-200 bg-stone-50 text-stone-700"}`}>
                    <p className="font-semibold">{thread.title}</p>
                    <p className="mt-1 text-xs opacity-75">Introduced in chapter {thread.introduced_at ?? "?"} · {thread.status}</p>
                  </div>
                )) : <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No unresolved threads loaded yet.</p>}
              </div>
            </div>

            {reviewPassages.length > 0 ? (
              <div className={inspectorSectionClass}>
                <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Cross-referenced passages</p>
                <div className="mt-3 space-y-2">
                  {reviewPassages.map((passage, index) => (
                    <button
                      key={`${passage.chapter_num}-${index}`}
                      onClick={() => jumpToChapter(passage.chapter_num)}
                      className={`block w-full rounded-md border px-3 py-3 text-left text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-200 hover:bg-white/[0.07]" : "border-stone-200 bg-stone-50 text-stone-700 hover:bg-stone-100"}`}
                    >
                      <p className="font-semibold">Chapter {passage.chapter_num}{passage.chapter_title ? `: ${passage.chapter_title}` : ""}{typeof passage.chunk_index === "number" ? ` | chunk ${passage.chunk_index}` : ""}</p>
                      <p className="mt-1 text-xs opacity-80">{passage.excerpt}</p>
                    </button>
                  ))}
                </div>
              </div>
            ) : null}
              </>
            ) : (
              <>
                <div className={inspectorSectionClass}>
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className={inspectorLabelClass}>Notes</p>
                      <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                        Save quick author notes for this chapter or for the whole book.
                      </p>
                    </div>
                    <Link href={`/${bookId}/notes`} className={inspectorSecondaryButtonClass}>All notes</Link>
                  </div>

                  <div className={`mt-4 inline-flex rounded-sm border p-1 ${isDark ? "border-white/[0.08] bg-[#080b0c]" : "border-stone-200 bg-stone-100"}`}>
                    <button
                      onClick={() => setNoteScope("chapter")}
                      className={`rounded-sm border-b-2 px-3 py-1.5 text-xs font-semibold ${noteScope === "chapter" ? isDark ? "border-teal-300 bg-white/[0.04] text-white" : "border-teal-600 bg-white text-stone-950" : isDark ? "border-transparent text-slate-300" : "border-transparent text-stone-600"}`}
                    >
                      Chapter {activeChapterNumber}
                    </button>
                    <button
                      onClick={() => setNoteScope("book")}
                      className={`rounded-sm border-b-2 px-3 py-1.5 text-xs font-semibold ${noteScope === "book" ? isDark ? "border-teal-300 bg-white/[0.04] text-white" : "border-teal-600 bg-white text-stone-950" : isDark ? "border-transparent text-slate-300" : "border-transparent text-stone-600"}`}
                    >
                      Whole book
                    </button>
                  </div>

                  <div className="mt-4 space-y-3">
                    <input
                      value={noteTitle}
                      onChange={(event) => setNoteTitle(event.target.value)}
                      placeholder="Note title"
                      className={`${inspectorInputClass} w-full px-3 py-2 text-sm`}
                    />
                    <div className={`overflow-hidden rounded-md border ${isDark ? "border-white/[0.08] bg-[#0a0d0f]" : "border-stone-200 bg-white"}`}>
                      <EditorToolbar editorKey="note-editor-modal" isDark={isDark} compact characters={characters} />
                      <RichTextEditor
                        editorKey="note-editor-modal"
                        html={noteBody}
                        onChange={(nextHtml, nextText) => {
                          setNoteBody(nextHtml)
                          setNoteBodyText(nextText)
                        }}
                        onCharacterClick={(characterName) => {
                          const char = characters.find((c) => c.name === characterName || c.aliases?.includes(characterName))
                          if (char) openCharCard(char)
                        }}
                        placeholder={noteScope === "chapter" ? `Add a note for chapter ${activeChapterNumber}` : "Add a book-level note"}
                        className={`min-h-[11rem] px-4 py-4 text-sm leading-7 outline-none ${isDark ? "bg-black/40 text-slate-100 placeholder:text-slate-500" : "bg-white text-stone-900 placeholder:text-stone-400"}`}
                      />
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <button
                        onClick={saveNote}
                        disabled={savingNote || !noteBodyText.trim()}
                        className={`${inspectorPrimaryButtonClass} px-4 py-3 text-sm`}
                      >
                        {savingNote ? "Saving..." : `Save ${noteScope === "chapter" ? "chapter" : "book"} note`}
                      </button>
                      <button
                        type="button"
                        onClick={() => void saveWorkspaceVaultNote()}
                        disabled={!noteBodyText.trim()}
                        className={`${inspectorSecondaryButtonClass} px-4 py-3 text-sm disabled:opacity-40`}
                      >
                        Save to workspace notes
                      </button>
                      <Link
                        href={`/${bookId}/notes`}
                        className={`${inspectorSecondaryButtonClass} inline-flex items-center justify-center px-4 py-3 text-sm`}
                      >
                        Open notes workspace
                      </Link>
                    </div>
                  </div>
                </div>

                <div className={inspectorSectionClass}>
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className={inspectorLabelClass}>Annotations</p>
                      <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Anchor comments, private notes, and review categories directly to manuscript passages.</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => openAnnotationComposer()}
                      className={inspectorSecondaryButtonClass}
                    >
                      Use selection
                    </button>
                  </div>
                  {annotationAnchor ? (
                    <div className={`mt-4 rounded-md border p-3 ${isDark ? "border-amber-500/20 bg-amber-500/10" : "border-amber-200 bg-amber-50"}`}>
                      <p className={`text-3xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-amber-200" : "text-amber-800"}`}>Selected passage</p>
                      <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-100" : "text-stone-700"}`}>{annotationAnchor.quote}</p>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <select
                          value={annotationCategory}
                          onChange={(event) => setAnnotationCategory(event.target.value as ManuscriptAnnotationCategory)}
                          className={`${inspectorInputClass} px-3 py-2 text-sm`}
                        >
                          {MANUSCRIPT_ANNOTATION_CATEGORIES.map((category) => (
                            <option key={category} value={category}>
                              {MANUSCRIPT_ANNOTATION_CATEGORY_LABELS[category]}
                            </option>
                          ))}
                        </select>
                        <div className={`inline-flex rounded-sm border p-1 ${isDark ? "border-white/[0.08] bg-[#080b0c]" : "border-stone-200 bg-white"}`}>
                          <button
                            type="button"
                            onClick={() => setAnnotationVisibility("shared")}
                            className={`rounded-sm border-b-2 px-3 py-1.5 text-xs font-semibold ${annotationVisibility === "shared" ? isDark ? "border-teal-300 bg-white/[0.04] text-white" : "border-teal-600 bg-stone-100 text-stone-950" : isDark ? "border-transparent text-slate-300" : "border-transparent text-stone-600"}`}
                          >
                            Shared
                          </button>
                          <button
                            type="button"
                            onClick={() => setAnnotationVisibility("private")}
                            className={`rounded-sm border-b-2 px-3 py-1.5 text-xs font-semibold ${annotationVisibility === "private" ? isDark ? "border-teal-300 bg-white/[0.04] text-white" : "border-teal-600 bg-stone-100 text-stone-950" : isDark ? "border-transparent text-slate-300" : "border-transparent text-stone-600"}`}
                          >
                            Private
                          </button>
                        </div>
                      </div>
                      <textarea
                        value={annotationDraft}
                        onChange={(event) => setAnnotationDraft(event.target.value)}
                        placeholder="Leave an inline annotation"
                        rows={4}
                        className={`${inspectorInputClass} mt-3 w-full px-3 py-2 text-sm`}
                      />
                      <div className="mt-3 flex flex-wrap gap-2">
                        <button
                          onClick={() => void saveAnnotation()}
                          disabled={annotationActionId === "new" || !annotationDraft.trim()}
                          className={`${inspectorPrimaryButtonClass} px-4 py-2 text-sm`}
                        >
                          {annotationActionId === "new" ? "Saving..." : "Save annotation"}
                        </button>
                        <button
                          type="button"
                          onClick={() => {
                            setAnnotationAnchor(null)
                            setAnnotationDraft("")
                          }}
                          className={`${inspectorSecondaryButtonClass} px-4 py-2 text-sm`}
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <p className={`mt-4 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Highlight text in the chapter editor, then add an annotation from the floating menu, toolbar, or Ctrl/Cmd+Shift+M.</p>
                  )}
                </div>

                <div className={inspectorSectionClass}>
                  <p className={inspectorLabelClass}>Chapter annotations</p>
                  <div className="mt-3 space-y-2">
                    {annotationsLoading ? <InlineLoadingRows label="Loading annotations" isDark={isDark} rows={3} /> : null}
                    {!annotationsLoading && chapterAnnotations.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No annotations saved for this chapter yet.</p> : null}
                    {[...openChapterAnnotations, ...resolvedChapterAnnotations].map((annotation) => (
                      <div
                        key={annotation.id}
                        className={`rounded-md border px-3 py-3 ${activeAnnotationId === annotation.id ? isDark ? "border-amber-400/40 bg-amber-500/10" : "border-amber-300 bg-amber-50" : isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="flex flex-wrap items-center gap-2">
                              <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{annotationCategoryLabel(annotation.category)}</p>
                              <span className={`rounded-sm border px-2 py-0.5 text-3xs font-semibold uppercase tracking-[0.14em] ${annotation.status === "resolved" ? isDark ? "border-white/[0.08] bg-white/[0.05] text-slate-300" : "border-stone-200 bg-stone-100 text-stone-700" : isDark ? "border-teal-400/20 bg-teal-500/10 text-teal-200" : "border-teal-200 bg-teal-50 text-teal-800"}`}>
                                {annotation.status}
                              </span>
                              <span className={`${inspectorChipClass} uppercase tracking-[0.14em]`}>
                                {annotation.visibility}
                              </span>
                            </div>
                            <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{annotation.created_by_label} · {new Date(annotation.updated_at).toLocaleString()}</p>
                          </div>
                          <div className="flex gap-2">
                            <button onClick={() => jumpToAnnotation(annotation)} className={`text-xs font-medium ${isDark ? "text-slate-300" : "text-stone-600"}`}>Jump</button>
                            {annotation.can_edit ? (
                              <button
                                onClick={() => void updateAnnotationStatus(annotation, annotation.status === "resolved" ? "open" : "resolved")}
                                disabled={annotationActionId === annotation.id}
                                className={`text-xs font-medium ${isDark ? "text-slate-300" : "text-stone-600"}`}
                              >
                                {annotation.status === "resolved" ? "Reopen" : "Resolve"}
                              </button>
                            ) : null}
                            {annotation.can_edit ? (
                              <button
                                onClick={() => void removeAnnotation(annotation.id)}
                                disabled={annotationActionId === annotation.id}
                                className={inspectorDangerButtonClass}
                              >
                                Delete
                              </button>
                            ) : null}
                          </div>
                        </div>
                        <blockquote className={`mt-3 border-l-2 pl-3 text-sm italic ${isDark ? "border-amber-300/40 text-slate-300" : "border-amber-300 text-stone-600"}`}>
                          {annotation.quote}
                        </blockquote>
                        <p className={`mt-3 whitespace-pre-wrap text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{annotation.comment}</p>
                      </div>
                    ))}
                  </div>
                </div>

                <div className={inspectorSectionClass}>
                  <p className={inspectorLabelClass}>Chapter-linked notes</p>
                  <div className="mt-3 space-y-2">
                    {notesLoading ? <InlineLoadingRows label="Loading notes" isDark={isDark} rows={3} /> : null}
                    {!notesLoading && chapterManualNotes.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No notes saved for this chapter yet.</p> : null}
                    {chapterManualNotes.map((note) => (
                      <div key={note.id} className={`rounded-md border px-3 py-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
                        {editingNoteId === note.id ? (
                          <div className="space-y-3">
                            <input
                              value={editNoteTitle}
                              onChange={(e) => setEditNoteTitle(e.target.value)}
                              placeholder="Note title"
                              className={`${inspectorInputClass} w-full px-3 py-2 text-sm`}
                            />
                            <textarea
                              value={editNoteBody}
                              onChange={(e) => setEditNoteBody(e.target.value)}
                              placeholder="Note content (markdown supported)"
                              rows={4}
                              className={`${inspectorInputClass} w-full px-3 py-2 text-sm`}
                            />
                            <div className="flex gap-2">
                              <button
                                onClick={saveEditedNote}
                                disabled={editingNoteSaving}
                                className={inspectorPrimaryButtonClass}
                              >
                                {editingNoteSaving ? "Saving..." : "Save"}
                              </button>
                              <button
                                onClick={cancelEditingNote}
                                className={inspectorSecondaryButtonClass}
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        ) : (
                          <>
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{note.title || `Chapter ${note.chapter_number} note`}</p>
                                <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{new Date(note.updated_at).toLocaleString()}</p>
                              </div>
                              <div className="flex gap-2">
                                <button onClick={() => startEditingNote(note)} className={`text-xs font-medium ${isDark ? "text-slate-300" : "text-stone-600"}`}>Edit</button>
                                <button onClick={() => removeNote(note.id)} className={inspectorDangerButtonClass}>Delete</button>
                              </div>
                            </div>
                            <div
                              className={`note-rich-content mt-3 text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}
                              dangerouslySetInnerHTML={{ __html: renderRichTextHtml(note.body) }}
                            />
                          </>
                        )}
                      </div>
                    ))}
                  </div>
                </div>

                <div className={inspectorSectionClass}>
                  <p className={inspectorLabelClass}>Whole-book notes</p>
                  <div className="mt-3 space-y-2">
                    {!notesLoading && generalNotes.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No general notes saved yet.</p> : null}
                    {generalNotes.map((note) => (
                      <div key={note.id} className={`rounded-md border px-3 py-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
                        {editingNoteId === note.id ? (
                          <div className="space-y-3">
                            <input
                              value={editNoteTitle}
                              onChange={(e) => setEditNoteTitle(e.target.value)}
                              placeholder="Note title"
                              className={`${inspectorInputClass} w-full px-3 py-2 text-sm`}
                            />
                            <textarea
                              value={editNoteBody}
                              onChange={(e) => setEditNoteBody(e.target.value)}
                              placeholder="Note content (markdown supported)"
                              rows={4}
                              className={`${inspectorInputClass} w-full px-3 py-2 text-sm`}
                            />
                            <div className="flex gap-2">
                              <button
                                onClick={saveEditedNote}
                                disabled={editingNoteSaving}
                                className={inspectorPrimaryButtonClass}
                              >
                                {editingNoteSaving ? "Saving..." : "Save"}
                              </button>
                              <button
                                onClick={cancelEditingNote}
                                className={inspectorSecondaryButtonClass}
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        ) : (
                          <>
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{note.title || "General book note"}</p>
                                <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{new Date(note.updated_at).toLocaleString()}</p>
                              </div>
                              <div className="flex gap-2">
                                <button onClick={() => startEditingNote(note)} className={`text-xs font-medium ${isDark ? "text-slate-300" : "text-stone-600"}`}>Edit</button>
                                <button onClick={() => removeNote(note.id)} className={inspectorDangerButtonClass}>Delete</button>
                              </div>
                            </div>
                            <div
                              className={`note-rich-content mt-3 text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}
                              dangerouslySetInnerHTML={{ __html: renderRichTextHtml(note.body) }}
                            />
                          </>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
          </aside>
          ) : null}
        </div>
        ) : null}

        {showReprocessConfirm ? (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
            <div className={`w-full max-w-md rounded-lg border p-5 ${isDark ? "border-white/10 bg-[#0f1117] text-slate-100" : "border-stone-200 bg-white text-stone-950"}`}>
              <h2 className="text-lg font-semibold">Reprocess manuscript?</h2>
              <p className={`mt-3 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                Reprocessing rebuilds the Character Bible, relationships, plot threads, summaries, world/lore data, and continuity signals from the saved manuscript. This will consume 1 book upload. Continue?
              </p>
              <div className="mt-5 flex flex-wrap justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowReprocessConfirm(false)}
                  disabled={reprocessing}
                  className={`rounded-md border px-4 py-2 text-sm font-medium disabled:opacity-50 ${isDark ? "border-white/10 text-slate-200" : "border-stone-200 text-stone-700"}`}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => void confirmReprocessManuscript()}
                  disabled={reprocessing}
                  className="rounded-md bg-[#1f615d] px-4 py-2 text-sm font-semibold text-white disabled:opacity-60"
                >
                  {reprocessing ? "Starting..." : "Reprocess and use 1 upload"}
                </button>
              </div>
            </div>
          </div>
        ) : null}

        <ManuscriptOverlayDialogs
          isDark={isDark}
          sceneEditorOpen={sceneEditorOpen}
          editingScene={editingScene}
          onCloseSceneEditor={closeSceneEditor}
          sceneTitleDraft={sceneTitleDraft}
          onSceneTitleDraftChange={setSceneTitleDraft}
          sceneChapterDraft={sceneChapterDraft}
          onSceneChapterDraftChange={setSceneChapterDraft}
          workspaceTree={workspaceTree}
          sceneDescriptionDraft={sceneDescriptionDraft}
          onSceneDescriptionDraftChange={setSceneDescriptionDraft}
          characters={characters}
          sceneHtmlDraft={sceneHtmlDraft}
          onSceneDraftChange={(nextHtml, nextText) => {
            setSceneHtmlDraft(nextHtml)
            setSceneBodyDraft(nextText)
          }}
          sceneVersions={sceneVersions}
          sceneVersionNameDraft={sceneVersionNameDraft}
          onSceneVersionNameDraftChange={setSceneVersionNameDraft}
          sceneVersionDetail={sceneVersionDetail}
          restoringSceneVersionId={restoringSceneVersionId}
          sceneBodyDraft={sceneBodyDraft}
          onCreateSceneSnapshot={() => void createSceneSnapshot()}
          onCompareSceneVersion={(versionId) => void compareSceneVersion(versionId)}
          onRestoreSceneSnapshot={(versionId) => void restoreSceneSnapshot(versionId)}
          sceneSaving={sceneSaving}
          onSaveScene={() => void saveScene()}
          showCompileDialog={showCompileDialog}
          writerWorkspace={writerWorkspace}
          manuscriptFrontMatter={manuscriptFrontMatter ?? null}
          onCloseCompileDialog={() => setShowCompileDialog(false)}
          compileFormat={compileFormat}
          fullBookWordCount={fullBookWordCount}
          includeSceneMetadataOnExport={includeSceneMetadataOnExport}
          onIncludeSceneMetadataOnExportChange={setIncludeSceneMetadataOnExport}
          onUpdateFrontMatter={updateFrontMatter}
          exporting={exporting}
          workspaceSaving={workspaceSaving}
          onCompileManuscript={() => void compileManuscript()}
        />

        <AddCharacterFromSelection
          bookId={bookId}
          selectedText={addCharacterText}
          isDark={isDark}
          firstChapter={activeChapterNumber ?? undefined}
          open={addCharacterOpen}
          onClose={() => setAddCharacterOpen(false)}
          onCreated={handleCharacterCreated}
        />
      </div>
    </div>
  )
}

function BookOpenIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 5.5c0-1 0-1.5.3-1.8.3-.2.8-.2 1.8-.2h3.1c1.5 0 2.4.4 2.8 1.2.4-.8 1.3-1.2 2.8-1.2h3.1c1 0 1.5 0 1.8.2.3.3.3.8.3 1.8v12c0 1 0 1.5-.3 1.8-.3.2-.8.2-1.8.2h-3.3c-1.4 0-2.2.3-2.6 1-.4-.7-1.2-1-2.6-1H6.1c-1 0-1.5 0-1.8-.2-.3-.3-.3-.8-.3-1.8v-12Z" />
      <path d="M12 5v15" />
    </svg>
  )
}

function ManuscriptEditorSkeleton({ isDark }: { isDark: boolean }) {
  const shellClass = isDark ? "bg-[#101416] text-slate-100" : "bg-[#f4f5f3] text-stone-950"
  const panelClass = isDark ? "border-white/10 bg-[#11171a]" : "border-stone-200 bg-white/90"
  const canvasClass = isDark ? "border-white/10 bg-[#0b1114]" : "border-stone-200 bg-[#faf8f4]"

  return (
    <div className={`min-h-screen ${shellClass}`}>
      <header className={`sticky top-0 z-40 border-b ${panelClass}`}>
        <div className="flex min-h-[4.25rem] items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <Skeleton className="h-7 w-7 rounded-sm" />
            <Skeleton className="h-5 w-52" />
          </div>
          <div className="flex items-center gap-3">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-10 w-20 rounded-sm" />
            <Skeleton className="h-10 w-28 rounded-sm" />
            <Skeleton className="h-10 w-10 rounded-sm" />
          </div>
        </div>
        <div className={`flex items-center justify-between border-t px-6 py-2 ${isDark ? "border-white/10" : "border-stone-200"}`}>
          <div className="flex gap-8">
            <Skeleton className="h-8 w-12" />
            <Skeleton className="h-8 w-10" />
            <Skeleton className="h-8 w-16" />
            <Skeleton className="h-8 w-20" />
          </div>
          <div className="flex gap-4">
            <Skeleton className="h-10 w-44 rounded-sm" />
            <Skeleton className="h-10 w-44 rounded-sm" />
          </div>
        </div>
      </header>

      <div className="grid min-w-0 xl:grid-cols-[22rem_minmax(0,1fr)_23.5rem]">
        <aside className={`hidden min-h-[calc(100vh-8.25rem)] border-r p-5 xl:block ${panelClass}`}>
          <Skeleton className="h-4 w-24" />
          <div className="mt-5 grid grid-cols-2 gap-2">
            <Skeleton className="h-10 rounded-sm" />
            <Skeleton className="h-10 rounded-sm" />
          </div>
          <Skeleton variant="card" className="mt-5 h-32 rounded-sm" />
          <Skeleton className="mt-4 h-10 rounded-sm" />
          <div className="mt-6 space-y-3">
            <Skeleton className="h-24 rounded-sm" />
            <Skeleton className="h-24 rounded-sm" />
            <Skeleton className="h-24 rounded-sm" />
          </div>
        </aside>

        <main className={`min-h-[calc(100vh-8.25rem)] border-r ${canvasClass}`}>
          <div className={`border-b px-7 py-6 ${isDark ? "border-white/10 bg-[#111721]" : "border-stone-200 bg-white"}`}>
            <Skeleton className="h-3 w-44" />
            <Skeleton className="mt-4 h-11 w-96" />
            <div className="mt-4 flex gap-4">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-4 w-24" />
            </div>
          </div>
          <div className={`border-b px-3 py-3 ${isDark ? "border-white/10 bg-[#0c1118]" : "border-stone-200 bg-white"}`}>
            <Skeleton className="h-11 w-full rounded-sm" />
          </div>
          <div className="px-8 py-10">
            <div className="mx-auto max-w-[780px] space-y-5">
              <Skeleton className="h-5 w-5/6" />
              <Skeleton className="h-5 w-4/6" />
              <Skeleton className="h-5 w-full" />
              <Skeleton className="h-5 w-11/12" />
              <Skeleton className="h-5 w-3/4" />
            </div>
          </div>
        </main>

        <aside className={`hidden min-h-[calc(100vh-8.25rem)] xl:block ${panelClass}`}>
          <div className={`border-b px-4 ${isDark ? "border-white/10" : "border-stone-200"}`}>
            <Skeleton className="h-12 w-full" />
          </div>
          <div className="space-y-0">
            <Skeleton className="h-40 rounded-none" />
            <Skeleton className="h-36 rounded-none" />
            <Skeleton className="h-36 rounded-none" />
            <Skeleton className="h-44 rounded-none" />
          </div>
        </aside>
      </div>
    </div>
  )
}

function DeferredPanelLoadingState({ label }: { label: string }) {
  return (
    <div className="flex min-h-[12rem] flex-col items-center justify-center gap-3 rounded-md border border-border bg-card/60 p-6">
      <Skeleton variant="card" className="w-full min-h-44" />
      <p className="text-sm text-muted-foreground">{label}</p>
    </div>
  )
}

function InlineLoadingRows({ isDark, label, rows = 3 }: { isDark: boolean; label: string; rows?: number }) {
  return (
    <div className="space-y-2" role="status" aria-label={label} aria-busy="true">
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }).map((_, index) => (
        <Skeleton
          key={`${label}-${index}`}
          className={`${index === rows - 1 ? "w-2/3" : "w-full"} h-3 ${isDark ? "bg-white/8" : "bg-stone-200/80"}`}
        />
      ))}
    </div>
  )
}

function annotationCategoryLabel(category: string) {
  return MANUSCRIPT_ANNOTATION_CATEGORY_LABELS[
    (category in MANUSCRIPT_ANNOTATION_CATEGORY_LABELS ? category : "general") as ManuscriptAnnotationCategory
  ]
}

function textToHtml(text: string) {
  const cleaned = text.trim()
  if (!cleaned) return "<p></p>"
  return cleaned
    .split(/\n{2,}/)
    .map((paragraph) => `<p>${escapeHtml(paragraph).replace(/\n/g, "<br>")}</p>`)
    .join("")
}

function escapeHtml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
}

function escapeAttribute(value: string) {
  return escapeHtml(value).replaceAll('"', "&quot;")
}
