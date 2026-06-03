export function ManuscriptModeSwitch<T extends string>({
  isDark,
  options,
  selected,
  onSelect,
  renderLabel,
}: {
  isDark: boolean
  options: readonly T[]
  selected: T
  onSelect: (value: T) => void
  renderLabel: (value: T) => string
}) {
  return (
    <div className={`inline-flex rounded-full p-1 ${isDark ? "border border-white/10 bg-black/30" : "border border-stone-200 bg-stone-100/80"}`}>
      {options.map((option) => (
        <button
          key={option}
          type="button"
          aria-pressed={selected === option}
          onClick={() => onSelect(option)}
          className={`rounded-full px-4 py-2 text-sm font-medium transition ${selected === option ? isDark ? "bg-white text-slate-950" : "bg-stone-900 text-white" : isDark ? "text-slate-300 hover:bg-white/10" : "text-stone-600 hover:bg-white"}`}
        >
          {renderLabel(option)}
        </button>
      ))}
    </div>
  )
}
