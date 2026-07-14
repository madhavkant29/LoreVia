import type { WorldElement } from "@/types/world-building"

import { EmptyState, WorkspaceCard } from "./WorldbuildingWorkspace.components"
import {
  accentBadgeClass,
  badgeClass,
  bodyTextClass,
  formatElementType,
  mutedTextClass,
  secondaryButtonClass,
  softPanelClass,
  summarizeRecord,
  titleTextClass,
} from "./WorldbuildingWorkspace.helpers"

export function ElementSuggestionsCard({
  isDark,
  suggestionElements,
  visibleSuggestionElements,
  showAllSuggestions,
  initialSuggestionCount,
  onAcceptElementSuggestion,
  onToggleShowAllSuggestions,
}: {
  isDark: boolean
  suggestionElements: WorldElement[]
  visibleSuggestionElements: WorldElement[]
  showAllSuggestions: boolean
  initialSuggestionCount: number
  onAcceptElementSuggestion: (element: WorldElement, suggestion: Record<string, unknown> | string) => void
  onToggleShowAllSuggestions: () => void
}) {
  return (
    <WorkspaceCard
      number="5"
      sectionLabel="Element Suggestions"
      title="Element Suggestions"
      description={suggestionElements.length > 0 ? `${suggestionElements.length} item${suggestionElements.length === 1 ? "" : "s"} ready for review.` : "Suggested world elements based on your manuscript."}
      isDark={isDark}
    >
      <div className="space-y-3">
        {suggestionElements.length === 0 ? (
          <EmptyState title="No element suggestions yet." description="No element suggestions yet." isDark={isDark} compact />
        ) : (
          visibleSuggestionElements.map((element) => (
            <article key={element.id} className={`rounded-md border p-4 ${softPanelClass(isDark)}`}>
              <h3 className={`text-sm font-semibold ${titleTextClass(isDark)}`}>{element.name}</h3>
              <div className="mt-3 grid gap-2">
                {element.suggestions.map((suggestion, index) => (
                  <div key={`${element.id}-${index}`} className={`rounded-xl border p-3 text-sm ${softPanelClass(isDark)}`}>
                    <p className={bodyTextClass(isDark)}>{summarizeRecord(suggestion)}</p>
                    <button
                      type="button"
                      onClick={() => onAcceptElementSuggestion(element, suggestion)}
                      className={`mt-3 rounded-full px-3 py-1.5 text-xs font-semibold ${isDark ? "bg-amber-300 text-stone-950" : "bg-stone-900 text-white"}`}
                    >
                      Mark implemented
                    </button>
                  </div>
                ))}
              </div>
            </article>
          ))
        )}
        {suggestionElements.length > initialSuggestionCount ? (
          <button
            type="button"
            onClick={onToggleShowAllSuggestions}
            className={secondaryButtonClass(isDark)}
          >
            {showAllSuggestions ? "Show fewer suggestions" : `Show all ${suggestionElements.length} suggestion groups`}
          </button>
        ) : null}
      </div>
    </WorkspaceCard>
  )
}

export function ExtractedElementsCard({
  isDark,
  extractedElements,
  visibleElements,
  visibleElementCards,
  elementTypeSummary,
  elementsLoading,
  showAllElements,
  initialElementCount,
  onRefreshElements,
  onToggleShowAllElements,
}: {
  isDark: boolean
  extractedElements: WorldElement[]
  visibleElements: WorldElement[]
  visibleElementCards: WorldElement[]
  elementTypeSummary: Record<string, number>
  elementsLoading: boolean
  showAllElements: boolean
  initialElementCount: number
  onRefreshElements: () => void
  onToggleShowAllElements: () => void
}) {
  return (
    <WorkspaceCard
      number="6"
      sectionLabel="Extracted Elements"
      title="Extracted Elements"
      description="Countries, regions, races, magic, and lore found in your corpus."
      isDark={isDark}
      action={(
        <button
          type="button"
          onClick={onRefreshElements}
          disabled={elementsLoading}
          className={secondaryButtonClass(isDark)}
        >
          {elementsLoading ? "Refreshing..." : "Refresh"}
        </button>
      )}
    >
      <div className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <span className={badgeClass(isDark)}>{extractedElements.length} total</span>
          {Object.entries(elementTypeSummary).slice(0, 5).map(([type, count]) => (
            <span key={type} className={accentBadgeClass("blue", isDark)}>
              {formatElementType(type)} {count}
            </span>
          ))}
        </div>
        {visibleElements.length === 0 ? (
          <EmptyState title="No extracted elements yet." description="No extracted elements yet." isDark={isDark} compact />
        ) : (
          <div className="grid gap-3">
            {visibleElementCards.map((element) => (
              <article key={element.id} className={`rounded-md border p-4 ${softPanelClass(isDark)}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <span className={accentBadgeClass("blue", isDark)}>{formatElementType(element.element_type)}</span>
                  <span className={badgeClass(isDark)}>{element.source_scope}</span>
                  {element.confidence ? <span className={badgeClass(isDark)}>{Math.round(element.confidence * 100)}%</span> : null}
                </div>
                <h3 className={`mt-3 text-base font-semibold ${titleTextClass(isDark)}`}>{element.name}</h3>
                {element.description ? <p className={`mt-2 line-clamp-3 text-sm leading-6 ${bodyTextClass(isDark)}`}>{element.description}</p> : null}
                <p className={`mt-3 text-xs ${mutedTextClass(isDark)}`}>
                  {element.usage_count.toLocaleString()} mention{element.usage_count === 1 ? "" : "s"}
                  {element.chapter_numbers.length ? ` - ${element.chapter_numbers.length} chapter${element.chapter_numbers.length === 1 ? "" : "s"}` : ""}
                  {element.world_document_title ? ` - ${element.world_document_title}` : ""}
                </p>
              </article>
            ))}
          </div>
        )}
        {visibleElements.length > initialElementCount ? (
          <button
            type="button"
            onClick={onToggleShowAllElements}
            className={secondaryButtonClass(isDark)}
          >
            {showAllElements ? "Show fewer elements" : `Show all ${visibleElements.length} elements`}
          </button>
        ) : null}
      </div>
    </WorkspaceCard>
  )
}
