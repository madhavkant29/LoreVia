type WorkspaceMode = "profile" | "review" | "duplicates" | "repair"
type CastFilter = "all" | "main" | "minor" | "needs-review" | "duplicates"

const CAST_FILTERS: Array<[CastFilter, string]> = [
  ["all", "All"],
  ["main", "Main"],
  ["minor", "Minor"],
  ["needs-review", "Needs review"],
  ["duplicates", "Duplicates"],
]

export function CharacterWorkspaceSidebarHeader({
  castFilter,
  isDark,
  mode,
  onCastFilterChange,
  onRoleFilterChange,
  onSearchChange,
  onStatusFilterChange,
  roleFilter,
  search,
  statusFilter,
  summary,
}: {
  castFilter: CastFilter
  isDark: boolean
  mode: WorkspaceMode
  onCastFilterChange: (filter: CastFilter) => void
  onRoleFilterChange?: (value: string) => void
  onSearchChange: (value: string) => void
  onStatusFilterChange?: (value: string) => void
  roleFilter?: string
  search: string
  statusFilter?: string
  summary: string
}) {
  const searchLabel = characterWorkspaceSearchLabel(mode)

  return (
    <div className={`sticky top-0 z-10 border-b px-4 py-4 ${isDark ? "border-[#17202c] bg-[#070c13]" : "border-stone-200 bg-white"}`}>
      <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${sectionEyebrowClasses(isDark, mode)}`}>
        {characterWorkspaceEyebrow(mode)}
      </p>
      <p className={`mt-1 text-sm ${isDark ? "text-slate-300" : "text-stone-600"}`}>{summary}</p>

      <label className={`mt-4 flex items-center gap-3 rounded-md border px-3 py-3 ${isDark ? "border-[#202a38] bg-[#0c1119]" : "border-stone-200 bg-stone-50"}`}>
        <span className="sr-only">{searchLabel}</span>
        <svg className={`h-4 w-4 ${isDark ? "text-slate-500" : "text-stone-400"}`} viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path fillRule="evenodd" d="M8.5 3a5.5 5.5 0 1 0 3.473 9.765l3.63 3.631a.75.75 0 1 0 1.06-1.06l-3.63-3.63A5.5 5.5 0 0 0 8.5 3ZM4.5 8.5a4 4 0 1 1 8 0 4 4 0 0 1-8 0Z" clipRule="evenodd" />
        </svg>
        <input
          value={search}
          onChange={(event) => onSearchChange(event.target.value)}
          aria-label={searchLabel}
          className={`min-w-0 flex-1 bg-transparent text-sm outline-none ${isDark ? "text-slate-100" : "text-stone-900"}`}
        />
        <span className={`rounded-md border px-1.5 py-0.5 text-3xs font-medium ${isDark ? "border-[#202a38] bg-white/[0.03] text-slate-500" : "border-stone-200 bg-white text-stone-400"}`}>
          Ctrl K
        </span>
      </label>

      {mode === "profile" ? (
        <div className="mt-4 space-y-3">
          <div className="grid grid-cols-2 gap-2">
            <label>
              <span className="sr-only">Filter by status</span>
              <select
                value={statusFilter ?? "all"}
                onChange={(event) => onStatusFilterChange?.(event.target.value)}
                className={`h-10 w-full rounded-md border px-3 text-xs font-medium outline-none ${isDark ? "border-[#202a38] bg-[#0c1119] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}
              >
                <option value="all">All statuses</option>
                <option value="reviewed">Reviewed</option>
                <option value="flagged">Flagged</option>
                <option value="unresolved">Unresolved</option>
              </select>
            </label>
            <label>
              <span className="sr-only">Filter by role</span>
              <select
                value={roleFilter ?? "all"}
                onChange={(event) => onRoleFilterChange?.(event.target.value)}
                className={`h-10 w-full rounded-md border px-3 text-xs font-medium outline-none ${isDark ? "border-[#202a38] bg-[#0c1119] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}
              >
                <option value="all">All roles</option>
                <option value="mc">Primary</option>
                <option value="sc">Supporting</option>
                <option value="background">Minor</option>
              </select>
            </label>
          </div>

          <div className="flex flex-wrap gap-2">
            {CAST_FILTERS.map(([value, label]) => (
              <button
                key={value}
                type="button"
                onClick={() => onCastFilterChange(value)}
                aria-pressed={castFilter === value}
                className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${filterChipClasses(isDark, castFilter === value)}`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}

function characterWorkspaceEyebrow(mode: WorkspaceMode) {
  if (mode === "duplicates") return "Duplicate review"
  if (mode === "review") return "Review queue"
  if (mode === "repair") return "Repair preview"
  return "Cast"
}

function characterWorkspaceSearchLabel(mode: WorkspaceMode) {
  if (mode === "duplicates") return "Search merge suggestions"
  if (mode === "review") return "Search review candidates"
  if (mode === "repair") return "Search repair preview"
  return "Search characters"
}

function sectionEyebrowClasses(isDark: boolean, mode: WorkspaceMode) {
  const tone = mode === "review" ? "teal" : mode === "duplicates" ? "violet" : mode === "repair" ? "amber" : "default"
  if (tone === "teal") return isDark ? "text-teal-300" : "text-teal-700"
  if (tone === "violet") return isDark ? "text-violet-300" : "text-violet-700"
  if (tone === "amber") return isDark ? "text-amber-300" : "text-amber-700"
  return isDark ? "text-slate-500" : "text-stone-400"
}

function filterChipClasses(isDark: boolean, active: boolean) {
  if (active) {
    return isDark
      ? "border-teal-400/30 bg-teal-500/10 text-teal-100"
      : "border-teal-300 bg-teal-50 text-teal-800"
  }
  return isDark
    ? "border-[#202a38] bg-white/[0.03] text-slate-400 hover:bg-white/[0.06]"
    : "border-stone-200 bg-white text-stone-500 hover:bg-stone-50"
}
