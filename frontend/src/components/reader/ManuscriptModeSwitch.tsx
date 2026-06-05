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
    <div className={`inline-flex rounded-sm border p-0 ${isDark ? "border-white/10 bg-[#0b1014]" : "border-stone-200 bg-stone-100/80"}`}>
      {options.map((option) => {
        const label = renderLabel(option)
        return (
        <button
          key={option}
          type="button"
          aria-pressed={selected === option}
          onClick={() => onSelect(option)}
          title={label}
          className={`min-h-10 border-r px-5 text-sm font-medium transition last:border-r-0 ${
            isDark ? "border-white/10" : "border-stone-200"
          } ${
            selected === option
              ? isDark
                ? "bg-white/[0.08] text-white"
                : "bg-stone-900 text-white"
              : isDark
                ? "text-slate-300 hover:bg-white/[0.05]"
                : "text-stone-600 hover:bg-white"
          }`}
        >
          {label}
        </button>
        )
      })}
    </div>
  )
}
