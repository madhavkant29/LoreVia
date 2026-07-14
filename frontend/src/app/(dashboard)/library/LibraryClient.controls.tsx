import type { RefObject } from "react"

import { Button } from "@/components/ui/Button"
import { Tooltip } from "@/components/ui/Tooltip"

import {
  MODE_FILTER_OPTIONS,
  STATUS_FILTER_OPTIONS,
  type ModeFilter,
  type SortOption,
  type StatusFilter,
  type ViewMode,
} from "./LibraryClient.helpers"
import { FilterIcon, GridIcon, ListIcon, SearchIcon } from "./LibraryClient.icons"

export function LibraryProjectControls({
  isDark,
  searchInputRef,
  search,
  filterSummary,
  filterOpen,
  modeFilter,
  statusFilter,
  showArchived,
  sortBy,
  viewMode,
  surfaceClass,
  controlClass,
  mutedText,
  headingText,
  onSearchChange,
  onFilterToggle,
  onModeFilterChange,
  onStatusFilterChange,
  onShowArchivedToggle,
  onSortChange,
  onViewModeChange,
}: {
  isDark: boolean
  searchInputRef: RefObject<HTMLInputElement | null>
  search: string
  filterSummary: string
  filterOpen: boolean
  modeFilter: ModeFilter
  statusFilter: StatusFilter
  showArchived: boolean
  sortBy: SortOption
  viewMode: ViewMode
  surfaceClass: string
  controlClass: string
  mutedText: string
  headingText: string
  onSearchChange: (value: string) => void
  onFilterToggle: () => void
  onModeFilterChange: (value: ModeFilter) => void
  onStatusFilterChange: (value: StatusFilter) => void
  onShowArchivedToggle: () => void
  onSortChange: (value: SortOption) => void
  onViewModeChange: (value: ViewMode) => void
}) {
  return (
    <section className={`rounded-sm border p-3 sm:p-4 ${surfaceClass}`}>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-1 flex-col gap-3 md:flex-row md:flex-wrap md:items-center">
          <label className={`flex min-h-12 flex-1 items-center gap-3 rounded-sm border px-4 ${controlClass}`}>
            <SearchIcon className={isDark ? "text-[#7e7b74]" : "text-stone-400"} />
            <input
              ref={searchInputRef}
              value={search}
              onChange={(event) => onSearchChange(event.target.value)}
              aria-label="Search projects"
              className="w-full bg-transparent text-[0.95rem] outline-none"
            />
            <span
              className={`hidden items-center rounded-md border px-2 py-1 text-3xs font-medium sm:inline-flex ${
                isDark ? "border-white/[0.08] bg-white/[0.03] text-[#9f9b94]" : "border-stone-200 bg-stone-50 text-stone-500"
              }`}
            >
              K
            </span>
          </label>

          <div className="relative">
            <Tooltip content="Refine by mode, status, or archive" align="start">
              <Button
                variant="secondary"
                size="md"
                onClick={onFilterToggle}
                className="min-h-12 rounded-sm"
                aria-expanded={filterOpen}
              >
                <FilterIcon className={isDark ? "text-[#d2cdc3]" : "text-stone-600"} />
                {filterSummary}
              </Button>
            </Tooltip>

            {filterOpen ? (
              <div className={`absolute left-0 top-full z-30 mt-3 w-[18rem] rounded-md border p-4 ${surfaceClass}`}>
                <div className="space-y-4">
                  <div>
                    <p className={`text-[0.68rem] font-semibold uppercase tracking-[0.24em] ${mutedText}`}>Project mode</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {MODE_FILTER_OPTIONS.map((option) => (
                        <Tooltip key={option.value} content={option.tooltip} side="bottom">
                          <button
                            type="button"
                            onClick={() => onModeFilterChange(option.value)}
                            className={`rounded-sm border px-3 py-1.5 text-xs font-medium transition ${
                              modeFilter === option.value
                                ? isDark
                                  ? "border-[#3d7a75] bg-[#234947] text-[#d7f0ed]"
                                  : "border-teal-700/20 bg-teal-50 text-teal-800"
                                : isDark
                                  ? "border-white/[0.08] bg-white/[0.03] text-[#b7b2aa]"
                                  : "border-stone-200 bg-stone-50 text-stone-600"
                            }`}
                            aria-pressed={modeFilter === option.value}
                          >
                            {option.label}
                          </button>
                        </Tooltip>
                      ))}
                    </div>
                  </div>

                  <div>
                    <p className={`text-[0.68rem] font-semibold uppercase tracking-[0.24em] ${mutedText}`}>Status</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {STATUS_FILTER_OPTIONS.map((option) => (
                        <Tooltip key={option.value} content={option.tooltip} side="bottom">
                          <button
                            type="button"
                            onClick={() => onStatusFilterChange(option.value)}
                            className={`rounded-sm border px-3 py-1.5 text-xs font-medium transition ${
                              statusFilter === option.value
                                ? isDark
                                  ? "border-[#3d7a75] bg-[#234947] text-[#d7f0ed]"
                                  : "border-teal-700/20 bg-teal-50 text-teal-800"
                                : isDark
                                  ? "border-white/[0.08] bg-white/[0.03] text-[#b7b2aa]"
                                  : "border-stone-200 bg-stone-50 text-stone-600"
                            }`}
                            aria-pressed={statusFilter === option.value}
                          >
                            {option.label}
                          </button>
                        </Tooltip>
                      ))}
                    </div>
                  </div>

                  <label className="flex items-center justify-between gap-3">
                    <span className={`text-sm ${headingText}`}>Show archived projects</span>
                    <Tooltip content="Include archived projects in results" side="bottom" align="end">
                      <button
                        type="button"
                        onClick={onShowArchivedToggle}
                        className={`relative h-7 w-12 rounded-full transition ${showArchived ? "bg-[#1f615d]" : isDark ? "bg-white/[0.12]" : "bg-stone-200"}`}
                        aria-label="Show archived projects"
                        aria-pressed={showArchived}
                      >
                        <span className={`absolute top-1 h-5 w-5 rounded-full bg-white transition ${showArchived ? "left-6" : "left-1"}`} />
                      </button>
                    </Tooltip>
                  </label>
                </div>
              </div>
            ) : null}
          </div>

          <Tooltip content="Choose how projects are ordered">
            <label className={`flex min-h-12 items-center gap-2 rounded-sm border px-4 text-sm ${controlClass}`}>
              <span className={mutedText}>Sort:</span>
              <select
                value={sortBy}
                onChange={(event) => onSortChange(event.target.value as SortOption)}
                className={`min-w-[11rem] cursor-pointer bg-transparent outline-none ${isDark ? "[color-scheme:dark]" : "[color-scheme:light]"}`}
                aria-label="Sort projects"
              >
                <option value="recent">Recently updated</option>
                <option value="progress">Most progress</option>
                <option value="title">Title A-Z</option>
              </select>
            </label>
          </Tooltip>
        </div>

        <div className={`inline-flex min-h-12 items-center rounded-sm border p-1 ${controlClass}`} role="group" aria-label="Project view mode">
          <Tooltip content="Show projects as cards">
            <button
              type="button"
              onClick={() => onViewModeChange("grid")}
              className={`inline-flex items-center gap-2 rounded-sm px-4 py-2 text-sm font-medium transition ${
                viewMode === "grid"
                  ? isDark
                    ? "bg-white/[0.08] text-[#f5f0e8]"
                    : "bg-[#eff4ef] text-[#1f615d]"
                  : mutedText
              }`}
              aria-label="Grid view"
              aria-pressed={viewMode === "grid"}
            >
              <GridIcon />
              Grid
            </button>
          </Tooltip>
          <Tooltip content="Show projects as rows">
            <button
              type="button"
              onClick={() => onViewModeChange("list")}
              className={`inline-flex items-center gap-2 rounded-sm px-4 py-2 text-sm font-medium transition ${
                viewMode === "list"
                  ? isDark
                    ? "bg-white/[0.08] text-[#f5f0e8]"
                    : "bg-[#eff4ef] text-[#1f615d]"
                  : mutedText
              }`}
              aria-label="List view"
              aria-pressed={viewMode === "list"}
            >
              <ListIcon />
              List
            </button>
          </Tooltip>
        </div>
      </div>
    </section>
  )
}
