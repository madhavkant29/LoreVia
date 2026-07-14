import type { CSSProperties, RefObject } from "react"

import type { ManuscriptPagedPreviewSection } from "@/components/reader/ManuscriptPagedPreview"
import type { PublishingPreset } from "@/types/book"
import type { Character } from "@/types/character"
import type { ChapterListItem } from "@/types/reader"

import { ManuscriptChapterEditorSurface } from "./manuscriptPage.chapterEditorSurface"
import type { DraftSurfaceMode, EditorMode } from "./manuscriptPage.constants"
import { ManuscriptFullBookEditorSurface } from "./manuscriptPage.fullBookEditorSurface"
import {
  type BookDraftMap,
  type ManuscriptBookDraft,
  type ManuscriptIndexFormat,
} from "./manuscriptPage.helpers"
import { InlineLoadingRows } from "./manuscriptPage.loading"
import { ManuscriptPagedPreview } from "./manuscriptPage.dynamic"

type ChapterRefs = RefObject<Record<number, HTMLDivElement | null>>

type FullBookDraftChange = {
  chapterNumber: number
  draft: ManuscriptBookDraft
}

type ManuscriptEditorPanelProps = {
  activeChapterNeedsReprocess: boolean
  activeChapterNumber: number
  autosaveMetaLabel: string | null
  bookDrafts: BookDraftMap
  bookTitle: string | null | undefined
  chapterApproxPages: number
  chapterHeading: string
  chapterIndexFormat: ManuscriptIndexFormat
  chapterListItems: ChapterListItem[]
  chapterPreviewSections: ManuscriptPagedPreviewSection[]
  chapterReadingTime: string
  chapterRefs: ChapterRefs
  chapterSceneCount: number
  chapterWordCount: number
  characters: Character[]
  draftSurfaceMode: DraftSurfaceMode
  editorMode: EditorMode
  firstLineIndent: boolean
  fullBookLoading: boolean
  fullBookPreviewSections: ManuscriptPagedPreviewSection[]
  html: string
  indexFormat: string
  isDark: boolean
  jumpTarget: number | null
  lineHeight: number
  pagedPreviewPreset: PublishingPreset["active_preset"] | null | undefined
  replaceExisting: boolean
  reprocessingChapterNumber: number | null
  saveDisabled: boolean
  saveStateLabel: (chapterNumber: number) => string
  saveStateTone: (chapterNumber: number) => string
  saving: boolean
  sheetStyle: CSSProperties
  showEditorSettings: boolean
  showPageGuides: boolean
  text: string
  onAddComment: () => void
  onChapterEditorBlur: () => void
  onChapterEditorFocus: () => void
  onChapterHeadingBlur: (value: string) => void
  onChapterPageCountChange: (pageCount: number) => void
  onChapterTextChange: (nextHtml: string, nextText: string) => void
  onCharacterClick: (characterName: string) => void
  onEditorSettingsToggle: () => void
  onFullBookDraftChange: (update: FullBookDraftChange) => void
  onFullBookEditorBlur: (chapterNumber: number) => void
  onFullBookEditorFocus: (chapterNumber: number) => void
  onFullBookHeadingBlur: (chapterNumber: number, draft: ManuscriptBookDraft, value: string) => void
  onFullBookPageCountChange: (pageCount: number) => void
  onIndexFormatChange: (value: string) => void
  onNotesShortcut: () => void
  onReprocessChapter: () => void
  onReplaceExistingToggle: () => void
  onSaveChapter: () => void
  onSaveChapterDraft: (chapterNumber: number, draft: ManuscriptBookDraft) => void
  formatChapterHeading: (chapterNumber: number, title: string) => string
}

