"use client"

import type { RefObject } from "react"
import Link from "next/link"

import type { PreWritingCheck } from "@/types/book"
import type { Character } from "@/types/character"
import type { InlineContinuityResponse } from "@/types/intelligence"
import type { SearchResult } from "@/types/reader"

type ManuscriptNonWriteWorkspaceProps = {
  isDark: boolean
  bookId: string
  activeChapterNumber: number
  preWritingCheck: PreWritingCheck | null
  editorMode: "chapter" | "book"
  onEditorModeChange: (mode: "chapter" | "book") => void
  draftSurfaceMode: "edit" | "paged"
  onDraftSurfaceModeChange: (mode: "edit" | "paged") => void
  leftRailVisible: boolean
  onToggleLeftRail: () => void
  chapterWordCount: number
  fullBookWordCount: number
  chapterPageSummaryLabel: string
  fullBookPageSummaryLabel: string
  draftSurfaceSummaryLabel: string
  showPageSetup: boolean
  onTogglePageSetup: () => void
  showSearchTools: boolean
  onToggleSearchTools: () => void
  fontFamily: "times" | "georgia" | "sans"
  onFontFamilyChange: (value: "times" | "georgia" | "sans") => void
  fontSize: number
  onFontSizeChange: (value: number) => void
  lineHeight: number
  onLineHeightChange: (value: number) => void
  firstLineIndent: boolean
  onToggleFirstLineIndent: () => void
  showPageGuides: boolean
  onToggleShowPageGuides: () => void
  searchInputRef: RefObject<HTMLInputElement | null>
  recallQuery: string
  onRecallQueryChange: (value: string) => void
  replaceQuery: string
  onReplaceQueryChange: (value: string) => void
  replaceValue: string
  onReplaceValueChange: (value: string) => void
  onReplaceInCurrentChapter: () => void
  onReplaceEverywhere: () => void
  recallCharacter: Character | null
  recallLoading: boolean
  recallResults: SearchResult[]
  activeFindIndex: number
  onJumpToChapter: (chapterNumber: number) => void
  inlineContinuity: InlineContinuityResponse | null
  logicSelectionText: string
  continuityLoading: boolean
}

