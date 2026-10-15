import type { WikiEntry, WorldQueryResponse } from "@/types/world-building"

import { EmptyState, LabeledField, LoadingState, WorkspaceCard } from "./WorldbuildingWorkspace.components"
import {
  accentBadgeClass,
  badgeClass,
  bodyTextClass,
  eyebrowClass,
  inputClass,
  mutedTextClass,
  primaryButtonClass,
  secondaryButtonClass,
  softPanelClass,
  worldRecordText,
  titleTextClass,
} from "./WorldbuildingWorkspace.helpers"

export function AutoWikiCard({
  isDark,
  logicQuery,
  logicLoading,
  logicResult,
  submittedQuery,
  logicStale,
  wikiEntries,
  wikiEntriesLoading,
  wikiGenerating,
  visibleWikiEntries,
  wikiTypeSummary,
  showAllWikiEntries,
  initialWikiCount,
  onLogicQueryChange,
  onRunLogicQuery,
  onRefreshWiki,
  onGenerateWiki,
  onToggleShowAllWikiEntries,
}: {
  isDark: boolean
  logicQuery: string
  logicLoading: boolean
  logicResult: WorldQueryResponse | null
  submittedQuery?: string
  logicStale?: boolean
  wikiEntries: WikiEntry[]
  wikiEntriesLoading: boolean
  wikiGenerating: boolean
  visibleWikiEntries: WikiEntry[]
  wikiTypeSummary: Record<string, number>
  showAllWikiEntries: boolean
  initialWikiCount: number
  onLogicQueryChange: (value: string) => void
  onRunLogicQuery: (mode: string) => void
  onRefreshWiki: () => void
  onGenerateWiki: () => void
  onToggleShowAllWikiEntries: () => void
}) {
  return (
    <WorkspaceCard
      number="7"
      sectionLabel="Auto Wiki"
      title="Generate wiki entries from manuscript text"
      description="Query the current canon, then generate entries, next moves, and source citations in one place."
      isDark={isDark}
      action={(
        <div className="flex flex-wrap gap-2">
          <button type="button" onClick={onRefreshWiki} className={secondaryButtonClass(isDark)}>
            Refresh
          </button>
          <button
            type="button"
            onClick={onGenerateWiki}
            disabled={wikiGenerating}
            className={primaryButtonClass("blue")}
          >
            {wikiGenerating ? "Generating..." : "Generate wiki"}
          </button>
        </div>
      )}
    >
      <div className="grid gap-4 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
        <div className={`rounded-lg border p-4 ${softPanelClass(isDark)}`}>
          <LabeledField label="Query the canon" isDark={isDark}>
            <textarea
              value={logicQuery}
              onChange={(event) => onLogicQueryChange(event.target.value)}
              rows={6}
              className={`${inputClass(isDark)} min-h-[10rem] resize-y leading-6`}
            />
          </LabeledField>
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" onClick={() => onRunLogicQuery("story_integration")} disabled={logicLoading || !logicQuery.trim()} className={primaryButtonClass("teal")}>
              {logicLoading ? "Thinking..." : "Run simulation"}
            </button>
            <button type="button" onClick={() => onRunLogicQuery("gap_detection")} disabled={logicLoading || !logicQuery.trim()} className={secondaryButtonClass(isDark)}>
              Canon status
            </button>
          </div>

          {logicResult ? (
            <div className={`mt-4 rounded-md border p-4 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-white bg-white"}`}>
              {submittedQuery ? <p className="mb-3 text-sm"><strong>Submitted question:</strong> {submittedQuery}{logicQuery.trim() !== submittedQuery ? " — the editor now contains a different question." : ""}</p> : null}
              {logicStale ? <p className="mb-3 border-l-2 border-amber-500 pl-3 text-sm" role="status">Canon sources or aliases have changed since this query began. Run the question again to use the latest context.</p> : null}
              <div className="flex flex-wrap gap-2">
                <span className={accentBadgeClass("teal", isDark)}>{logicResult.mode === "gap_detection" ? "Canon stress test" : "Story integration"}</span>
                {logicResult.logic_alerts.length > 0 ? <span className={accentBadgeClass("amber", isDark)}>{logicResult.logic_alerts.length} alerts</span> : null}
                {logicResult.citations.length > 0 ? <span className={accentBadgeClass("blue", isDark)}>{logicResult.citations.length} citations</span> : null}
              </div>
              <p className={`mt-3 text-sm leading-7 ${bodyTextClass(isDark)}`}>{logicResult.answer}</p>
              {logicResult.simulation_steps.length > 0 ? (
                <div className="mt-4 space-y-2">
                  <p className={eyebrowClass(isDark)}>Simulation steps</p>
                  {logicResult.simulation_steps.map((step) => (
                    <p key={step} className={`text-xs ${mutedTextClass(isDark)}`}>{step}</p>
                  ))}
                </div>
              ) : null}
              {logicResult.logic_alerts.length > 0 ? (
                <div className="mt-4 space-y-2">
                  <p className={eyebrowClass(isDark)}>Logic alerts</p>
                  {logicResult.logic_alerts.map((alert, index) => (
                    <div key={`alert-${index}`} className={`rounded-xl border px-3 py-2 text-sm ${isDark ? "border-rose-400/20 bg-rose-500/10 text-rose-100" : "border-rose-200 bg-rose-50 text-rose-800"}`}>
                      {worldRecordText(alert)}
                    </div>
                  ))}
                </div>
              ) : null}
              {logicResult.suggestions.length > 0 ? (
                <div className="mt-4 space-y-2">
                  <p className={eyebrowClass(isDark)}>Suggested next moves</p>
                  {logicResult.suggestions.map((suggestion, index) => (
                    <div key={`suggestion-${index}`} className={`rounded-xl border px-3 py-2 text-sm ${softPanelClass(isDark)}`}>
                      {worldRecordText(suggestion)}
                    </div>
                  ))}
                </div>
              ) : null}
              {logicResult.citations.length > 0 ? (
                <div className="mt-4 space-y-2">
                  <p className={eyebrowClass(isDark)}>Source citations</p>
                  {logicResult.citations.map((citation, index) => (
                    <div key={`citation-${index}`} className={`rounded-xl border px-3 py-2 text-sm ${softPanelClass(isDark)}`}>
                      {worldRecordText(citation)}
                    </div>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}
        </div>

        <div className={`rounded-lg border p-4 ${softPanelClass(isDark)}`}>
          <div className="flex flex-wrap gap-2">
            <span className={badgeClass(isDark)}>{wikiEntries.length} total</span>
            {Object.entries(wikiTypeSummary).slice(0, 3).map(([type, count]) => (
              <span key={type} className={accentBadgeClass("blue", isDark)}>
                {count} {type}
              </span>
            ))}
          </div>
          <div className="mt-4 space-y-3">
            {wikiEntriesLoading ? <LoadingState label="Loading wiki entries..." isDark={isDark} /> : null}
            {!wikiEntriesLoading && wikiEntries.length === 0 ? (
              <EmptyState
                title="No wiki entries yet."
                description="The wiki has not been generated from the manuscript yet. Generate entries when processing has enough story text."
                isDark={isDark}
                action={(
                  <button
                    type="button"
                    onClick={onGenerateWiki}
                    disabled={wikiGenerating}
                    className={secondaryButtonClass(isDark)}
                  >
                    {wikiGenerating ? "Generating..." : "Generate wiki"}
                  </button>
                )}
              />
            ) : null}
            {visibleWikiEntries.map((entry) => (
              <article key={entry.id} className={`rounded-md border p-3 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-white bg-white"}`}>
                <div className="flex items-center justify-between gap-3">
                  <h4 className={`text-sm font-semibold ${titleTextClass(isDark)}`}>{entry.name}</h4>
                  <span className={badgeClass(isDark)}>{entry.entry_type}</span>
                </div>
                {entry.first_mention ? <p className={`mt-1 text-xs ${mutedTextClass(isDark)}`}>First mention: chapter {entry.first_mention}</p> : null}
                {entry.description ? <p className={`mt-2 text-sm leading-6 ${bodyTextClass(isDark)}`}>{entry.description}</p> : null}
              </article>
            ))}
            {wikiEntries.length > initialWikiCount ? (
              <button
                type="button"
                onClick={onToggleShowAllWikiEntries}
                className={`${secondaryButtonClass(isDark)} w-full`}
              >
                {showAllWikiEntries ? "Show fewer entries" : `Show all ${wikiEntries.length} entries`}
              </button>
            ) : null}
          </div>
        </div>
      </div>
    </WorkspaceCard>
  )
}