export function ManuscriptEditorPanel({
  activeChapterNeedsReprocess,
  activeChapterNumber,
  autosaveMetaLabel,
  bookDrafts,
  bookTitle,
  chapterApproxPages,
  chapterHeading,
  chapterIndexFormat,
  chapterListItems,
  chapterPreviewSections,
  chapterReadingTime,
  chapterRefs,
  chapterSceneCount,
  chapterWordCount,
  characters,
  draftSurfaceMode,
  editorMode,
  firstLineIndent,
  fullBookLoading,
  fullBookPreviewSections,
  html,
  indexFormat,
  isDark,
  jumpTarget,
  lineHeight,
  pagedPreviewPreset,
  replaceExisting,
  reprocessingChapterNumber,
  saveDisabled,
  saveStateLabel,
  saveStateTone,
  saving,
  sheetStyle,
  showEditorSettings,
  showPageGuides,
  text,
  onAddComment,
  onChapterEditorBlur,
  onChapterEditorFocus,
  onChapterHeadingBlur,
  onChapterPageCountChange,
  onChapterTextChange,
  onCharacterClick,
  onEditorSettingsToggle,
  onFullBookDraftChange,
  onFullBookEditorBlur,
  onFullBookEditorFocus,
  onFullBookHeadingBlur,
  onFullBookPageCountChange,
  onIndexFormatChange,
  onNotesShortcut,
  onReprocessChapter,
  onReplaceExistingToggle,
  onSaveChapter,
  onSaveChapterDraft,
  formatChapterHeading,
}: ManuscriptEditorPanelProps) {
  if (editorMode === "chapter") {
    if (draftSurfaceMode === "paged") {
      return (
        <ManuscriptPagedPreview
          sections={chapterPreviewSections}
          preset={pagedPreviewPreset}
          firstLineIndent={firstLineIndent}
          lineHeight={lineHeight}
          isDark={isDark}
          onPageCountChange={onChapterPageCountChange}
        />
      )
    }

    return (
      <ManuscriptChapterEditorSurface
        activeChapterNeedsReprocess={activeChapterNeedsReprocess}
        activeChapterNumber={activeChapterNumber}
        autosaveMetaLabel={autosaveMetaLabel}
        bookTitle={bookTitle}
        characters={characters}
        chapterApproxPages={chapterApproxPages}
        chapterHeading={chapterHeading}
        chapterReadingTime={chapterReadingTime}
        chapterSceneCount={chapterSceneCount}
        chapterWordCount={chapterWordCount}
        editorKey={`chapter-${activeChapterNumber}`}
        firstLineIndent={firstLineIndent}
        html={html}
        indexFormat={indexFormat}
        isDark={isDark}
        replaceExisting={replaceExisting}
        reprocessingChapterNumber={reprocessingChapterNumber}
        saveDisabled={saveDisabled}
        saveStateLabel={saveStateLabel(activeChapterNumber)}
        saveStateTone={saveStateTone(activeChapterNumber)}
        sheetStyle={sheetStyle}
        showEditorSettings={showEditorSettings}
        showPageGuides={showPageGuides}
        text={text}
        onAddComment={onAddComment}
        onChapterHeadingBlur={onChapterHeadingBlur}
        onCharacterClick={onCharacterClick}
        onEditorBlur={onChapterEditorBlur}
        onEditorFocus={onChapterEditorFocus}
        onEditorSettingsToggle={onEditorSettingsToggle}
        onIndexFormatChange={onIndexFormatChange}
        onNotesShortcut={onNotesShortcut}
        onReprocessChapter={onReprocessChapter}
        onReplaceExistingToggle={onReplaceExistingToggle}
        onSave={onSaveChapter}
        onTextChange={onChapterTextChange}
      />
    )
  }

  if (draftSurfaceMode === "paged") {
    return (
      <div className="space-y-5">
        {fullBookLoading ? <InlineLoadingRows label="Loading full manuscript" isDark={isDark} rows={2} /> : null}
        {fullBookPreviewSections.length > 0 ? (
          <ManuscriptPagedPreview
            sections={fullBookPreviewSections}
            preset={pagedPreviewPreset}
            firstLineIndent={firstLineIndent}
            lineHeight={lineHeight}
            isDark={isDark}
            onPageCountChange={onFullBookPageCountChange}
          />
        ) : (
          <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No chapter drafts are ready for full-book preview yet.</p>
        )}
      </div>
    )
  }

  return (
    <ManuscriptFullBookEditorSurface
      bookDrafts={bookDrafts}
      chapterIndexFormat={chapterIndexFormat}
      chapterListItems={chapterListItems}
      chapterRefs={chapterRefs}
      characters={characters}
      firstLineIndent={firstLineIndent}
      formatChapterHeading={formatChapterHeading}
      isDark={isDark}
      jumpTarget={jumpTarget}
      saveStateLabel={saveStateLabel}
      saveStateTone={saveStateTone}
      saving={saving}
      sheetStyle={sheetStyle}
      showPageGuides={showPageGuides}
      onAddComment={onAddComment}
      onCharacterClick={onCharacterClick}
      onDraftChange={onFullBookDraftChange}
      onEditorBlur={onFullBookEditorBlur}
      onEditorFocus={onFullBookEditorFocus}
      onHeadingBlur={onFullBookHeadingBlur}
      onNotesShortcut={onNotesShortcut}
      onSaveChapterDraft={onSaveChapterDraft}
    />
  )
}
