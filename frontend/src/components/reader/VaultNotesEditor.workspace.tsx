"use client"

import type { MouseEvent, RefObject } from "react"
import dynamic from "next/dynamic"

import { Skeleton } from "@/components/ui/Skeleton"
import { Tooltip } from "@/components/ui/Tooltip"
import type { VaultNote } from "@/types/book"
import { markdownButtonClass } from "./VaultNotesEditor.helpers"
import { VaultNoteEmptyState } from "./VaultNotesEditor.emptyState"
import { VaultNoteEditorHeader } from "./VaultNotesEditor.header"
import { VaultNoteMetricsFooter } from "./VaultNotesEditor.metrics"

const WhatsTheWordPanel = dynamic(
  () => import("@/components/intelligence/WhatsTheWordPanel").then((module) => module.WhatsTheWordPanel),
  { ssr: false }
)

const MarkdownPreview = dynamic(
  () => import("./MarkdownPreview").then((module) => module.MarkdownPreview),
  {
    ssr: false,
    loading: () => <Skeleton variant="card" className="min-h-[32rem] rounded-sm" />,
  }
)

type EditorMode = "edit" | "preview" | "split"
const PRIMARY_TOOLBAR_KEYS = new Set(["bold", "italic", "h2", "bullets", "link"])

type ToolbarButton = {
  key: string
  label: string
  title: string
  className?: string
  action: () => void
}

type VaultNoteWorkspaceProps = {
  bookId: string
  busy?: boolean
  findWithinNote: string
  firstLineIndent: boolean
  isDark: boolean
  isFavorite: boolean
  mode: EditorMode
  notes: VaultNote[]
  replaceWithinNote: string
  selectedContent: string
  selectedNote: VaultNote | null
  status: string | null
  textareaRef: RefObject<HTMLTextAreaElement | null>
  toolbarButtons: ToolbarButton[]
  onCopyReference: () => void
  onFavoriteToggle: () => void
  onFindWithinNoteChange: (value: string) => void
  onFirstLineIndentChange: (value: boolean | ((current: boolean) => boolean)) => void
  onModeChange: (mode: EditorMode) => void
  onOpenGraph: () => void
  onOpenNote: (path: string) => void
  onReplaceInSelectedNote: () => void
  onReplaceWithinNoteChange: (value: string) => void
  onSaveNow: () => void
  onSyncSelectionMenu: (event?: MouseEvent<HTMLTextAreaElement>) => void
  onUpdateDraft: (path: string, value: string) => void
}