export function ManuscriptNonWriteWorkspace({
  isDark,
  bookId,
  activeChapterNumber,
  preWritingCheck,
  editorMode,
  onEditorModeChange,
  draftSurfaceMode,
  onDraftSurfaceModeChange,
  leftRailVisible,
  onToggleLeftRail,
  chapterWordCount,
  fullBookWordCount,
  chapterPageSummaryLabel,
  fullBookPageSummaryLabel,
  draftSurfaceSummaryLabel,
  showPageSetup,
  onTogglePageSetup,
  showSearchTools,
  onToggleSearchTools,
  fontFamily,
  onFontFamilyChange,
  fontSize,
  onFontSizeChange,
  lineHeight,
  onLineHeightChange,
  firstLineIndent,
  onToggleFirstLineIndent,
  showPageGuides,
  onToggleShowPageGuides,
  searchInputRef,
  recallQuery,
  onRecallQueryChange,
  replaceQuery,
  onReplaceQueryChange,
  replaceValue,
  onReplaceValueChange,
  onReplaceInCurrentChapter,
  onReplaceEverywhere,
  recallCharacter,
  recallLoading,
  recallResults,
  activeFindIndex,
  onJumpToChapter,
  inlineContinuity,
  logicSelectionText,
  continuityLoading,
}: ManuscriptNonWriteWorkspaceProps) {
  return (
    <>
      {preWritingCheck ? (
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

      <div className={`mb-8 rounded-[1.4rem] border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-stone-200 bg-white/90"}`}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <div className={`inline-flex rounded-full p-1 ${isDark ? "border border-white/10 bg-black/40 shadow-inner" : "border border-stone-200 bg-stone-100 shadow-inner"}`}>
              {(["chapter", "book"] as const).map((mode) => (
                <button
                  key={mode}
                  onClick={() => onEditorModeChange(mode)}
                  className={`rounded-full px-5 py-2 text-sm font-medium transition ${editorMode === mode ? isDark ? "bg-white text-slate-950 shadow-sm" : "bg-stone-900 text-white shadow-sm" : isDark ? "text-slate-300 hover:bg-white/10" : "text-stone-600 hover:bg-white"}`}
                >
                  {mode === "chapter" ? "Chapter" : "Full book"}
                </button>
              ))}
            </div>
            <div className={`inline-flex rounded-full p-1 ${isDark ? "border border-white/10 bg-black/30 shadow-inner" : "border border-stone-200 bg-stone-50 shadow-inner"}`}>
              {(["edit", "paged"] as const).map((mode) => (
                <button
                  key={mode}
                  type="button"
                  aria-pressed={draftSurfaceMode === mode}
                  onClick={() => onDraftSurfaceModeChange(mode)}
                  className={`rounded-full px-4 py-2 text-sm font-medium transition ${draftSurfaceMode === mode ? isDark ? "bg-sky-300 text-slate-950 shadow-sm" : "bg-sky-700 text-white shadow-sm" : isDark ? "text-slate-300 hover:bg-white/10" : "text-stone-600 hover:bg-white"}`}
                >
                  {mode === "edit" ? "Draft" : "Paged preview"}
                </button>
              ))}
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <button onClick={onTogglePageSetup} className={`rounded-full px-3 py-1.5 text-xs font-medium ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>
              {showPageSetup ? "Hide page setup" : "Page setup"}
            </button>
            <button onClick={onToggleSearchTools} className={`rounded-full px-3 py-1.5 text-xs font-medium ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>
              {showSearchTools ? "Hide search tools" : "Find and jump"}
            </button>
            <button onClick={onToggleLeftRail} className={`rounded-full px-3 py-1.5 text-xs font-medium ${leftRailVisible ? isDark ? "bg-indigo-400/15 text-white" : "bg-violet-100 text-stone-900" : isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>
              {leftRailVisible ? "Hide chapters" : "Show chapters"}
            </button>
          </div>
        </div>
        <div className={`mt-3 flex flex-wrap items-center gap-4 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
          <span>{editorMode === "chapter" ? `${chapterWordCount.toLocaleString()} words` : `${fullBookWordCount.toLocaleString()} words`}</span>
          <span>{editorMode === "chapter" ? chapterPageSummaryLabel : fullBookPageSummaryLabel}</span>
          <span>{draftSurfaceSummaryLabel}</span>
        </div>
        {showPageSetup ? (
          <div className="mt-4 grid gap-3 md:grid-cols-[auto_auto_auto_1fr]">
            <label className={`text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
              Font
              <select
                value={fontFamily}
                onChange={(event) => onFontFamilyChange(event.target.value as "times" | "georgia" | "sans")}
                disabled={draftSurfaceMode === "paged"}
                className={`ml-2 rounded-lg border px-2 py-1 text-sm ${isDark ? "border-white/10 bg-black text-slate-100 disabled:opacity-50" : "border-stone-200 bg-white text-stone-900 disabled:opacity-50"}`}
              >
                <option value="times">Times</option>
                <option value="georgia">Georgia</option>
                <option value="sans">Sans</option>
              </select>
            </label>
            <label className={`text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
              Font size
              <select
                value={fontSize}
                onChange={(event) => onFontSizeChange(Number(event.target.value))}
                disabled={draftSurfaceMode === "paged"}
                className={`ml-2 rounded-lg border px-2 py-1 text-sm ${isDark ? "border-white/10 bg-black text-slate-100 disabled:opacity-50" : "border-stone-200 bg-white text-stone-900 disabled:opacity-50"}`}
              >
                {[11, 12, 13, 14, 15].map((size) => <option key={size} value={size}>{size}pt</option>)}
              </select>
            </label>
            <label className={`text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
              Line height
              <select value={lineHeight} onChange={(event) => onLineHeightChange(Number(event.target.value))} className={`ml-2 rounded-lg border px-2 py-1 text-sm ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}>
                {[1.6, 1.8, 2].map((value) => <option key={value} value={value}>{value}</option>)}
              </select>
            </label>
            <div className="flex flex-wrap items-center gap-2">
              <button onClick={onToggleFirstLineIndent} className={`rounded-full px-3 py-1.5 text-xs font-medium ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>
                {firstLineIndent ? "Indent on" : "Indent off"}
              </button>
              <button
                onClick={onToggleShowPageGuides}
                disabled={draftSurfaceMode === "paged"}
                className={`rounded-full px-3 py-1.5 text-xs font-medium ${isDark ? "bg-white/10 text-slate-200 disabled:opacity-50" : "bg-stone-100 text-stone-700 disabled:opacity-50"}`}
              >
                {showPageGuides ? "Page guides on" : "Page guides off"}
              </button>
            </div>
          </div>
        ) : null}
        {showPageSetup && draftSurfaceMode === "paged" ? (
          <p className={`mt-3 text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>
            Paged preview follows the active export preset for paper size, margins, and base typography.
          </p>
        ) : null}
        {showSearchTools ? (
          <div className="mt-4 space-y-3">
            <input
              ref={searchInputRef}
              type="text"
              value={recallQuery}
              onChange={(event) => onRecallQueryChange(event.target.value)}
              placeholder="Search character, scene detail, clue, or thread"
              className={`w-full rounded-[0.9rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"}`}
            />
            <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto_auto]">
              <input
                type="text"
                value={replaceQuery}
                onChange={(event) => onReplaceQueryChange(event.target.value)}
                placeholder="Find text"
                className={`rounded-[0.9rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"}`}
              />
              <input
                type="text"
                value={replaceValue}
                onChange={(event) => onReplaceValueChange(event.target.value)}
                placeholder="Replace with"
                className={`rounded-[0.9rem] border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100 placeholder:text-slate-500" : "border-stone-200 bg-white text-stone-900 placeholder:text-stone-400"}`}
              />
              <button onClick={onReplaceInCurrentChapter} disabled={!replaceQuery} className={`rounded-[0.9rem] px-4 py-2 text-sm font-medium ${isDark ? "bg-white/10 text-slate-200 disabled:opacity-40" : "bg-stone-100 text-stone-700 disabled:opacity-40"}`}>
                Replace one
              </button>
              <button onClick={onReplaceEverywhere} disabled={!replaceQuery} className={`rounded-[0.9rem] px-4 py-2 text-sm font-medium ${isDark ? "bg-white/10 text-slate-200 disabled:opacity-40" : "bg-stone-100 text-stone-700 disabled:opacity-40"}`}>
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
                      onClick={() => onJumpToChapter(result.chapter_num)}
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

      {inlineContinuity ? (
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
                {inlineContinuity.issues.length === 0 ? <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>No hard chapter-memory contradiction surfaced in this pass, but this scene still deserves another check for setup, recall, and causal clarity.</p> : null}
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
    </>
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
