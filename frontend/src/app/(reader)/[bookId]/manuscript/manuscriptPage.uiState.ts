import { useState } from "react"

import type { ManuscriptDraftFontFamily } from "@/components/reader/ManuscriptNonWriteWorkspace"
import type { Character } from "@/types/character"

import type { DraftSurfaceMode, EditorMode, RightPane, WorkspaceTab } from "./manuscriptPage.constants"
import type { ManuscriptCharacterCardDraft } from "./manuscriptPage.helpers"

type CompileFormat = "pdf" | "docx" | "epub" | "vault"

export function useManuscriptEditorUiState() {
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
  const [charCardDraft, setCharCardDraft] = useState<ManuscriptCharacterCardDraft>({
    arcSummary: "",
    description: "",
    personalityTags: "",
    motivations: "",
    fears: "",
  })
  const [showExportMenu, setShowExportMenu] = useState(false)
  const [showCompileDialog, setShowCompileDialog] = useState(false)
  const [showReprocessConfirm, setShowReprocessConfirm] = useState(false)
  const [compileFormat, setCompileFormat] = useState<CompileFormat>("docx")
  const [includeSceneMetadataOnImport, setIncludeSceneMetadataOnImport] = useState(false)
  const [includeSceneMetadataOnExport, setIncludeSceneMetadataOnExport] = useState(false)
  const [includeTableOfContentsOnExport, setIncludeTableOfContentsOnExport] = useState(false)
  const [showEditorSettings, setShowEditorSettings] = useState(false)
  const [activeEditorKey, setActiveEditorKey] = useState<string | null>(null)
  const [fullBookLoading, setFullBookLoading] = useState(false)
  const [exporting, setExporting] = useState<CompileFormat | null>(null)
  const [reprocessing, setReprocessing] = useState(false)
  const [processingRetrying, setProcessingRetrying] = useState(false)
  const [reprocessingChapterNumber, setReprocessingChapterNumber] = useState<number | null>(null)
  const [jumpTarget, setJumpTarget] = useState<number | null>(null)
  const [activeFindIndex, setActiveFindIndex] = useState(0)
  const [replaceQuery, setReplaceQuery] = useState("")
  const [replaceValue, setReplaceValue] = useState("")
  const [gotoPageInput, setGotoPageInput] = useState("")
  const [showPageSetup, setShowPageSetup] = useState(false)
  const [showSearchTools, setShowSearchTools] = useState(false)

  return {
    activeEditorKey,
    activeFindIndex,
    activeRightPane,
    chapterPreviewPageCount,
    charCardDraft,
    charCardEditing,
    charCardSaving,
    compileFormat,
    draftSurfaceMode,
    editorMode,
    exporting,
    firstLineIndent,
    focusMode,
    fontFamily,
    fontSize,
    fontSizeLocked,
    fullBookLoading,
    fullBookPreviewPageCount,
    gotoPageInput,
    includeSceneMetadataOnExport,
    includeSceneMetadataOnImport,
    includeTableOfContentsOnExport,
    jumpTarget,
    lineHeight,
    processingRetrying,
    replaceQuery,
    replaceValue,
    reprocessing,
    reprocessingChapterNumber,
    selectedCharCard,
    setActiveEditorKey,
    setActiveFindIndex,
    setActiveRightPane,
    setChapterPreviewPageCount,
    setCharCardDraft,
    setCharCardEditing,
    setCharCardSaving,
    setCompileFormat,
    setDraftSurfaceMode,
    setEditorMode,
    setExporting,
    setFirstLineIndent,
    setFocusMode,
    setFontFamily,
    setFontSize,
    setFontSizeLocked,
    setFullBookLoading,
    setFullBookPreviewPageCount,
    setGotoPageInput,
    setIncludeSceneMetadataOnExport,
    setIncludeSceneMetadataOnImport,
    setIncludeTableOfContentsOnExport,
    setJumpTarget,
    setLineHeight,
    setProcessingRetrying,
    setReplaceQuery,
    setReplaceValue,
    setReprocessing,
    setReprocessingChapterNumber,
    setSelectedCharCard,
    setShowCompileDialog,
    setShowEditorSettings,
    setShowExportMenu,
    setShowLeftRail,
    setShowPageGuides,
    setShowPageSetup,
    setShowReprocessConfirm,
    setShowRightRail,
    setShowSearchTools,
    setWorkspaceTab,
    showCompileDialog,
    showEditorSettings,
    showExportMenu,
    showLeftRail,
    showPageGuides,
    showPageSetup,
    showReprocessConfirm,
    showRightRail,
    showSearchTools,
    workspaceTab,
  }
}
