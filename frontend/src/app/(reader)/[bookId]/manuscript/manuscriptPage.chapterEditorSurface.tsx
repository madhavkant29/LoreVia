import type { CSSProperties } from "react"

import type { Character } from "@/types/character"

import {
  EditorToolbar,
  RichTextEditor,
} from "./manuscriptPage.dynamic"

type ManuscriptChapterEditorSurfaceProps = {
  activeChapterNeedsReprocess: boolean
  activeChapterNumber: number
  autosaveMetaLabel: string | null
  bookTitle: string | null | undefined
  characters: Character[]
  chapterApproxPages: number
  chapterHeading: string
  chapterReadingTime: string
  chapterSceneCount: number
  chapterWordCount: number
  editorKey: string
  firstLineIndent: boolean
  html: string
  indexFormat: string
  isDark: boolean
  replaceExisting: boolean
  reprocessingChapterNumber: number | null
  saveDisabled: boolean
  saveStateLabel: string
  saveStateTone: string
  sheetStyle: CSSProperties
  showEditorSettings: boolean
  showPageGuides: boolean
  text: string
  onAddComment: () => void
  onChapterHeadingBlur: (value: string) => void
  onCharacterClick: (characterName: string) => void
  onEditorBlur: () => void
  onEditorFocus: () => void
  onEditorSettingsToggle: () => void
  onIndexFormatChange: (value: string) => void
  onNotesShortcut: () => void
  onReprocessChapter: () => void
  onReplaceExistingToggle: () => void
  onSave: () => void
  onTextChange: (nextHtml: string, nextText: string) => void
}

export function ManuscriptChapterEditorSurface({
  activeChapterNeedsReprocess,
  activeChapterNumber,
  autosaveMetaLabel,
  bookTitle,
  characters,
  chapterApproxPages,
  chapterHeading,
  chapterReadingTime,
  chapterSceneCount,
  chapterWordCount,
  editorKey,
  firstLineIndent,
  html,
  indexFormat,
  isDark,
  replaceExisting,
  reprocessingChapterNumber,
  saveDisabled,
  saveStateLabel,
  saveStateTone,
  sheetStyle,
  showEditorSettings,
  showPageGuides,
  text,
  onAddComment,
  onChapterHeadingBlur,
  onCharacterClick,
  onEditorBlur,
  onEditorFocus,
  onEditorSettingsToggle,
  onIndexFormatChange,
  onNotesShortcut,
  onReprocessChapter,
  onReplaceExistingToggle,
  onSave,
  onTextChange,
}: ManuscriptChapterEditorSurfaceProps) {
  return (
    <div className="space-y-4">
      <div className={`relative mx-auto w-full max-w-full overflow-visible border ${isDark ? "border-white/10 bg-[#0e1218]" : "border-[#d8d0c4] bg-[#fdfcf9]"}`}>
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
              <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>{bookTitle || "Manuscript"}</p>
              <input
                key={`chapter-heading-${activeChapterNumber}-${chapterHeading}`}
                type="text"
                defaultValue={chapterHeading}
                onBlur={(event) => onChapterHeadingBlur(event.target.value)}
                className={`mt-3 w-full border-0 bg-transparent font-serif text-3xl font-semibold leading-tight outline-none sm:text-4xl ${isDark ? "text-white" : "text-stone-950"}`}
              />
              <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{chapterReadingTime} · {chapterSceneCount} scene{chapterSceneCount === 1 ? "" : "s"}</p>
              <p className={`mt-2 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{chapterWordCount.toLocaleString()} words · ~{chapterApproxPages} pages</p>
            </div>
            <div className="flex items-center gap-2">
              <span className={`rounded-sm px-3 py-1.5 text-3xs font-semibold ${saveStateTone}`}>
                {saveStateLabel}
              </span>
              <button
                type="button"
                onClick={onEditorSettingsToggle}
                className={`hidden rounded-sm border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}
                aria-label="Editor settings"
              >
                ⚙
              </button>
              {activeChapterNeedsReprocess ? (
                <button
                  type="button"
                  onClick={onReprocessChapter}
                  disabled={reprocessingChapterNumber === activeChapterNumber}
                  className={`rounded-sm border px-3 py-2 text-sm font-semibold disabled:opacity-60 ${isDark ? "border-amber-300/30 bg-amber-400/10 text-amber-100" : "border-amber-200 bg-amber-50 text-amber-700"}`}
                >
                  {reprocessingChapterNumber === activeChapterNumber ? "Starting..." : "Reprocess chapter"}
                </button>
              ) : null}
              <button
                onClick={onSave}
                disabled={saveDisabled}
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
                onClick={onReplaceExistingToggle}
                className={`rounded-sm px-2.5 py-1 font-semibold ${replaceExisting ? isDark ? "bg-white text-slate-950" : "bg-stone-900 text-white" : isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}
              >
                {replaceExisting ? "On" : "Off"}
              </button>
            </div>
          ) : null}
          {showEditorSettings ? (
            <div className={`mt-4 inline-flex items-center gap-2 rounded-sm border px-3 py-2 text-xs ${isDark ? "border-white/10 bg-black/30 text-slate-300" : "border-stone-200 bg-white text-stone-600"}`}>
              <span>Index format</span>
              <select
                value={indexFormat}
                onChange={(event) => onIndexFormatChange(event.target.value)}
                className={`rounded-sm border px-2 py-1 font-semibold outline-none ${isDark ? "border-white/[0.08] bg-black/70 text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
              >
                <option value="arabic">1, 2, 3</option>
                <option value="roman-upper">I, II, III</option>
                <option value="roman-lower">i, ii, iii</option>
                <option value="alpha-upper">A, B, C</option>
                <option value="alpha-lower">a, b, c</option>
              </select>
            </div>
          ) : null}
          {autosaveMetaLabel ? <p className={`mt-3 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{autosaveMetaLabel}</p> : null}
        </div>
        <div className={`sticky top-[8.25rem] z-10 border-b px-3 py-3 transition-all duration-200 translate-y-0 opacity-100 pointer-events-auto ${isDark ? "border-white/10 bg-[#0c1118]" : "border-[#e6dfd4] bg-[#f7f3ed]"}`}>
          <EditorToolbar editorKey={editorKey} isDark={isDark} compact characters={characters} onAddComment={onAddComment} onOpenNotes={onNotesShortcut} />
        </div>
        <RichTextEditor
          html={html}
          onChange={onTextChange}
          onFocus={onEditorFocus}
          onBlur={onEditorBlur}
          onShortcutSave={onSave}
          onShortcutComment={onAddComment}
          onShortcutNotes={onNotesShortcut}
          onCharacterClick={onCharacterClick}
          editorKey={editorKey}
          style={{ ...sheetStyle, textIndent: firstLineIndent ? "1.5em" : "0" }}
          className={`relative min-h-[58vh] w-full border-0 bg-transparent px-5 py-10 outline-none sm:px-[18mm] sm:py-[22mm] ${isDark ? "text-slate-100" : "text-stone-900"}`}
          contentClassName="mx-auto w-full max-w-[780px]"
        />
        <div className={`flex flex-wrap items-center justify-between gap-3 border-t px-5 py-3 text-xs sm:px-7 ${isDark ? "border-white/10 bg-[#0b1016] text-slate-400" : "border-[#e6dfd4] bg-[#f7f3ed] text-stone-500"}`}>
          <span>{chapterWordCount.toLocaleString()} words</span>
          <span>{saveStateLabel}</span>
        </div>
      </div>
    </div>
  )
}
