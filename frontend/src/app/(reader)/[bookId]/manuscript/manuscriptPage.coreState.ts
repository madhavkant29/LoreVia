"use client"

import { useState } from "react"

import type {
  Book,
  BookNote,
  ChapterVersion,
  ChapterVersionDetail,
  ManuscriptAnnotation,
  ManuscriptWorkspaceTree,
  PreWritingCheck,
  WriterWorkspace,
} from "@/types/book"
import type { Character } from "@/types/character"
import type { AdvisorSuggestion, EditorialReview, EditorialReviewPassage, InlineContinuityResponse } from "@/types/intelligence"
import type { ChapterListResponse, PlotThread } from "@/types/reader"

import type { BookDraftMap } from "./manuscriptPage.helpers"

export function useManuscriptCoreState() {
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
  const [restoringVersionId, setRestoringVersionId] = useState<string | null>(null)
  const [writerWorkspace, setWriterWorkspace] = useState<WriterWorkspace | null>(null)
  const [workspaceSaving, setWorkspaceSaving] = useState(false)
  const [bookDrafts, setBookDrafts] = useState<BookDraftMap>({})
  const [contentVersionByChapter, setContentVersionByChapter] = useState<Record<number, number>>({})
  const [notes, setNotes] = useState<BookNote[]>([])
  const [notesLoading, setNotesLoading] = useState(false)
  const [dirtyDrafts, setDirtyDrafts] = useState<number[]>([])
  const [autosaveState, setAutosaveState] = useState<Record<number, { status: "pending" | "saved" | "error"; updatedAt?: string }>>({})
  const [annotations, setAnnotations] = useState<ManuscriptAnnotation[]>([])
  const [annotationsLoading, setAnnotationsLoading] = useState(false)
  const [newCorkboardTitle, setNewCorkboardTitle] = useState("")
  const [selectionMenu, setSelectionMenu] = useState<{ text: string; top: number; left: number } | null>(null)
  const [addCharacterOpen, setAddCharacterOpen] = useState(false)
  const [addCharacterText, setAddCharacterText] = useState("")

  return {
    addCharacterOpen,
    addCharacterText,
    annotations,
    annotationsLoading,
    autosaveState,
    book,
    bookDrafts,
    characters,
    chapterList,
    chapterTitle,
    chapterVersionDetail,
    chapterVersionNameDraft,
    chapterVersions,
    contentVersionByChapter,
    deletingChapterNumber,
    dirtyDrafts,
    draftChapterNumber,
    html,
    inlineContinuity,
    loading,
    newCorkboardTitle,
    notes,
    notesLoading,
    plotThreads,
    preWritingCheck,
    replaceExisting,
    restoringVersionId,
    review,
    reviewPassages,
    saving,
    selectedChapter,
    selectionMenu,
    setAddCharacterOpen,
    setAddCharacterText,
    setAnnotations,
    setAnnotationsLoading,
    setAutosaveState,
    setBook,
    setBookDrafts,
    setCharacters,
    setChapterList,
    setChapterTitle,
    setChapterVersionDetail,
    setChapterVersionNameDraft,
    setChapterVersions,
    setContentVersionByChapter,
    setDeletingChapterNumber,
    setDirtyDrafts,
    setDraftChapterNumber,
    setHtml,
    setInlineContinuity,
    setLoading,
    setNewCorkboardTitle,
    setNotes,
    setNotesLoading,
    setPlotThreads,
    setPreWritingCheck,
    setReplaceExisting,
    setRestoringVersionId,
    setReview,
    setReviewPassages,
    setSaving,
    setSelectedChapter,
    setSelectionMenu,
    setStatusMessage,
    setSuggestions,
    setText,
    setWorkspaceSaving,
    setWorkspaceTree,
    setWriterWorkspace,
    statusMessage,
    suggestions,
    text,
    workspaceSaving,
    workspaceTree,
    writerWorkspace,
  }
}
