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
    <div role="tablist" aria-label="Character workspace tabs" className={`mt-6 flex flex-wrap gap-8 border-b ${isDark ? "border-[#17202c]" : "border-stone-200"}`}>
      {PROFILE_TABS.map(([value, label]) => (
        <button
          key={value}
          type="button"
          role="tab"
          aria-selected={active === value}
          onClick={() => onSelect(value)}
          className={`pb-3 text-sm font-medium transition ${
            active === value
              ? isDark ? "border-b-2 border-teal-300 text-white" : "border-b-2 border-teal-700 text-stone-950"
              : isDark ? "text-slate-400 hover:text-slate-200" : "text-stone-500 hover:text-stone-800"
          }`}
        >
          {label}
        </button>
      ))}
    </div>
  )
}
