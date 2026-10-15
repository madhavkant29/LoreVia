import type { RefObject } from "react"

import {
  MODE_FILTER_OPTIONS,
  STATUS_FILTER_OPTIONS,
  type ModeFilter,
  type SortOption,
  type StatusFilter,
  type ViewMode,
} from "./LibraryClient.helpers"
import { GridIcon, ListIcon, SearchIcon } from "./LibraryClient.icons"

export function LibraryProjectControls({
  isDark,
  searchInputRef,
  search,
  modeFilter,
  statusFilter,
  showArchived,
  sortBy,
  viewMode,
  controlClass,
  mutedText,
  onSearchChange,
  onModeFilterChange,
  onStatusFilterChange,
  onShowArchivedToggle,
  onSortChange,
  onViewModeChange,
  onResetFilters,
}: {
  isDark: boolean
  searchInputRef: RefObject<HTMLInputElement | null>
  search: string
  modeFilter: ModeFilter
  statusFilter: StatusFilter
  showArchived: boolean
  sortBy: SortOption
  viewMode: ViewMode
  controlClass: string
  mutedText: string
  onSearchChange: (value: string) => void
  onModeFilterChange: (value: ModeFilter) => void
  onStatusFilterChange: (value: StatusFilter) => void
  onShowArchivedToggle: () => void
  onSortChange: (value: SortOption) => void
  onViewModeChange: (value: ViewMode) => void
  onResetFilters?: () => void
}) {
  const selectClass = `min-h-11 w-full border px-3 text-sm outline-none focus:ring-2 focus:ring-teal-500/30 ${controlClass}`

  return (
    <section aria-label="Project search and filters" className={`border-y py-3 ${isDark ? "border-white/[0.1]" : "border-stone-200"}`}>
      <div className="grid grid-cols-2 items-end gap-3 lg:grid-cols-4">
        <label className={`col-span-2 flex min-h-11 items-center gap-3 border px-3 focus-within:ring-2 focus-within:ring-teal-500 ${controlClass}`}>
          <SearchIcon className={isDark ? "text-[#7e7b74]" : "text-stone-400"} />
          <input
            type="search"
            ref={searchInputRef}
            value={search}
            onChange={(event) => onSearchChange(event.target.value)}
            aria-label="Search projects"
            placeholder="Search title, author, or series"
            className="min-w-0 w-full bg-transparent text-sm outline-none"
          />
          <kbd className={`hidden text-sm sm:inline ${mutedText}`}>/</kbd>
        </label>

        <label>
          <span className={`mb-1 block text-xs ${mutedText}`}>Project mode</span>
          <select value={modeFilter} onChange={(event) => onModeFilterChange(event.target.value as ModeFilter)} className={selectClass} aria-label="Project mode">
            {MODE_FILTER_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </label>

        <label>
          <span className={`mb-1 block text-xs ${mutedText}`}>Project status</span>
          <select value={statusFilter} onChange={(event) => onStatusFilterChange(event.target.value as StatusFilter)} className={selectClass} aria-label="Project status">
            {STATUS_FILTER_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </label>

        <label className="col-span-2 sm:col-span-1">
          <span className={`mb-1 block text-xs ${mutedText}`}>Sort projects</span>
          <select value={sortBy} onChange={(event) => onSortChange(event.target.value as SortOption)} className={selectClass} aria-label="Sort projects">
            <option value="recent">Recently updated</option>
            <option value="progress">Most progress</option>
            <option value="title">Title A-Z</option>
          </select>
        </label>

        <div className="col-span-2 flex flex-wrap items-end justify-between gap-3 sm:col-span-1 lg:col-span-3">
          <label className="flex min-h-11 cursor-pointer items-center gap-2 text-sm">
            <input type="checkbox" checked={showArchived} onChange={onShowArchivedToggle} />
            Include archived
          </label>
          {onResetFilters && (search || modeFilter !== "all" || statusFilter !== "all" || showArchived) ? <button type="button" onClick={onResetFilters} className="min-h-11 text-sm underline underline-offset-4">Reset filters</button> : null}
          <div className={`flex border ${controlClass}`} role="group" aria-label="Project view mode">
            <button type="button" onClick={() => onViewModeChange("grid")} aria-label="Grid view" aria-pressed={viewMode === "grid"} className={`flex min-h-11 items-center gap-2 px-3 ${viewMode === "grid" ? "bg-teal-500/15 text-teal-700 dark:text-teal-200" : mutedText}`}><GridIcon /><span className="text-sm">Grid</span></button>
            <button type="button" onClick={() => onViewModeChange("list")} aria-label="List view" aria-pressed={viewMode === "list"} className={`flex min-h-11 items-center gap-2 px-3 ${viewMode === "list" ? "bg-teal-500/15 text-teal-700 dark:text-teal-200" : mutedText}`}><ListIcon /><span className="text-sm">List</span></button>
          </div>
        </div>
      </div>
    </section>
  )
}
