import { useEffect, useRef, type Dispatch, type SetStateAction } from "react"
import type { Route } from "next"
import Link from "next/link"

import { ManuscriptExportMenu } from "@/components/reader/ManuscriptExportMenu"
import { ManuscriptModeSwitch } from "@/components/reader/ManuscriptModeSwitch"
import { LastSavedLabel, ProcessingStatusStrip, RecoverableInlineError, SaveStatePill } from "@/components/ui/ResponsivenessStatus"
import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"
import type { ReprocessCta } from "@/lib/utils/editorProjectCta"
import type { NormalizedProcessingStatus } from "@/lib/utils/processingStatus"
import type { SaveState } from "@/types/book"
import { WORKSPACE_TABS, type DraftSurfaceMode, type EditorMode, type SaveTarget, type WorkspaceTab } from "./manuscriptPage.constants"
import { BookOpenIcon } from "./manuscriptPage.loading"

type PublishingPreset = "standard_manuscript" | "trade_paperback" | "kdp_paperback"
type CompileFormat = "docx" | "pdf" | "epub" | "vault"

type ManuscriptHeaderProps = {
  activeLastSavedAt?: string | Date | null
  activePreset: PublishingPreset
  activeSaveState: SaveState
  autoReprocessEnabled: boolean
  bookTitle?: string | null
  compileFormatSetter: Dispatch<SetStateAction<CompileFormat>>
  draftSurfaceMode: DraftSurfaceMode
  editorMode: EditorMode
  exporting: CompileFormat | null
  failedSaveByTarget: Partial<Record<SaveTarget, () => Promise<void>>>
  focusMode: boolean
  homeHref: string
  includeTableOfContentsOnExport: boolean
  isDark: boolean
  normalizedProcessingStatus: NormalizedProcessingStatus | null
  outlineOpen: boolean
  processingRetrying: boolean
  reprocessCta: ReprocessCta
  reprocessing: boolean
  saveStateByTarget: Partial<Record<SaveTarget, SaveState>>
  showExportMenu: boolean
  inspectorOpen: boolean
  workspaceSaving: boolean
  workspaceTab: WorkspaceTab
  onAutoReprocessChange: (enabled: boolean) => void
  onCompileDialogOpenChange: Dispatch<SetStateAction<boolean>>
  onDraftSurfaceModeChange: Dispatch<SetStateAction<DraftSurfaceMode>>
  onEditorModeChange: Dispatch<SetStateAction<EditorMode>>
  onExportMenuOpenChange: Dispatch<SetStateAction<boolean>>
  onFocusModeChange: Dispatch<SetStateAction<boolean>>
  onIncludeTableOfContentsChange: Dispatch<SetStateAction<boolean>>
  onInspectorOpenChange: Dispatch<SetStateAction<boolean>>
  onOpenProject: () => void
  onOutlineOpenChange: Dispatch<SetStateAction<boolean>>
  onPresetChange: (nextPreset: PublishingPreset) => void
  onPrint: () => void
  onRetryProcessing: () => void
  onShowEditorSettingsChange: Dispatch<SetStateAction<boolean>>
  onShowReprocessConfirmChange: Dispatch<SetStateAction<boolean>>
  onWorkspaceTabChange: Dispatch<SetStateAction<WorkspaceTab>>
}

