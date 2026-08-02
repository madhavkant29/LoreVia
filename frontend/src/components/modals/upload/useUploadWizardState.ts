"use client"

import { useCallback, useMemo, useReducer } from "react"
import type { Dispatch, SetStateAction } from "react"

import type { BookMode } from "@/lib/stores/bookModeStore"
import type { BookWorkType, ImportPreview } from "@/types/book"

type ChapterSource = "paste" | "upload"

type UploadWizardState = {
  title: string
  author: string
  authorManuallyEdited: boolean
  mode: BookMode
  startEmpty: boolean
  selectedTags: string[]
  customTag: string
  selectedSeriesIds: string[]
  existingBookId: string
  existingBookMenuOpen: boolean
  hoveredExistingBookId: string | null
  chapterSource: ChapterSource
  chapterNumber: string
  chapterNumberDirty: boolean
  chapterTitle: string
  chapterText: string
  replaceExisting: boolean
  splitIntoChapters: boolean
  chunkLongDocuments: boolean
  files: File[]
  workType: BookWorkType
  workTypeDirty: boolean
  autoExtractCover: boolean
  preserveChapterNumbers: boolean
  preserveSourceChapters: boolean
  coverFile: File | null
  advancedSettingsOpen: boolean
  usernameInput: string
  importPreview: ImportPreview | null
  dismissPreview: boolean
  importAsSingle: boolean
  showEditor: boolean
}

type UploadWizardAction = {
  field: keyof UploadWizardState
  value: unknown
}

function reducer(state: UploadWizardState, action: UploadWizardAction): UploadWizardState {
  const current = state[action.field]
  const next = typeof action.value === "function"
    ? (action.value as (value: typeof current) => unknown)(current)
    : action.value
  return Object.is(current, next) ? state : { ...state, [action.field]: next }
}

export function useUploadWizardState(initialMode: BookMode, initialExistingBookId: string) {
  const [state, dispatch] = useReducer(reducer, {
    title: "",
    author: "",
    authorManuallyEdited: false,
    mode: initialMode,
    startEmpty: false,
    selectedTags: [],
    customTag: "",
    selectedSeriesIds: [],
    existingBookId: initialExistingBookId,
    existingBookMenuOpen: false,
    hoveredExistingBookId: null,
    chapterSource: "paste",
    chapterNumber: "",
    chapterNumberDirty: false,
    chapterTitle: "",
    chapterText: "",
    replaceExisting: false,
    splitIntoChapters: true,
    chunkLongDocuments: false,
    files: [],
    workType: "novel",
    workTypeDirty: false,
    autoExtractCover: true,
    preserveChapterNumbers: false,
    preserveSourceChapters: false,
    coverFile: null,
    advancedSettingsOpen: true,
    usernameInput: "",
    importPreview: null,
    dismissPreview: false,
    importAsSingle: false,
    showEditor: false,
  })

  const setField = useCallback(<K extends keyof UploadWizardState>(
    field: K,
    value: SetStateAction<UploadWizardState[K]>,
  ) => dispatch({ field, value }), [])

  const makeSetter = useCallback(<K extends keyof UploadWizardState>(field: K): Dispatch<SetStateAction<UploadWizardState[K]>> => (
    value,
  ) => setField(field, value), [setField])

  const setters = useMemo(() => ({
    setTitle: makeSetter("title"),
    setAuthor: makeSetter("author"),
    setAuthorManuallyEdited: makeSetter("authorManuallyEdited"),
    setMode: makeSetter("mode"),
    setStartEmpty: makeSetter("startEmpty"),
    setSelectedTags: makeSetter("selectedTags"),
    setCustomTag: makeSetter("customTag"),
    setSelectedSeriesIds: makeSetter("selectedSeriesIds"),
    setExistingBookId: makeSetter("existingBookId"),
    setExistingBookMenuOpen: makeSetter("existingBookMenuOpen"),
    setHoveredExistingBookId: makeSetter("hoveredExistingBookId"),
    setChapterSource: makeSetter("chapterSource"),
    setChapterNumber: makeSetter("chapterNumber"),
    setChapterNumberDirty: makeSetter("chapterNumberDirty"),
    setChapterTitle: makeSetter("chapterTitle"),
    setChapterText: makeSetter("chapterText"),
    setReplaceExisting: makeSetter("replaceExisting"),
    setSplitIntoChapters: makeSetter("splitIntoChapters"),
    setChunkLongDocuments: makeSetter("chunkLongDocuments"),
    setFiles: makeSetter("files"),
    setWorkType: makeSetter("workType"),
    setWorkTypeDirty: makeSetter("workTypeDirty"),
    setAutoExtractCover: makeSetter("autoExtractCover"),
    setPreserveChapterNumbers: makeSetter("preserveChapterNumbers"),
    setPreserveSourceChapters: makeSetter("preserveSourceChapters"),
    setCoverFile: makeSetter("coverFile"),
    setAdvancedSettingsOpen: makeSetter("advancedSettingsOpen"),
    setUsernameInput: makeSetter("usernameInput"),
    setImportPreview: makeSetter("importPreview"),
    setDismissPreview: makeSetter("dismissPreview"),
    setImportAsSingle: makeSetter("importAsSingle"),
    setShowEditor: makeSetter("showEditor"),
  }), [makeSetter])

  return useMemo(() => ({ ...state, ...setters }), [setters, state])
}

export type UploadWizardController = ReturnType<typeof useUploadWizardState>