export function VaultNoteWorkspace({
  bookId,
  busy = false,
  findWithinNote,
  firstLineIndent,
  isDark,
  isFavorite,
  mode,
  notes,
  replaceWithinNote,
  selectedContent,
  selectedNote,
  status,
  textareaRef,
  toolbarButtons,
  onCopyReference,
  onFavoriteToggle,
  onFindWithinNoteChange,
  onFirstLineIndentChange,
  onModeChange,
  onOpenGraph,
  onOpenNote,
  onReplaceInSelectedNote,
  onReplaceWithinNoteChange,
  onSaveNow,
  onSyncSelectionMenu,
  onUpdateDraft,
}: VaultNoteWorkspaceProps) {
  const primaryToolbarButtons = toolbarButtons.filter((button) => PRIMARY_TOOLBAR_KEYS.has(button.key))
  const secondaryToolbarButtons = toolbarButtons.filter((button) => !PRIMARY_TOOLBAR_KEYS.has(button.key))

  return (
    <section className={`overflow-hidden rounded-sm border ${isDark ? "border-white/[0.08] bg-[#08111e]/95" : "border-stone-200 bg-white"}`}>
      {selectedNote ? (
        <>
          <VaultNoteEditorHeader
            busy={busy}
            isDark={isDark}
            isFavorite={isFavorite}
            mode={mode}
            selectedNote={selectedNote}
            status={status}
            onCopyReference={onCopyReference}
            onFavoriteToggle={onFavoriteToggle}
            onModeChange={onModeChange}
            onOpenGraph={onOpenGraph}
            onSaveNow={onSaveNow}
          />

          <div className="p-0">
            <WhatsTheWordPanel bookId={bookId} isDark={isDark} className="m-3" />
            <fieldset disabled={busy} className={`min-w-0 ${isDark ? "bg-[#0a1323]" : "bg-stone-50"}`}>
              {(mode === "edit" || mode === "split") ? (
                  <div className={`border-b px-3 py-3 ${isDark ? "border-white/[0.08] bg-white/[0.02]" : "border-stone-200 bg-white/80"}`}>
                  <div className="flex flex-wrap items-center gap-2">
                    {primaryToolbarButtons.map((button) => (
                      <Tooltip key={button.key} content={button.title}>
                        <button
                          type="button"
                          aria-label={button.title}
                          onClick={button.action}
                          className={`${markdownButtonClass(isDark)} ${button.className ?? ""}`}
                        >
                          {button.label}
                        </button>
                      </Tooltip>
                    ))}
                    <Tooltip content="Toggle paragraph indent">
                      <button
                        type="button"
                        aria-label="Toggle paragraph indent"
                        aria-pressed={firstLineIndent}
                        onClick={() => onFirstLineIndentChange((value) => !value)}
                        className={`${markdownButtonClass(isDark)} ${firstLineIndent ? (isDark ? "bg-emerald-400/15 text-emerald-200" : "bg-emerald-100 text-emerald-800") : ""}`}
                      >
                        ¶ Indent
                      </button>
                    </Tooltip>
                    <details className="relative">
                      <summary className={`${markdownButtonClass(isDark)} cursor-pointer list-none px-3`}>More formatting</summary>
                      <div className={`relative z-20 mt-2 flex max-w-full flex-wrap gap-2 rounded-sm border p-3 shadow-lg ${isDark ? "border-white/10 bg-[#08111d]" : "border-stone-200 bg-white"}`}>
                        {secondaryToolbarButtons.map((button) => (
                          <Tooltip key={button.key} content={button.title}>
                            <button
                              type="button"
                              aria-label={button.title}
                              onClick={button.action}
                              className={`${markdownButtonClass(isDark)} ${button.className ?? ""}`}
                            >
                              {button.label}
                            </button>
                          </Tooltip>
                        ))}
                      </div>
                    </details>
                  </div>
                  <details className="mt-3">
                    <summary className={`cursor-pointer text-sm font-medium ${isDark ? "text-slate-400" : "text-stone-600"}`}>Find and replace</summary>
                    <div className="mt-3 grid gap-2 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
                      <input
                        value={findWithinNote}
                        onChange={(event) => onFindWithinNoteChange(event.target.value)}
                        aria-label="Find in this note"
                        className={`rounded-sm border px-3 py-2 text-sm ${isDark ? "border-white/[0.08] bg-[#08111d] text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
                      />
                      <input
                        value={replaceWithinNote}
                        onChange={(event) => onReplaceWithinNoteChange(event.target.value)}
                        aria-label="Replace with"
                        className={`rounded-sm border px-3 py-2 text-sm ${isDark ? "border-white/[0.08] bg-[#08111d] text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
                      />
                      <button type="button" onClick={onReplaceInSelectedNote} disabled={!findWithinNote.trim()} className={`rounded-sm px-4 py-2 text-sm font-medium ${isDark ? "bg-white/10 text-slate-200 disabled:opacity-40" : "bg-stone-100 text-stone-700 disabled:opacity-40"}`}>
                        Replace all
                      </button>
                    </div>
                  </details>
                </div>
              ) : null}

              <div id="note-editor-panel" role="tabpanel" aria-labelledby={`note-mode-${mode}`} className={`${mode === "split" ? "grid gap-px xl:grid-cols-2" : ""} ${isDark && mode === "split" ? "bg-white/[0.08]" : ""}`}>
                {mode !== "preview" ? (
                  <textarea
                    ref={textareaRef}
                    aria-label="Note content"
                    value={selectedContent}
                    onChange={(event) => onUpdateDraft(selectedNote.path, event.target.value)}
                    onMouseUp={(event) => onSyncSelectionMenu(event)}
                    onKeyUp={() => onSyncSelectionMenu()}
                    spellCheck={false}
                    style={{ textIndent: firstLineIndent ? "1.5em" : "0" }}
                    className={`min-h-[24rem] w-full resize-y border-0 px-4 py-5 font-mono text-base leading-8 outline-none sm:min-h-[32rem] xl:min-h-[42rem] ${
                      isDark
                        ? "bg-[#0a1323] text-slate-100"
                        : "bg-white text-stone-900"
                    } ${mode === "split" ? "xl:min-h-[48rem]" : ""}`}
                  />
                ) : null}

                {mode !== "edit" ? (
                  <div className={`${mode === "split" ? (isDark ? "bg-[#08111d]" : "bg-white") : "p-4"}`}>
                    <MarkdownPreview
                      content={selectedContent}
                      isDark={isDark}
                      notes={notes}
                      currentPath={selectedNote.path}
                      onOpenNote={onOpenNote}
                    />
                  </div>
                ) : null}
              </div>

              <VaultNoteMetricsFooter content={selectedContent} isDark={isDark} />
            </fieldset>
          </div>
        </>
      ) : (
        <VaultNoteEmptyState isDark={isDark} />
      )}
    </section>
  )
}