export function ManuscriptHeader({
  activeLastSavedAt,
  activePreset,
  activeSaveState,
  autoReprocessEnabled,
  bookTitle,
  compileFormatSetter,
  draftSurfaceMode,
  editorMode,
  exporting,
  failedSaveByTarget,
  focusMode,
  homeHref,
  includeTableOfContentsOnExport,
  isDark,
  normalizedProcessingStatus,
  outlineOpen,
  onAutoReprocessChange,
  onCompileDialogOpenChange,
  onDraftSurfaceModeChange,
  onEditorModeChange,
  onExportMenuOpenChange,
  onFocusModeChange,
  onIncludeTableOfContentsChange,
  onInspectorOpenChange,
  onOpenProject,
  onOutlineOpenChange,
  onPresetChange,
  onPrint,
  onRetryProcessing,
  onShowEditorSettingsChange,
  onShowReprocessConfirmChange,
  onWorkspaceTabChange,
  processingRetrying,
  reprocessCta,
  reprocessing,
  saveStateByTarget,
  showExportMenu,
  inspectorOpen,
  workspaceSaving,
  workspaceTab,
}: ManuscriptHeaderProps) {
  const failedTarget = Object.entries(saveStateByTarget).find(([, state]) => state === "error")?.[0] as SaveTarget | undefined
  const headerRef = useRef<HTMLElement>(null)
  const moreRef = useRef<HTMLDetailsElement>(null)

  useEffect(() => {
    const header = headerRef.current
    const workspace = header?.closest<HTMLElement>("[data-manuscript-workspace]")
    if (!header || !workspace || typeof ResizeObserver === "undefined") return
    const observer = new ResizeObserver(() => workspace.style.setProperty("--manuscript-header-height", `${header.getBoundingClientRect().height}px`))
    observer.observe(header)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    function dismiss(event: PointerEvent) {
      if (event.target instanceof Node && !moreRef.current?.contains(event.target) && moreRef.current) moreRef.current.open = false
    }
    document.addEventListener("pointerdown", dismiss)
    return () => document.removeEventListener("pointerdown", dismiss)
  }, [])

  return (
    <header ref={headerRef} className={`relative z-40 border-b xl:sticky xl:top-0 ${isDark ? "border-white/10 bg-[#111416]" : "border-stone-200 bg-white"}`}>
      <h1 className="sr-only">{bookTitle || "Manuscript"} manuscript editor</h1>
      <div className="flex flex-col">
        <div className="flex min-h-[4.25rem] flex-col gap-4 px-4 py-3 lg:flex-row lg:items-center lg:justify-between lg:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <span className={`inline-flex h-7 w-7 shrink-0 items-center justify-center ${isDark ? "text-slate-200" : "text-stone-700"}`} aria-hidden>
              <BookOpenIcon />
            </span>
            <Link
              href={homeHref as Route}
              data-testid="manuscript-home-link"
              className={`shrink-0 text-sm font-semibold ${isDark ? "text-slate-300 hover:text-teal-200" : "text-stone-600 hover:text-teal-700"}`}
            >
              Home
            </Link>
            <button
              type="button"
              onClick={onOpenProject}
              className={`flex min-w-0 items-center gap-2 text-left text-base font-semibold ${isDark ? "text-white hover:text-teal-200" : "text-stone-950 hover:text-teal-700"}`}
              title="Open project overview"
            >
              <span className="truncate">{bookTitle || "Manuscript"}</span>
              <span className={`hidden text-xs font-normal sm:inline ${isDark ? "text-slate-400" : "text-stone-600"}`}>Overview</span>
            </button>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-2">
              <SaveStatePill state={activeSaveState} />
              {activeLastSavedAt ? <LastSavedLabel value={activeLastSavedAt} className="hidden sm:inline" /> : null}
            </div>
            <div className="hidden sm:block">
              <ManuscriptExportMenu
                isDark={isDark}
                open={showExportMenu}
                activePreset={activePreset}
                exporting={exporting}
                includeTableOfContents={includeTableOfContentsOnExport}
                onToggle={() => onExportMenuOpenChange((value) => !value)}
                onPresetChange={onPresetChange}
                onIncludeTableOfContentsChange={onIncludeTableOfContentsChange}
                onPrint={() => {
                  onExportMenuOpenChange(false)
                  onPrint()
                }}
                onCompile={(format) => {
                  compileFormatSetter(format)
                  onExportMenuOpenChange(false)
                  onCompileDialogOpenChange(true)
                }}
              />
            </div>
            <button onClick={() => onFocusModeChange((value) => !value)} className={`hidden min-h-10 rounded-sm border px-4 text-sm font-medium sm:block ${focusMode ? isDark ? "border-emerald-300/40 bg-emerald-400/15 text-white" : "border-emerald-300 bg-emerald-50 text-stone-900" : isDark ? "border-white/10 bg-white/[0.03] text-slate-200 hover:bg-white/[0.06]" : "border-stone-200 bg-white text-stone-700"}`}>
              {focusMode ? "Exit focus" : "Focus mode"}
            </button>
            {reprocessCta.visible ? (
              <button
                type="button"
                disabled={reprocessCta.disabled || reprocessing}
                title={reprocessCta.disabledReason ?? undefined}
                onClick={() => {
                  if (reprocessing) return
                  onShowReprocessConfirmChange(true)
                }}
                className={`hidden min-h-10 rounded-sm border px-4 text-sm font-medium disabled:opacity-40 sm:block ${
                  reprocessCta.isProcessing
                    ? isDark ? "border-sky-400/30 bg-sky-500/15 text-sky-200" : "border-sky-300 bg-sky-50 text-sky-700"
                    : isDark ? "border-white/10 bg-white/[0.03] text-slate-200 hover:bg-white/[0.06]" : "border-stone-200 bg-white text-stone-700"
                }`}
              >
                {reprocessCta.label}
              </button>
            ) : null}
            <details ref={moreRef} className="relative" onKeyDown={(event) => {
              if (event.key === "Escape") {
                event.currentTarget.open = false
                event.currentTarget.querySelector("summary")?.focus()
              }
            }} onBlur={(event) => {
              if (event.relatedTarget instanceof Node && !event.currentTarget.contains(event.relatedTarget)) event.currentTarget.open = false
            }} onClick={(event) => {
              if (event.target instanceof Element && event.target.closest("button, a")) event.currentTarget.open = false
            }}>
              <summary className={`flex min-h-10 cursor-pointer list-none items-center rounded-sm border px-3 text-sm font-medium ${isDark ? "border-white/10 bg-white/[0.03] text-slate-200 hover:bg-white/[0.06]" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"}`}>More</summary>
              <div className={`absolute left-0 top-full z-50 mt-2 max-h-[65dvh] w-64 overflow-y-auto rounded-sm border p-3 sm:left-auto sm:right-0 sm:w-72 ${isDark ? "border-white/15 bg-[#111416]" : "border-stone-200 bg-white"}`}>
                <div className={`grid gap-1 border-b pb-2 sm:hidden ${isDark ? "border-white/10" : "border-stone-200"}`}>
                  <Link href={`${homeHref}/export` as Route} className={`px-1 py-2 text-sm font-medium ${isDark ? "text-slate-200" : "text-stone-700"}`}>Files &amp; export</Link>
                  <button type="button" onClick={() => onFocusModeChange((value) => !value)} className={`px-1 py-2 text-left text-sm font-medium ${isDark ? "text-slate-200" : "text-stone-700"}`}>{focusMode ? "Exit focus mode" : "Enter focus mode"}</button>
                  {reprocessCta.visible ? (
                    <button
                      type="button"
                      disabled={reprocessCta.disabled || reprocessing}
                      onClick={() => onShowReprocessConfirmChange(true)}
                      className={`px-1 py-2 text-left text-sm font-medium disabled:opacity-40 ${isDark ? "text-slate-200" : "text-stone-700"}`}
                    >
                      {reprocessCta.label}
                    </button>
                  ) : null}
                </div>
                <label
                  className={`flex items-start gap-3 px-1 py-2 text-sm ${isDark ? "text-slate-200" : "text-stone-700"}`}
                  title="Turning this off stops LoreVia from reprocessing saved edits automatically."
                >
                  <input
                    type="checkbox"
                    checked={autoReprocessEnabled}
                    disabled={workspaceSaving}
                    onChange={(event) => onAutoReprocessChange(event.target.checked)}
                    className="mt-0.5 h-4 w-4 rounded border-stone-300"
                  />
                  <span>
                    <span className="block font-medium">Auto reprocess edits</span>
                    <span className={`mt-1 block text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-500"}`}>Refresh story intelligence after saved edits.</span>
                  </span>
                </label>
                <button
                  type="button"
                  onClick={() => onShowEditorSettingsChange((value) => !value)}
                  className={`mt-1 w-full border-t px-1 pt-3 text-left text-sm font-medium ${isDark ? "border-white/10 text-slate-200" : "border-stone-200 text-stone-700"}`}
                >
                  Editor settings
                </button>
                <button type="button" onClick={() => {
                  moreRef.current?.querySelector("summary")?.focus()
                  window.dispatchEvent(new CustomEvent(SUPPORT_HELP_EVENT))
                }} className={`mt-2 w-full px-1 py-2 text-left text-sm font-medium ${isDark ? "text-slate-200" : "text-stone-700"}`}>
                  Help
                </button>
              </div>
            </details>
          </div>
        </div>
        {!autoReprocessEnabled ? (
          <div className={`border-t px-4 py-2 text-sm lg:px-6 ${isDark ? "border-white/10 bg-amber-400/10 text-amber-100" : "border-amber-200 bg-amber-50 text-amber-900"}`}>
            Turning this off stops LoreVia from reprocessing saved edits automatically. To update story memory, open each edited chapter and click Reprocess. This adds extra steps, but can reduce token usage.
          </div>
        ) : null}
        {normalizedProcessingStatus && !normalizedProcessingStatus.ready ? (
          <div className={`border-t px-4 py-2 lg:px-6 ${isDark ? "border-white/10" : "border-stone-200"}`}>
            <ProcessingStatusStrip
              status={normalizedProcessingStatus}
              retrying={processingRetrying}
              onRetry={normalizedProcessingStatus.retryAvailable || normalizedProcessingStatus.resumeAvailable ? onRetryProcessing : undefined}
            />
          </div>
        ) : null}
        {failedTarget ? (
          <div className={`border-t px-4 py-2 lg:px-6 ${isDark ? "border-white/10" : "border-stone-200"}`}>
            <RecoverableInlineError
              message="One change could not be saved."
              actionLabel="Retry"
              onAction={failedSaveByTarget[failedTarget] ? () => void failedSaveByTarget[failedTarget]?.() : undefined}
            >
              Your local draft is still visible in this browser.
            </RecoverableInlineError>
          </div>
        ) : null}
        <div className={`flex flex-wrap items-center gap-x-4 gap-y-2 border-t px-4 py-2 lg:justify-between lg:px-6 ${isDark ? "border-white/10" : "border-stone-200"}`}>
          <div className="flex flex-wrap items-center gap-4" role="tablist" aria-label="Manuscript workspace modes">
            {WORKSPACE_TABS.map((tab) => (
              <button
                key={tab.id}
                type="button"
                role="tab"
                id={`manuscript-tab-${tab.id}`}
                aria-controls="manuscript-workspace-panel"
                tabIndex={workspaceTab === tab.id ? 0 : -1}
                aria-selected={workspaceTab === tab.id}
                onKeyDown={(event) => {
                  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return
                  event.preventDefault()
                  const index = WORKSPACE_TABS.findIndex((item) => item.id === tab.id)
                  const next = event.key === "Home" ? 0 : event.key === "End" ? WORKSPACE_TABS.length - 1 : (index + (event.key === "ArrowRight" ? 1 : -1) + WORKSPACE_TABS.length) % WORKSPACE_TABS.length
                  onWorkspaceTabChange(WORKSPACE_TABS[next].id)
                  document.getElementById(`manuscript-tab-${WORKSPACE_TABS[next].id}`)?.focus()
                }}
                onClick={() => onWorkspaceTabChange(tab.id)}
                title={tab.title}
                className={`border-b-2 py-3 text-sm font-medium transition ${workspaceTab === tab.id ? isDark ? "border-teal-300 text-white" : "border-teal-600 text-stone-950" : isDark ? "border-transparent text-slate-400 hover:text-slate-200" : "border-transparent text-stone-500 hover:text-stone-800"}`}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <div className="contents sm:ml-auto sm:flex sm:flex-wrap sm:items-center sm:gap-2">
            <button
              type="button"
              aria-pressed={outlineOpen}
              onClick={() => onOutlineOpenChange((value) => !value)}
              className={`min-h-9 rounded-sm border px-3 text-sm font-medium ${outlineOpen ? isDark ? "border-teal-300/40 text-white" : "border-teal-600 text-teal-800" : isDark ? "border-white/10 text-slate-300" : "border-stone-200 text-stone-600"}`}
            >
              Outline
            </button>
            <button
              type="button"
              aria-pressed={inspectorOpen}
              disabled={workspaceTab === "plan"}
              onClick={() => onInspectorOpenChange((value) => !value)}
              className={`min-h-9 rounded-sm border px-3 text-sm font-medium disabled:opacity-40 ${inspectorOpen ? isDark ? "border-teal-300/40 text-white" : "border-teal-600 text-teal-800" : isDark ? "border-white/10 text-slate-300" : "border-stone-200 text-stone-600"}`}
            >
              Inspector
            </button>
            <div className="hidden items-center gap-2 sm:flex">
              <ManuscriptModeSwitch
                isDark={isDark}
                options={["edit", "paged"] as const}
                selected={draftSurfaceMode}
                onSelect={onDraftSurfaceModeChange}
                renderLabel={(mode) => mode === "edit" ? "Draft" : "Paged preview"}
              />
              <ManuscriptModeSwitch
                isDark={isDark}
                options={["chapter", "book"] as const}
                selected={editorMode}
                onSelect={onEditorModeChange}
                renderLabel={(mode) => mode === "chapter" ? "Chapter" : "Full book"}
              />
            </div>
            <div className="grid w-full grid-cols-2 gap-2 sm:hidden">
              <select aria-label="Draft view" value={draftSurfaceMode} onChange={(event) => onDraftSurfaceModeChange(event.target.value as DraftSurfaceMode)} className={`min-h-10 rounded-sm border px-3 text-sm ${isDark ? "border-white/10 bg-[#0b1014] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                <option value="edit">Draft</option>
                <option value="paged">Paged preview</option>
              </select>
              <select aria-label="Manuscript scope" value={editorMode} onChange={(event) => onEditorModeChange(event.target.value as EditorMode)} className={`min-h-10 rounded-sm border px-3 text-sm ${isDark ? "border-white/10 bg-[#0b1014] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                <option value="chapter">Chapter</option>
                <option value="book">Full book</option>
              </select>
            </div>
          </div>
        </div>
      </div>
    </header>
  )
}
