import type { Dispatch, SetStateAction } from "react"
import Link from "next/link"

import { ManuscriptExportMenu } from "@/components/reader/ManuscriptExportMenu"
import { ManuscriptModeSwitch } from "@/components/reader/ManuscriptModeSwitch"
import { LastSavedLabel, ProcessingStatusStrip, RecoverableInlineError, SaveStatePill } from "@/components/ui/ResponsivenessStatus"
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
  processingRetrying: boolean
  reprocessCta: ReprocessCta
  reprocessing: boolean
  saveStateByTarget: Partial<Record<SaveTarget, SaveState>>
  showExportMenu: boolean
  workspaceSaving: boolean
  workspaceTab: WorkspaceTab
  onAutoReprocessChange: (enabled: boolean) => void
  onCompileDialogOpenChange: Dispatch<SetStateAction<boolean>>
  onDraftSurfaceModeChange: Dispatch<SetStateAction<DraftSurfaceMode>>
  onEditorModeChange: Dispatch<SetStateAction<EditorMode>>
  onExportMenuOpenChange: Dispatch<SetStateAction<boolean>>
  onFocusModeChange: Dispatch<SetStateAction<boolean>>
  onIncludeTableOfContentsChange: Dispatch<SetStateAction<boolean>>
  onOpenProject: () => void
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
  onAutoReprocessChange,
  onCompileDialogOpenChange,
  onDraftSurfaceModeChange,
  onEditorModeChange,
  onExportMenuOpenChange,
  onFocusModeChange,
  onIncludeTableOfContentsChange,
  onOpenProject,
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
  workspaceSaving,
  workspaceTab,
}: ManuscriptHeaderProps) {
  const failedTarget = Object.entries(saveStateByTarget).find(([, state]) => state === "error")?.[0] as SaveTarget | undefined

  return (
    <header className={`sticky top-0 z-40 border-b ${isDark ? "border-white/10 bg-[#111416]/95" : "border-stone-200 bg-white/95"}`}>
      <div className="flex flex-col">
        <div className="flex min-h-[4.25rem] flex-col gap-4 px-4 py-3 lg:flex-row lg:items-center lg:justify-between lg:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <span className={`inline-flex h-7 w-7 shrink-0 items-center justify-center ${isDark ? "text-slate-200" : "text-stone-700"}`} aria-hidden>
              <BookOpenIcon />
            </span>
            <Link
              href={homeHref}
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
              <span className="text-xs" aria-hidden>v</span>
            </button>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <SaveStatePill state={activeSaveState} />
              <LastSavedLabel value={activeLastSavedAt} className="hidden sm:inline" />
            </div>
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
            <button onClick={() => onFocusModeChange((value) => !value)} className={`min-h-10 rounded-sm border px-4 text-sm font-medium ${focusMode ? isDark ? "border-emerald-300/40 bg-emerald-400/15 text-white" : "border-emerald-300 bg-emerald-50 text-stone-900" : isDark ? "border-white/10 bg-white/[0.03] text-slate-200 hover:bg-white/[0.06]" : "border-stone-200 bg-white text-stone-700"}`}>
              {focusMode ? "Exit focus" : "Focus mode"}
            </button>
            {saveStateByTarget.workspace ? <SaveStatePill state={saveStateByTarget.workspace} /> : null}
            {saveStateByTarget.corkboard ? <SaveStatePill state={saveStateByTarget.corkboard} /> : null}
            <label
              className={`flex min-h-10 items-center gap-2 rounded-sm border px-3 text-sm font-medium ${isDark ? "border-white/10 bg-white/[0.03] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}
              title="Turning this off stops LoreVia from reprocessing saved edits automatically."
            >
              <input
                type="checkbox"
                checked={autoReprocessEnabled}
                disabled={workspaceSaving}
                onChange={(event) => onAutoReprocessChange(event.target.checked)}
                className="h-4 w-4 rounded border-stone-300"
              />
              Auto reprocess edits
            </label>
            {reprocessCta.visible ? (
              <button
                type="button"
                disabled={reprocessCta.disabled || reprocessing}
                title={reprocessCta.disabledReason ?? undefined}
                onClick={() => {
                  if (reprocessing) return
                  onShowReprocessConfirmChange(true)
                }}
                className={`min-h-10 rounded-sm border px-4 text-sm font-medium disabled:opacity-40 ${
                  reprocessCta.isProcessing
                    ? isDark ? "border-sky-400/30 bg-sky-500/15 text-sky-200" : "border-sky-300 bg-sky-50 text-sky-700"
                    : isDark ? "border-white/10 bg-white/[0.03] text-slate-200 hover:bg-white/[0.06]" : "border-stone-200 bg-white text-stone-700"
                }`}
              >
                {reprocessCta.label}
              </button>
            ) : null}
            <button
              type="button"
              onClick={() => onShowEditorSettingsChange((value) => !value)}
              className={`inline-flex h-10 w-10 items-center justify-center rounded-sm border text-sm ${isDark ? "border-white/10 bg-white/[0.03] text-slate-200 hover:bg-white/[0.06]" : "border-stone-200 bg-white text-stone-700"}`}
              aria-label="Editor settings"
              title="Editor settings"
            >
              ...
            </button>
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
              onRetry={normalizedProcessingStatus.retryAvailable ? onRetryProcessing : undefined}
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
        <div className={`flex flex-col gap-3 border-t px-4 py-2 lg:flex-row lg:items-center lg:justify-between lg:px-6 ${isDark ? "border-white/10" : "border-stone-200"}`}>
          <div className="flex flex-wrap items-center gap-8" role="tablist" aria-label="Manuscript workspace modes">
            {WORKSPACE_TABS.map((tab) => (
              <button
                key={tab.id}
                type="button"
                role="tab"
                aria-selected={workspaceTab === tab.id}
                onClick={() => onWorkspaceTabChange(tab.id)}
                title={tab.title}
                className={`border-b-2 py-3 text-sm font-medium transition ${workspaceTab === tab.id ? isDark ? "border-teal-300 text-white" : "border-teal-600 text-stone-950" : isDark ? "border-transparent text-slate-400 hover:text-slate-200" : "border-transparent text-stone-500 hover:text-stone-800"}`}
              >
                {tab.label}
              </button>
            ))}
          </div>
          <div className="flex flex-wrap items-center gap-3 lg:ml-auto">
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
        </div>
      </div>
    </header>
  )
}
