import Link from "next/link"
import type { Route } from "next"

import type { WorldGapItem, WorldGapResult } from "@/types/world-building"

import { EmptyState, EvidencePanel, LoadingState, SectionPanel, WorkspaceCard } from "./WorldbuildingWorkspace.components"
import {
  accentBadgeClass,
  badgeClass,
  bodyTextClass,
  mutedActionClass,
  mutedTextClass,
  primaryButtonClass,
  secondaryButtonClass,
  severityClass,
  softPanelClass,
  titleTextClass,
} from "./WorldbuildingWorkspace.helpers"

export function GapAnalysisCard({
  bookId,
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
  return (
    <WorkspaceCard
      number="2"
      sectionLabel="Gap Analysis"
      title="Grouped inconsistencies and cleanup notes"
      description={analysis?.generated_at ? `Last run ${new Date(analysis.generated_at).toLocaleString()}` : "Run a pass after updating the world corpus or story manuscript to surface inconsistencies and cleanup notes."}
      isDark={isDark}
      action={(
        <button
          type="button"
          onClick={onRunAnalysis}
          disabled={analysisLoading || !documentsAvailable}
          className={secondaryButtonClass(isDark)}
        >
          {analysisLoading ? "Checking gaps..." : "Run gap detection"}
        </button>
      )}
    >
      {analysisLoading ? (
        <LoadingState label="Comparing the world corpus against chapters, characters, and timeline signals..." isDark={isDark} />
      ) : analysis ? (
        <div className="space-y-4">
          {analysis.consistency_flags.length > 0 ? (
            <SectionPanel
              title="Consistency flags"
              meta={`${analysis.consistency_flags.length} item${analysis.consistency_flags.length === 1 ? "" : "s"}`}
              description="These checks caught conflicting definitions inside the extracted canon before broader gap grouping was applied."
              isDark={isDark}
            >
              <div className="grid gap-3">
                {analysis.consistency_flags.map((flag, index) => (
                  <article key={String(flag.id ?? `consistency-${index}`)} className={`rounded-md border p-4 ${softPanelClass(isDark)}`}>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={severityClass("high", isDark)}>high</span>
                      {flag.type ? <span className={badgeClass(isDark)}>{String(flag.type).replaceAll("_", " ")}</span> : null}
                    </div>
                    <h4 className={`mt-3 text-base font-semibold ${titleTextClass(isDark)}`}>{String(flag.title ?? "Consistency flag")}</h4>
                    <p className={`mt-2 text-sm leading-6 ${bodyTextClass(isDark)}`}>{String(flag.description ?? "LoreVia found an extracted canon definition that needs a closer pass.")}</p>
                  </article>
                ))}
              </div>
            </SectionPanel>
          ) : null}

          {analysis.gap_groups.length === 0 && analysis.consistency_flags.length === 0 ? (
            <EmptyState
              title="No analysis yet."
              description="Gap results need reference documents and a completed scan. Upload canon material, then run detection."
              isDark={isDark}
              action={(
                <button
                  type="button"
                  onClick={onRunAnalysis}
                  disabled={runButtonLoading || !documentsAvailable}
                  className={secondaryButtonClass(isDark)}
                >
                  {runButtonLoading ? "Running..." : "Run gap detection"}
                </button>
              )}
            />
          ) : (
            analysis.gap_groups.map((group) => (
              <SectionPanel
                key={group.key}
                title={group.label}
                meta={`${group.items.length} item${group.items.length === 1 ? "" : "s"}`}
                description={group.description ?? undefined}
                isDark={isDark}
              >
                <div className="grid gap-3">
                  {(expandedGapGroups[group.key] ? group.items : group.items.slice(0, initialGapItemsPerGroup)).map((item) => {
                    const alreadySaved = openGapIds.has(item.id)
                    return (
                      <article key={item.id} className={`rounded-md border p-4 ${softPanelClass(isDark)}`}>
                        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className={severityClass(item.severity, isDark)}>{item.severity}</span>
                              {item.world_document_title ? <span className={badgeClass(isDark)}>{item.world_document_title}</span> : null}
                              {item.story_chapter_number ? (
                                <Link href={`/${bookId}/chapter/${item.story_chapter_number}` as Route} className={accentBadgeClass("blue", isDark)}>
                                  Chapter {item.story_chapter_number}
                                </Link>
                              ) : null}
                            </div>
                            <h4 className={`mt-3 text-base font-semibold ${titleTextClass(isDark)}`}>{item.title}</h4>
                            {item.canonical_name ? (
                              <p className={`mt-1 text-xs ${mutedTextClass(isDark)}`}>
                                Canon: {item.canonical_name}
                                {item.entity_type ? ` - ${item.entity_type}` : ""}
                                {item.confidence ? ` - ${(item.confidence * 100).toFixed(0)}% confidence` : ""}
                              </p>
                            ) : null}
                            <p className={`mt-2 text-sm leading-6 ${bodyTextClass(isDark)}`}>{item.description}</p>
                          </div>
                          <button
                            type="button"
                            onClick={() => onSaveGapAsNote(item)}
                            disabled={alreadySaved || noteSavingId === item.id}
                            className={alreadySaved ? mutedActionClass(isDark, "teal") : primaryButtonClass("violet")}
                          >
                            {alreadySaved ? "Saved to notes" : noteSavingId === item.id ? "Saving..." : "Save as note"}
                          </button>
                        </div>

                        <div className="mt-4 grid gap-3 lg:grid-cols-2">
                          <EvidencePanel title="World evidence" body={item.world_evidence || "No direct world document excerpt was attached to this item."} isDark={isDark} />
                          <EvidencePanel title="Story evidence" body={item.story_evidence || "No direct story excerpt was attached to this item."} isDark={isDark} />
                        </div>

                        <div className={`mt-4 rounded-md border px-4 py-3 ${isDark ? "border-amber-300/15 bg-amber-400/10 text-amber-100" : "border-amber-200 bg-amber-50 text-amber-900"}`}>
                          <p className="text-3xs font-semibold uppercase tracking-[0.22em]">Suggested fix</p>
                          <p className="mt-2 text-sm leading-6">{item.suggested_fix}</p>
                        </div>
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
              </SectionPanel>
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
              {runButtonLoading ? "Running..." : "Run gap detection"}
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
    </WorkspaceCard>
  )
}
