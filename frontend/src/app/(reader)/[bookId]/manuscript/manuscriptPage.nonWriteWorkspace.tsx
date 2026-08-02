import { Suspense, type RefObject } from "react"

import { Skeleton } from "@/components/ui/Skeleton"
import type { ManuscriptDraftFontFamily } from "@/components/reader/ManuscriptNonWriteWorkspace"
import type { PreWritingCheck } from "@/types/book"
import type { Character } from "@/types/character"
import type { InlineContinuityResponse } from "@/types/intelligence"
import type { SearchResult } from "@/types/reader"

import type { DraftSurfaceMode, EditorMode } from "./manuscriptPage.constants"
import { ManuscriptNonWriteWorkspace } from "./manuscriptPage.dynamic"

type ManuscriptNonWriteWorkspaceSectionProps = {
  activeChapterNumber: number
  activeFindIndex: number
  bookId: string
  chapterPageSummaryLabel: string
  chapterWordCount: number
  continuityLoading: boolean
  draftSurfaceMode: DraftSurfaceMode
  draftSurfaceSummaryLabel: string
  editorMode: EditorMode
  firstLineIndent: boolean
  fontFamily: ManuscriptDraftFontFamily
  fontSize: number
  fullBookPageSummaryLabel: string
  fullBookWordCount: number
  inlineContinuity: InlineContinuityResponse | null
  isDark: boolean
  leftRailVisible: boolean
  lineHeight: number
  logicSelectionText: string
  preWritingCheck: PreWritingCheck | null
  recallCharacter: Character | null
  recallLoading: boolean
  recallQuery: string
  recallResults: SearchResult[]
  replaceQuery: string
  replaceValue: string
  searchInputRef: RefObject<HTMLInputElement | null>
  showPageGuides: boolean
  showPageSetup: boolean
  showSearchTools: boolean
  onDraftSurfaceModeChange: (mode: DraftSurfaceMode) => void
  onEditorModeChange: (mode: EditorMode) => void
  onFontFamilyChange: (fontFamily: ManuscriptDraftFontFamily) => void
  onFontSizeChange: (value: number) => void
  onJumpToChapter: (chapterNumber: number) => void
  onLineHeightChange: (value: number) => void
  onRecallQueryChange: (value: string) => void
  onReplaceEverywhere: () => void
  onReplaceInCurrentChapter: () => void
  onReplaceQueryChange: (value: string) => void
  onReplaceValueChange: (value: string) => void
  onToggleFirstLineIndent: () => void
  onToggleLeftRail: () => void
  onTogglePageSetup: () => void
  onToggleSearchTools: () => void
  onToggleShowPageGuides: () => void
}

export function ManuscriptNonWriteWorkspaceSection({
  activeChapterNumber,
  activeFindIndex,
  bookId,
  chapterPageSummaryLabel,
  chapterWordCount,
  continuityLoading,
  draftSurfaceMode,
  draftSurfaceSummaryLabel,
  editorMode,
  firstLineIndent,
  fontFamily,
  fontSize,
  fullBookPageSummaryLabel,
  fullBookWordCount,
  inlineContinuity,
  isDark,
  leftRailVisible,
  lineHeight,
  logicSelectionText,
  preWritingCheck,
  recallCharacter,
  recallLoading,
  recallQuery,
  recallResults,
  replaceQuery,
  replaceValue,
  searchInputRef,
  showPageGuides,
  showPageSetup,
  showSearchTools,
  onDraftSurfaceModeChange,
  onEditorModeChange,
  onFontFamilyChange,
  onFontSizeChange,
  onJumpToChapter,
  onLineHeightChange,
  onRecallQueryChange,
  onReplaceEverywhere,
  onReplaceInCurrentChapter,
  onReplaceQueryChange,
  onReplaceValueChange,
  onToggleFirstLineIndent,
  onToggleLeftRail,
  onTogglePageSetup,
  onToggleSearchTools,
  onToggleShowPageGuides,
}: ManuscriptNonWriteWorkspaceSectionProps) {
  return (
    <Suspense fallback={<Skeleton variant="card" className="min-h-64" />}>
      <ManuscriptNonWriteWorkspace
        isDark={isDark}
        bookId={bookId}
        activeChapterNumber={activeChapterNumber}
        preWritingCheck={preWritingCheck}
        editorMode={editorMode}
        onEditorModeChange={onEditorModeChange}
        draftSurfaceMode={draftSurfaceMode}
        onDraftSurfaceModeChange={onDraftSurfaceModeChange}
        leftRailVisible={leftRailVisible}
        onToggleLeftRail={onToggleLeftRail}
        chapterWordCount={chapterWordCount}
        fullBookWordCount={fullBookWordCount}
        chapterPageSummaryLabel={chapterPageSummaryLabel}
        fullBookPageSummaryLabel={fullBookPageSummaryLabel}
        draftSurfaceSummaryLabel={draftSurfaceSummaryLabel}
        showPageSetup={showPageSetup}
        onTogglePageSetup={onTogglePageSetup}
        showSearchTools={showSearchTools}
        onToggleSearchTools={onToggleSearchTools}
        fontFamily={fontFamily}
        onFontFamilyChange={onFontFamilyChange}
        fontSize={fontSize}
        onFontSizeChange={onFontSizeChange}
        lineHeight={lineHeight}
        onLineHeightChange={onLineHeightChange}
        firstLineIndent={firstLineIndent}
        onToggleFirstLineIndent={onToggleFirstLineIndent}
        showPageGuides={showPageGuides}
        onToggleShowPageGuides={onToggleShowPageGuides}
        searchInputRef={searchInputRef}
        recallQuery={recallQuery}
        onRecallQueryChange={onRecallQueryChange}
        replaceQuery={replaceQuery}
        onReplaceQueryChange={onReplaceQueryChange}
        replaceValue={replaceValue}
        onReplaceValueChange={onReplaceValueChange}
        onReplaceInCurrentChapter={onReplaceInCurrentChapter}
        onReplaceEverywhere={onReplaceEverywhere}
        recallCharacter={recallCharacter}
        recallLoading={recallLoading}
        recallResults={recallResults}
        activeFindIndex={activeFindIndex}
        onJumpToChapter={onJumpToChapter}
        inlineContinuity={inlineContinuity}
        logicSelectionText={logicSelectionText}
        continuityLoading={continuityLoading}
      />
    </Suspense>
  )
}
