import type { WorldIntegrationResult } from "@/types/world-building"

import { EmptyState, WorkspaceCard } from "./WorldbuildingWorkspace.components"
import {
  accentBadgeClass,
  badgeClass,
  bodyTextClass,
  primaryButtonClass,
  secondaryButtonClass,
  softPanelClass,
  titleTextClass,
} from "./WorldbuildingWorkspace.helpers"

type IntegrationOpportunity = WorldIntegrationResult["integration_opportunities"][number]

export function WorldbuildingOpportunitiesCard({
  isDark,
  documentsAvailable,
  integration,
  visibleOpportunities,
  showAllOpportunities,
  loadingIntegration,
  noteSavingId,
  initialOpportunityCount,
  onRunIntegration,
  onSaveIntegrationAsNote,
  onToggleShowAllOpportunities,
}: {
  isDark: boolean
  documentsAvailable: boolean
  integration: WorldIntegrationResult | null
  visibleOpportunities: IntegrationOpportunity[]
  showAllOpportunities: boolean
  loadingIntegration: boolean
  noteSavingId: string | null
  initialOpportunityCount: number
  onRunIntegration: () => void
  onSaveIntegrationAsNote: (item: IntegrationOpportunity) => void
  onToggleShowAllOpportunities: () => void
}) {
  const totalOpportunities = integration?.integration_opportunities.length ?? 0

  return (
    <WorkspaceCard
      number="3"
      sectionLabel="Opportunities"
      title="Underused canon and story opportunities"
      description="Find world elements that could strengthen story presence."
      isDark={isDark}
      action={(
        <button
          type="button"
          onClick={onRunIntegration}
          disabled={loadingIntegration || !documentsAvailable}
          className={secondaryButtonClass(isDark)}
        >
          {loadingIntegration ? "Mapping..." : "Refresh opportunities"}
        </button>
      )}
    >
      {integration?.is_stale ? <p role="status" className="mb-4 border-l-2 border-amber-500 pl-3 text-sm">These opportunities use earlier canon or manuscript content. A background refresh may still be running. Refresh to check the latest result.</p> : null}
      {integration ? (
        <div className="space-y-3">
          {integration.integration_opportunities.length === 0 ? (
            <EmptyState
              title="No opportunities yet."
              description="Opportunity mapping has not run, or the last scan found nothing underused. Run the scan after adding reference docs."
              isDark={isDark}
              action={(
                <button
                  type="button"
                  onClick={onRunIntegration}
                  disabled={loadingIntegration || !documentsAvailable}
                  className={secondaryButtonClass(isDark)}
                >
                  {loadingIntegration ? "Mapping..." : "Refresh opportunities"}
                </button>
              )}
            />
          ) : (
            visibleOpportunities.map((item) => (
              <article key={item.id} className={`rounded-md border p-4 ${softPanelClass(isDark)}`}>
                <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap gap-2">
                      <span className={accentBadgeClass("teal", isDark)}>{item.element_type}</span>
                      {item.target_chapter ? <span className={badgeClass(isDark)}>Chapter {item.target_chapter}</span> : null}
                    </div>
                    <h3 className={`mt-3 text-base font-semibold ${titleTextClass(isDark)}`}>{item.element_name}</h3>
                    <p className={`mt-2 text-sm leading-6 ${bodyTextClass(isDark)}`}>{item.description}</p>
                  </div>
                  <button
                    type="button"
                    onClick={() => onSaveIntegrationAsNote(item)}
                    disabled={!!noteSavingId}
                    className={primaryButtonClass("teal")}
                  >
                    {noteSavingId === item.id ? "Saving..." : "Save as note"}
                  </button>
                </div>
                {item.suggestions.length > 0 ? (
                  <div className="mt-4 grid gap-2 md:grid-cols-2">
                    {item.suggestions.map((suggestion) => (
                      <p key={suggestion} className={`rounded-xl border px-3 py-2 text-sm ${softPanelClass(isDark)}`}>
                        {suggestion}
                      </p>
                    ))}
                  </div>
                ) : null}
              </article>
            ))
          )}
          {totalOpportunities > initialOpportunityCount ? (
            <button
              type="button"
              onClick={onToggleShowAllOpportunities}
              className={secondaryButtonClass(isDark)}
            >
              {showAllOpportunities ? "Show fewer opportunities" : `Show all ${totalOpportunities} opportunities`}
            </button>
          ) : null}
        </div>
      ) : (
        <EmptyState
          title="No opportunities yet."
          description="No opportunity scan is loaded yet. Refresh to load the latest result and request an update if the source content has changed."
          isDark={isDark}
          action={(
            <button
              type="button"
              onClick={onRunIntegration}
              disabled={loadingIntegration || !documentsAvailable}
              className={secondaryButtonClass(isDark)}
            >
              {loadingIntegration ? "Mapping..." : "Refresh opportunities"}
            </button>
          )}
        />
      )}
    </WorkspaceCard>
  )
}
