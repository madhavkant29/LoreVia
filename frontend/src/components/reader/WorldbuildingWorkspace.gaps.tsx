import Link from "next/link"
import type { Route } from "next"
import { useState } from "react"

import type { WorldGapItem, WorldGapResult } from "@/types/world-building"

import { EmptyState, LoadingState } from "./WorldbuildingWorkspace.components"
import {
  bodyTextClass,
  mutedActionClass,
  mutedTextClass,
  primaryButtonClass,
  secondaryButtonClass,
  titleTextClass,
} from "./WorldbuildingWorkspace.helpers"

function severityTextClass(severity: string, isDark: boolean) {
  const normalized = severity.toLowerCase()
  if (normalized === "critical") return isDark ? "text-rose-300" : "text-rose-700"
  if (normalized === "high") return isDark ? "text-amber-300" : "text-amber-800"
  return isDark ? "text-slate-400" : "text-stone-500"
}

export function GapAnalysisCard({
  bookId,
  availableChapters = [],
  isDark,
  analysis,
  analysisLoading,
  runButtonLoading,
  documentsAvailable,
  expandedGapGroups,
  openGapIds,
  noteSavingId,
  initialGapItemsPerGroup,
  onRunAnalysis,
  onStartNewDocument,
  onSaveGapAsNote,
  onToggleGapGroup,
}: {
  bookId: string
  availableChapters?: number[]
  isDark: boolean
  analysis: WorldGapResult | null
  analysisLoading: boolean
  runButtonLoading: boolean
  documentsAvailable: boolean
  expandedGapGroups: Record<string, boolean>
  openGapIds: Set<string>
  noteSavingId: string | null
  initialGapItemsPerGroup: number
  onRunAnalysis: () => void
  onStartNewDocument: () => void
  onSaveGapAsNote: (item: WorldGapItem) => void
  onToggleGapGroup: (groupKey: string) => void
}) {
  const [selectedGapId, setSelectedGapId] = useState<string | null>(null)
  const gapCount = analysis?.gap_groups.reduce((total, group) => total + group.items.length, 0) ?? 0

  return (
    <section aria-label="Canon conflicts">
      <div className={`flex flex-col gap-4 border-b pb-4 sm:flex-row sm:items-end sm:justify-between ${isDark ? "border-white/10" : "border-stone-200"}`}>
        <div>
          <h2 className={`text-lg font-semibold ${titleTextClass(isDark)}`}>Canon conflicts</h2>
          <p className={`mt-1 text-sm leading-6 ${mutedTextClass(isDark)}`}>
            {analysis?.generated_at
              ? `${gapCount} gap${gapCount === 1 ? "" : "s"} · Last checked ${new Date(analysis.generated_at).toLocaleString()}`
              : "Compare canon sources with the current manuscript, then save only confirmed issues to the cleanup queue."}
          </p>
        </div>
        <button
          type="button"
          onClick={onRunAnalysis}
          disabled={analysisLoading || runButtonLoading || !documentsAvailable}
          className={secondaryButtonClass(isDark)}
        >
          {analysisLoading || runButtonLoading ? "Refreshing…" : "Refresh comparison"}
        </button>
      </div>
      {analysis?.is_stale ? <p className="mt-4 border-l-2 border-amber-500 pl-3 text-sm" role="status">{analysis.generated_at ? "This comparison uses earlier source or manuscript content." : "A comparison is being prepared."} {analysis.refresh_job_id ? "A background refresh has been requested." : "Refresh to check for an updated comparison."} Results below are not a confirmed assessment of the latest content.</p> : null}
      {runButtonLoading && analysis ? <p className="mt-3 text-sm" role="status">Loading the latest comparison. The previous result remains below.</p> : null}

      {analysisLoading ? (
        <div className="mt-4"><LoadingState label="Comparing canon sources against manuscript evidence…" isDark={isDark} /></div>
      ) : analysis ? (
        <div>
          {analysis.consistency_flags.length > 0 ? (
            <section className={`border-b py-4 ${isDark ? "border-white/10" : "border-stone-200"}`}>
              <div className="flex items-baseline justify-between gap-3">
                <h3 className={`text-sm font-semibold ${titleTextClass(isDark)}`}>Source consistency</h3>
                <span className={`text-xs ${mutedTextClass(isDark)}`}>{analysis.consistency_flags.length}</span>
              </div>
              <div className={`mt-2 divide-y ${isDark ? "divide-white/10" : "divide-stone-200"}`}>
                {analysis.consistency_flags.map((flag, index) => (
                  <article key={String(flag.id ?? `consistency-${index}`)} className="py-3">
                    <div className="flex flex-wrap items-baseline gap-3">
                      <h4 className={`text-sm font-semibold ${titleTextClass(isDark)}`}>{String(flag.title ?? "Consistency flag")}</h4>
                      {flag.severity ? <span className={`text-xs font-medium ${severityTextClass(String(flag.severity), isDark)}`}>{String(flag.severity)} priority</span> : null}
                      {flag.type ? <span className={`text-xs ${mutedTextClass(isDark)}`}>{String(flag.type).replaceAll("_", " ")}</span> : null}
                    </div>
                    <p className={`mt-1 text-sm leading-6 ${bodyTextClass(isDark)}`}>{String(flag.description ?? "LoreVia found an extracted canon definition that needs a closer pass.")}</p>
                  </article>
                ))}
              </div>
            </section>
          ) : null}

          {analysis.gap_groups.length === 0 && analysis.consistency_flags.length === 0 ? (
            <EmptyState
              title={analysis.generated_at ? "No gaps were flagged in this comparison." : "No completed comparison is available yet."}
              description={analysis.generated_at ? "This reflects the available canon and manuscript evidence. It does not establish that every world detail is consistent." : "Canon comparisons refresh in the background after source changes. Refresh to check the latest result."}
              isDark={isDark}
              action={(
                <button
                  type="button"
                  onClick={onRunAnalysis}
                  disabled={runButtonLoading || !documentsAvailable}
                  className={secondaryButtonClass(isDark)}
                >
                  {runButtonLoading ? "Refreshing..." : "Check latest comparison"}
                </button>
              )}
            />
          ) : (
            analysis.gap_groups.map((group) => (
              <section key={group.key} className={`border-b py-4 ${isDark ? "border-white/10" : "border-stone-200"}`}>
                <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
                  <div>
                    <h3 className={`text-sm font-semibold ${titleTextClass(isDark)}`}>{group.label}</h3>
                    {group.description ? <p className={`mt-1 text-sm ${mutedTextClass(isDark)}`}>{group.description}</p> : null}
                  </div>
                  <span className={`text-xs ${mutedTextClass(isDark)}`}>{group.items.length} item{group.items.length === 1 ? "" : "s"}</span>
                </div>
                <div className={`mt-3 divide-y border-t ${isDark ? "divide-white/10 border-white/10" : "divide-stone-200 border-stone-200"}`}>
                  {(expandedGapGroups[group.key] ? group.items : group.items.slice(0, initialGapItemsPerGroup)).map((item) => {
                    const alreadySaved = openGapIds.has(item.id)
                    const isSelected = selectedGapId === item.id
                    return (
                      <article key={item.id}>
                        <button
                          type="button"
                          aria-expanded={isSelected}
                          onClick={() => setSelectedGapId(isSelected ? null : item.id)}
                          className={`w-full py-4 text-left ${isSelected ? (isDark ? "bg-white/[0.04]" : "bg-stone-50") : ""}`}
                        >
                          <span className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                            <span className="min-w-0">
                              <span className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                                <span className={`font-medium ${severityTextClass(item.severity, isDark)}`}>{item.severity.charAt(0).toUpperCase() + item.severity.slice(1)} priority</span>
                                {item.world_document_title ? <span className={mutedTextClass(isDark)}>{item.world_document_title}</span> : null}
                                {item.story_chapter_number ? <span className={mutedTextClass(isDark)}>Chapter {item.story_chapter_number}</span> : null}
                              </span>
                              <span className={`mt-2 block text-base font-semibold ${titleTextClass(isDark)}`}>{item.title}</span>
                              <span className={`mt-1 block text-sm leading-6 ${bodyTextClass(isDark)}`}>{item.description}</span>
                            </span>
                            <span className={`shrink-0 text-xs font-medium ${isDark ? "text-slate-300" : "text-stone-600"}`}>{isSelected ? "Hide evidence" : "Review evidence"}</span>
                          </span>
                        </button>

                        {isSelected ? (
                          <div className={`border-t pb-5 pt-4 ${isDark ? "border-white/10 bg-white/[0.02]" : "border-stone-200 bg-stone-50/60"}`}>
                            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                              <div>
                                {item.canonical_name ? (
                                  <p className={`text-xs ${mutedTextClass(isDark)}`}>
                                    Canon: {item.canonical_name}
                                    {item.entity_type ? ` · ${item.entity_type}` : ""}
                                    {item.confidence ? ` · ${(item.confidence * 100).toFixed(0)}% confidence` : ""}
                                  </p>
                                ) : null}
                                {item.story_chapter_number && availableChapters.includes(item.story_chapter_number) ? (
                                  <Link href={`/${bookId}/manuscript?chapter=${item.story_chapter_number}` as Route} className={`mt-2 inline-flex text-sm underline decoration-transparent underline-offset-4 hover:decoration-current ${isDark ? "text-sky-300" : "text-sky-700"}`}>
                                    Open chapter {item.story_chapter_number}
                                  </Link>
                                ) : item.story_chapter_number ? <p className="mt-2 text-sm">This chapter has not been verified in the current manuscript chapter list.</p> : null}
                              </div>
                              <button
                                type="button"
                                onClick={() => onSaveGapAsNote(item)}
                                disabled={alreadySaved || !!noteSavingId}
                                className={alreadySaved ? mutedActionClass(isDark, "teal") : primaryButtonClass("teal")}
                              >
                                {alreadySaved ? "Saved to cleanup" : noteSavingId === item.id ? "Saving…" : "Add to cleanup"}
                              </button>
                            </div>

                            <dl className={`mt-4 grid border-y lg:grid-cols-2 ${isDark ? "border-white/10" : "border-stone-200"}`}>
                              <div className="py-3 lg:pr-5">
                                <dt className={`text-xs ${mutedTextClass(isDark)}`}>Canon evidence</dt>
                                <dd className={`mt-1 text-sm leading-6 ${bodyTextClass(isDark)}`}>{item.world_evidence || "No canon excerpt attached."}</dd>
                              </div>
                              <div className={`py-3 lg:border-l lg:pl-5 ${isDark ? "border-white/10" : "border-stone-200"}`}>
                                <dt className={`text-xs ${mutedTextClass(isDark)}`}>Manuscript evidence</dt>
                                <dd className={`mt-1 text-sm leading-6 ${bodyTextClass(isDark)}`}>{item.story_evidence || "No manuscript excerpt attached."}</dd>
                              </div>
                            </dl>

                            <div className="mt-3 grid gap-1 sm:grid-cols-[110px_minmax(0,1fr)]">
                              <p className={`text-xs ${mutedTextClass(isDark)}`}>Suggested fix</p>
                              <p className={`text-sm leading-6 ${isDark ? "text-amber-100" : "text-amber-900"}`}>{item.suggested_fix}</p>
                            </div>
                          </div>
                        ) : null}
                      </article>
                    )
                  })}
                </div>
                {group.items.length > initialGapItemsPerGroup ? (
                  <button
                    type="button"
                    onClick={() => onToggleGapGroup(group.key)}
                    className={`mt-3 ${secondaryButtonClass(isDark)}`}
                  >
                    {expandedGapGroups[group.key] ? "Show fewer items" : `Show all ${group.items.length} items`}
                  </button>
                ) : null}
              </section>
            ))
          )}
        </div>
      ) : (
        <EmptyState
          title="No analysis yet."
          description={documentsAvailable
            ? "Gap detection has not run yet. Start a scan to compare your reference docs with the manuscript."
            : "Reference docs are missing. Upload canon material first, then run gap detection."}
          isDark={isDark}
          action={documentsAvailable ? (
            <button
              type="button"
              onClick={onRunAnalysis}
              disabled={runButtonLoading}
              className={secondaryButtonClass(isDark)}
            >
              {runButtonLoading ? "Refreshing..." : "Check latest comparison"}
            </button>
          ) : (
            <button
              type="button"
              onClick={onStartNewDocument}
              className={secondaryButtonClass(isDark)}
            >
              Start a reference doc
            </button>
          )}
        />
      )}
    </section>
  )
}
