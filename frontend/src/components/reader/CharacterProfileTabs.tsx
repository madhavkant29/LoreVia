export type CharacterProfileTab = "overview" | "relationships" | "mentions" | "timeline" | "continuity" | "arc" | "evidence" | "notes"

const PROFILE_TABS: Array<[CharacterProfileTab, string]> = [
  ["overview", "Overview"],
  ["relationships", "Relationships"],
  ["mentions", "Mentions"],
  ["timeline", "Timeline"],
  ["arc", "Arc"],
  ["continuity", "Continuity"],
  ["evidence", "Evidence"],
  ["notes", "Notes"],
]

export function CharacterProfileTabs({
  active,
  isDark,
  onSelect,
}: {
  active: CharacterProfileTab
  isDark: boolean
  onSelect: (tab: CharacterProfileTab) => void
}) {
  return (
    <div role="tablist" aria-label="Character workspace tabs" className={`mt-5 flex max-w-full flex-wrap gap-x-5 border-b sm:flex-nowrap sm:gap-7 sm:overflow-x-auto ${isDark ? "border-[#17202c]" : "border-stone-200"}`}>
      {PROFILE_TABS.map(([value, label]) => (
        <button
          key={value}
          type="button"
          role="tab"
          id={`character-tab-${value}`}
          aria-controls="character-profile-panel"
          tabIndex={active === value ? 0 : -1}
          aria-selected={active === value}
          onClick={() => onSelect(value)}
          onKeyDown={(event) => {
            const index = PROFILE_TABS.findIndex(([tab]) => tab === value)
            const next = event.key === "ArrowRight" ? (index + 1) % PROFILE_TABS.length
              : event.key === "ArrowLeft" ? (index + PROFILE_TABS.length - 1) % PROFILE_TABS.length
                : event.key === "Home" ? 0 : event.key === "End" ? PROFILE_TABS.length - 1 : null
            if (next === null) return
            event.preventDefault()
            onSelect(PROFILE_TABS[next][0])
            document.getElementById(`character-tab-${PROFILE_TABS[next][0]}`)?.focus()
          }}
          className={`shrink-0 pb-3 text-sm font-medium transition-colors ${
            active === value
              ? isDark ? "border-b-2 border-teal-300 text-white" : "border-b-2 border-teal-700 text-stone-950"
              : isDark ? "text-slate-400 hover:text-slate-200" : "text-stone-600 hover:text-stone-800"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  )
}
