export function InfoRow({ label, value, isDark, dot = false }: { label: string; value: string; isDark: boolean; dot?: boolean }) {
  return (
    <div className="grid grid-cols-[7rem_minmax(0,1fr)] items-center gap-3 text-sm">
      <span className={isDark ? "text-slate-500" : "text-slate-400"}>{label}</span>
      <span className={`flex min-w-0 items-center gap-2 font-medium capitalize ${isDark ? "text-slate-300" : "text-slate-700"}`}>
        {dot ? <span className="h-2 w-2 rounded-full bg-emerald-400" /> : null}
        {value}
      </span>
    </div>
  )
}
