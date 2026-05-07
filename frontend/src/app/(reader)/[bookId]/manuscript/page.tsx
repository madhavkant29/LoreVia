"use client"

import type { CSSProperties, ReactNode } from "react"
import { useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import { useParams, useRouter, useSearchParams } from "next/navigation"

import { booksApi } from "@/lib/api/books"
import { intelligenceApi } from "@/lib/api/intelligence"
import { readerApi } from "@/lib/api/reader"
import { saveContextualVaultNote } from "@/lib/utils/notes"
import { htmlToPlainText, renderRichTextHtml, sanitizeRichTextHtml } from "@/lib/utils/richText"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { capture } from "@/lib/analytics/posthog"
import type { Book, BookNote, ChapterVersion, ChapterVersionDetail, CorkboardCard, EmotionalArcOverview, ManuscriptFrontMatter, ManuscriptWorkspaceTree, NovelScene, PreWritingCheck, ReadabilityMetrics, WriterWorkspace, WritingTemplate } from "@/types/book"
import type { Character } from "@/types/character"
import type { AdvisorSuggestion, EditorialReview, EditorialReviewPassage, InlineContinuityResponse, ManuscriptSynopsis, VoiceConsistencyMatch, VoiceConsistencyReview } from "@/types/intelligence"
import type { ChapterListResponse, PlotThread, SearchResult } from "@/types/reader"

type EditorMode = "chapter" | "book"
type BookDraftMap = Record<number, { title: string; text: string; html: string }>
type WorkspaceTab = "write" | "plan" | "analyze" | "characters"
type RightPane = "context" | "advisor" | "notes" | "arcs" | "insights" | "character"

export default function ManuscriptPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const router = useRouter()
  const searchParams = useSearchParams()
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
  const [statusMessage, setStatusMessage] = useState<string | null>(null)
  const [review, setReview] = useState<EditorialReview | null>(null)
  const [reviewPassages, setReviewPassages] = useState<EditorialReviewPassage[]>([])
  const [voiceReview, setVoiceReview] = useState<VoiceConsistencyReview | null>(null)
  const [voiceCharacters, setVoiceCharacters] = useState<string[]>([])
  const [inlineContinuity, setInlineContinuity] = useState<InlineContinuityResponse | null>(null)
  const [suggestions, setSuggestions] = useState<AdvisorSuggestion[]>([])
  const [plotThreads, setPlotThreads] = useState<PlotThread[]>([])
  const [preWritingCheck, setPreWritingCheck] = useState<PreWritingCheck | null>(null)
  const [chapterVersions, setChapterVersions] = useState<ChapterVersion[]>([])
  const [chapterVersionDetail, setChapterVersionDetail] = useState<ChapterVersionDetail | null>(null)
  const [workspaceTree, setWorkspaceTree] = useState<ManuscriptWorkspaceTree | null>(null)
  const [sceneSearch, setSceneSearch] = useState("")
  const [chapterSearch, setChapterSearch] = useState("")
  const [collapsedSceneGroups, setCollapsedSceneGroups] = useState<Record<string, boolean>>({})
  const [sceneEditorOpen, setSceneEditorOpen] = useState(false)
  const [editingScene, setEditingScene] = useState<NovelScene | null>(null)
  const [sceneTitleDraft, setSceneTitleDraft] = useState("")
  const [sceneDescriptionDraft, setSceneDescriptionDraft] = useState("")
  const [sceneBodyDraft, setSceneBodyDraft] = useState("")
  const [sceneChapterDraft, setSceneChapterDraft] = useState<number | null>(null)
  const [sceneSaving, setSceneSaving] = useState(false)
  const [restoringVersionId, setRestoringVersionId] = useState<string | null>(null)
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
  const [workspaceTab, setWorkspaceTab] = useState<WorkspaceTab>("write")
  const [fontSize, setFontSize] = useState(12)
  const [fontSizeLocked, setFontSizeLocked] = useState(false)
  const [fontFamily, setFontFamily] = useState<"times" | "georgia" | "sans">("times")
  const [lineHeight, setLineHeight] = useState(1.8)
  const [showPageGuides, setShowPageGuides] = useState(true)
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
  const [compileFormat, setCompileFormat] = useState<"pdf" | "docx" | "epub" | "obsidian">("docx")
  const [includeSceneMetadataOnImport, setIncludeSceneMetadataOnImport] = useState(true)
  const [includeSceneMetadataOnExport, setIncludeSceneMetadataOnExport] = useState(true)
  const [showEditorSettings, setShowEditorSettings] = useState(false)
  const [activeEditorKey, setActiveEditorKey] = useState<string | null>(null)
  const [fullBookLoading, setFullBookLoading] = useState(false)
  const [bookDrafts, setBookDrafts] = useState<BookDraftMap>({})
  const [exporting, setExporting] = useState<"pdf" | "docx" | "epub" | "obsidian" | null>(null)
  const [jumpTarget, setJumpTarget] = useState<number | null>(null)
  const [activeFindIndex, setActiveFindIndex] = useState(0)
  const [replaceQuery, setReplaceQuery] = useState("")
  const [replaceValue, setReplaceValue] = useState("")
  const [gotoPageInput, setGotoPageInput] = useState("")
  const [showPageSetup, setShowPageSetup] = useState(false)
  const [showSearchTools, setShowSearchTools] = useState(false)
  const [notes, setNotes] = useState<BookNote[]>([])
  const [notesLoading, setNotesLoading] = useState(false)
  const [notesLoaded, setNotesLoaded] = useState(false)
  const [savingNote, setSavingNote] = useState(false)
  const [noteScope, setNoteScope] = useState<"chapter" | "book">("chapter")
  const [noteTitle, setNoteTitle] = useState("")
  const [noteBody, setNoteBody] = useState("")
  const [noteBodyText, setNoteBodyText] = useState("")
  const [dirtyDrafts, setDirtyDrafts] = useState<number[]>([])
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null)
  const [editNoteTitle, setEditNoteTitle] = useState("")
  const [editNoteBody, setEditNoteBody] = useState("")
  const [editingNoteSaving, setEditingNoteSaving] = useState(false)
  const [newCorkboardTitle, setNewCorkboardTitle] = useState("")
  const [voiceMatches, setVoiceMatches] = useState<VoiceConsistencyMatch[]>([])
  const [selectionMenu, setSelectionMenu] = useState<{ text: string; top: number; left: number } | null>(null)

  const chapterRefs = useRef<Record<number, HTMLDivElement | null>>({})
  const searchInputRef = useRef<HTMLInputElement | null>(null)
  const manuscriptSectionRef = useRef<HTMLDivElement | null>(null)
  const initialChapterLoadedRef = useRef<number | null>(null)
  const handledSceneIntentRef = useRef(false)

  const nextChapterNumber = useMemo(() => {
    const numbers = chapterList?.chapters.map((chapter) => chapter.number) ?? []
    return numbers.length ? Math.max(...numbers) + 1 : 1
  }, [chapterList])

  const activeChapterNumber = selectedChapter ?? draftChapterNumber ?? nextChapterNumber

  const sheetStyle = {
    fontSize: `${fontSize}pt`,
    lineHeight: String(lineHeight),
    fontFamily: fontFamily === "times" ? '"Times New Roman", Georgia, serif' : fontFamily === "georgia" ? 'Georgia, "Times New Roman", serif' : '"Space Grotesk", "Avenir Next", "Segoe UI Variable Text", sans-serif',
  } as const

  const chapterWordCount = useMemo(() => countWords(text), [text])
  const chapterApproxPages = useMemo(() => Math.max(1, Math.ceil(chapterWordCount / 500)), [chapterWordCount])
  const fullBookWordCount = useMemo(() => Object.values(bookDrafts).reduce((sum, draft) => sum + countWords(draft.text), 0), [bookDrafts])
  const fullBookApproxPages = useMemo(() => Math.max(1, Math.ceil(fullBookWordCount / 500)), [fullBookWordCount])
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
  const leftRailVisible = workspaceTab === "write" && !focusMode && showLeftRail
  const rightRailVisible = workspaceTab === "write" && !focusMode && showRightRail
  const desktopLayoutClass = leftRailVisible && rightRailVisible
    ? "xl:grid-cols-[17rem_minmax(0,1fr)_21rem]"
    : leftRailVisible
      ? "xl:grid-cols-[17rem_minmax(0,1fr)]"
      : rightRailVisible
        ? "xl:grid-cols-[minmax(0,1fr)_21rem]"
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
  const chapterLinkedNotes = useMemo(
    () => notes.filter((note) => note.chapter_number === activeChapterNumber),
    [activeChapterNumber, notes]
  )
  const generalNotes = useMemo(
    () => notes.filter((note) => note.chapter_number === null),
    [notes]
  )
  const filteredChapterItems = useMemo(() => {
    const query = chapterSearch.trim().toLowerCase()
    if (!query) return chapterListItems
    return chapterListItems.filter((chapter) => {
      const title = chapter.title?.toLowerCase() ?? ""
      return title.includes(query) || `chapter ${chapter.number}`.includes(query)
    })
  }, [chapterListItems, chapterSearch])
  const activeChapterDisplayTitle = chapterTitle.trim() || chapterListItems.find((chapter) => chapter.number === activeChapterNumber)?.title?.trim() || `Chapter ${activeChapterNumber}`
  const activeChapterHeading = `${activeChapterNumber}. ${activeChapterDisplayTitle}`
  const activeChapterWordTarget = writerWorkspace?.word_count_goals.chapter_target ?? 0
  const activeChapterContextCharacters = (preWritingCheck?.active_characters ?? []).slice(0, 4)
  const activeThreadSummary = preWritingCheck?.unresolved_threads.slice(0, 3) ?? []
  const recentEventSummary = preWritingCheck?.recent_events.slice(0, 3) ?? []
  const warningSummary = preWritingCheck?.alerts.slice(0, 3) ?? []
  const arcSummaryCharacter = emotionalArc?.characters[0] ?? null
  const filteredSceneGroups = useMemo(() => {
    if (!workspaceTree) return []
    const query = sceneSearch.trim().toLowerCase()
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
  }, [sceneSearch, workspaceTree])
  const filteredNotePaths = useMemo(() => {
    const paths = workspaceTree?.note_paths ?? []
    const query = sceneSearch.trim().toLowerCase()
    if (!query) return paths
    return paths.filter((path) => path.toLowerCase().includes(query))
  }, [sceneSearch, workspaceTree])
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

  const loadWorkspaceTree = async () => {
    try {
      const tree = await booksApi.getWorkspaceTree(bookId)
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

  const openSceneEditor = (scene?: NovelScene | null) => {
    setEditingScene(scene ?? null)
    setSceneTitleDraft(scene?.title ?? "")
    setSceneDescriptionDraft(scene?.description ?? "")
    setSceneBodyDraft(scene?.body ?? "")
    setSceneChapterDraft(scene?.chapter_number ?? (selectedChapter ?? null))
    setSceneEditorOpen(true)
  }

  const closeSceneEditor = () => {
    setSceneEditorOpen(false)
    setEditingScene(null)
    setSceneTitleDraft("")
    setSceneDescriptionDraft("")
    setSceneBodyDraft("")
    setSceneChapterDraft(selectedChapter ?? null)
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
      await booksApi.saveScene(bookId, {
        id: editingScene?.id,
        title: sceneTitleDraft.trim(),
        description: sceneDescriptionDraft.trim() || null,
        body: sceneBodyDraft,
        chapter_number: sceneChapterDraft,
        status: sceneChapterDraft ? "assigned" : "unassigned",
        sort_order: editingScene?.sort_order ?? 1,
      })
      await loadWorkspaceTree()
      closeSceneEditor()
      setStatusMessage(editingScene ? "Scene updated." : "Scene saved.")
    } finally {
      setSceneSaving(false)
    }
  }

  const removeScene = async (scene: NovelScene) => {
    await booksApi.deleteScene(bookId, scene.id)
    await loadWorkspaceTree()
    setStatusMessage(`Deleted scene "${scene.title}".`)
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
      await booksApi.createChapterSnapshot(bookId, selectedChapter, `Manual snapshot before edits to Chapter ${selectedChapter}`)
      setChapterVersions(await booksApi.getChapterVersions(bookId, selectedChapter))
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

  const applyTemplateToChapter = (template: WritingTemplate) => {
    const nextText = text.trim() ? `${text.trim()}\n\n${template.content}` : template.content
    const nextHtml = textToHtml(nextText)
    setText(nextText)
    setHtml(nextHtml)
    markDraftDirty(activeChapterNumber)
    setBookDrafts((current) => ({
      ...current,
      [activeChapterNumber]: { title: chapterTitle, text: nextText, html: nextHtml },
    }))
    setStatusMessage(`Inserted ${template.title} into chapter ${activeChapterNumber}.`)
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
      const payload = await intelligenceApi.proseTighten(bookId, selectedText, activeChapterNumber)
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
      initialChapterLoadedRef.current = initialChapterNumber
      setDraftChapterNumber(null)
      setChapterTitle(title)
      setText(chapterText)
      setHtml(chapterHtml)
      setBookDrafts((current) => ({
        ...current,
        [initialChapterNumber]: {
          title,
          text: current[initialChapterNumber]?.text ?? chapterText,
          html: current[initialChapterNumber]?.html ?? chapterHtml,
        },
      }))
    } catch {
      setChapterTitle(chapterMeta?.title || `Chapter ${initialChapterNumber}`)
      setText("")
      setHtml(textToHtml(""))
    }
  }

  const loadNotes = async () => {
    setNotesLoading(true)
    try {
      const noteData = await booksApi.getBookNotes(bookId)
      setNotes(noteData)
      setNotesLoaded(true)
    } finally {
      setNotesLoading(false)
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
    setNotes([])
    setNotesLoaded(false)
    setNotesLoading(false)
    booksApi.getCharacters(bookId).then(setCharacters).catch(() => setCharacters([]))
    booksApi.getWriterWorkspace(bookId).then(setWriterWorkspace).catch(() => setWriterWorkspace(null))
    booksApi.getEmotionalArc(bookId).then(setEmotionalArc).catch(() => setEmotionalArc(null))
    intelligenceApi.synopsis(bookId, "minimal").then(setSynopsis).catch(() => setSynopsis(null))
    void loadWorkspaceTree()
  }, [bookId])

  useEffect(() => {
    if (!showRightRail || activeRightPane !== "notes" || notesLoaded || notesLoading) return
    loadNotes().catch(() => {
      setNotes([])
      setNotesLoaded(true)
    })
  }, [activeRightPane, bookId, notesLoaded, notesLoading, showRightRail])

  useEffect(() => {
    if (selectedChapter === null) {
      setDraftChapterNumber(nextChapterNumber)
      setChapterTitle(`Chapter ${nextChapterNumber}`)
      setText("")
      setHtml(textToHtml(""))
      setReview(null)
      setReviewPassages([])
      setVoiceReview(null)
      setVoiceCharacters([])
      setVoiceMatches([])
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
      setDraftChapterNumber(null)
      setChapterTitle(title)
      setText(chapterText)
      setHtml(chapterHtml)
      setBookDrafts((current) => ({
        ...current,
        [selectedChapter]: {
          title,
          text: current[selectedChapter]?.text ?? chapterText,
          html: current[selectedChapter]?.html ?? chapterHtml,
        },
      }))
      setReview(null)
      setReviewPassages([])
      setVoiceReview(null)
      setVoiceCharacters([])
      setVoiceMatches([])
      setStatusMessage(null)
    }).catch(() => {
      setChapterTitle(chapterMeta?.title || `Chapter ${selectedChapter}`)
      setText("")
      setHtml(textToHtml(""))
    })
  }, [bookId, chapterList, nextChapterNumber, selectedChapter])

  useEffect(() => {
    if (loading) return
    const handle = window.setTimeout(() => {
      booksApi.getPreWritingCheck(bookId, activeChapterNumber).then(setPreWritingCheck).catch(() => {})
    }, 180)
    return () => window.clearTimeout(handle)
  }, [activeChapterNumber, bookId, loading])

  useEffect(() => {
    if (!statusMessage) return
    const handle = window.setTimeout(() => setStatusMessage(null), 3200)
    return () => window.clearTimeout(handle)
  }, [statusMessage])

  useEffect(() => {
    if (!showLeftRail || selectedChapter === null) {
      setChapterVersions([])
      return
    }
    booksApi.getChapterVersions(bookId, selectedChapter).then(setChapterVersions).catch(() => setChapterVersions([]))
  }, [bookId, selectedChapter, showLeftRail])

  useEffect(() => {
    if (editorMode !== "book" || !chapterList?.chapters.length) return
    const missingNumbers = chapterList.chapters
      .map((chapter) => chapter.number)
      .filter((number) => !(number in bookDrafts))
    if (!missingNumbers.length) return

    setFullBookLoading(true)
    Promise.all(missingNumbers.map((number) => readerApi.getChapter(bookId, number)))
      .then((chapters) => {
        setBookDrafts((current) => {
          const next = { ...current }
          for (const chapter of chapters) {
            next[chapter.chapter_number] = {
              title: chapter.chapter_title || `Chapter ${chapter.chapter_number}`,
              text: chapter.text_content || "",
              html: chapter.html_content || textToHtml(chapter.text_content || ""),
            }
          }
          return next
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
    if (workspaceTab === "analyze") {
      setShowLeftRail(false)
      setShowRightRail(true)
      setActiveRightPane("insights")
      return
    }
    if (workspaceTab === "characters") {
      setShowLeftRail(false)
      setShowRightRail(true)
      setActiveRightPane("character")
    }
  }, [focusMode, workspaceTab])

  useEffect(() => {
    if (workspaceTab !== "write" || editorMode !== "chapter") {
      setSelectionMenu(null)
      return
    }

    const syncSelectionMenu = () => {
      const selection = window.getSelection()
      const selectedText = selection?.toString().trim() ?? ""
      const editor = document.querySelector<HTMLElement>(`[data-editor-key="chapter-${activeChapterNumber}"]`)
      const anchorNode = selection?.anchorNode

      if (!selection || !selectedText || !editor || !anchorNode || !editor.contains(anchorNode) || selection.rangeCount === 0) {
        setSelectionMenu(null)
        return
      }

      const rect = selection.getRangeAt(0).getBoundingClientRect()
      if (!rect.width && !rect.height) {
        setSelectionMenu(null)
        return
      }

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
  }, [activeChapterNumber, editorMode, workspaceTab])

  useEffect(() => {
    const trimmed = text.trim()
    if (!trimmed) {
      setReadability(null)
      setInlineContinuity(null)
      setReadabilityLoading(false)
      setContinuityLoading(false)
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
    }, 500)
    return () => window.clearTimeout(handle)
  }, [activeChapterNumber, bookId, text])

  const runAutomaticChecks = async (chapterNum: number, content: string) => {
    const [editorial, voice, suggestionResult, threads, synopsisResult, emotionalArcResult] = await Promise.all([
      intelligenceApi.editorialReview(bookId, content, chapterNum),
      intelligenceApi.voiceConsistencyReview(bookId, content, chapterNum),
      intelligenceApi.advisorSuggestions(bookId),
      readerApi.getPlotThreads(bookId, chapterNum),
      intelligenceApi.synopsis(bookId, "minimal").catch(() => null),
      booksApi.getEmotionalArc(bookId).catch(() => null),
    ])
    setReview(editorial.review)
    setReviewPassages(editorial.retrieved_passages)
    setVoiceReview(voice.review)
    setVoiceCharacters(voice.characters_reviewed)
    setVoiceMatches(voice.character_matches ?? [])
    setSuggestions(suggestionResult.suggestions.filter((item) => item.chapter_ref === null || item.chapter_ref <= chapterNum).slice(0, 6))
    setPlotThreads(threads.filter((thread) => thread.status !== "resolved").slice(0, 8))
    if (synopsisResult) setSynopsis(synopsisResult)
    if (emotionalArcResult) setEmotionalArc(emotionalArcResult)
  }

  const saveChapterDraft = async (chapterNumber: number, draft?: { title: string; text: string; html: string }) => {
    const currentDraft = draft ?? bookDrafts[chapterNumber] ?? { title: chapterTitle, text, html }
    if (!currentDraft.text.trim()) return

    const result = await booksApi.importManuscript(bookId, {
      text: currentDraft.text,
      html: currentDraft.html,
      title: currentDraft.title.trim() || undefined,
      chapterNumber,
      replaceExisting: true,
    })
    const importedChapter = result.imported_chapters[0] ?? chapterNumber
    setSelectedChapter(importedChapter)
    clearDraftDirty(chapterNumber)
    clearDraftDirty(importedChapter)
    await loadWorkspaceTree()
    await runAutomaticChecks(importedChapter, currentDraft.text)
    setStatusMessage(`Saved chapter ${importedChapter}. Continuity, synopsis, and thread context refreshed.`)
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
        replaceExisting: replaceExisting || selectedChapter !== null,
      })
      await loadBase()
      const importedChapter = result.imported_chapters[0] ?? activeChapterNumber
      setSelectedChapter(importedChapter)
      clearDraftDirty(importedChapter)
      setBookDrafts((current) => ({
        ...current,
        [importedChapter]: { title: chapterTitle.trim() || `Chapter ${importedChapter}`, text, html },
      }))
      await loadWorkspaceTree()
      await runAutomaticChecks(importedChapter, text)
      setStatusMessage(`Saved chapter ${importedChapter}. Continuity, synopsis, and thread context refreshed.`)
    } catch {
      setStatusMessage("Save failed. Please check the chapter number and try again.")
    } finally {
      setSaving(false)
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

  const exportManuscript = async (format: "pdf" | "docx" | "epub" | "obsidian") => {
    setExporting(format)
    try {
      const preset = writerWorkspace?.publishing.active_preset ?? "standard_manuscript"
      const blob = await booksApi.exportManuscript(bookId, format, preset, includeSceneMetadataOnExport)
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      const extension = format === "obsidian" ? "zip" : format
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

  const saveVoiceIssueAsNote = async (issue: { character_name: string; title: string; description: string; severity?: string; evidence?: string; suggestion?: string }) => {
    const noteBody = `**Voice Issue: ${issue.character_name} - ${issue.title}**\n\n${issue.description}${issue.evidence ? `\n\n**Evidence:** ${issue.evidence}` : ""}${issue.suggestion ? `\n\n**Suggestion:** ${issue.suggestion}` : ""}${issue.severity ? `\n\n**Severity:** ${issue.severity}` : ""}`
    const noteTitle = `Voice: ${issue.character_name} - ${issue.title}`
    await saveWorkspaceVaultNote({
      title: noteTitle,
      body: noteBody,
      folderSegments: activeChapterNumber ? [`Chapter ${activeChapterNumber}`, "Voice"] : ["Voice"],
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

  if (loading) {
    return <div className={`min-h-screen px-6 py-20 ${isDark ? "bg-black text-slate-400" : "bg-stone-50 text-stone-500"}`}>Loading manuscript workspace...</div>
  }

  return (
    <div className={`min-h-screen ${isDark ? "bg-[#080808] text-slate-100" : "bg-[#f3eee6] text-stone-950"}`}>
      {selectionMenu && workspaceTab === "write" && editorMode === "chapter" ? (
        <div
          className="pointer-events-none fixed z-50 hidden -translate-x-1/2 xl:block"
          style={{ top: selectionMenu.top, left: selectionMenu.left }}
        >
          <div className={`pointer-events-auto flex items-center gap-2 rounded-full border px-2 py-2 shadow-[0_18px_50px_-24px_rgba(15,23,42,0.45)] ${isDark ? "border-white/10 bg-[#0f1117]" : "border-stone-200 bg-white"}`}>
            <button
              type="button"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => void tightenSelectedText()}
              disabled={tighteningSelection}
              className="rounded-full bg-[linear-gradient(135deg,#0f766e,#115e59)] px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
            >
              {tighteningSelection ? "Tightening..." : "Tighten"}
            </button>
            <button
              type="button"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => openRightPane("context")}
              className={`rounded-full px-3 py-1.5 text-xs font-medium ${isDark ? "bg-white/8 text-slate-200" : "bg-stone-100 text-stone-700"}`}
            >
              Check consistency
            </button>
            <Link
              href={`/${bookId}/advisor`}
              className={`rounded-full px-3 py-1.5 text-xs font-medium ${isDark ? "bg-white/8 text-slate-200" : "bg-stone-100 text-stone-700"}`}
            >
              Ask advisor
            </Link>
          </div>
        </div>
      ) : null}
      <div className="mx-auto max-w-[1600px] px-4 pb-12 pt-5 sm:px-6 lg:px-8">
        <div className={`rounded-[2rem] border px-5 py-5 shadow-[0_22px_70px_-55px_rgba(15,23,42,0.2)] ${isDark ? "border-white/10 bg-white/[0.03]" : "border-white/80 bg-white/92"}`}>
          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div className="min-w-0">
                <p className={`text-base ${isDark ? "text-slate-300" : "text-stone-600"}`}>{book?.title}</p>
                <h1 className={`mt-2 font-serif text-4xl leading-tight ${isDark ? "text-white" : "text-stone-950"}`}>{activeChapterHeading}</h1>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <div className="flex items-center gap-2">
                  <span className="inline-flex h-2.5 w-2.5 rounded-full bg-emerald-400" />
                  <div>
                    <p className={`text-sm font-semibold ${isDark ? "text-emerald-300" : "text-emerald-700"}`}>{saving ? "Saving..." : dirtyDrafts.includes(activeChapterNumber) ? "Unsaved" : "Saved"}</p>
                    <p className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{statusMessage ? statusMessage : "Just now"}</p>
                  </div>
                </div>
                <div className="relative">
                  <button
                    type="button"
                    onClick={() => setShowExportMenu((value) => !value)}
                    className={`rounded-full border px-4 py-2 text-sm font-medium ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}
                  >
                    Export
                  </button>
                  {showExportMenu ? (
                    <div className={`absolute right-0 top-full z-20 mt-2 w-64 rounded-2xl border p-1.5 shadow-[0_18px_50px_-24px_rgba(15,23,42,0.4)] ${isDark ? "border-white/10 bg-[#0f1117]" : "border-stone-200 bg-white"}`}>
                      <div className="px-3 py-2">
                        <p className={`text-[11px] font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Publishing preset</p>
                        <select
                          value={writerWorkspace?.publishing.active_preset ?? "standard_manuscript"}
                          onChange={(event) => {
                            const nextPreset = event.target.value as WriterWorkspace["publishing"]["active_preset"]
                            void saveWorkspace({
                              publishing: {
                                ...(writerWorkspace?.publishing ?? { trim_size: "6x9", include_title_page: true, mirror_margins: true }),
                                active_preset: nextPreset,
                              },
                            }, { silent: true })
                          }}
                          className={`mt-2 w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
                        >
                          <option value="standard_manuscript">Standard manuscript</option>
                          <option value="trade_paperback">Trade paperback</option>
                          <option value="kdp_paperback">Amazon KDP paperback</option>
                        </select>
                      </div>
                      <button onClick={() => { setShowExportMenu(false); printManuscript() }} className={`block w-full rounded-xl px-3 py-2 text-left text-sm ${isDark ? "text-slate-200 hover:bg-white/10" : "text-stone-700 hover:bg-stone-100"}`}>Print</button>
                      <button onClick={() => { setCompileFormat("docx"); setShowExportMenu(false); setShowCompileDialog(true) }} disabled={!!exporting} className={`block w-full rounded-xl px-3 py-2 text-left text-sm disabled:opacity-40 ${isDark ? "text-slate-200 hover:bg-white/10" : "text-stone-700 hover:bg-stone-100"}`}>{exporting === "docx" ? "Exporting Word..." : "Compile Word / DOCX"}</button>
                      <button onClick={() => { setCompileFormat("pdf"); setShowExportMenu(false); setShowCompileDialog(true) }} disabled={!!exporting} className={`block w-full rounded-xl px-3 py-2 text-left text-sm disabled:opacity-40 ${isDark ? "text-slate-200 hover:bg-white/10" : "text-stone-700 hover:bg-stone-100"}`}>{exporting === "pdf" ? "Exporting PDF..." : "Compile submission PDF"}</button>
                      <button onClick={() => { setCompileFormat("epub"); setShowExportMenu(false); setShowCompileDialog(true) }} disabled={!!exporting} className={`block w-full rounded-xl px-3 py-2 text-left text-sm disabled:opacity-40 ${isDark ? "text-slate-200 hover:bg-white/10" : "text-stone-700 hover:bg-stone-100"}`}>{exporting === "epub" ? "Exporting EPUB..." : "Compile EPUB"}</button>
                      <button onClick={() => { setCompileFormat("obsidian"); setShowExportMenu(false); setShowCompileDialog(true) }} disabled={!!exporting} className={`block w-full rounded-xl px-3 py-2 text-left text-sm disabled:opacity-40 ${isDark ? "text-slate-200 hover:bg-white/10" : "text-stone-700 hover:bg-stone-100"}`}>{exporting === "obsidian" ? "Exporting vault..." : "Export Obsidian vault"}</button>
                    </div>
                  ) : null}
                </div>
                <button onClick={() => setFocusMode((value) => !value)} className={`rounded-full border px-4 py-2 text-sm font-medium ${focusMode ? isDark ? "border-emerald-300/40 bg-emerald-400/15 text-white" : "border-emerald-300 bg-emerald-50 text-stone-900" : isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                  {focusMode ? "Exit focus" : "Focus mode"}
                </button>
                <button
                  type="button"
                  onClick={() => setShowEditorSettings((value) => !value)}
                  className={`rounded-full border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}
                  aria-label="Editor settings"
                >
                  •••
                </button>
              </div>
            </div>
            <div className={`flex flex-wrap items-center gap-5 border-t pt-4 ${isDark ? "border-white/10" : "border-stone-200"}`}>
              {(["write", "plan", "analyze", "characters"] as const).map((tab) => (
                <button
                  key={tab}
                  type="button"
                  onClick={() => setWorkspaceTab(tab)}
                  className={`border-b-2 pb-2 text-sm font-medium transition ${workspaceTab === tab ? isDark ? "border-sky-400 text-white" : "border-sky-500 text-stone-950" : isDark ? "border-transparent text-slate-400 hover:text-slate-200" : "border-transparent text-stone-500 hover:text-stone-800"}`}
                >
                  {tab === "write" ? "Write" : tab === "plan" ? "Plan" : tab === "analyze" ? "Analyze" : "Characters"}
                </button>
              ))}
              <Link href={`/${bookId}/world-gap`} className={`border-b-2 border-transparent pb-2 text-sm font-medium transition ${isDark ? "text-slate-400 hover:text-slate-200" : "text-stone-500 hover:text-stone-800"}`}>Worldbuilding</Link>
              <Link href={`/${bookId}/export`} className={`border-b-2 border-transparent pb-2 text-sm font-medium transition ${isDark ? "text-slate-400 hover:text-slate-200" : "text-stone-500 hover:text-stone-800"}`}>Export</Link>
              <div className={`ml-auto inline-flex rounded-full p-1 ${isDark ? "border border-white/10 bg-black/30" : "border border-stone-200 bg-stone-100/80"}`}>
                {(["chapter", "book"] as const).map((mode) => (
                  <button
                    key={`header-mode-${mode}`}
                    type="button"
                    onClick={() => setEditorMode(mode)}
                    className={`rounded-full px-4 py-2 text-sm font-medium transition ${editorMode === mode ? isDark ? "bg-white text-slate-950" : "bg-stone-900 text-white" : isDark ? "text-slate-300 hover:bg-white/10" : "text-stone-600 hover:bg-white"}`}
                  >
                    {mode === "chapter" ? "Chapter" : "Full book"}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {workspaceTab === "plan" ? (
        <div className="mt-6 grid gap-5 xl:grid-cols-[1.2fr_1fr]">
          <section className={`rounded-[1.7rem] border p-5 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white/90"}`}>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-emerald-300" : "text-emerald-700"}`}>Writer dashboard</p>
                <h2 className={`mt-2 text-2xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>Goals, templates, and live readability</h2>
              </div>
              <button
                type="button"
                onClick={() => void tightenSelectedText()}
                disabled={tighteningSelection}
                className="rounded-full bg-[linear-gradient(135deg,#0f766e,#115e59)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                {tighteningSelection ? "Tightening..." : "Tighten selected text"}
              </button>
            </div>
            <p className={`mt-3 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>
              {editorMode === "chapter"
                ? "Highlight a passage inside the active chapter editor to tighten only that selection."
                : "Switch to chapter view to tighten a selected passage without touching the rest of the manuscript."}
            </p>
            <div className="mt-5 grid gap-4 md:grid-cols-3">
              <MetricCard
                label="Chapter goal"
                value={writerWorkspace?.word_count_goals.chapter_target ? `${chapterWordCount.toLocaleString()} / ${writerWorkspace.word_count_goals.chapter_target.toLocaleString()}` : `${chapterWordCount.toLocaleString()} words`}
                note={chapterGoalProgress !== null ? `${chapterGoalProgress}% of target` : "Set a chapter target below"}
                isDark={isDark}
              />
              <MetricCard
                label="Book goal"
                value={writerWorkspace?.word_count_goals.book_target ? `${fullBookWordCount.toLocaleString()} / ${writerWorkspace.word_count_goals.book_target.toLocaleString()}` : `${fullBookWordCount.toLocaleString()} words`}
                note={bookGoalProgress !== null ? `${bookGoalProgress}% of target` : "Set a manuscript target below"}
                isDark={isDark}
              />
              <MetricCard
                label="Readability"
                value={readabilityLoading ? "Scoring..." : readability ? `${readability.label} (${Math.round(readability.reading_ease)})` : "Waiting..."}
                note={readability ? `${readability.average_sentence_length} words/sentence · grade ${readability.grade_level}` : "Live score updates while you write"}
                isDark={isDark}
              />
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <ProgressStrip
                label="Chapter progress"
                progress={chapterGoalProgress}
                fallback={`${chapterApproxPages} page${chapterApproxPages === 1 ? "" : "s"} in the current chapter draft`}
                isDark={isDark}
              />
              <ProgressStrip
                label="Book progress"
                progress={bookGoalProgress}
                fallback={`${fullBookApproxPages.toLocaleString()} estimated manuscript pages`}
                isDark={isDark}
              />
            </div>
            <div className="mt-5 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
              <div className={`rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/80"}`}>
                <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Word count goals</p>
                <div className="mt-3 grid gap-3 md:grid-cols-3">
                  <input
                    type="number"
                    value={writerWorkspace?.word_count_goals.chapter_target ?? ""}
                    onChange={(event) => setWriterWorkspace((current) => current ? { ...current, word_count_goals: { ...current.word_count_goals, chapter_target: Number(event.target.value) || null } } : current)}
                    placeholder="Chapter"
                    className={`rounded-[0.95rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
                  />
                  <input
                    type="number"
                    value={writerWorkspace?.word_count_goals.book_target ?? ""}
                    onChange={(event) => setWriterWorkspace((current) => current ? { ...current, word_count_goals: { ...current.word_count_goals, book_target: Number(event.target.value) || null } } : current)}
                    placeholder="Book"
                    className={`rounded-[0.95rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
                  />
                  <input
                    type="number"
                    value={writerWorkspace?.word_count_goals.session_target ?? ""}
                    onChange={(event) => setWriterWorkspace((current) => current ? { ...current, word_count_goals: { ...current.word_count_goals, session_target: Number(event.target.value) || null } } : current)}
                    placeholder="Session"
                    className={`rounded-[0.95rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
                  />
                </div>
                <button
                  type="button"
                  onClick={() => writerWorkspace && void saveWorkspace({ word_count_goals: writerWorkspace.word_count_goals })}
                  disabled={!writerWorkspace || workspaceSaving}
                  className="mt-3 rounded-full bg-[linear-gradient(135deg,#2563eb,#1d4ed8)] px-4 py-2 text-xs font-semibold text-white disabled:opacity-50"
                >
                  {workspaceSaving ? "Saving..." : "Save goals"}
                </button>
              </div>
              <div className={`rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/80"}`}>
                <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Templates</p>
                <div className="mt-3 space-y-3">
                  {(writerWorkspace?.templates ?? []).map((template) => (
                    <article key={template.id} className={`rounded-[1rem] border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-white bg-white"}`}>
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{template.title}</p>
                          <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{template.kind} template</p>
                        </div>
                        <button onClick={() => applyTemplateToChapter(template)} className={`rounded-full px-3 py-1.5 text-xs font-semibold ${isDark ? "bg-emerald-500/10 text-emerald-200" : "bg-emerald-50 text-emerald-700"}`}>Insert</button>
                      </div>
                      <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-700"}`}>{template.description}</p>
                    </article>
                  ))}
                  {chapterVersions.length === 0 ? <p className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>No snapshots saved for this chapter yet.</p> : null}
                </div>
              </div>
            </div>
          </section>

          <section className={`rounded-[1.7rem] border p-5 ${isDark ? "border-white/10 bg-white/[0.04]" : "border-stone-200 bg-white/90"}`}>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-amber-300" : "text-amber-700"}`}>Planning board</p>
                <h2 className={`mt-2 text-2xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>Corkboard and emotional arc</h2>
              </div>
            </div>
            <div className="mt-4 flex gap-2">
              <input
                value={newCorkboardTitle}
                onChange={(event) => setNewCorkboardTitle(event.target.value)}
                placeholder="New corkboard card"
                className={`flex-1 rounded-[1rem] border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/30 text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-stone-50 text-stone-900 placeholder:text-stone-400"}`}
              />
              <button onClick={() => void addCorkboardCard()} disabled={!writerWorkspace || !newCorkboardTitle.trim()} className="rounded-[1rem] bg-[linear-gradient(135deg,#d97706,#b45309)] px-4 py-3 text-sm font-semibold text-white disabled:opacity-50">Add</button>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              {["ideas", "drafting", "revised"].map((lane) => (
                <div key={lane} className={`rounded-[1.1rem] border p-3 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/80"}`}>
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>{lane}</p>
                  <div className="mt-3 space-y-2">
                    {(writerWorkspace?.corkboard_cards ?? []).filter((card) => card.lane === lane).map((card) => (
                      <article key={card.id} className={`rounded-[0.95rem] border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-white bg-white"}`}>
                        <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{card.title}</p>
                        {card.chapter_number ? <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Chapter {card.chapter_number}</p> : null}
                        <div className="mt-3 flex gap-2">
                          {lane !== "ideas" ? <button onClick={() => void updateCardLane(card.id, "ideas")} className={`text-xs ${isDark ? "text-slate-300" : "text-stone-600"}`}>Ideas</button> : null}
                          {lane !== "drafting" ? <button onClick={() => void updateCardLane(card.id, "drafting")} className={`text-xs ${isDark ? "text-slate-300" : "text-stone-600"}`}>Drafting</button> : null}
                          {lane !== "revised" ? <button onClick={() => void updateCardLane(card.id, "revised")} className={`text-xs ${isDark ? "text-slate-300" : "text-stone-600"}`}>Revised</button> : null}
                        </div>
                      </article>
                    ))}
                    {(writerWorkspace?.corkboard_cards ?? []).filter((card) => card.lane === lane).length === 0 ? <p className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>No cards yet.</p> : null}
                  </div>
                </div>
              ))}
            </div>
            <div className={`mt-5 rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/80"}`}>
              <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Emotional arc tracking</p>
              {emotionalArc?.characters.length ? (
                <div className="mt-3 space-y-3">
                  {emotionalArc.characters.slice(0, 4).map((character) => (
                    <article key={character.character_id} className={`rounded-[1rem] border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-white bg-white"}`}>
                      <div className="flex items-center justify-between gap-3">
                        <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{character.character_name}</p>
                        <span className={`text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>trajectory {character.trajectory_score > 0 ? "+" : ""}{character.trajectory_score}</span>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-2">
                        {character.points.slice(-4).map((point) => (
                          <span key={`${character.character_id}-${point.chapter_number}-${point.label}`} className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${point.sentiment >= 0 ? isDark ? "bg-emerald-500/10 text-emerald-200" : "bg-emerald-50 text-emerald-700" : isDark ? "bg-rose-500/10 text-rose-200" : "bg-rose-50 text-rose-700"}`}>
                            Ch. {point.chapter_number}: {point.label}
                          </span>
                        ))}
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <p className={`mt-3 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Emotional arc tracking will populate as character growth events become available.</p>
              )}
            </div>
          </section>
        </div>
        ) : null}

        {(workspaceTab === "write" || workspaceTab === "analyze" || workspaceTab === "characters") ? (
        <div className={`mt-8 grid gap-5 ${desktopLayoutClass}`}>
          {leftRailVisible ? (
          <aside className={`rounded-[1.8rem] border p-4 ${isDark ? "border-white/10 bg-[#0d1117]" : "border-stone-200 bg-white/90"}`}>
            <div className="flex items-center justify-between">
              <div>
                <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Workspace</p>
                <p className={`mt-1 text-[11px] ${isDark ? "text-slate-500" : "text-stone-500"}`}>{book?.title || "Current project"}</p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => {
                    setSelectedChapter(null)
                    setDraftChapterNumber(nextChapterNumber)
                    setReplaceExisting(false)
                    setChapterTitle(`Chapter ${nextChapterNumber}`)
                    setText("")
                    setHtml(textToHtml(""))
                    setReview(null)
                    setReviewPassages([])
                    setVoiceReview(null)
                    setVoiceCharacters([])
                    setVoiceMatches([])
                  }}
                  className={`rounded-full px-3 py-1.5 text-xs ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}
                >
                  New
                </button>
                <button
                  onClick={() => openSceneEditor(null)}
                  className={`rounded-full px-3 py-1.5 text-xs ${isDark ? "bg-emerald-500/15 text-emerald-200" : "bg-emerald-50 text-emerald-700"}`}
                >
                  Scene
                </button>
              </div>
            </div>
            <div className={`mt-4 rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-white"}`}>
              <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Manuscript</p>
              <h2 className={`mt-3 text-2xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{book?.title}</h2>
              <p className={`mt-2 text-sm ${isDark ? "text-sky-300" : "text-sky-700"}`}>Story manuscript</p>
              <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{fullBookWordCount.toLocaleString()} words across the working draft</p>
            </div>
            <input
              type="text"
              value={chapterSearch}
              onChange={(event) => setChapterSearch(event.target.value)}
              placeholder="Search chapters"
              className={`mt-4 w-full rounded-[0.95rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/30 text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"}`}
            />
            <div className="mt-4">
              <p className={`text-[11px] font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>chapters</p>
              <div className="mt-2 space-y-2">
              {filteredChapterItems.map((chapter) => {
                const active = selectedChapter === chapter.number || (selectedChapter === null && draftChapterNumber === chapter.number)
                const rowWordCount = countWords(bookDrafts[chapter.number]?.text ?? "")
                return (
                  <button
                    key={chapter.number}
                    onClick={() => {
                      setSelectedChapter(chapter.number)
                      setDraftChapterNumber(null)
                      setReplaceExisting(true)
                    }}
                    className={`w-full rounded-[1rem] border px-3 py-3 text-left text-sm transition ${active ? isDark ? "border-sky-400/40 bg-sky-400/15 text-white" : "border-sky-300 bg-sky-50 text-stone-900" : isDark ? "border-white/10 bg-white/[0.03] text-slate-300 hover:bg-white/10" : "border-stone-200 bg-stone-50 text-stone-700 hover:bg-white"}`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-semibold">Chapter {chapter.number}</p>
                      <span className={`h-2.5 w-2.5 rounded-full ${active ? "bg-sky-400" : chapter.processed ? "bg-emerald-400" : isDark ? "bg-slate-600" : "bg-stone-300"}`} />
                    </div>
                    <p className="mt-1 line-clamp-1 text-xs opacity-75">{chapter.title || `Chapter ${chapter.number}`}</p>
                    <p className={`mt-2 text-[11px] ${isDark ? "text-slate-500" : "text-stone-500"}`}>{rowWordCount > 0 ? `${rowWordCount.toLocaleString()} words` : "Draft ready"} · {dirtyDrafts.includes(chapter.number) ? "needs review" : "saved"}</p>
                  </button>
                )
              })}
              </div>
            </div>
            <div className="mt-4">
              <div className="flex items-center justify-between gap-3">
                <p className={`text-[11px] font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>scenes/</p>
                <Link
                  href={`/${bookId}/scenes`}
                  className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${isDark ? "bg-white/10 text-slate-200" : "bg-white text-stone-700"}`}
                >
                  Open workspace
                </Link>
                <label className={`flex items-center gap-2 text-[11px] ${isDark ? "text-slate-400" : "text-stone-500"}`}>
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
                  return (
                    <div key={group.id} className={`rounded-[1rem] border p-2 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-white"}`}>
                      <button
                        onClick={() => setCollapsedSceneGroups((current) => ({ ...current, [group.id]: !collapsed }))}
                        className="flex w-full items-center justify-between gap-3 rounded-[0.85rem] px-2 py-2 text-left"
                      >
                        <span className={`text-xs font-semibold uppercase tracking-[0.12em] ${isDark ? "text-slate-300" : "text-stone-700"}`}>{group.label}</span>
                        <span className={`text-[11px] ${isDark ? "text-slate-500" : "text-stone-500"}`}>{collapsed ? "+" : "−"}</span>
                      </button>
                      {!collapsed ? (
                        <div className="mt-1 space-y-2">
                          {group.scenes.map((scene) => (
                            <div key={scene.id} className={`rounded-[0.9rem] border px-3 py-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
                              <div className="flex items-start justify-between gap-3">
                                <div className="min-w-0 flex-1">
                                  <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{scene.title}</p>
                                  <p className={`mt-1 text-[11px] ${isDark ? "text-slate-500" : "text-stone-500"}`}>{scene.path}</p>
                                  {scene.description ? <p className={`mt-2 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>{scene.description}</p> : null}
                                </div>
                                <button onClick={() => void insertSceneIntoDraft(scene)} className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${isDark ? "bg-emerald-500/15 text-emerald-200" : "bg-emerald-50 text-emerald-700"}`}>Insert</button>
                              </div>
                              <div className="mt-3 flex flex-wrap gap-2">
                                <button onClick={() => openSceneEditor(scene)} className={`rounded-full px-2.5 py-1 text-[11px] ${isDark ? "bg-white/10 text-slate-200" : "bg-white text-stone-700"}`}>Edit</button>
                                <button onClick={() => void removeScene(scene)} className={`rounded-full px-2.5 py-1 text-[11px] ${isDark ? "bg-rose-500/10 text-rose-200" : "bg-rose-50 text-rose-700"}`}>Delete</button>
                              </div>
                            </div>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  )
                })}
                {filteredSceneGroups.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>No scenes match this search yet.</p> : null}
              </div>
            </div>
            <div className="mt-4 hidden">
              <p className={`text-[11px] font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>notes/</p>
              <div className={`mt-2 rounded-[1rem] border p-3 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-white"}`}>
                <div className="space-y-2">
                  {filteredNotePaths.slice(0, 12).map((path) => (
                    <p key={path} className={`text-xs ${isDark ? "text-slate-300" : "text-stone-700"}`}>{path}</p>
                  ))}
                  {filteredNotePaths.length === 0 ? <p className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>No note files match this search.</p> : null}
                </div>
              </div>
            </div>
            <div className={`mt-4 rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-white"}`}>
              <div className="flex items-center justify-between gap-3">
                <p className={`text-sm font-medium ${isDark ? "text-slate-300" : "text-stone-700"}`}>Manuscript progress</p>
                <span className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{bookGoalProgress ?? 0}%</span>
              </div>
              <div className={`mt-3 h-2 overflow-hidden rounded-full ${isDark ? "bg-white/10" : "bg-stone-100"}`}>
                <div className="h-full rounded-full bg-[linear-gradient(135deg,#0ea5e9,#2563eb)]" style={{ width: `${Math.max(12, bookGoalProgress ?? 18)}%` }} />
              </div>
              <p className={`mt-3 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>
                {fullBookWordCount.toLocaleString()} / {(writerWorkspace?.word_count_goals.book_target ?? fullBookWordCount).toLocaleString()} words
              </p>
            </div>
            {selectedChapter !== null ? (
              <div className="hidden">
                <div className="flex items-center justify-between gap-3">
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Version history</p>
                  <button onClick={() => void createSnapshot()} className={`rounded-full px-3 py-1.5 text-[11px] font-semibold ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>Save snapshot</button>
                </div>
                <div className="mt-2 space-y-2">
                  {chapterVersions.map((version) => (
                    <div key={version.id} className={`rounded-[0.85rem] px-3 py-3 ${isDark ? "bg-white/[0.03]" : "bg-stone-50"}`}>
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className={`text-sm font-medium ${isDark ? "text-white" : "text-stone-900"}`}>{version.note || "Previous draft"}</p>
                          <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                        {new Date(version.created_at).toLocaleString()} {version.word_count ? `· ${version.word_count} words` : ""}
                      </p>
                          <p className={`mt-1 text-[11px] uppercase tracking-[0.12em] ${isDark ? "text-slate-500" : "text-stone-500"}`}>{version.snapshot_kind || "manual"}</p>
                        </div>
                        <button
                          onClick={() => void restoreSnapshot(version.id)}
                          disabled={restoringVersionId === version.id}
                          className={`rounded-full px-3 py-1.5 text-[11px] font-semibold ${isDark ? "bg-amber-500/10 text-amber-200 disabled:opacity-50" : "bg-amber-50 text-amber-700 disabled:opacity-50"}`}
                        >
                          {restoringVersionId === version.id ? "Restoring..." : "Restore"}
                        </button>
                        <button
                          onClick={() => void previewSnapshot(version.id)}
                          className={`rounded-full px-3 py-1.5 text-[11px] font-semibold ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}
                        >
                          Preview
                        </button>
                      </div>
                      {chapterVersionDetail?.id === version.id ? (
                        <div className={`mt-3 max-h-44 overflow-y-auto rounded-[0.8rem] border px-3 py-2 text-xs leading-5 ${isDark ? "border-white/10 bg-black/30 text-slate-300" : "border-stone-200 bg-white text-stone-700"}`}>
                          {chapterVersionDetail.text || "No text stored in this snapshot."}
                        </div>
                      ) : null}
                    </div>
                  ))}
                  {chapterVersions.length === 0 ? <p className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>No snapshots saved for this chapter yet.</p> : null}
                </div>
              </div>
            ) : null}
          </aside>
          ) : null}

          <section ref={manuscriptSectionRef} className={`rounded-[1.8rem] border p-5 ${!leftRailVisible && !rightRailVisible ? "xl:mx-auto xl:max-w-[980px]" : ""} ${isDark ? "border-white/10 bg-black/80" : "border-stone-200 bg-[#faf8f4]"}`}>
            {preWritingCheck && workspaceTab !== "write" ? (
              <div className={`mb-5 rounded-[1.3rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-emerald-300" : "text-emerald-700"}`}>Before you start Chapter {preWritingCheck.upcoming_chapter}</p>
                    <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>Here’s what’s happening right now in the manuscript.</p>
                  </div>
                  <div className="flex gap-2">
                    <Link href={`/${bookId}/plot-threads`} className={`rounded-full px-3 py-1.5 text-xs font-semibold ${isDark ? "bg-white/10 text-slate-200" : "bg-white text-stone-700"}`}>Threads</Link>
                    <Link href={`/${bookId}/timeline`} className={`rounded-full px-3 py-1.5 text-xs font-semibold ${isDark ? "bg-white/10 text-slate-200" : "bg-white text-stone-700"}`}>Major events</Link>
                  </div>
                </div>
                <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
                  <InfoList title="Active characters" isDark={isDark} items={preWritingCheck.active_characters.slice(0, 4).map((character) => character.name)} emptyLabel="No active characters loaded." />
                  <InfoList title="Unresolved threads" isDark={isDark} items={preWritingCheck.unresolved_threads.slice(0, 3).map((thread) => thread.title)} emptyLabel="No unresolved threads loaded." />
                  <InfoList title="Last events" isDark={isDark} items={preWritingCheck.recent_events.slice(0, 3).map((event) => `Ch. ${event.chapter_number}: ${event.detail}`)} emptyLabel="No recent events loaded." />
                  <InfoList title="Ongoing alerts" isDark={isDark} items={preWritingCheck.alerts.slice(0, 3).map((alert) => alert.title)} emptyLabel="No active warnings right now." />
                </div>
              </div>
            ) : null}

            <div className="hidden">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className={`inline-flex rounded-full p-1 ${isDark ? "border border-white/10 bg-black/30" : "border border-stone-200 bg-stone-50"}`}>
                  {(["chapter", "book"] as const).map((mode) => (
                    <button
                      key={mode}
                      onClick={() => setEditorMode(mode)}
                      className={`rounded-full px-4 py-2 text-sm font-medium transition ${editorMode === mode ? isDark ? "bg-white text-slate-950" : "bg-stone-900 text-white" : isDark ? "text-slate-300 hover:bg-white/10" : "text-stone-600 hover:bg-stone-100"}`}
                    >
                      {mode === "chapter" ? "Chapter" : "Full book"}
                    </button>
                  ))}
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <label className={`text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                    Font
                    <select value={fontFamily} onChange={(event) => setFontFamily(event.target.value as "times" | "georgia" | "sans")} className={`ml-2 rounded-lg border px-2 py-1 text-sm ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}>
                      <option value="times">Times</option>
                      <option value="georgia">Georgia</option>
                      <option value="sans">Sans</option>
                    </select>
                  </label>
                  <label className={`text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                    Font size
                    <select value={fontSize} onChange={(event) => { setFontSize(Number(event.target.value)); setFontSizeLocked(true) }} className={`ml-2 rounded-lg border px-2 py-1 text-sm ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}>
                      {[11, 12, 13, 14, 15].map((size) => <option key={size} value={size}>{size}pt</option>)}
                    </select>
                  </label>
                  <label className={`text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                    Line height
                    <select value={lineHeight} onChange={(event) => setLineHeight(Number(event.target.value))} className={`ml-2 rounded-lg border px-2 py-1 text-sm ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}>
                      {[1.6, 1.8, 2].map((value) => <option key={value} value={value}>{value}</option>)}
                    </select>
                  </label>
                  <button onClick={() => setFirstLineIndent((value) => !value)} className={`rounded-full px-3 py-1.5 text-xs font-medium ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>
                    {firstLineIndent ? "Indent on" : "Indent off"}
                  </button>
                  <button onClick={() => setShowPageGuides((value) => !value)} className={`rounded-full px-3 py-1.5 text-xs font-medium ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>
                    {showPageGuides ? "Page guides on" : "Page guides off"}
                  </button>
                </div>
              </div>
              <div className={`mt-3 flex flex-wrap items-center gap-4 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                <span>{editorMode === "chapter" ? `${chapterWordCount.toLocaleString()} words` : `${fullBookWordCount.toLocaleString()} words`}</span>
                <span>{editorMode === "chapter" ? `~${chapterApproxPages} on-screen pages` : `~${fullBookApproxPages} on-screen pages`}</span>
                <span>{editorMode === "chapter" ? "Single document view" : "Stacked document view"}</span>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto_auto]">
                <input
                  type="text"
                  value={replaceQuery}
                  onChange={(event) => setReplaceQuery(event.target.value)}
                  placeholder="Find text"
                  className={`rounded-[0.9rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"}`}
                />
                <input
                  type="text"
                  value={replaceValue}
                  onChange={(event) => setReplaceValue(event.target.value)}
                  placeholder="Replace with"
                  className={`rounded-[0.9rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"}`}
                />
                <button onClick={replaceInCurrentChapter} disabled={!replaceQuery} className={`rounded-[0.9rem] px-4 py-2 text-sm font-medium ${isDark ? "bg-white/10 text-slate-200 disabled:opacity-40" : "bg-stone-100 text-stone-700 disabled:opacity-40"}`}>
                  Replace one
                </button>
                <button onClick={replaceEverywhere} disabled={!replaceQuery} className={`rounded-[0.9rem] px-4 py-2 text-sm font-medium ${isDark ? "bg-white/10 text-slate-200 disabled:opacity-40" : "bg-stone-100 text-stone-700 disabled:opacity-40"}`}>
                  {editorMode === "chapter" ? "Replace all" : "Replace across book"}
                </button>
              </div>
            </div>

            <div className="hidden">
              <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Find and jump</p>
              <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Use continuity retrieval like a manuscript-level Ctrl+F and jump straight into the full-book editor.</p>
              <input
                ref={searchInputRef}
                type="text"
                value={recallQuery}
                onChange={(event) => setRecallQuery(event.target.value)}
                placeholder="Type character name, scene detail, clue, or thread"
                className={`mt-3 w-full rounded-[0.9rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"}`}
              />
              {recallResults.length > 0 ? (
                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <button onClick={() => jumpToSearchResult((activeFindIndex - 1 + recallResults.length) % recallResults.length)} className={`rounded-full px-3 py-1.5 text-xs font-medium ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>Previous</button>
                  <button onClick={() => jumpToSearchResult((activeFindIndex + 1) % recallResults.length)} className={`rounded-full px-3 py-1.5 text-xs font-medium ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>Next</button>
                  <span className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{activeFindIndex + 1} of {recallResults.length}</span>
                </div>
              ) : null}
              <div className="mt-3 grid gap-3 lg:grid-cols-2">
                <div className={`rounded-[1rem] border p-3 ${isDark ? "border-white/10 bg-black/40" : "border-stone-200 bg-white"}`}>
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Instant character info</p>
                  {recallCharacter ? (
                    <div className="mt-2 space-y-2">
                      <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{recallCharacter.name}</p>
                      <p className={`text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>First seen in chapter {recallCharacter.first_chapter}{recallCharacter.last_seen_chapter ? ` · last seen in chapter ${recallCharacter.last_seen_chapter}` : ""}</p>
                      {recallCharacter.arc_summary ? <p className={`text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{recallCharacter.arc_summary}</p> : null}
                    </div>
                  ) : (
                    <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Type a known character name to get an instant reminder.</p>
                  )}
                </div>
                <div className={`rounded-[1rem] border p-3 ${isDark ? "border-white/10 bg-black/40" : "border-stone-200 bg-white"}`}>
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Quick search hits</p>
                  <div className="mt-2 space-y-2">
                    {recallLoading ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Searching...</p> : null}
                    {!recallLoading && recallResults.map((result, index) => (
                      <button
                        key={`${result.chapter_num}-${index}`}
                        onClick={() => jumpToChapter(result.chapter_num)}
                        className={`block w-full rounded-[0.85rem] p-2 text-left ${activeFindIndex === index ? isDark ? "bg-emerald-500/15" : "bg-emerald-50" : isDark ? "bg-white/[0.03] hover:bg-white/[0.08]" : "bg-stone-50 hover:bg-stone-100"}`}
                      >
                        <p className={`text-xs font-semibold ${isDark ? "text-emerald-300" : "text-emerald-700"}`}>Chapter {result.chapter_num}{result.chapter_title ? ` - ${result.chapter_title}` : ""}</p>
                        <p className={`mt-1 text-xs ${isDark ? "text-slate-300" : "text-stone-600"}`}>{result.summary}</p>
                      </button>
                    ))}
                    {!recallLoading && recallQuery.trim().length >= 2 && recallResults.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No matches yet.</p> : null}
                  </div>
                </div>
              </div>
            </div>

            {workspaceTab !== "write" ? (
            <div className={`mb-8 rounded-[1.4rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-white/90"}`}>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className={`inline-flex rounded-full p-1 ${isDark ? "border border-white/10 bg-black/40 shadow-inner" : "border border-stone-200 bg-stone-100 shadow-inner"}`}>
                  {(["chapter", "book"] as const).map((mode) => (
                    <button
                      key={mode}
                      onClick={() => setEditorMode(mode)}
                      className={`rounded-full px-5 py-2 text-sm font-medium transition ${editorMode === mode ? isDark ? "bg-white text-slate-950 shadow-sm" : "bg-stone-900 text-white shadow-sm" : isDark ? "text-slate-300 hover:bg-white/10" : "text-stone-600 hover:bg-white"}`}
                    >
                      {mode === "chapter" ? "Chapter" : "Full book"}
                    </button>
                  ))}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <button onClick={() => setShowPageSetup((value) => !value)} className={`rounded-full px-3 py-1.5 text-xs font-medium ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>
                    {showPageSetup ? "Hide page setup" : "Page setup"}
                  </button>
                  <button onClick={() => setShowSearchTools((value) => !value)} className={`rounded-full px-3 py-1.5 text-xs font-medium ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>
                    {showSearchTools ? "Hide search tools" : "Find and jump"}
                  </button>
                  <button onClick={() => setShowLeftRail((value) => !value)} className={`rounded-full px-3 py-1.5 text-xs font-medium ${leftRailVisible ? isDark ? "bg-indigo-400/15 text-white" : "bg-violet-100 text-stone-900" : isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>
                    {leftRailVisible ? "Hide chapters" : "Show chapters"}
                  </button>
                </div>
              </div>
              <div className={`mt-3 flex flex-wrap items-center gap-4 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                <span>{editorMode === "chapter" ? `${chapterWordCount.toLocaleString()} words` : `${fullBookWordCount.toLocaleString()} words`}</span>
                <span>{editorMode === "chapter" ? `~${chapterApproxPages} pages` : `~${fullBookApproxPages} pages`}</span>
                <span>{editorMode === "chapter" ? "Single document" : "Full manuscript"}</span>
              </div>
              {showPageSetup ? (
                <div className="mt-4 grid gap-3 md:grid-cols-[auto_auto_auto_1fr]">
                  <label className={`text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                    Font
                    <select value={fontFamily} onChange={(event) => setFontFamily(event.target.value as "times" | "georgia" | "sans")} className={`ml-2 rounded-lg border px-2 py-1 text-sm ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}>
                      <option value="times">Times</option>
                      <option value="georgia">Georgia</option>
                      <option value="sans">Sans</option>
                    </select>
                  </label>
                  <label className={`text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                    Font size
                    <select value={fontSize} onChange={(event) => { setFontSize(Number(event.target.value)); setFontSizeLocked(true) }} className={`ml-2 rounded-lg border px-2 py-1 text-sm ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}>
                      {[11, 12, 13, 14, 15].map((size) => <option key={size} value={size}>{size}pt</option>)}
                    </select>
                  </label>
                  <label className={`text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                    Line height
                    <select value={lineHeight} onChange={(event) => setLineHeight(Number(event.target.value))} className={`ml-2 rounded-lg border px-2 py-1 text-sm ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}>
                      {[1.6, 1.8, 2].map((value) => <option key={value} value={value}>{value}</option>)}
                    </select>
                  </label>
                  <div className="flex flex-wrap items-center gap-2">
                    <button onClick={() => setFirstLineIndent((value) => !value)} className={`rounded-full px-3 py-1.5 text-xs font-medium ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>
                      {firstLineIndent ? "Indent on" : "Indent off"}
                    </button>
                    <button onClick={() => setShowPageGuides((value) => !value)} className={`rounded-full px-3 py-1.5 text-xs font-medium ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>
                      {showPageGuides ? "Page guides on" : "Page guides off"}
                    </button>
                  </div>
                </div>
              ) : null}
              {showSearchTools ? (
                <div className="mt-4 space-y-3">
                  <input
                    ref={searchInputRef}
                    type="text"
                    value={recallQuery}
                    onChange={(event) => setRecallQuery(event.target.value)}
                    placeholder="Search character, scene detail, clue, or thread"
                    className={`w-full rounded-[0.9rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"}`}
                  />
                  <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto_auto]">
                    <input
                      type="text"
                      value={replaceQuery}
                      onChange={(event) => setReplaceQuery(event.target.value)}
                      placeholder="Find text"
                      className={`rounded-[0.9rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"}`}
                    />
                    <input
                      type="text"
                      value={replaceValue}
                      onChange={(event) => setReplaceValue(event.target.value)}
                      placeholder="Replace with"
                      className={`rounded-[0.9rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"}`}
                    />
                    <button onClick={replaceInCurrentChapter} disabled={!replaceQuery} className={`rounded-[0.9rem] px-4 py-2 text-sm font-medium ${isDark ? "bg-white/10 text-slate-200 disabled:opacity-40" : "bg-stone-100 text-stone-700 disabled:opacity-40"}`}>
                      Replace one
                    </button>
                    <button onClick={replaceEverywhere} disabled={!replaceQuery} className={`rounded-[0.9rem] px-4 py-2 text-sm font-medium ${isDark ? "bg-white/10 text-slate-200 disabled:opacity-40" : "bg-stone-100 text-stone-700 disabled:opacity-40"}`}>
                      {editorMode === "chapter" ? "Replace all" : "Replace across book"}
                    </button>
                  </div>
                  <div className="grid gap-3 lg:grid-cols-2">
                    <div className={`rounded-[1rem] border p-3 ${isDark ? "border-white/10 bg-black/40" : "border-stone-200 bg-stone-50"}`}>
                      <p className={`text-[11px] font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Instant character info</p>
                      {recallCharacter ? (
                        <div className="mt-2 space-y-2">
                          <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{recallCharacter.name}</p>
                          <p className={`text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>First seen in chapter {recallCharacter.first_chapter}{recallCharacter.last_seen_chapter ? ` · last seen in chapter ${recallCharacter.last_seen_chapter}` : ""}</p>
                          {recallCharacter.arc_summary ? <p className={`text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{recallCharacter.arc_summary}</p> : null}
                        </div>
                      ) : (
                        <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Type a known character name to get an instant reminder.</p>
                      )}
                    </div>
                    <div className={`rounded-[1rem] border p-3 ${isDark ? "border-white/10 bg-black/40" : "border-stone-200 bg-stone-50"}`}>
                      <p className={`text-[11px] font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Quick search hits</p>
                      <div className="mt-2 space-y-2">
                        {recallLoading ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Searching...</p> : null}
                        {!recallLoading && recallResults.map((result, index) => (
                          <button
                            key={`${result.chapter_num}-${index}`}
                            onClick={() => jumpToChapter(result.chapter_num)}
                            className={`block w-full rounded-[0.85rem] p-2 text-left ${activeFindIndex === index ? isDark ? "bg-emerald-500/15" : "bg-emerald-50" : isDark ? "bg-white/[0.03] hover:bg-white/[0.08]" : "bg-white hover:bg-stone-100"}`}
                          >
                            <p className={`text-xs font-semibold ${isDark ? "text-emerald-300" : "text-emerald-700"}`}>Chapter {result.chapter_num}{result.chapter_title ? ` - ${result.chapter_title}` : ""}</p>
                            <p className={`mt-1 text-xs ${isDark ? "text-slate-300" : "text-stone-600"}`}>{result.summary}</p>
                          </button>
                        ))}
                        {!recallLoading && recallQuery.trim().length >= 2 && recallResults.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No matches yet.</p> : null}
                      </div>
                    </div>
                  </div>
                </div>
              ) : null}
            </div>
            ) : null}

            {inlineContinuity && workspaceTab !== "write" ? (
              <div className={`mb-8 rounded-[1.4rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-white/90"}`}>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-rose-300" : "text-rose-700"}`}>Chapter memory continuity checker</p>
                    <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-stone-700"}`}>{inlineContinuity.overall_verdict}</p>
                  </div>
                  {logicSelectionText ? <p className={`max-w-sm text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Last tightened selection: {logicSelectionText.slice(0, 100)}</p> : null}
                </div>
                <div className="mt-4 grid gap-3 lg:grid-cols-2">
                  <div className={`rounded-[1rem] border p-3 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50"}`}>
                    <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Inline issues</p>
                    <div className="mt-3 space-y-3">
                      {continuityLoading ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Refreshing continuity memory…</p> : null}
                      {inlineContinuity.issues.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No chapter-memory contradictions surfaced in this pass.</p> : null}
                      {inlineContinuity.issues.slice(0, 6).map((issue, index) => (
                        <article key={`${issue.title}-${index}`} className={`rounded-[0.95rem] border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-white bg-white"}`}>
                          <div className="flex items-center justify-between gap-3">
                            <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{issue.title}</p>
                            <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${issue.severity === "critical" ? isDark ? "bg-rose-500/10 text-rose-200" : "bg-rose-50 text-rose-700" : isDark ? "bg-amber-500/10 text-amber-200" : "bg-amber-50 text-amber-700"}`}>{issue.severity}</span>
                          </div>
                          <p className={`mt-2 text-xs italic ${isDark ? "text-slate-400" : "text-stone-500"}`}>"{issue.snippet}"</p>
                          <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-700"}`}>{issue.explanation}</p>
                          {issue.suggestion ? <p className={`mt-2 text-xs ${isDark ? "text-emerald-300" : "text-emerald-700"}`}>Fix: {issue.suggestion}</p> : null}
                        </article>
                      ))}
                    </div>
                  </div>
                  <div className={`rounded-[1rem] border p-3 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50"}`}>
                    <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Memory bank</p>
                    <div className="mt-3 space-y-2">
                      {inlineContinuity.memory_bank.map((item, index) => (
                        <p key={`${item}-${index}`} className={`text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-700"}`}>{item}</p>
                      ))}
                      {inlineContinuity.memory_bank.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No retrieval notes were needed for this pass.</p> : null}
                    </div>
                  </div>
                </div>
              </div>
            ) : null}

            {editorMode === "chapter" ? (
              <div className="space-y-4">
                <div className={`relative mx-auto w-full max-w-full rounded-[1.4rem] border shadow-[0_24px_80px_-55px_rgba(15,23,42,0.25)] ${isDark ? "border-white/10 bg-[#101010]" : "border-[#d8d0c4] bg-[#fdfcf9]"}`}>
                  {showPageGuides ? (
                    <div
                      aria-hidden
                      className={`pointer-events-none absolute inset-0 rounded-[1.4rem] ${isDark ? "opacity-20" : "opacity-35"}`}
                      style={{
                        backgroundImage: `repeating-linear-gradient(to bottom, transparent 0, transparent calc(297mm - 1px), ${isDark ? "rgba(255,255,255,0.08)" : "rgba(15,23,42,0.08)"} calc(297mm - 1px), ${isDark ? "rgba(255,255,255,0.08)" : "rgba(15,23,42,0.08)"} 297mm)`,
                      }}
                    />
                  ) : null}
                  <div className={`border-b rounded-t-[1.4rem] px-6 py-6 sm:px-8 ${isDark ? "border-white/10 bg-white/[0.02]" : "border-[#e6dfd4] bg-[#f7f3ed]"}`}>
                    <div className="flex items-start justify-between gap-4">
                      <div className="min-w-0 flex-1">
                        <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{book?.title || "Manuscript"}</p>
                        <input
                          key={`chapter-heading-${activeChapterNumber}-${chapterTitle}`}
                          type="text"
                          defaultValue={formatChapterHeading(activeChapterNumber, chapterTitle)}
                          onBlur={(event) => void handleChapterHeadingBlur(event.target.value, activeChapterNumber, chapterTitle)}
                          className={`mt-3 w-full border-0 bg-transparent font-serif text-3xl font-semibold leading-tight outline-none sm:text-4xl ${isDark ? "text-white placeholder:text-slate-600" : "text-stone-950 placeholder:text-stone-400"}`}
                        />
                        <p className={`mt-2 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{chapterWordCount.toLocaleString()} words · ~{chapterApproxPages} pages</p>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className={`rounded-full px-3 py-1.5 text-[11px] font-semibold ${dirtyDrafts.includes(activeChapterNumber) ? isDark ? "bg-amber-500/10 text-amber-200" : "bg-amber-100 text-amber-800" : isDark ? "bg-emerald-500/10 text-emerald-200" : "bg-emerald-100 text-emerald-800"}`}>
                          {saving ? "Saving..." : dirtyDrafts.includes(activeChapterNumber) ? "Unsaved" : "Saved"}
                        </span>
                        <button
                          type="button"
                          onClick={() => setShowEditorSettings((value) => !value)}
                          className={`hidden rounded-full border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}
                          aria-label="Editor settings"
                        >
                          ⚙
                        </button>
                        <button
                          onClick={saveCurrentChapter}
                          disabled={saving || !text.trim()}
                          className={`rounded-full border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-100 disabled:opacity-40" : "border-stone-200 bg-white text-stone-700 disabled:opacity-40"}`}
                          aria-label="Save now"
                        >
                          Save
                        </button>
                      </div>
                    </div>
                    {showEditorSettings ? (
                      <div className={`mt-4 inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs ${isDark ? "border-white/10 bg-black/30 text-slate-300" : "border-stone-200 bg-white text-stone-600"}`}>
                        <span>Replace existing chapter</span>
                        <button
                          type="button"
                          onClick={() => setReplaceExisting((value) => !value)}
                          className={`rounded-full px-2.5 py-1 font-semibold ${replaceExisting || selectedChapter !== null ? isDark ? "bg-white text-slate-950" : "bg-stone-900 text-white" : isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}
                        >
                          {replaceExisting || selectedChapter !== null ? "On" : "Off"}
                        </button>
                      </div>
                    ) : null}
                  </div>
                  <div className={`sticky top-3 z-10 border-b px-4 py-3 transition-all duration-200 translate-y-0 opacity-100 pointer-events-auto ${isDark ? "border-white/10 bg-[#0d1117]/95 backdrop-blur" : "border-[#e6dfd4] bg-[#f7f3ed]/95 backdrop-blur"}`}>
                    <EditorToolbar isDark={isDark} compact characters={characters} />
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
                    onCharacterClick={(characterName) => {
                      const char = characters.find((c) => c.name === characterName || c.aliases?.includes(characterName))
                      if (char) openCharCard(char)
                    }}
                    editorKey={`chapter-${activeChapterNumber}`}
                    placeholder="Write or paste the chapter here..."
                    style={{ ...sheetStyle, textIndent: firstLineIndent ? "1.5em" : "0" }}
                    className={`relative min-h-[297mm] w-full border-0 bg-transparent px-6 py-10 sm:px-[20mm] sm:py-[24mm] outline-none ${isDark ? "text-slate-100 placeholder:text-slate-500" : "text-stone-900 placeholder:text-stone-400"}`}
                    contentClassName="mx-auto w-full max-w-[760px]"
                  />
                </div>
              </div>
            ) : (
              <div className="space-y-5">
                {fullBookLoading ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Loading the full manuscript...</p> : null}
                {(chapterList?.chapters ?? []).map((chapter) => {
                  const draft = bookDrafts[chapter.number] ?? { title: chapter.title || `Chapter ${chapter.number}`, text: "", html: textToHtml("") }
                  return (
                    <div
                      key={chapter.number}
                      ref={(node) => {
                        chapterRefs.current[chapter.number] = node
                      }}
                      className={`relative mx-auto w-full max-w-full rounded-[1.4rem] border shadow-[0_24px_80px_-55px_rgba(15,23,42,0.25)] ${jumpTarget === chapter.number ? isDark ? "border-teal-400/40 bg-[#101010]" : "border-teal-300 bg-[#fdfcf9]" : isDark ? "border-white/10 bg-[#101010]" : "border-[#d8d0c4] bg-[#fdfcf9]"}`}
                    >
                      {showPageGuides ? (
                        <div
                          aria-hidden
                          className={`pointer-events-none absolute inset-0 rounded-[1.4rem] ${isDark ? "opacity-20" : "opacity-35"}`}
                          style={{
                            backgroundImage: `repeating-linear-gradient(to bottom, transparent 0, transparent calc(297mm - 1px), ${isDark ? "rgba(255,255,255,0.08)" : "rgba(15,23,42,0.08)"} calc(297mm - 1px), ${isDark ? "rgba(255,255,255,0.08)" : "rgba(15,23,42,0.08)"} 297mm)`,
                          }}
                        />
                      ) : null}
                      <div className={`border-b rounded-t-[1.4rem] px-6 py-6 sm:px-8 ${isDark ? "border-white/10 bg-white/[0.02]" : "border-[#e6dfd4] bg-[#f7f3ed]"}`}>
                        <div className="flex items-start justify-between gap-4">
                          <div className="min-w-0 flex-1">
                            <p className={`text-[11px] font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Chapter {chapter.number}</p>
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
                          </div>
                          <div className="flex items-center gap-2">
                            <span className={`rounded-full px-3 py-1.5 text-[11px] font-semibold ${dirtyDrafts.includes(chapter.number) ? isDark ? "bg-amber-500/10 text-amber-200" : "bg-amber-100 text-amber-800" : isDark ? "bg-emerald-500/10 text-emerald-200" : "bg-emerald-100 text-emerald-800"}`}>
                              {saving ? "Saving..." : dirtyDrafts.includes(chapter.number) ? "Unsaved" : "Saved"}
                            </span>
                            <button
                              onClick={() => void saveChapterDraft(chapter.number, draft)}
                              disabled={saving || !draft.text.trim()}
                              className={`rounded-full border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-100 disabled:opacity-40" : "border-stone-200 bg-white text-stone-700 disabled:opacity-40"}`}
                              aria-label={`Save chapter ${chapter.number}`}
                            >
                              Save
                            </button>
                          </div>
                        </div>
                      </div>
                      <div className={`sticky top-3 z-10 border-b px-4 py-3 transition-all duration-200 translate-y-0 opacity-100 pointer-events-auto ${isDark ? "border-white/10 bg-[#0d1117]/95 backdrop-blur" : "border-[#e6dfd4] bg-[#f7f3ed]/95 backdrop-blur"}`}>
                        <EditorToolbar isDark={isDark} compact characters={characters} />
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
                        onCharacterClick={(characterName) => {
                          const char = characters.find((c) => c.name === characterName || c.aliases?.includes(characterName))
                          if (char) openCharCard(char)
                        }}
                        editorKey={`book-${chapter.number}`}
                        placeholder="Draft this chapter..."
                        style={{ ...sheetStyle, textIndent: firstLineIndent ? "1.5em" : "0" }}
                        className={`relative min-h-[240mm] w-full border-0 bg-transparent px-6 py-10 sm:px-[20mm] sm:py-[22mm] outline-none ${isDark ? "text-slate-100 placeholder:text-slate-500" : "text-stone-900 placeholder:text-stone-400"}`}
                        contentClassName="mx-auto w-full max-w-[760px]"
                      />
                    </div>
                  )
                })}
              </div>
            )}

            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <p className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>
                {editorMode === "chapter"
                  ? "Save runs continuity review and refreshes unresolved plot-thread context immediately after ingest."
                  : "Full-book mode lets continuity findings and search hits jump straight to the right chapter card."}
              </p>
              {editorMode === "book" ? (
                <button
                  onClick={saveFullBook}
                  disabled={saving || Object.values(bookDrafts).every((draft) => !draft.text.trim())}
                  className={`rounded-full border px-4 py-2 text-sm font-medium ${isDark ? "border-white/10 bg-white/5 text-slate-100 disabled:opacity-40" : "border-stone-200 bg-white text-stone-700 disabled:opacity-40"}`}
                >
                  {saving ? "Saving..." : "Save all chapters"}
                </button>
              ) : null}
            </div>
            {statusMessage ? <p className={`mt-3 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{statusMessage}</p> : null}
          </section>

          {workspaceTab === "write" && rightRailVisible ? (
          <aside className="space-y-4">
            <div className={`rounded-[1.6rem] border p-2 ${isDark ? "border-white/10 bg-[#0d1117]" : "border-stone-200 bg-white/90"}`}>
              <div className="flex items-center gap-1">
                {([
                  ["context", "Context"],
                  ["advisor", "Advisor"],
                  ["notes", "Notes"],
                  ["arcs", "Arcs"],
                ] as const).map(([pane, label]) => (
                  <button
                    key={pane}
                    type="button"
                    onClick={() => openRightPane(pane)}
                    className={`rounded-full px-3 py-2 text-sm font-medium transition ${activeRightPane === pane ? isDark ? "bg-white text-slate-950" : "bg-stone-900 text-white" : isDark ? "text-slate-300 hover:bg-white/10" : "text-stone-600 hover:bg-stone-100"}`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {activeRightPane === "character" && selectedCharCard ? (
              <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-[#0d1117]" : "border-stone-200 bg-white/90"}`}>
                <button
                  onClick={() => {
                    setSelectedCharCard(null)
                    setActiveRightPane("context")
                  }}
                  className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}
                >
                  Back to context
                </button>
                <div className="mt-4">
                  <p className={`text-lg font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{selectedCharCard.name}</p>
                  <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>
                    {selectedCharCard.role === "mc" ? "POV" : selectedCharCard.role === "sc" ? "Supporting" : "Background"} · Ch. {selectedCharCard.first_chapter}{selectedCharCard.last_seen_chapter ? ` to ${selectedCharCard.last_seen_chapter}` : ""}
                  </p>
                  {selectedCharCard.description ? <p className={`mt-4 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-700"}`}>{selectedCharCard.description}</p> : null}
                  {selectedCharCard.arc_summary ? <p className={`mt-4 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-600"}`}>{selectedCharCard.arc_summary}</p> : null}
                </div>
              </div>
            ) : null}

            {activeRightPane === "context" ? (
              <>
                <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-[#0d1117]" : "border-stone-200 bg-white/90"}`}>
                  <div className="flex items-center justify-between gap-3">
                    <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Active characters</p>
                    <span className={`text-sm font-semibold ${isDark ? "text-slate-300" : "text-stone-700"}`}>{activeChapterContextCharacters.length || Math.min(4, characters.length)}</span>
                  </div>
                  <div className="mt-4 space-y-3">
                    {(activeChapterContextCharacters.length ? activeChapterContextCharacters.map((character) => ({
                      id: character.id,
                      name: character.name,
                      role: character.role,
                    })) : characters.slice(0, 4).map((character) => ({
                      id: character.id,
                      name: character.name,
                      role: character.role,
                    }))).map((character) => (
                      <button key={character.id} onClick={() => {
                        const match = characters.find((item) => item.id === character.id)
                        if (match) openCharCard(match)
                      }} className="flex w-full items-center justify-between gap-3 text-left">
                        <div className="flex items-center gap-3">
                          <span className="h-2.5 w-2.5 rounded-full bg-sky-400" />
                          <span className={`text-sm ${isDark ? "text-slate-100" : "text-stone-900"}`}>{character.name}</span>
                        </div>
                        <span className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{character.role === "mc" ? "POV" : character.role === "sc" ? "Major" : "Supporting"}</span>
                      </button>
                    ))}
                    {activeChapterContextCharacters.length === 0 && characters.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>No characters loaded yet.</p> : null}
                  </div>
                  <Link href={`/${bookId}/characters`} className={`mt-4 inline-flex text-sm ${isDark ? "text-sky-300" : "text-sky-700"}`}>View all characters →</Link>
                </div>

                <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-[#0d1117]" : "border-stone-200 bg-white/90"}`}>
                  <div className="flex items-center justify-between gap-3">
                    <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Unresolved threads</p>
                    <span className={`text-sm font-semibold ${isDark ? "text-slate-300" : "text-stone-700"}`}>{activeThreadSummary.length || Math.min(3, plotThreads.length)}</span>
                  </div>
                  <div className="mt-4 space-y-3">
                    {(activeThreadSummary.length ? activeThreadSummary.map((thread) => thread.title) : plotThreads.slice(0, 3).map((thread) => thread.title)).map((thread) => (
                      <div key={thread} className="flex items-start gap-3">
                        <span className="mt-1.5 h-2 w-2 rounded-full bg-amber-400" />
                        <p className={`text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{thread}</p>
                      </div>
                    ))}
                    {activeThreadSummary.length === 0 && plotThreads.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>No unresolved threads loaded yet.</p> : null}
                  </div>
                  <Link href={`/${bookId}/plot-threads`} className={`mt-4 inline-flex text-sm ${isDark ? "text-sky-300" : "text-sky-700"}`}>View all threads →</Link>
                </div>

                <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-[#0d1117]" : "border-stone-200 bg-white/90"}`}>
                  <div className="flex items-center justify-between gap-3">
                    <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Recent events</p>
                    <span className={`text-sm font-semibold ${isDark ? "text-slate-300" : "text-stone-700"}`}>{recentEventSummary.length}</span>
                  </div>
                  <div className="mt-4 space-y-3">
                    {recentEventSummary.map((event) => (
                      <div key={`${event.chapter_number}-${event.detail}`} className="flex items-start gap-3">
                        <span className="mt-1.5 h-2 w-2 rounded-full bg-emerald-400" />
                        <p className={`text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{event.detail}</p>
                      </div>
                    ))}
                    {recentEventSummary.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>Recent chapter events will appear here.</p> : null}
                  </div>
                  <Link href={`/${bookId}/timeline`} className={`mt-4 inline-flex text-sm ${isDark ? "text-sky-300" : "text-sky-700"}`}>View timeline →</Link>
                </div>

                <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-[#0d1117]" : "border-stone-200 bg-white/90"}`}>
                  <div className="flex items-center justify-between gap-3">
                    <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Continuity warnings</p>
                    <span className={`text-sm font-semibold ${isDark ? "text-slate-300" : "text-stone-700"}`}>{warningSummary.length || review?.continuity_issues.length || 0}</span>
                  </div>
                  <div className="mt-4 space-y-3">
                    {(warningSummary.length ? warningSummary : review?.continuity_issues.slice(0, 3) ?? []).map((warning, index) => (
                      <div key={`${warning.title}-${index}`} className="flex items-start gap-3">
                        <span className="mt-1.5 h-2 w-2 rounded-full bg-amber-400" />
                        <p className={`text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{warning.title}</p>
                      </div>
                    ))}
                    {warningSummary.length === 0 && !review?.continuity_issues.length ? <p className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>No continuity warnings surfaced for this chapter.</p> : null}
                  </div>
                </div>

                <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-sky-500/30 bg-sky-500/5" : "border-sky-200 bg-sky-50/80"}`}>
                  <div className="flex items-center justify-between gap-3">
                    <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Ask LoreVia</p>
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${isDark ? "bg-sky-500/15 text-sky-200" : "bg-sky-100 text-sky-700"}`}>Beta</span>
                  </div>
                  <div className={`mt-4 rounded-[1rem] border px-3 py-3 text-sm ${isDark ? "border-white/10 bg-black/20 text-slate-500" : "border-stone-200 bg-white text-stone-400"}`}>
                    Ask anything about your story...
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    <button onClick={() => openRightPane("context")} className={`rounded-full px-3 py-1.5 text-xs font-medium ${isDark ? "bg-white/10 text-slate-200" : "bg-white text-stone-700"}`}>Check continuity</button>
                    <button onClick={() => void tightenSelectedText()} className={`rounded-full px-3 py-1.5 text-xs font-medium ${isDark ? "bg-white/10 text-slate-200" : "bg-white text-stone-700"}`}>Tighten selection</button>
                    <button onClick={() => openRightPane("advisor")} className={`rounded-full px-3 py-1.5 text-xs font-medium ${isDark ? "bg-white/10 text-slate-200" : "bg-white text-stone-700"}`}>Suggest rewrite</button>
                  </div>
                </div>
              </>
            ) : null}

            {activeRightPane === "advisor" ? (
              <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-[#0d1117]" : "border-stone-200 bg-white/90"}`}>
                <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Chapter advisor</p>
                <p className={`mt-3 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-700"}`}>Use LoreVia while drafting to tighten prose, surface continuity risks, and suggest stronger scene transitions.</p>
                <div className="mt-4 space-y-3">
                  {suggestions.slice(0, 3).map((suggestion, index) => (
                    <div key={`${suggestion.title}-${index}`} className={`rounded-[1rem] border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
                      <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{suggestion.title}</p>
                      <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-400" : "text-stone-600"}`}>{suggestion.description}</p>
                    </div>
                  ))}
                  {suggestions.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>Advisor suggestions will appear here after review passes run.</p> : null}
                </div>
                <Link href={`/${bookId}/advisor`} className={`mt-4 inline-flex text-sm ${isDark ? "text-sky-300" : "text-sky-700"}`}>Open full advisor →</Link>
              </div>
            ) : null}

            {activeRightPane === "notes" ? (
              <>
                <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-[#0d1117]" : "border-stone-200 bg-white/90"}`}>
                  <div className="flex items-center justify-between gap-3">
                    <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Chapter notes</p>
                    <Link href={`/${bookId}/notes`} className={`text-sm ${isDark ? "text-sky-300" : "text-sky-700"}`}>All notes →</Link>
                  </div>
                  <div className="mt-4 space-y-3">
                    {chapterLinkedNotes.slice(0, 4).map((note) => (
                      <div key={note.id} className={`rounded-[1rem] border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
                        <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{note.title || `Chapter ${activeChapterNumber} note`}</p>
                        <p className={`mt-2 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{new Date(note.updated_at).toLocaleString()}</p>
                      </div>
                    ))}
                    {chapterLinkedNotes.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>No notes saved for this chapter yet.</p> : null}
                  </div>
                </div>
                <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-[#0d1117]" : "border-stone-200 bg-white/90"}`}>
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Book notes</p>
                  <div className="mt-4 space-y-3">
                    {generalNotes.slice(0, 3).map((note) => (
                      <div key={note.id} className={`rounded-[1rem] border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
                        <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{note.title || "Book note"}</p>
                        <p className={`mt-2 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{new Date(note.updated_at).toLocaleString()}</p>
                      </div>
                    ))}
                    {generalNotes.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>No book-level notes saved yet.</p> : null}
                  </div>
                </div>
              </>
            ) : null}

            {activeRightPane === "arcs" ? (
              <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-[#0d1117]" : "border-stone-200 bg-white/90"}`}>
                <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Character emotional arc</p>
                {arcSummaryCharacter ? (
                  <div className="mt-4">
                    <p className={`text-lg font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{arcSummaryCharacter.character_name}</p>
                    <div className="mt-4 space-y-3">
                      {arcSummaryCharacter.points.slice(-6).map((point) => (
                        <div key={`${point.chapter_number}-${point.label}`} className="grid grid-cols-[auto_1fr] gap-3">
                          <span className={`text-xs font-semibold ${isDark ? "text-slate-500" : "text-stone-500"}`}>Ch. {point.chapter_number}</span>
                          <div className="flex items-center gap-3">
                            <span className={`h-2 w-full rounded-full ${point.sentiment >= 0 ? "bg-emerald-400/60" : "bg-rose-400/60"}`} />
                            <span className={`min-w-[7rem] text-sm ${isDark ? "text-slate-200" : "text-stone-700"}`}>{point.label}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <p className={`mt-4 text-sm ${isDark ? "text-slate-500" : "text-stone-500"}`}>Character arc tracking will appear once growth events are available.</p>
                )}
              </div>
            ) : null}
          </aside>
          ) : null}

          {workspaceTab !== "write" && rightRailVisible ? (
          <aside className="space-y-4">

            {/* ── Character Card pane ──────────────────────────── */}
            {activeRightPane === "character" ? (
              <div className={`rounded-[1.6rem] border ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-white/80"}`}>
                {/* Header: browse list or card header */}
                {selectedCharCard ? (
                  <>
                    <div className={`flex items-center justify-between gap-3 border-b p-4 ${isDark ? "border-white/10" : "border-stone-200"}`}>
                      <div>
                        <button
                          onClick={() => setSelectedCharCard(null)}
                          className={`mb-1 text-[11px] font-semibold uppercase tracking-[0.18em] transition ${isDark ? "text-slate-500 hover:text-slate-300" : "text-stone-400 hover:text-stone-600"}`}
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
                              className="rounded-full bg-[linear-gradient(135deg,#4f46e5,#4338ca)] px-4 py-1.5 text-xs font-semibold text-white disabled:opacity-50"
                            >
                              {charCardSaving ? "Saving…" : "Save"}
                            </button>
                            <button
                              onClick={() => setCharCardEditing(false)}
                              className={`rounded-full border px-3 py-1.5 text-xs font-medium ${isDark ? "border-white/10 text-slate-300" : "border-stone-200 text-stone-600"}`}
                            >
                              Cancel
                            </button>
                          </>
                        ) : (
                          <button
                            onClick={() => setCharCardEditing(true)}
                            className={`rounded-full border px-3 py-1.5 text-xs font-medium ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}
                          >
                            Edit card
                          </button>
                        )}
                      </div>
                    </div>

                    <div className="space-y-4 p-4">
                      {/* Role + First chapter badges */}
                      <div className="flex flex-wrap gap-2">
                        {selectedCharCard.role && (
                          <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${
                            selectedCharCard.role === "mc" ? isDark ? "bg-indigo-500/20 text-indigo-200" : "bg-indigo-100 text-indigo-700"
                            : selectedCharCard.role === "sc" ? isDark ? "bg-teal-500/20 text-teal-200" : "bg-teal-100 text-teal-700"
                            : isDark ? "bg-white/10 text-slate-300" : "bg-stone-100 text-stone-600"
                          }`}>{selectedCharCard.role === "mc" ? "Main" : selectedCharCard.role === "sc" ? "Supporting" : "Background"}</span>
                        )}
                        <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${isDark ? "bg-white/8 text-slate-400" : "bg-stone-100 text-stone-500"}`}>
                          Ch. {selectedCharCard.first_chapter}{selectedCharCard.last_seen_chapter ? ` to ${selectedCharCard.last_seen_chapter}` : ""}
                        </span>
                        {selectedCharCard.archetype && (
                          <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${isDark ? "bg-white/8 text-slate-400" : "bg-stone-100 text-stone-500"}`}>{selectedCharCard.archetype}</span>
                        )}
                        {selectedCharCard.character_type === "gag" && (
                          <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${isDark ? "bg-amber-500/20 text-amber-300" : "bg-amber-100 text-amber-700"}`}>🎭 Gag</span>
                        )}
                      </div>

                      {/* Description */}
                      <div>
                        <p className={`mb-1 text-[10px] font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Description</p>
                        {charCardEditing ? (
                          <textarea
                            rows={3}
                            value={charCardDraft.description}
                            onChange={e => setCharCardDraft(d => ({ ...d, description: e.target.value }))}
                            className={`w-full resize-none rounded-[0.8rem] border px-3 py-2 text-sm leading-6 outline-none ${isDark ? "border-white/10 bg-black/30 text-slate-200" : "border-stone-200 bg-stone-50 text-stone-800"}`}
                          />
                        ) : (
                          <p className={`text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{selectedCharCard.description || <span className="opacity-40">No description yet.</span>}</p>
                        )}
                      </div>

                      {/* Arc summary */}
                      <div>
                        <p className={`mb-1 text-[10px] font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Arc summary</p>
                        {charCardEditing ? (
                          <textarea
                            rows={4}
                            value={charCardDraft.arcSummary}
                            onChange={e => setCharCardDraft(d => ({ ...d, arcSummary: e.target.value }))}
                            className={`w-full resize-none rounded-[0.8rem] border px-3 py-2 text-sm leading-6 outline-none ${isDark ? "border-white/10 bg-black/30 text-slate-200" : "border-stone-200 bg-stone-50 text-stone-800"}`}
                          />
                        ) : (
                          <p className={`text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{selectedCharCard.arc_summary || <span className="opacity-40">No arc summary yet.</span>}</p>
                        )}
                      </div>

                      {/* Personality tags */}
                      <div>
                        <p className={`mb-1 text-[10px] font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Personality</p>
                        {charCardEditing ? (
                          <input
                            value={charCardDraft.personalityTags}
                            onChange={e => setCharCardDraft(d => ({ ...d, personalityTags: e.target.value }))}
                            placeholder="Comma-separated traits"
                            className={`w-full rounded-[0.8rem] border px-3 py-2 text-sm outline-none ${isDark ? "border-white/10 bg-black/30 text-slate-200 placeholder:text-slate-600" : "border-stone-200 bg-stone-50 text-stone-800"}`}
                          />
                        ) : (
                          <div className="flex flex-wrap gap-1.5">
                            {(selectedCharCard.personality_tags ?? []).length > 0 ? selectedCharCard.personality_tags.map(tag => (
                              <span key={tag} className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${isDark ? "bg-violet-500/15 text-violet-200" : "bg-violet-100 text-violet-700"}`}>{tag}</span>
                            )) : <span className={`text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>None recorded.</span>}
                          </div>
                        )}
                      </div>

                      {/* Motivations */}
                      <div>
                        <p className={`mb-1 text-[10px] font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Motivations</p>
                        {charCardEditing ? (
                          <input
                            value={charCardDraft.motivations}
                            onChange={e => setCharCardDraft(d => ({ ...d, motivations: e.target.value }))}
                            placeholder="Comma-separated"
                            className={`w-full rounded-[0.8rem] border px-3 py-2 text-sm outline-none ${isDark ? "border-white/10 bg-black/30 text-slate-200 placeholder:text-slate-600" : "border-stone-200 bg-stone-50 text-stone-800"}`}
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
                        <p className={`mb-1 text-[10px] font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Fears</p>
                        {charCardEditing ? (
                          <input
                            value={charCardDraft.fears}
                            onChange={e => setCharCardDraft(d => ({ ...d, fears: e.target.value }))}
                            placeholder="Comma-separated"
                            className={`w-full rounded-[0.8rem] border px-3 py-2 text-sm outline-none ${isDark ? "border-white/10 bg-black/30 text-slate-200 placeholder:text-slate-600" : "border-stone-200 bg-stone-50 text-stone-800"}`}
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
                          <p className={`mb-1 text-[10px] font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Growth events</p>
                          <div className="space-y-2">
                            {selectedCharCard.growth_events!
                              .slice()
                              .sort((left, right) => (right.chapter_number ?? right.chapter ?? 0) - (left.chapter_number ?? left.chapter ?? 0))
                              .map((ev, i) => (
                              <div key={i} className={`rounded-[0.8rem] border px-3 py-2 text-xs ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
                                {(ev.chapter_number ?? ev.chapter) ? (
                                  <span className={`font-semibold ${isDark ? "text-indigo-300" : "text-violet-600"}`}>
                                    Ch. {ev.chapter_number ?? ev.chapter} ·{" "}
                                  </span>
                                ) : null}
                                <span className={isDark ? "text-slate-300" : "text-stone-700"}>{ev.event_title || ev.event || "Untitled event"}</span>
                                {(ev.description || ev.impact) ? (
                                  <p className={`mt-1 leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>{ev.description || ev.impact}</p>
                                ) : null}
                                <div className="mt-2 flex flex-wrap gap-1.5">
                                  {typeof ev.impact_score === "number" ? (
                                    <span className={`rounded-full px-2 py-0.5 ${isDark ? "bg-white/10 text-slate-300" : "bg-stone-200 text-stone-600"}`}>
                                      impact {ev.impact_score}/10
                                    </span>
                                  ) : null}
                                  {ev.growth_direction ? (
                                    <span className={`rounded-full px-2 py-0.5 capitalize ${isDark ? "bg-white/10 text-slate-300" : "bg-stone-200 text-stone-600"}`}>
                                      {ev.growth_direction}
                                    </span>
                                  ) : null}
                                  {typeof ev.growth_magnitude === "number" ? (
                                    <span className={`rounded-full px-2 py-0.5 ${isDark ? "bg-white/10 text-slate-300" : "bg-stone-200 text-stone-600"}`}>
                                      growth {ev.growth_magnitude}/10
                                    </span>
                                  ) : null}
                                  {ev.is_major ? (
                                    <span className={`rounded-full px-2 py-0.5 ${isDark ? "bg-amber-500/15 text-amber-300" : "bg-amber-100 text-amber-700"}`}>
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
                        className={`w-full rounded-full border px-4 py-2 text-xs font-semibold transition ${isDark ? "border-white/10 bg-white/5 text-slate-200 hover:bg-white/10" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}
                      >
                        Save as note
                      </button>
                    </div>
                  </>
                ) : (
                  /* Browse list */
                  <div className="p-4">
                    <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Characters</p>
                    <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-400"}`}>Click a name to open their card.</p>
                    <div className="mt-3 space-y-2">
                      {characters.length === 0 ? (
                        <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No characters extracted yet.</p>
                      ) : characters.map(char => (
                        <button
                          key={char.id}
                          onClick={() => openCharCard(char)}
                          className={`w-full rounded-[1rem] border px-3 py-3 text-left transition ${
                            isDark ? "border-white/10 bg-white/[0.03] hover:bg-white/[0.07]" : "border-stone-200 bg-stone-50 hover:bg-white"
                          }`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{char.name}</p>
                            {char.role && (
                              <span className={`text-[10px] font-semibold uppercase px-2 py-0.5 rounded-full ${
                                char.role === "mc" ? isDark ? "bg-indigo-500/20 text-indigo-300" : "bg-indigo-100 text-indigo-700"
                                : char.role === "sc" ? isDark ? "bg-teal-500/20 text-teal-300" : "bg-teal-100 text-teal-700"
                                : isDark ? "bg-white/10 text-slate-400" : "bg-stone-100 text-stone-500"
                              }`}>{char.role}</span>
                            )}
                          </div>
                          {char.arc_summary && (
                            <p className={`mt-1 text-xs line-clamp-2 ${isDark ? "text-slate-400" : "text-stone-500"}`}>{char.arc_summary}</p>
                          )}
                          {char.personality_tags && char.personality_tags.length > 0 && (
                            <div className="mt-1.5 flex flex-wrap gap-1">
                              {char.personality_tags.slice(0, 3).map(t => (
                                <span key={t} className={`text-[10px] rounded-full px-2 py-0.5 ${isDark ? "bg-white/8 text-slate-400" : "bg-stone-100 text-stone-500"}`}>{t}</span>
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
                <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-white/80"}`}>
                  <div className="flex items-center justify-between gap-3">
                    <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Page navigator</p>
                    <span className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>~{fullBookApproxPages} pages</span>
                  </div>
                  <div className="mt-3 flex gap-2">
                    <input
                      type="number"
                      min={1}
                      max={Math.max(1, fullBookApproxPages)}
                      value={gotoPageInput}
                      onChange={(event) => setGotoPageInput(event.target.value)}
                      placeholder="Page #"
                      className={`w-full rounded-[0.9rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"}`}
                    />
                    <button
                      onClick={() => {
                        const page = parseInt(gotoPageInput)
                        if (!Number.isNaN(page)) jumpToPage(page)
                      }}
                      className={`rounded-[0.9rem] px-3 py-2 text-sm font-medium ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}
                    >
                      Go
                    </button>
                  </div>
                  <div className="mt-3 max-h-64 space-y-2 overflow-y-auto pr-1">
                    {fullBookPageMap.map((item) => (
                      <button
                        key={`page-${item.chapter}`}
                        onClick={() => jumpToPage(item.startPage)}
                        className={`block w-full rounded-[1rem] border px-3 py-3 text-left text-sm ${jumpTarget === item.chapter ? isDark ? "border-teal-400/30 bg-teal-500/10 text-slate-100" : "border-teal-300 bg-teal-50 text-stone-900" : isDark ? "border-white/10 bg-white/[0.03] text-slate-200 hover:bg-white/[0.07]" : "border-stone-200 bg-stone-50 text-stone-700 hover:bg-stone-100"}`}
                      >
                        <p className="font-semibold">Pages {item.startPage}{item.endPage > item.startPage ? ` to ${item.endPage}` : ""}</p>
                        <p className="mt-1 text-xs opacity-75">Chapter {item.chapter} · {item.title}</p>
                      </button>
                    ))}
                  </div>
                </div>

                <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-white/80"}`}>
                  <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>References</p>
                  <div className="mt-3 max-h-72 space-y-2 overflow-y-auto pr-1">
                    {fullBookReferenceItems.length > 0 ? fullBookReferenceItems.map((item) => {
                      const pageRef = fullBookPageMap.find((entry) => entry.chapter === item.chapter)
                      return (
                        <button
                          key={item.id}
                          onClick={() => jumpToChapter(item.chapter)}
                          className={`block w-full rounded-[1rem] border px-3 py-3 text-left text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-200 hover:bg-white/[0.07]" : "border-stone-200 bg-stone-50 text-stone-700 hover:bg-stone-100"}`}
                        >
                          <div className="flex items-center justify-between gap-3">
                            <p className="font-semibold">Page {pageRef?.startPage ?? "?"}</p>
                            <span className={`text-[11px] ${isDark ? "text-slate-500" : "text-stone-500"}`}>{item.source}</span>
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
              <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-white/80"}`}>
                <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Synopsis generator</p>
                <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{synopsis.synopsis}</p>
                {synopsis.focus_points.length > 0 ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {synopsis.focus_points.map((point) => (
                      <span key={point} className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${isDark ? "bg-white/10 text-slate-300" : "bg-stone-100 text-stone-700"}`}>{point}</span>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}

            <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-white/80"}`}>
              <div className="flex items-center justify-between gap-3">
                <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Continuity check</p>
                <Link href={`/${bookId}/reports`} className={`rounded-full px-3 py-1.5 text-xs font-semibold ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>Report history</Link>
              </div>
              {review ? (
                <div className="mt-3 space-y-3">
                  <p className={`text-sm font-medium ${isDark ? "text-white" : "text-stone-900"}`}>{review.overall_verdict}</p>
                  {review.continuity_issues.length > 0 ? review.continuity_issues.map((issue, index) => (
                    <div key={`${issue.title}-${index}`} className={`rounded-[1rem] border px-3 py-3 text-sm ${isDark ? "border-amber-500/20 bg-amber-500/10 text-slate-200" : "border-amber-200 bg-amber-50 text-stone-700"}`}>
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1">
                          <p className="font-semibold">{issue.title}</p>
                          <p className="mt-1 text-xs leading-5 opacity-80">{issue.description}</p>
                          {issue.suggestion ? <p className="mt-2 text-xs font-medium opacity-90">{issue.suggestion}</p> : null}
                        </div>
                        <button
                          onClick={() => void saveContinuityIssueAsNote(issue)}
                          className={`shrink-0 rounded-full px-3 py-1.5 text-[11px] font-semibold transition ${isDark ? "bg-white/10 text-slate-200 hover:bg-white/20" : "bg-white text-stone-700 hover:bg-stone-100"}`}
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
                      <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Insertion opportunities</p>
                      {review.insertion_opportunities.map((item, index) => (
                        <div key={`${item.title}-${index}`} className={`rounded-[1rem] border px-3 py-3 text-sm ${isDark ? "border-teal-500/20 bg-teal-500/10 text-slate-200" : "border-teal-200 bg-teal-50 text-stone-700"}`}>
                          <div className="flex items-start justify-between gap-3">
                            <div>
                              <p className="font-semibold">{item.title}</p>
                              <p className="mt-1 text-xs opacity-75">Chapter {item.target_chapter}{item.target_chapter_title ? ` - ${item.target_chapter_title}` : ""}</p>
                            </div>
                            <button onClick={() => jumpToChapter(item.target_chapter)} className={`rounded-full px-3 py-1 text-[11px] font-semibold ${isDark ? "bg-white/10 text-slate-100" : "bg-white text-stone-700"}`}>
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
                    className={`rounded-full border px-4 py-2 text-xs font-semibold ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-stone-50 text-stone-700"}`}
                  >
                    Download continuity report
                  </button>
                </div>
              ) : (
                <p className={`mt-3 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Save a chapter to run checks.</p>
              )}
            </div>

            <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-white/80"}`}>
              <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Character voice consistency</p>
              {voiceReview ? (
                <div className="mt-3 space-y-3">
                  <p className={`text-sm font-medium ${isDark ? "text-white" : "text-stone-900"}`}>{voiceReview.overall_verdict}</p>
                  {voiceCharacters.length > 0 ? (
                    <p className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Reviewed: {voiceCharacters.join(", ")}</p>
                  ) : null}
                  {voiceMatches.length > 0 ? (
                    <div className="space-y-2">
                      {voiceMatches.map((match) => (
                        <div key={match.character_name} className={`rounded-[1rem] border px-3 py-3 text-sm ${match.match_score >= 70 ? isDark ? "border-emerald-500/20 bg-emerald-500/10 text-slate-200" : "border-emerald-200 bg-emerald-50 text-stone-700" : isDark ? "border-amber-500/20 bg-amber-500/10 text-slate-200" : "border-amber-200 bg-amber-50 text-stone-700"}`}>
                          <div className="flex items-center justify-between gap-3">
                            <p className="font-semibold">{match.character_name}</p>
                            <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${isDark ? "bg-white/10 text-slate-200" : "bg-white text-stone-700"}`}>{match.match_score}% match</span>
                          </div>
                          <p className="mt-2 text-xs opacity-80">Baseline {match.baseline_sample_size} samples · current chapter {match.sample_dialogue_count} excerpts</p>
                          {match.strongest_signals.length > 0 ? <p className="mt-2 text-xs opacity-90">{match.strongest_signals.join(". ")}.</p> : null}
                          {match.closest_other_character ? <p className="mt-2 text-xs opacity-80">Closest alternate voice: {match.closest_other_character}{typeof match.closest_other_score === "number" ? ` (${match.closest_other_score}% match)` : ""}</p> : null}
                        </div>
                      ))}
                    </div>
                  ) : null}
                  {voiceReview.issues.length > 0 ? voiceReview.issues.map((issue, index) => (
                    <div key={`${issue.character_name}-${issue.title}-${index}`} className={`rounded-[1rem] border px-3 py-3 text-sm ${isDark ? "border-rose-500/20 bg-rose-500/10 text-slate-200" : "border-rose-200 bg-rose-50 text-stone-700"}`}>
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1">
                          <div className="flex items-center justify-between gap-3">
                            <p className="font-semibold">{issue.character_name}: {issue.title}</p>
                            <span className={`rounded-full px-2 py-1 text-[10px] uppercase tracking-[0.16em] ${isDark ? "bg-white/10 text-slate-300" : "bg-white text-stone-600"}`}>{issue.severity}</span>
                          </div>
                          <p className="mt-2 text-xs leading-5 opacity-90">{issue.description}</p>
                          {issue.evidence ? <p className="mt-2 text-xs opacity-80">Evidence: {issue.evidence}</p> : null}
                          {issue.suggestion ? <p className="mt-2 text-xs opacity-90">Suggestion: {issue.suggestion}</p> : null}
                        </div>
                        <button
                          onClick={() => void saveVoiceIssueAsNote(issue)}
                          className={`shrink-0 rounded-full px-3 py-1.5 text-[11px] font-semibold transition ${isDark ? "bg-white/10 text-slate-200 hover:bg-white/20" : "bg-white text-stone-700 hover:bg-stone-100"}`}
                        >
                          Save as note
                        </button>
                      </div>
                    </div>
                  )) : (
                    <p className={`text-sm ${isDark ? "text-teal-300" : "text-teal-700"}`}>No character voice issues found in the latest save.</p>
                  )}
                </div>
              ) : (
                <p className={`mt-3 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Save a chapter to compare dialogue and behaviour against established character baselines.</p>
              )}
            </div>

            <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-white/80"}`}>
              <div className="flex items-center justify-between gap-3">
                <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Open threads</p>
                <Link href={`/${bookId}/plot-threads`} className={`rounded-full px-3 py-1.5 text-xs font-semibold ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>Dashboard</Link>
              </div>
              <div className="mt-3 space-y-2">
                {plotThreads.length > 0 ? plotThreads.map((thread) => (
                  <div key={thread.id} className={`rounded-[1rem] border px-3 py-3 text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-200" : "border-stone-200 bg-stone-50 text-stone-700"}`}>
                    <p className="font-semibold">{thread.title}</p>
                    <p className="mt-1 text-xs opacity-75">Introduced in chapter {thread.introduced_at ?? "?"} · {thread.status}</p>
                  </div>
                )) : <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No unresolved threads loaded yet.</p>}
              </div>
            </div>

            {reviewPassages.length > 0 ? (
              <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-white/80"}`}>
                <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Cross-referenced passages</p>
                <div className="mt-3 space-y-2">
                  {reviewPassages.map((passage, index) => (
                    <button
                      key={`${passage.chapter_num}-${index}`}
                      onClick={() => jumpToChapter(passage.chapter_num)}
                      className={`block w-full rounded-[1rem] border px-3 py-3 text-left text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-200 hover:bg-white/[0.07]" : "border-stone-200 bg-stone-50 text-stone-700 hover:bg-stone-100"}`}
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
                <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-white/80"}`}>
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Notes</p>
                      <p className={`mt-1 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                        Save quick author notes for this chapter or for the whole book.
                      </p>
                    </div>
                    <Link href={`/${bookId}/notes`} className={`rounded-full px-3 py-1.5 text-xs font-semibold ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>All notes</Link>
                  </div>

                  <div className="mt-4 inline-flex rounded-full p-1 border border-white/10 bg-black/20">
                    <button
                      onClick={() => setNoteScope("chapter")}
                      className={`rounded-full px-3 py-1.5 text-xs font-medium ${noteScope === "chapter" ? "bg-white text-slate-950" : isDark ? "text-slate-300" : "text-stone-600"}`}
                    >
                      Chapter {activeChapterNumber}
                    </button>
                    <button
                      onClick={() => setNoteScope("book")}
                      className={`rounded-full px-3 py-1.5 text-xs font-medium ${noteScope === "book" ? "bg-white text-slate-950" : isDark ? "text-slate-300" : "text-stone-600"}`}
                    >
                      Whole book
                    </button>
                  </div>

                  <div className="mt-4 space-y-3">
                    <input
                      value={noteTitle}
                      onChange={(event) => setNoteTitle(event.target.value)}
                      placeholder="Note title"
                      className={`w-full rounded-[0.9rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"}`}
                    />
                    <div className={`overflow-hidden rounded-[1rem] border ${isDark ? "border-white/10 bg-[#0b0f17]" : "border-stone-200 bg-white"}`}>
                      <EditorToolbar isDark={isDark} compact characters={characters} />
                      <RichTextEditor
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
                        className="rounded-[1rem] bg-[linear-gradient(135deg,#d97706,#b45309)] px-4 py-3 text-sm font-semibold text-white transition disabled:opacity-40"
                      >
                        {savingNote ? "Saving..." : `Save ${noteScope === "chapter" ? "chapter" : "book"} note`}
                      </button>
                      <button
                        type="button"
                        onClick={() => void saveWorkspaceVaultNote()}
                        disabled={!noteBodyText.trim()}
                        className={`rounded-[1rem] px-4 py-3 text-sm font-semibold transition disabled:opacity-40 ${isDark ? "bg-white/10 text-slate-100" : "bg-stone-100 text-stone-700"}`}
                      >
                        Save to workspace notes
                      </button>
                      <Link
                        href={`/${bookId}/notes`}
                        className={`inline-flex items-center justify-center rounded-[1rem] px-4 py-3 text-sm font-semibold ${isDark ? "bg-white/6 text-slate-200" : "bg-white text-stone-700 border border-stone-200"}`}
                      >
                        Open notes workspace
                      </Link>
                    </div>
                  </div>
                </div>

                <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-white/80"}`}>
                  <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Chapter-linked notes</p>
                  <div className="mt-3 space-y-2">
                    {notesLoading ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Loading notes...</p> : null}
                    {!notesLoading && chapterLinkedNotes.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No notes saved for this chapter yet.</p> : null}
                    {chapterLinkedNotes.map((note) => (
                      <div key={note.id} className={`rounded-[1rem] border px-3 py-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
                        {editingNoteId === note.id ? (
                          <div className="space-y-3">
                            <input
                              value={editNoteTitle}
                              onChange={(e) => setEditNoteTitle(e.target.value)}
                              placeholder="Note title"
                              className={`w-full rounded-md border px-3 py-2 text-sm ${isDark ? "border-slate-700 bg-slate-800 text-white" : "border-stone-300 bg-white text-stone-900"}`}
                            />
                            <textarea
                              value={editNoteBody}
                              onChange={(e) => setEditNoteBody(e.target.value)}
                              placeholder="Note content (markdown supported)"
                              rows={4}
                              className={`w-full rounded-md border px-3 py-2 text-sm ${isDark ? "border-slate-700 bg-slate-800 text-white" : "border-stone-300 bg-white text-stone-900"}`}
                            />
                            <div className="flex gap-2">
                              <button
                                onClick={saveEditedNote}
                                disabled={editingNoteSaving}
                                className={`rounded-md px-3 py-1.5 text-xs font-semibold ${isDark ? "bg-emerald-600 text-white disabled:opacity-40" : "bg-emerald-600 text-white disabled:opacity-40"}`}
                              >
                                {editingNoteSaving ? "Saving..." : "Save"}
                              </button>
                              <button
                                onClick={cancelEditingNote}
                                className={`rounded-md px-3 py-1.5 text-xs font-semibold ${isDark ? "border border-slate-600 text-slate-300" : "border border-stone-300 text-stone-700"}`}
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
                                <button onClick={() => removeNote(note.id)} className={`text-xs font-medium ${isDark ? "text-rose-300" : "text-rose-700"}`}>Delete</button>
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

                <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-white/80"}`}>
                  <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Whole-book notes</p>
                  <div className="mt-3 space-y-2">
                    {!notesLoading && generalNotes.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No general notes saved yet.</p> : null}
                    {generalNotes.map((note) => (
                      <div key={note.id} className={`rounded-[1rem] border px-3 py-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
                        {editingNoteId === note.id ? (
                          <div className="space-y-3">
                            <input
                              value={editNoteTitle}
                              onChange={(e) => setEditNoteTitle(e.target.value)}
                              placeholder="Note title"
                              className={`w-full rounded-md border px-3 py-2 text-sm ${isDark ? "border-slate-700 bg-slate-800 text-white" : "border-stone-300 bg-white text-stone-900"}`}
                            />
                            <textarea
                              value={editNoteBody}
                              onChange={(e) => setEditNoteBody(e.target.value)}
                              placeholder="Note content (markdown supported)"
                              rows={4}
                              className={`w-full rounded-md border px-3 py-2 text-sm ${isDark ? "border-slate-700 bg-slate-800 text-white" : "border-stone-300 bg-white text-stone-900"}`}
                            />
                            <div className="flex gap-2">
                              <button
                                onClick={saveEditedNote}
                                disabled={editingNoteSaving}
                                className={`rounded-md px-3 py-1.5 text-xs font-semibold ${isDark ? "bg-emerald-600 text-white disabled:opacity-40" : "bg-emerald-600 text-white disabled:opacity-40"}`}
                              >
                                {editingNoteSaving ? "Saving..." : "Save"}
                              </button>
                              <button
                                onClick={cancelEditingNote}
                                className={`rounded-md px-3 py-1.5 text-xs font-semibold ${isDark ? "border border-slate-600 text-slate-300" : "border border-stone-300 text-stone-700"}`}
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
                                <button onClick={() => removeNote(note.id)} className={`text-xs font-medium ${isDark ? "text-rose-300" : "text-rose-700"}`}>Delete</button>
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

        {sceneEditorOpen ? (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/55 px-4 py-8">
            <div className={`max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-[1.6rem] border p-5 shadow-2xl ${isDark ? "border-white/10 bg-[#0b0f17] text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-emerald-300" : "text-emerald-700"}`}>Scene workspace</p>
                  <h3 className="mt-2 text-2xl font-semibold">{editingScene ? "Edit chapter scene" : "New chapter scene"}</h3>
                  <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Scenes live in the chapter file tree. LoreVia extracts metadata from labels like POV, Location, Characters, Goals, Conflict, and Plot Threads when you save.</p>
                </div>
                <button onClick={closeSceneEditor} className={`rounded-full px-3 py-1.5 text-sm ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>Close</button>
              </div>
              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <label className="text-sm">
                  <span className={`mb-2 block text-xs font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Title</span>
                  <input
                    value={sceneTitleDraft}
                    onChange={(event) => setSceneTitleDraft(event.target.value)}
                    placeholder="Scene title"
                    className={`w-full rounded-[0.95rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
                  />
                </label>
                <label className="text-sm">
                  <span className={`mb-2 block text-xs font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Optional chapter tag</span>
                  <select
                    value={sceneChapterDraft ?? ""}
                    onChange={(event) => setSceneChapterDraft(event.target.value ? Number(event.target.value) : null)}
                    className={`w-full rounded-[0.95rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
                  >
                    <option value="">Unassigned / decide later</option>
                    {(workspaceTree?.chapters ?? []).map((chapter) => (
                      <option key={chapter.chapter_number} value={chapter.chapter_number}>Chapter {chapter.chapter_number}</option>
                    ))}
                  </select>
                </label>
              </div>
              <label className="mt-4 block text-sm">
                <span className={`mb-2 block text-xs font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Description</span>
                <input
                  value={sceneDescriptionDraft}
                  onChange={(event) => setSceneDescriptionDraft(event.target.value)}
                  placeholder="Optional context for later"
                  className={`w-full rounded-[0.95rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
                />
              </label>
              <label className="mt-4 block text-sm">
                <span className={`mb-2 block text-xs font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>Scene body</span>
                <textarea
                  value={sceneBodyDraft}
                  onChange={(event) => setSceneBodyDraft(event.target.value)}
                  rows={14}
                  placeholder="Write the scene here..."
                  className={`w-full rounded-[1rem] border px-4 py-3 text-sm leading-7 ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
                />
              </label>
              <div className="mt-5 flex flex-wrap justify-end gap-3">
                <button onClick={closeSceneEditor} className={`rounded-full px-4 py-2 text-sm ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>Cancel</button>
                <button onClick={() => void saveScene()} disabled={sceneSaving || !sceneTitleDraft.trim() || !sceneBodyDraft.trim()} className="rounded-full bg-[linear-gradient(135deg,#0f766e,#115e59)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
                  {sceneSaving ? "Saving..." : editingScene ? "Save scene" : "Create scene"}
                </button>
              </div>
            </div>
          </div>
        ) : null}

        {showCompileDialog && writerWorkspace && manuscriptFrontMatter ? (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 px-4 py-8">
            <div className={`max-h-[92vh] w-full max-w-5xl overflow-y-auto rounded-[1.7rem] border p-6 shadow-2xl ${isDark ? "border-white/10 bg-[#0b0f17] text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-amber-300" : "text-amber-700"}`}>Compile manuscript</p>
                  <h3 className="mt-2 text-2xl font-semibold">Front page and submission metadata</h3>
                  <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>This template feeds the title page, headers, word count line, and export packaging before the manuscript compiles.</p>
                </div>
                <button onClick={() => setShowCompileDialog(false)} className={`rounded-full px-3 py-1.5 text-sm ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>Close</button>
              </div>

              <div className={`mt-5 rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50"}`}>
                <div className="flex flex-wrap items-center gap-4 text-sm">
                  <span>Format: <strong>{compileFormat.toUpperCase()}</strong></span>
                  <span>Automatic manuscript word count: <strong>{fullBookWordCount.toLocaleString()}</strong></span>
                  <span>Preset: <strong>{writerWorkspace.publishing.active_preset}</strong></span>
                </div>
                <label className={`mt-4 flex items-start gap-3 rounded-[1rem] border px-4 py-3 text-sm ${isDark ? "border-white/10 bg-black/20 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                  <input
                    type="checkbox"
                    checked={includeSceneMetadataOnExport}
                    onChange={(event) => setIncludeSceneMetadataOnExport(event.target.checked)}
                    className="mt-1 h-4 w-4 rounded border-stone-300"
                  />
                  <span>
                    <span className="block font-semibold">Include scene metadata</span>
                    <span className={`mt-1 block text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                      Turn this off for clean submission prose with scene breaks rendered as ***.
                    </span>
                  </span>
                </label>
              </div>

              <div className="mt-5 grid gap-4 md:grid-cols-2">
                <Field label="Author name">
                  <input value={manuscriptFrontMatter.author_name} onChange={(event) => updateFrontMatter("author_name", event.target.value)} className={inputClass(isDark)} />
                </Field>
                <Field label="Pen name">
                  <input value={manuscriptFrontMatter.pen_name} onChange={(event) => updateFrontMatter("pen_name", event.target.value)} className={inputClass(isDark)} />
                </Field>
                <Field label="Contact email">
                  <input value={manuscriptFrontMatter.contact_email} onChange={(event) => updateFrontMatter("contact_email", event.target.value)} className={inputClass(isDark)} />
                </Field>
                <Field label="Contact phone">
                  <input value={manuscriptFrontMatter.contact_phone} onChange={(event) => updateFrontMatter("contact_phone", event.target.value)} className={inputClass(isDark)} />
                </Field>
                <Field label="Book title">
                  <input value={manuscriptFrontMatter.title} onChange={(event) => updateFrontMatter("title", event.target.value)} className={inputClass(isDark)} />
                </Field>
                <Field label="Subtitle">
                  <input value={manuscriptFrontMatter.subtitle} onChange={(event) => updateFrontMatter("subtitle", event.target.value)} className={inputClass(isDark)} />
                </Field>
                <Field label="Header last name">
                  <input value={manuscriptFrontMatter.header_last_name} onChange={(event) => updateFrontMatter("header_last_name", event.target.value)} className={inputClass(isDark)} />
                </Field>
                <Field label="Header title">
                  <input value={manuscriptFrontMatter.header_title} onChange={(event) => updateFrontMatter("header_title", event.target.value)} className={inputClass(isDark)} />
                </Field>
              </div>

              <Field label="Contact address" className="mt-4">
                <textarea value={manuscriptFrontMatter.contact_address} onChange={(event) => updateFrontMatter("contact_address", event.target.value)} rows={3} className={textareaClass(isDark)} />
              </Field>

              <div className="mt-5 grid gap-4 lg:grid-cols-2">
                <Field label="Dedication">
                  <textarea value={manuscriptFrontMatter.dedication} onChange={(event) => updateFrontMatter("dedication", event.target.value)} rows={4} className={textareaClass(isDark)} />
                  <Toggle checked={manuscriptFrontMatter.include_dedication} onChange={(checked) => updateFrontMatter("include_dedication", checked)} isDark={isDark} label="Include in compile" />
                </Field>
                <Field label="Acknowledgments">
                  <textarea value={manuscriptFrontMatter.acknowledgments} onChange={(event) => updateFrontMatter("acknowledgments", event.target.value)} rows={4} className={textareaClass(isDark)} />
                  <Toggle checked={manuscriptFrontMatter.include_acknowledgments} onChange={(checked) => updateFrontMatter("include_acknowledgments", checked)} isDark={isDark} label="Include in compile" />
                </Field>
                <Field label="Epigraph">
                  <textarea value={manuscriptFrontMatter.epigraph} onChange={(event) => updateFrontMatter("epigraph", event.target.value)} rows={4} className={textareaClass(isDark)} />
                  <Toggle checked={manuscriptFrontMatter.include_epigraph} onChange={(checked) => updateFrontMatter("include_epigraph", checked)} isDark={isDark} label="Include in compile" />
                </Field>
                <Field label="Prologue page">
                  <textarea value={manuscriptFrontMatter.prologue} onChange={(event) => updateFrontMatter("prologue", event.target.value)} rows={4} className={textareaClass(isDark)} />
                  <Toggle checked={manuscriptFrontMatter.include_prologue} onChange={(checked) => updateFrontMatter("include_prologue", checked)} isDark={isDark} label="Include in compile" />
                </Field>
              </div>

              <div className="mt-6 flex flex-wrap justify-end gap-3">
                <button onClick={() => setShowCompileDialog(false)} className={`rounded-full px-4 py-2 text-sm ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>Cancel</button>
                <button onClick={() => void compileManuscript()} disabled={!!exporting || workspaceSaving} className="rounded-full bg-[linear-gradient(135deg,#1d4ed8,#1e40af)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">
                  {exporting ? "Compiling..." : `Compile ${compileFormat.toUpperCase()}`}
                </button>
              </div>
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}

function EditorToolbar({
  isDark,
  compact = false,
  characters = [],
}: {
  isDark: boolean
  compact?: boolean
  characters?: Character[]
}) {
  const [showMentionPicker, setShowMentionPicker] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const selectionRef = useRef<Range | null>(null)

  const run = (command: string, value?: string) => {
    document.execCommand(command, false, value)
  }

  const cacheSelection = () => {
    const selection = window.getSelection()
    if (!selection || selection.rangeCount === 0) return
    selectionRef.current = selection.getRangeAt(0).cloneRange()
  }

  const restoreSelection = () => {
    const selection = window.getSelection()
    if (!selection || !selectionRef.current) return
    selection.removeAllRanges()
    selection.addRange(selectionRef.current)
  }

  const insertLink = () => {
    const href = window.prompt("Enter a URL")
    if (!href) return
    const label = window.getSelection()?.toString().trim()
    if (label) {
      run("createLink", href)
      return
    }
    run("insertHTML", `<a href="${escapeAttribute(href)}" target="_blank" rel="noreferrer noopener">${escapeHtml(href)}</a>`)
  }

  const insertImage = () => {
    cacheSelection()
    fileInputRef.current?.click()
  }

  const insertMention = (name: string) => {
    run(
      "insertHTML",
      `<span class="mention-token" data-mention="${escapeAttribute(name)}">@${escapeHtml(name)}</span>&nbsp;`
    )
    setShowMentionPicker(false)
  }

  const shellClass = compact
    ? `border-b px-3 py-2 ${isDark ? "border-white/10 bg-[#0f131a]/85 backdrop-blur" : "border-stone-200 bg-[#f6f1e8]/90 backdrop-blur"}`
    : ""
  const groupClass = "flex flex-wrap items-center gap-1.5"
  const buttonClass = `rounded-md px-2.5 py-2 text-[11px] font-medium transition ${
    isDark ? "text-slate-200 hover:bg-white/8" : "text-stone-700 hover:bg-white"
  }`
  const dividerClass = isDark ? "h-5 w-px bg-white/10" : "h-5 w-px bg-stone-200"
  const mentionableCharacters = characters.slice(0, 8)

  return (
    <div className={`flex flex-wrap items-center justify-between gap-3 ${shellClass}`}>
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={(event) => {
          const file = event.target.files?.[0]
          if (!file) return
          const reader = new FileReader()
          reader.onload = () => {
            const result = typeof reader.result === "string" ? reader.result : ""
            if (!result) return
            restoreSelection()
            run("insertHTML", `<p><img src="${escapeAttribute(result)}" alt="${escapeAttribute(file.name || "Embedded image")}" /></p>`)
            event.target.value = ""
          }
          reader.readAsDataURL(file)
        }}
      />
      <div className={`${groupClass} ${compact ? "justify-start" : ""}`}>
        <button type="button" title="Heading" onMouseDown={(event) => { event.preventDefault(); cacheSelection() }} onClick={() => run("formatBlock", "<h2>")} className={buttonClass}>H</button>
        <button type="button" title="Bold (Ctrl+B)" onMouseDown={(event) => { event.preventDefault(); cacheSelection() }} onClick={() => run("bold")} className={buttonClass}>B</button>
        <button type="button" title="Italic (Ctrl+I)" onMouseDown={(event) => { event.preventDefault(); cacheSelection() }} onClick={() => run("italic")} className={buttonClass}>I</button>
        <span className={dividerClass} />
        <button type="button" title="Bulleted list" onMouseDown={(event) => { event.preventDefault(); cacheSelection() }} onClick={() => run("insertUnorderedList")} className={buttonClass}>List</button>
        <button type="button" title="Numbered list" onMouseDown={(event) => { event.preventDefault(); cacheSelection() }} onClick={() => run("insertOrderedList")} className={buttonClass}>1.</button>
        <button type="button" title="Quote" onMouseDown={(event) => { event.preventDefault(); cacheSelection() }} onClick={() => run("formatBlock", "<blockquote>")} className={buttonClass}>Quote</button>
        <span className={dividerClass} />
        <button type="button" title="Insert link" onMouseDown={(event) => { event.preventDefault(); cacheSelection() }} onClick={insertLink} className={buttonClass}>Link</button>
        <button type="button" title="Insert image" onMouseDown={(event) => { event.preventDefault(); cacheSelection() }} onClick={insertImage} className={buttonClass}>Image</button>
        <div className="relative">
          <button
            type="button"
            title="Mention character"
            onMouseDown={(event) => { event.preventDefault(); cacheSelection() }}
            onClick={() => setShowMentionPicker((current) => !current)}
            className={buttonClass}
          >
            @
          </button>
          {showMentionPicker && mentionableCharacters.length > 0 ? (
            <div
              className={`absolute left-0 top-full z-20 mt-2 w-52 rounded-xl border p-1 shadow-[0_18px_50px_-24px_rgba(15,23,42,0.4)] ${
                isDark ? "border-white/10 bg-[#0f172a]" : "border-stone-200 bg-white"
              }`}
            >
              {mentionableCharacters.map((character) => (
                <button
                  key={character.id}
                  type="button"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => insertMention(character.name)}
                  className={`block w-full rounded-lg px-3 py-2 text-left text-sm transition ${
                    isDark ? "text-slate-200 hover:bg-white/8" : "text-stone-700 hover:bg-stone-100"
                  }`}
                >
                  @{character.name}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      </div>
      <div className={groupClass}>
        <button type="button" title="Align left" onMouseDown={(event) => { event.preventDefault(); cacheSelection() }} onClick={() => run("justifyLeft")} className={buttonClass}>Left</button>
        <button type="button" title="Align center" onMouseDown={(event) => { event.preventDefault(); cacheSelection() }} onClick={() => run("justifyCenter")} className={buttonClass}>Center</button>
        <button type="button" title="Align right" onMouseDown={(event) => { event.preventDefault(); cacheSelection() }} onClick={() => run("justifyRight")} className={buttonClass}>Right</button>
        <span className={dividerClass} />
        <button type="button" title="Undo (Ctrl+Z)" onMouseDown={(event) => { event.preventDefault(); cacheSelection() }} onClick={() => run("undo")} className={buttonClass}>Undo</button>
        <button type="button" title="Redo (Ctrl+Y)" onMouseDown={(event) => { event.preventDefault(); cacheSelection() }} onClick={() => run("redo")} className={buttonClass}>Redo</button>
      </div>
    </div>
  )
}

function RichTextEditor({
  html,
  onChange,
  placeholder,
  className,
  style,
  contentClassName,
  editorKey,
  onFocus,
  onBlur,
  onCharacterClick,
}: {
  html: string
  onChange: (html: string, text: string) => void
  placeholder?: string
  className?: string
  style?: CSSProperties
  contentClassName?: string
  editorKey?: string
  onFocus?: () => void
  onBlur?: () => void
  onCharacterClick?: (characterName: string) => void
}) {
  const ref = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    if (!ref.current) return
    if (ref.current.innerHTML !== html) {
      ref.current.innerHTML = html || "<p></p>"
    }
  }, [html])

  return (
    <div
      ref={ref}
      contentEditable
      suppressContentEditableWarning
      data-editor-key={editorKey}
      data-placeholder={placeholder}
      onFocus={onFocus}
      onBlur={onBlur}
      onInput={(event) => {
        const nextHtml = sanitizeRichTextHtml(event.currentTarget.innerHTML, onCharacterClick)
        const nextText = htmlToPlainText(nextHtml)
        onChange(nextHtml, nextText)
      }}
      className={`${className ?? ""} ${contentClassName ?? ""} manuscript-editor`}
      style={style}
    />
  )
}

function InfoList({
  title,
  items,
  emptyLabel,
  isDark,
}: {
  title: string
  items: string[]
  emptyLabel: string
  isDark: boolean
}) {
  return (
    <div>
      <p className={`text-[11px] font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>{title}</p>
      <div className="mt-2 space-y-2">
        {items.length > 0 ? items.map((item, index) => (
          <p key={`${item}-${index}`} className={`text-sm ${isDark ? "text-slate-200" : "text-stone-700"}`}>{item}</p>
        )) : <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{emptyLabel}</p>}
      </div>
    </div>
  )
}

function Field({
  label,
  children,
  className,
}: {
  label: string
  children: ReactNode
  className?: string
}) {
  return (
    <label className={className}>
      <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{label}</span>
      {children}
    </label>
  )
}

function Toggle({
  checked,
  onChange,
  isDark,
  label,
}: {
  checked: boolean
  onChange: (checked: boolean) => void
  isDark: boolean
  label: string
}) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      className={`mt-3 rounded-full px-3 py-1.5 text-xs font-semibold ${checked ? isDark ? "bg-emerald-500/15 text-emerald-200" : "bg-emerald-50 text-emerald-700" : isDark ? "bg-white/10 text-slate-300" : "bg-stone-100 text-stone-700"}`}
    >
      {label}: {checked ? "On" : "Off"}
    </button>
  )
}

function MetricCard({
  label,
  value,
  note,
  isDark,
}: {
  label: string
  value: string
  note: string
  isDark: boolean
}) {
  return (
    <div className={`rounded-[1.2rem] border px-4 py-4 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/80"}`}>
      <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{label}</p>
      <p className={`mt-3 text-2xl font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{value}</p>
      <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{note}</p>
    </div>
  )
}

function ProgressStrip({
  label,
  progress,
  fallback,
  isDark,
}: {
  label: string
  progress: number | null
  fallback: string
  isDark: boolean
}) {
  const fill = Math.max(0, Math.min(100, progress ?? 0))

  return (
    <div className={`rounded-[1.1rem] border px-4 py-3 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-stone-50/80"}`}>
      <div className="flex items-center justify-between gap-3">
        <p className={`text-[11px] font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{label}</p>
        <p className={`text-xs font-semibold ${isDark ? "text-slate-300" : "text-stone-600"}`}>{progress !== null ? `${fill}%` : "No target"}</p>
      </div>
      <div className={`mt-3 h-2 overflow-hidden rounded-full ${isDark ? "bg-white/10" : "bg-stone-200"}`}>
        <div
          className="h-full rounded-full bg-[linear-gradient(135deg,#0891b2,#2563eb)] transition-[width]"
          style={{ width: `${progress !== null ? fill : 18}%` }}
        />
      </div>
      <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>
        {progress !== null ? "You are moving toward the active target." : fallback}
      </p>
    </div>
  )
}

function countWords(text: string) {
  return text.trim() ? text.trim().split(/\s+/).length : 0
}

function inputClass(isDark: boolean) {
  return `w-full rounded-[0.95rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`
}

function textareaClass(isDark: boolean) {
  return `w-full rounded-[1rem] border px-4 py-3 text-sm leading-6 ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`
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
