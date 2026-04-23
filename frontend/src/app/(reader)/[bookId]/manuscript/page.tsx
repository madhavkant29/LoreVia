"use client"

import type { CSSProperties } from "react"
import { useEffect, useMemo, useRef, useState } from "react"
import Link from "next/link"
import { useParams } from "next/navigation"

import { booksApi } from "@/lib/api/books"
import { intelligenceApi } from "@/lib/api/intelligence"
import { readerApi } from "@/lib/api/reader"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import type { Book, BookNote, ChapterVersion, PreWritingCheck } from "@/types/book"
import type { Character } from "@/types/character"
import type { AdvisorSuggestion, EditorialReview, EditorialReviewPassage, ManuscriptSynopsis, VoiceConsistencyReview } from "@/types/intelligence"
import type { ChapterListResponse, PlotThread, SearchResult } from "@/types/reader"

type EditorMode = "chapter" | "book"
type BookDraftMap = Record<number, { title: string; text: string; html: string }>
type RightPane = "insights" | "notes"

export default function ManuscriptPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  const [book, setBook] = useState<Book | null>(null)
  const [characters, setCharacters] = useState<Character[]>([])
  const [chapterList, setChapterList] = useState<ChapterListResponse | null>(null)
  const [selectedChapter, setSelectedChapter] = useState<number | null>(null)
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
  const [suggestions, setSuggestions] = useState<AdvisorSuggestion[]>([])
  const [plotThreads, setPlotThreads] = useState<PlotThread[]>([])
  const [preWritingCheck, setPreWritingCheck] = useState<PreWritingCheck | null>(null)
  const [chapterVersions, setChapterVersions] = useState<ChapterVersion[]>([])
  const [recallQuery, setRecallQuery] = useState("")
  const [recallResults, setRecallResults] = useState<SearchResult[]>([])
  const [recallCharacter, setRecallCharacter] = useState<Character | null>(null)
  const [recallLoading, setRecallLoading] = useState(false)
  const [synopsis, setSynopsis] = useState<ManuscriptSynopsis | null>(null)
  const [editorMode, setEditorMode] = useState<EditorMode>("chapter")
  const [fontSize, setFontSize] = useState(12)
  const [fontFamily, setFontFamily] = useState<"times" | "georgia" | "sans">("times")
  const [lineHeight, setLineHeight] = useState(1.8)
  const [showPageGuides, setShowPageGuides] = useState(true)
  const [firstLineIndent, setFirstLineIndent] = useState(true)
  const [showLeftRail, setShowLeftRail] = useState(false)
  const [showRightRail, setShowRightRail] = useState(false)
  const [activeRightPane, setActiveRightPane] = useState<RightPane>("insights")
  const [fullBookLoading, setFullBookLoading] = useState(false)
  const [bookDrafts, setBookDrafts] = useState<BookDraftMap>({})
  const [exporting, setExporting] = useState<"pdf" | "docx" | null>(null)
  const [jumpTarget, setJumpTarget] = useState<number | null>(null)
  const [activeFindIndex, setActiveFindIndex] = useState(0)
  const [replaceQuery, setReplaceQuery] = useState("")
  const [replaceValue, setReplaceValue] = useState("")
  const [gotoPageInput, setGotoPageInput] = useState("")
  const [showPageSetup, setShowPageSetup] = useState(false)
  const [showSearchTools, setShowSearchTools] = useState(false)
  const [notes, setNotes] = useState<BookNote[]>([])
  const [notesLoading, setNotesLoading] = useState(true)
  const [savingNote, setSavingNote] = useState(false)
  const [noteScope, setNoteScope] = useState<"chapter" | "book">("chapter")
  const [noteTitle, setNoteTitle] = useState("")
  const [noteBody, setNoteBody] = useState("")

  const chapterRefs = useRef<Record<number, HTMLDivElement | null>>({})
  const searchInputRef = useRef<HTMLInputElement | null>(null)

  const nextChapterNumber = useMemo(() => {
    const numbers = chapterList?.chapters.map((chapter) => chapter.number) ?? []
    return numbers.length ? Math.max(...numbers) + 1 : 1
  }, [chapterList])

  const activeChapterNumber = selectedChapter ?? nextChapterNumber

  const sheetStyle = {
    fontSize: `${fontSize}pt`,
    lineHeight: String(lineHeight),
    fontFamily: fontFamily === "times" ? '"Times New Roman", Georgia, serif' : fontFamily === "georgia" ? 'Georgia, "Times New Roman", serif' : 'Inter, Arial, sans-serif',
  } as const

  const chapterWordCount = useMemo(() => countWords(text), [text])
  const chapterApproxPages = useMemo(() => Math.max(1, Math.ceil(chapterWordCount / 500)), [chapterWordCount])
  const fullBookWordCount = useMemo(() => Object.values(bookDrafts).reduce((sum, draft) => sum + countWords(draft.text), 0), [bookDrafts])
  const fullBookApproxPages = useMemo(() => Math.max(1, Math.ceil(fullBookWordCount / 500)), [fullBookWordCount])
  const desktopLayoutClass = showLeftRail && showRightRail
    ? "xl:grid-cols-[17rem_minmax(0,1fr)_21rem]"
    : showLeftRail
      ? "xl:grid-cols-[17rem_minmax(0,1fr)]"
      : showRightRail
        ? "xl:grid-cols-[minmax(0,1fr)_21rem]"
        : "xl:grid-cols-1"
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
  const openRightPane = (pane: RightPane) => {
    if (showRightRail && activeRightPane === pane) {
      setShowRightRail(false)
      return
    }
    setActiveRightPane(pane)
    setShowRightRail(true)
  }

  const loadBase = async () => {
    const [bookData, chapters, characterData, synopsisData] = await Promise.all([
      booksApi.get(bookId),
      readerApi.getChapterList(bookId),
      booksApi.getCharacters(bookId).catch(() => []),
      intelligenceApi.synopsis(bookId, "minimal").catch(() => null),
    ])
    setBook(bookData)
    setChapterList(chapters)
    setCharacters(characterData)
    setSynopsis(synopsisData)
    if (selectedChapter === null && chapters.chapters.length > 0) {
      setSelectedChapter(chapters.chapters[chapters.chapters.length - 1].number)
    }
  }

  const loadNotes = async () => {
    setNotesLoading(true)
    try {
      const noteData = await booksApi.getBookNotes(bookId)
      setNotes(noteData)
    } finally {
      setNotesLoading(false)
    }
  }

  useEffect(() => {
    loadBase().finally(() => setLoading(false))
  }, [bookId])

  useEffect(() => {
    loadNotes().catch(() => setNotes([]))
  }, [bookId])

  useEffect(() => {
    if (selectedChapter === null) {
      setChapterTitle(`Chapter ${nextChapterNumber}`)
      setText("")
      setHtml(textToHtml(""))
      setReview(null)
      setReviewPassages([])
      setVoiceReview(null)
      setVoiceCharacters([])
      return
    }
    const chapterMeta = chapterList?.chapters.find((item) => item.number === selectedChapter)
    readerApi.getChapter(bookId, selectedChapter).then((chapter) => {
      const title = chapter.chapter_title || chapterMeta?.title || `Chapter ${selectedChapter}`
      const chapterText = chapter.text_content || ""
      const chapterHtml = chapter.html_content || textToHtml(chapterText)
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
      setStatusMessage(null)
    }).catch(() => {
      setChapterTitle(chapterMeta?.title || `Chapter ${selectedChapter}`)
      setText("")
      setHtml(textToHtml(""))
    })
  }, [bookId, chapterList, nextChapterNumber, selectedChapter])

  useEffect(() => {
    booksApi.getPreWritingCheck(bookId, activeChapterNumber).then(setPreWritingCheck).catch(() => {})
  }, [activeChapterNumber, bookId])

  useEffect(() => {
    if (selectedChapter === null) {
      setChapterVersions([])
      return
    }
    booksApi.getChapterVersions(bookId, selectedChapter).then(setChapterVersions).catch(() => setChapterVersions([]))
  }, [bookId, selectedChapter])

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

  const runAutomaticChecks = async (chapterNum: number, content: string) => {
    const [editorial, voice, suggestionResult, threads, synopsisResult] = await Promise.all([
      intelligenceApi.editorialReview(bookId, content, chapterNum),
      intelligenceApi.voiceConsistencyReview(bookId, content, chapterNum),
      intelligenceApi.advisorSuggestions(bookId),
      readerApi.getPlotThreads(bookId, chapterNum),
      intelligenceApi.synopsis(bookId, "minimal").catch(() => null),
    ])
    setReview(editorial.review)
    setReviewPassages(editorial.retrieved_passages)
    setVoiceReview(voice.review)
    setVoiceCharacters(voice.characters_reviewed)
    setSuggestions(suggestionResult.suggestions.filter((item) => item.chapter_ref === null || item.chapter_ref <= chapterNum).slice(0, 6))
    setPlotThreads(threads.filter((thread) => thread.status !== "resolved").slice(0, 8))
    if (synopsisResult) setSynopsis(synopsisResult)
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
      setBookDrafts((current) => ({
        ...current,
        [importedChapter]: { title: chapterTitle.trim() || `Chapter ${importedChapter}`, text, html },
      }))
      await runAutomaticChecks(importedChapter, text)
      setStatusMessage(`Saved chapter ${importedChapter}. Continuity, synopsis, and thread context refreshed.`)
    } catch {
      setStatusMessage("Save failed. Please check the chapter number and try again.")
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

  const exportManuscript = async (format: "pdf" | "docx") => {
    setExporting(format)
    try {
      const blob = await booksApi.exportManuscript(bookId, format)
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = `${(book?.title || "lorevia").replace(/\s+/g, "-").toLowerCase()}-manuscript.${format}`
      link.click()
      URL.revokeObjectURL(url)
    } finally {
      setExporting(null)
    }
  }

  const saveNote = async () => {
    if (!noteBody.trim()) return
    setSavingNote(true)
    try {
      const saved = await booksApi.saveBookNote(bookId, {
        chapterNumber: noteScope === "chapter" ? activeChapterNumber : null,
        title: noteTitle.trim() || null,
        body: noteBody,
      })
      setNotes((current) => [saved, ...current.filter((note) => note.id !== saved.id)])
      setNoteTitle("")
      setNoteBody("")
      setStatusMessage(`Saved note${saved.chapter_number ? ` for chapter ${saved.chapter_number}` : ""}.`)
    } finally {
      setSavingNote(false)
    }
  }

  const removeNote = async (noteId: string) => {
    await booksApi.deleteBookNote(bookId, noteId)
    setNotes((current) => current.filter((note) => note.id !== noteId))
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
      <div className="mx-auto max-w-[1600px] px-4 pb-12 pt-5 sm:px-6 lg:px-8">
        <div className={`rounded-[2rem] border px-5 py-5 shadow-[0_22px_70px_-55px_rgba(15,23,42,0.2)] ${isDark ? "border-white/10 bg-white/[0.03]" : "border-white/80 bg-white/92"}`}>
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <p className={`text-[11px] font-semibold uppercase tracking-[0.32em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Manuscript editor</p>
              <h1 className={`mt-2 font-serif text-4xl leading-tight ${isDark ? "text-white" : "text-stone-950"}`}>{book?.title}</h1>
              <p className={`mt-2 max-w-2xl text-sm leading-7 ${isDark ? "text-slate-400" : "text-stone-600"}`}>
                A quiet drafting space with A4 pages, chapter and full-book modes, and continuity jumps that stay close when you need them.
              </p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link href={`/${bookId}`} className={`rounded-full border px-4 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>Overview</Link>
              <Link href={`/${bookId}/advisor`} className="rounded-full bg-stone-900 px-4 py-2 text-sm font-semibold text-white">Story Advisor</Link>
              <button onClick={printManuscript} className={`rounded-full border px-4 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                Print
              </button>
              <button onClick={() => void exportManuscript("docx")} disabled={!!exporting} className={`rounded-full border px-4 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                {exporting === "docx" ? "Exporting..." : "Download Word"}
              </button>
              <button onClick={() => void exportManuscript("pdf")} disabled={!!exporting} className={`rounded-full border px-4 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                {exporting === "pdf" ? "Exporting..." : "Download PDF"}
              </button>
              <button onClick={() => setShowLeftRail((value) => !value)} className={`rounded-full border px-4 py-2 text-sm font-medium ${showLeftRail ? isDark ? "border-indigo-300/40 bg-indigo-400/15 text-white" : "border-violet-300 bg-violet-50 text-stone-900" : isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                {showLeftRail ? "Hide chapters" : "Chapters"}
              </button>
              <button onClick={() => openRightPane("insights")} className={`rounded-full border px-4 py-2 text-sm font-medium ${showRightRail && activeRightPane === "insights" ? isDark ? "border-emerald-300/40 bg-emerald-400/15 text-white" : "border-emerald-300 bg-emerald-50 text-stone-900" : isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                {showRightRail && activeRightPane === "insights" ? "Hide insights" : "Insights"}
              </button>
              <button onClick={() => openRightPane("notes")} className={`rounded-full border px-4 py-2 text-sm font-medium ${showRightRail && activeRightPane === "notes" ? isDark ? "border-amber-300/40 bg-amber-400/15 text-white" : "border-amber-300 bg-amber-50 text-stone-900" : isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                {showRightRail && activeRightPane === "notes" ? "Hide notes" : "Notes"}
              </button>
            </div>
          </div>
        </div>

        <div className={`mt-5 grid gap-5 ${desktopLayoutClass}`}>
          {showLeftRail ? (
          <aside className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-white/80"}`}>
            <div className="flex items-center justify-between">
              <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Chapters</p>
              <button
                onClick={() => {
                  setSelectedChapter(null)
                  setReplaceExisting(false)
                  setChapterTitle(`Chapter ${nextChapterNumber}`)
                  setText("")
                  setHtml(textToHtml(""))
                  setReview(null)
                  setReviewPassages([])
                }}
                className={`rounded-full px-3 py-1.5 text-xs ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}
              >
                New chapter
              </button>
            </div>
            <div className="mt-4 space-y-2">
              {(chapterList?.chapters ?? []).map((chapter) => {
                const active = selectedChapter === chapter.number
                return (
                  <button
                    key={chapter.number}
                    onClick={() => {
                      setSelectedChapter(chapter.number)
                      setReplaceExisting(true)
                    }}
                    className={`w-full rounded-[1rem] border px-3 py-3 text-left text-sm transition ${active ? isDark ? "border-indigo-400/40 bg-indigo-400/15 text-white" : "border-violet-300 bg-violet-50 text-stone-900" : isDark ? "border-white/10 bg-white/[0.03] text-slate-300 hover:bg-white/10" : "border-stone-200 bg-stone-50 text-stone-700 hover:bg-white"}`}
                  >
                    <p className="font-semibold">Chapter {chapter.number}</p>
                    <p className="mt-1 line-clamp-2 text-xs opacity-75">{chapter.title || "Untitled"}</p>
                  </button>
                )
              })}
            </div>
            {chapterVersions.length > 0 ? (
              <div className={`mt-4 rounded-[1rem] border p-3 ${isDark ? "border-white/10 bg-black/20" : "border-stone-200 bg-white"}`}>
                <p className={`text-[11px] font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Version history</p>
                <div className="mt-2 space-y-2">
                  {chapterVersions.map((version) => (
                    <div key={version.id} className={`rounded-[0.85rem] px-3 py-2 ${isDark ? "bg-white/[0.03]" : "bg-stone-50"}`}>
                      <p className={`text-sm font-medium ${isDark ? "text-white" : "text-stone-900"}`}>{version.note || "Previous draft"}</p>
                      <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                        {new Date(version.created_at).toLocaleString()} {version.word_count ? `· ${version.word_count} words` : ""}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </aside>
          ) : null}

          <section className={`rounded-[1.8rem] border p-5 ${!showLeftRail && !showRightRail ? "xl:mx-auto xl:max-w-[980px]" : ""} ${isDark ? "border-white/10 bg-black/80" : "border-stone-200 bg-[#faf8f4]"}`}>
            {preWritingCheck ? (
              <div className={`mb-5 rounded-[1.3rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-emerald-300" : "text-emerald-700"}`}>Before you start Chapter {preWritingCheck.upcoming_chapter}</p>
                    <p className={`mt-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>Here’s what’s happening right now in the manuscript.</p>
                  </div>
                  <div className="flex gap-2">
                    <Link href={`/${bookId}/plot-threads`} className={`rounded-full px-3 py-1.5 text-xs font-semibold ${isDark ? "bg-white/10 text-slate-200" : "bg-white text-stone-700"}`}>Threads</Link>
                    <Link href={`/${bookId}/timeline`} className={`rounded-full px-3 py-1.5 text-xs font-semibold ${isDark ? "bg-white/10 text-slate-200" : "bg-white text-stone-700"}`}>Timeline</Link>
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
                    <select value={fontSize} onChange={(event) => setFontSize(Number(event.target.value))} className={`ml-2 rounded-lg border px-2 py-1 text-sm ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}>
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

            <div className={`mb-5 rounded-[1.2rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-white"}`}>
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
                <div className="flex flex-wrap items-center gap-2">
                  <button onClick={() => setShowPageSetup((value) => !value)} className={`rounded-full px-3 py-1.5 text-xs font-medium ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>
                    {showPageSetup ? "Hide page setup" : "Page setup"}
                  </button>
                  <button onClick={() => setShowSearchTools((value) => !value)} className={`rounded-full px-3 py-1.5 text-xs font-medium ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>
                    {showSearchTools ? "Hide search tools" : "Find and jump"}
                  </button>
                  <button onClick={() => setShowLeftRail((value) => !value)} className={`rounded-full px-3 py-1.5 text-xs font-medium ${showLeftRail ? isDark ? "bg-indigo-400/15 text-white" : "bg-violet-100 text-stone-900" : isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>
                    {showLeftRail ? "Hide chapters" : "Show chapters"}
                  </button>
                  <button onClick={() => openRightPane("insights")} className={`rounded-full px-3 py-1.5 text-xs font-medium ${showRightRail && activeRightPane === "insights" ? isDark ? "bg-emerald-400/15 text-white" : "bg-emerald-100 text-stone-900" : isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>
                    {showRightRail && activeRightPane === "insights" ? "Hide insights" : "Show insights"}
                  </button>
                  <button onClick={() => openRightPane("notes")} className={`rounded-full px-3 py-1.5 text-xs font-medium ${showRightRail && activeRightPane === "notes" ? isDark ? "bg-amber-400/15 text-white" : "bg-amber-100 text-stone-900" : isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>
                    {showRightRail && activeRightPane === "notes" ? "Hide notes" : "Show notes"}
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
                    <select value={fontSize} onChange={(event) => setFontSize(Number(event.target.value))} className={`ml-2 rounded-lg border px-2 py-1 text-sm ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}>
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

            {editorMode === "chapter" ? (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <input
                      type="number"
                      min={1}
                      value={activeChapterNumber}
                      onChange={(e) => setSelectedChapter(e.target.value ? parseInt(e.target.value) : null)}
                      className={`w-28 rounded-[0.9rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-100" : "border-stone-200 bg-stone-50 text-stone-900"}`}
                    />
                    <input
                      type="text"
                      value={chapterTitle}
                      onChange={(e) => {
                        setChapterTitle(e.target.value)
                        setBookDrafts((current) => ({
                          ...current,
                          [activeChapterNumber]: { title: e.target.value, text, html },
                        }))
                      }}
                      placeholder="Chapter title"
                      className={`min-w-[18rem] flex-1 rounded-[0.9rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-100" : "border-stone-200 bg-stone-50 text-stone-900"}`}
                    />
                  </div>
                  <button
                    onClick={saveCurrentChapter}
                    disabled={saving || !text.trim()}
                    className="rounded-[1rem] bg-[linear-gradient(135deg,#0f766e,#115e59)] px-5 py-3 text-sm font-semibold text-white transition disabled:opacity-40"
                  >
                    {saving ? "Saving..." : "Save chapter"}
                  </button>
                </div>
                <label className={`flex items-center gap-2 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                    <input type="checkbox" checked={replaceExisting || selectedChapter !== null} onChange={(e) => setReplaceExisting(e.target.checked)} />
                    Replace existing chapter
                </label>

                <div className={`relative mx-auto w-full max-w-[210mm] overflow-hidden rounded-[1.25rem] border shadow-[0_24px_80px_-55px_rgba(15,23,42,0.25)] ${isDark ? "border-white/10 bg-[#101010]" : "border-[#d8d0c4] bg-[#fdfcf9]"}`}>
                  {showPageGuides ? (
                    <div
                      aria-hidden
                      className={`pointer-events-none absolute inset-0 ${isDark ? "opacity-20" : "opacity-35"}`}
                      style={{
                        backgroundImage: `repeating-linear-gradient(to bottom, transparent 0, transparent calc(297mm - 1px), ${isDark ? "rgba(255,255,255,0.08)" : "rgba(15,23,42,0.08)"} calc(297mm - 1px), ${isDark ? "rgba(255,255,255,0.08)" : "rgba(15,23,42,0.08)"} 297mm)`,
                      }}
                    />
                  ) : null}
                  <div className={`border-b px-5 py-3 ${isDark ? "border-white/10 bg-white/[0.02]" : "border-[#e6dfd4] bg-[#f7f3ed]"}`}>
                    <EditorToolbar isDark={isDark} />
                  </div>
                  <RichTextEditor
                    html={html}
                    onChange={(nextHtml, nextText) => {
                      setHtml(nextHtml)
                      setText(nextText)
                      setBookDrafts((current) => ({
                        ...current,
                        [activeChapterNumber]: { title: chapterTitle, text: nextText, html: nextHtml },
                      }))
                    }}
                    placeholder="Write or paste the chapter here..."
                    style={{ ...sheetStyle, textIndent: firstLineIndent ? "1.5em" : "0" }}
                    className={`relative min-h-[297mm] w-full border-0 bg-transparent px-[20mm] py-[24mm] outline-none ${isDark ? "text-slate-100 placeholder:text-slate-500" : "text-stone-900 placeholder:text-stone-400"}`}
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
                      className={`relative mx-auto w-full max-w-[210mm] overflow-hidden rounded-[1.25rem] border shadow-[0_24px_80px_-55px_rgba(15,23,42,0.25)] ${jumpTarget === chapter.number ? isDark ? "border-teal-400/40 bg-[#101010]" : "border-teal-300 bg-[#fdfcf9]" : isDark ? "border-white/10 bg-[#101010]" : "border-[#d8d0c4] bg-[#fdfcf9]"}`}
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
                      <div className={`mb-4 border-b px-[20mm] py-4 ${isDark ? "border-white/10 bg-white/[0.02]" : "border-[#e6dfd4] bg-[#f7f3ed]"}`}>
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Chapter {chapter.number}</p>
                          <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{countWords(draft.text).toLocaleString()} words · ~{Math.max(1, Math.ceil(countWords(draft.text) / 500))} pages</p>
                        </div>
                        <button
                          onClick={() => void saveChapterDraft(chapter.number, draft)}
                          disabled={saving || !draft.text.trim()}
                          className="rounded-full bg-[linear-gradient(135deg,#0f766e,#115e59)] px-4 py-2 text-xs font-semibold text-white disabled:opacity-40"
                        >
                          Save this chapter
                        </button>
                      </div>
                      </div>
                      <input
                        type="text"
                        value={draft.title}
                        onChange={(event) => setBookDrafts((current) => ({
                          ...current,
                          [chapter.number]: {
                            title: event.target.value,
                            text: current[chapter.number]?.text ?? "",
                            html: current[chapter.number]?.html ?? draft.html,
                          },
                        }))}
                        className={`mb-4 mt-5 w-full border-0 bg-transparent px-[20mm] text-2xl font-semibold outline-none ${isDark ? "text-white" : "text-stone-950"}`}
                      />
                      <div className={`border-y px-[20mm] py-3 ${isDark ? "border-white/10 bg-white/[0.02]" : "border-[#e6dfd4] bg-[#f7f3ed]"}`}>
                        <EditorToolbar isDark={isDark} compact />
                      </div>
                      <RichTextEditor
                        html={draft.html}
                        onChange={(nextHtml, nextText) => setBookDrafts((current) => ({
                          ...current,
                          [chapter.number]: {
                            title: current[chapter.number]?.title ?? draft.title,
                            text: nextText,
                            html: nextHtml,
                          },
                        }))}
                        placeholder="Draft this chapter..."
                        style={{ ...sheetStyle, textIndent: firstLineIndent ? "1.5em" : "0" }}
                        className={`relative min-h-[240mm] w-full border-0 bg-transparent px-[20mm] py-[22mm] outline-none ${isDark ? "text-slate-100 placeholder:text-slate-500" : "text-stone-900 placeholder:text-stone-400"}`}
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
              <button
                onClick={editorMode === "chapter" ? saveCurrentChapter : saveFullBook}
                disabled={saving || (editorMode === "chapter" ? !text.trim() : Object.values(bookDrafts).every((draft) => !draft.text.trim()))}
                className="rounded-[1rem] bg-[linear-gradient(135deg,#0f766e,#115e59)] px-5 py-3 text-sm font-semibold text-white transition disabled:opacity-40"
              >
                {saving ? "Saving..." : editorMode === "chapter" ? "Save chapter" : "Save full book"}
              </button>
            </div>
            {statusMessage ? <p className={`mt-3 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{statusMessage}</p> : null}
          </section>

          {showRightRail ? (
          <aside className="space-y-4">
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
                        <p className="font-semibold">Pages {item.startPage}{item.endPage > item.startPage ? `–${item.endPage}` : ""}</p>
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
                      <p className="font-semibold">{issue.title}</p>
                      <p className="mt-1 text-xs leading-5 opacity-80">{issue.description}</p>
                      {issue.suggestion ? <p className="mt-2 text-xs font-medium opacity-90">{issue.suggestion}</p> : null}
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
                  {voiceReview.issues.length > 0 ? voiceReview.issues.map((issue, index) => (
                    <div key={`${issue.character_name}-${issue.title}-${index}`} className={`rounded-[1rem] border px-3 py-3 text-sm ${isDark ? "border-rose-500/20 bg-rose-500/10 text-slate-200" : "border-rose-200 bg-rose-50 text-stone-700"}`}>
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-semibold">{issue.character_name}: {issue.title}</p>
                        <span className={`rounded-full px-2 py-1 text-[10px] uppercase tracking-[0.16em] ${isDark ? "bg-white/10 text-slate-300" : "bg-white text-stone-600"}`}>{issue.severity}</span>
                      </div>
                      <p className="mt-2 text-xs leading-5 opacity-90">{issue.description}</p>
                      {issue.evidence ? <p className="mt-2 text-xs opacity-80">Evidence: {issue.evidence}</p> : null}
                      {issue.suggestion ? <p className="mt-2 text-xs opacity-90">Suggestion: {issue.suggestion}</p> : null}
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
                      <p className="font-semibold">Chapter {passage.chapter_num}{passage.chapter_title ? ` — ${passage.chapter_title}` : ""}{typeof passage.chunk_index === "number" ? ` · chunk ${passage.chunk_index}` : ""}</p>
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
                    <Link href="/notes" className={`rounded-full px-3 py-1.5 text-xs font-semibold ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>All notes</Link>
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
                    <textarea
                      value={noteBody}
                      onChange={(event) => setNoteBody(event.target.value)}
                      placeholder={noteScope === "chapter" ? `Add a note for chapter ${activeChapterNumber}` : "Add a book-level note"}
                      rows={6}
                      className={`w-full rounded-[1rem] border px-3 py-3 text-sm leading-6 outline-none ${isDark ? "border-white/10 bg-black text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"}`}
                    />
                    <button
                      onClick={saveNote}
                      disabled={savingNote || !noteBody.trim()}
                      className="rounded-[1rem] bg-[linear-gradient(135deg,#d97706,#b45309)] px-4 py-3 text-sm font-semibold text-white transition disabled:opacity-40"
                    >
                      {savingNote ? "Saving..." : `Save ${noteScope === "chapter" ? "chapter" : "book"} note`}
                    </button>
                  </div>
                </div>

                <div className={`rounded-[1.6rem] border p-4 ${isDark ? "border-white/10 bg-white/5" : "border-stone-200 bg-white/80"}`}>
                  <p className={`text-xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Chapter-linked notes</p>
                  <div className="mt-3 space-y-2">
                    {notesLoading ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>Loading notes...</p> : null}
                    {!notesLoading && chapterLinkedNotes.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No notes saved for this chapter yet.</p> : null}
                    {chapterLinkedNotes.map((note) => (
                      <div key={note.id} className={`rounded-[1rem] border px-3 py-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-stone-50"}`}>
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{note.title || `Chapter ${note.chapter_number} note`}</p>
                            <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{new Date(note.updated_at).toLocaleString()}</p>
                          </div>
                          <button onClick={() => removeNote(note.id)} className={`text-xs font-medium ${isDark ? "text-rose-300" : "text-rose-700"}`}>Delete</button>
                        </div>
                        <p className={`mt-3 whitespace-pre-wrap text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{note.body}</p>
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
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{note.title || "General book note"}</p>
                            <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{new Date(note.updated_at).toLocaleString()}</p>
                          </div>
                          <button onClick={() => removeNote(note.id)} className={`text-xs font-medium ${isDark ? "text-rose-300" : "text-rose-700"}`}>Delete</button>
                        </div>
                        <p className={`mt-3 whitespace-pre-wrap text-sm leading-6 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{note.body}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
          </aside>
          ) : null}
        </div>
      </div>
    </div>
  )
}

function EditorToolbar({ isDark, compact = false }: { isDark: boolean; compact?: boolean }) {
  const run = (command: string, value?: string) => {
    document.execCommand(command, false, value)
  }

  const buttonClass = `rounded-md border px-3 py-2 text-xs font-medium transition ${isDark ? "border-white/10 bg-white/[0.03] text-slate-200 hover:bg-white/[0.08]" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`

  return (
    <div className={`mb-5 flex flex-wrap items-center gap-x-6 gap-y-3 ${compact ? "justify-start" : "justify-between"}`}>
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" title="Bold (Ctrl+B)" onClick={() => run("bold")} className={buttonClass}>Bold</button>
        <button type="button" title="Italic (Ctrl+I)" onClick={() => run("italic")} className={buttonClass}>Italic</button>
        <button type="button" title="Underline (Ctrl+U)" onClick={() => run("underline")} className={buttonClass}>Underline</button>
        <button type="button" title="Strikethrough" onClick={() => run("strikeThrough")} className={buttonClass}>Strike</button>
        <button type="button" title="Bulleted list" onClick={() => run("insertUnorderedList")} className={buttonClass}>Bullets</button>
        <button type="button" title="Numbered list" onClick={() => run("insertOrderedList")} className={buttonClass}>Numbers</button>
        <button type="button" title="Block quote" onClick={() => run("formatBlock", "<blockquote>")} className={buttonClass}>Quote</button>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <button type="button" title="Heading 1" onClick={() => run("formatBlock", "<h1>")} className={buttonClass}>H1</button>
        <button type="button" title="Heading 2" onClick={() => run("formatBlock", "<h2>")} className={buttonClass}>H2</button>
        <button type="button" title="Paragraph" onClick={() => run("formatBlock", "<p>")} className={buttonClass}>Body</button>
        <button type="button" title="Align left" onClick={() => run("justifyLeft")} className={buttonClass}>Left</button>
        <button type="button" title="Align center" onClick={() => run("justifyCenter")} className={buttonClass}>Center</button>
        <button type="button" title="Align right" onClick={() => run("justifyRight")} className={buttonClass}>Right</button>
        <button type="button" title="Undo (Ctrl+Z)" onClick={() => run("undo")} className={buttonClass}>Undo</button>
        <button type="button" title="Redo (Ctrl+Y)" onClick={() => run("redo")} className={buttonClass}>Redo</button>
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
}: {
  html: string
  onChange: (html: string, text: string) => void
  placeholder?: string
  className?: string
  style?: CSSProperties
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
      data-placeholder={placeholder}
      onInput={(event) => {
        const nextHtml = sanitizeEditorHtml(event.currentTarget.innerHTML)
        const nextText = htmlToPlainText(nextHtml)
        onChange(nextHtml, nextText)
      }}
      className={`${className ?? ""} manuscript-editor`}
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
        {items.length > 0 ? items.map((item) => (
          <p key={item} className={`text-sm ${isDark ? "text-slate-200" : "text-stone-700"}`}>{item}</p>
        )) : <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{emptyLabel}</p>}
      </div>
    </div>
  )
}

function countWords(text: string) {
  return text.trim() ? text.trim().split(/\s+/).length : 0
}

function textToHtml(text: string) {
  const cleaned = text.trim()
  if (!cleaned) return "<p></p>"
  return cleaned
    .split(/\n{2,}/)
    .map((paragraph) => `<p>${escapeHtml(paragraph).replace(/\n/g, "<br>")}</p>`)
    .join("")
}

function htmlToPlainText(html: string) {
  if (typeof window === "undefined") return html.replace(/<[^>]+>/g, " ")
  const container = document.createElement("div")
  container.innerHTML = html
  const blocks = Array.from(container.querySelectorAll("h1,h2,h3,p,blockquote,li,div"))
    .map((node) => node.textContent?.trim() ?? "")
    .filter(Boolean)
  return blocks.length ? blocks.join("\n\n") : (container.textContent ?? "").trim()
}

function sanitizeEditorHtml(html: string) {
  if (typeof window === "undefined") return html
  const container = document.createElement("div")
  container.innerHTML = html
  for (const node of Array.from(container.querySelectorAll("*"))) {
    const tag = node.tagName.toLowerCase()
    if (!["p", "br", "strong", "b", "em", "i", "u", "s", "strike", "h1", "h2", "h3", "blockquote", "ul", "ol", "li", "div", "span"].includes(tag)) {
      node.replaceWith(...Array.from(node.childNodes))
      continue
    }
    Array.from(node.attributes).forEach((attribute) => {
      if (attribute.name !== "style") {
        node.removeAttribute(attribute.name)
      }
    })
    const textAlign = (node as HTMLElement).style.textAlign
    node.removeAttribute("style")
    if (textAlign && ["left", "center", "right", "justify"].includes(textAlign)) {
      ;(node as HTMLElement).style.textAlign = textAlign
    }
  }
  const normalized = container.innerHTML.trim()
  return normalized || "<p></p>"
}

function escapeHtml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
}
