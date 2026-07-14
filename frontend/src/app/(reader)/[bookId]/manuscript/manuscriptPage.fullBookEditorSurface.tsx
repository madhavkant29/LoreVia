import type { CSSProperties, RefObject } from "react"

import type { Character } from "@/types/character"
import type { ChapterListItem } from "@/types/reader"
import {
  buildSceneOutline,
  countWords,
  formatReadingTimeLabel,
} from "@/lib/utils/manuscriptEditor"
import { formatIndex } from "@/lib/utils/chapterLabels"

import {
  EditorToolbar,
  RichTextEditor,
} from "./manuscriptPage.dynamic"
import {
  textToHtml,
  type BookDraftMap,
  type ManuscriptBookDraft,
  type ManuscriptIndexFormat,
} from "./manuscriptPage.helpers"

type ChapterRefs = RefObject<Record<number, HTMLDivElement | null>>

type FullBookChapterDraftUpdate = {
  chapterNumber: number
  draft: ManuscriptBookDraft
}

type ManuscriptFullBookEditorSurfaceProps = {
  bookDrafts: BookDraftMap
  chapterIndexFormat: ManuscriptIndexFormat
  chapterListItems: ChapterListItem[]
  chapterRefs: ChapterRefs
  characters: Character[]
  firstLineIndent: boolean
  formatChapterHeading: (chapterNumber: number, title: string) => string
  isDark: boolean
  jumpTarget: number | null
  saveStateLabel: (chapterNumber: number) => string
  saveStateTone: (chapterNumber: number) => string
  saving: boolean
  sheetStyle: CSSProperties
  showPageGuides: boolean
  onAddComment: () => void
  onCharacterClick: (characterName: string) => void
  onDraftChange: (update: FullBookChapterDraftUpdate) => void
  onEditorBlur: (chapterNumber: number) => void
  onEditorFocus: (chapterNumber: number) => void
  onHeadingBlur: (chapterNumber: number, draft: ManuscriptBookDraft, value: string) => void
  onNotesShortcut: () => void
  onSaveChapterDraft: (chapterNumber: number, draft: ManuscriptBookDraft) => void
}

type FullBookChapterCardProps = Omit<ManuscriptFullBookEditorSurfaceProps, "chapterListItems"> & {
  chapter: ChapterListItem
}

function FullBookChapterCard({
  bookDrafts,
  chapter,
  chapterIndexFormat,
  chapterRefs,
  characters,
  firstLineIndent,
  formatChapterHeading,
  isDark,
  jumpTarget,
  saveStateLabel,
  saveStateTone,
  saving,
  sheetStyle,
  showPageGuides,
  onAddComment,
  onCharacterClick,
  onDraftChange,
  onEditorBlur,
  onEditorFocus,
  onHeadingBlur,
  onNotesShortcut,
  onSaveChapterDraft,
}: FullBookChapterCardProps) {
  const draft = bookDrafts[chapter.number] ?? { title: chapter.title || `Chapter ${chapter.number}`, text: "", html: textToHtml("") }
  const wordCount = countWords(draft.text)
  const sceneCount = buildSceneOutline(draft.text).length
  const editorKey = `book-${chapter.number}`

  return (
    <div
      key={chapter.number}
      ref={(node) => {
        chapterRefs.current[chapter.number] = node
      }}
      style={{ contentVisibility: "auto", containIntrinsicSize: "820px" }}
      className={`relative mx-auto w-full max-w-full overflow-visible border ${jumpTarget === chapter.number ? isDark ? "border-teal-400/50 bg-[#0e1218]" : "border-teal-300 bg-[#fdfcf9]" : isDark ? "border-white/10 bg-[#0e1218]" : "border-[#d8d0c4] bg-[#fdfcf9]"}`}
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
            <p className={`text-3xs font-semibold uppercase tracking-[0.24em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Chapter {formatIndex(chapter.number, chapterIndexFormat)}</p>
            <input
              key={`book-heading-${chapter.number}-${draft.title}`}
              type="text"
              defaultValue={formatChapterHeading(chapter.number, draft.title)}
              onBlur={(event) => onHeadingBlur(chapter.number, draft, event.target.value)}
              className={`mt-3 w-full border-0 bg-transparent font-serif text-3xl font-semibold leading-tight outline-none sm:text-4xl ${isDark ? "text-white" : "text-stone-950"}`}
            />
            <p className={`mt-2 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{wordCount.toLocaleString()} words / ~{Math.max(1, Math.ceil(wordCount / 500))} pages</p>
            <p className={`mt-1 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>{formatReadingTimeLabel(wordCount > 0 ? Math.max(1, Math.ceil(wordCount / 250)) : 0)} · {sceneCount} scene{sceneCount === 1 ? "" : "s"}</p>
          </div>
          <div className="flex items-center gap-2">
            <span className={`rounded-sm px-3 py-1.5 text-3xs font-semibold ${saveStateTone(chapter.number)}`}>
              {saveStateLabel(chapter.number)}
            </span>
            <button
              onClick={() => onSaveChapterDraft(chapter.number, draft)}
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
        <EditorToolbar editorKey={editorKey} isDark={isDark} compact characters={characters} onAddComment={onAddComment} onOpenNotes={onNotesShortcut} />
      </div>
      <RichTextEditor
        html={draft.html}
        onChange={(nextHtml, nextText) => {
          onDraftChange({
            chapterNumber: chapter.number,
            draft: {
              title: draft.title,
              text: nextText,
              html: nextHtml,
            },
          })
        }}
        onFocus={() => onEditorFocus(chapter.number)}
        onBlur={() => onEditorBlur(chapter.number)}
        onShortcutSave={() => onSaveChapterDraft(chapter.number, draft)}
        onShortcutComment={onAddComment}
        onShortcutNotes={onNotesShortcut}
        onCharacterClick={onCharacterClick}
        editorKey={editorKey}
        style={{ ...sheetStyle, textIndent: firstLineIndent ? "1.5em" : "0" }}
        className={`relative min-h-[54vh] w-full border-0 bg-transparent px-5 py-10 outline-none sm:px-[18mm] sm:py-[22mm] ${isDark ? "text-slate-100" : "text-stone-900"}`}
        contentClassName="mx-auto w-full max-w-[780px]"
      />
      <div className={`flex flex-wrap items-center justify-between gap-3 border-t px-5 py-3 text-xs sm:px-7 ${isDark ? "border-white/10 bg-[#0b1016] text-slate-400" : "border-[#e6dfd4] bg-[#f7f3ed] text-stone-500"}`}>
        <span>{wordCount.toLocaleString()} words</span>
        <span>{saveStateLabel(chapter.number)}</span>
      </div>
    </div>
  )
}

export function ManuscriptFullBookEditorSurface({
  chapterListItems,
  ...props
}: ManuscriptFullBookEditorSurfaceProps) {
  return (
    <div className="space-y-5">
      {chapterListItems.map((chapter) => (
        <FullBookChapterCard
          key={chapter.number}
          chapter={chapter}
          {...props}
        />
      ))}
    </div>
  )
}
