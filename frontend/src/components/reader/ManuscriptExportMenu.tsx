import { memo } from "react"

type PublishingPreset = "standard_manuscript" | "trade_paperback" | "kdp_paperback"
type CompileFormat = "docx" | "pdf" | "epub" | "vault"

export const ManuscriptExportMenu = memo(function ManuscriptExportMenu({
  isDark,
  open,
  activePreset,
  exporting,
  onToggle,
  onPresetChange,
  onPrint,
  onCompile,
}: {
  isDark: boolean
  open: boolean
  activePreset: PublishingPreset
  exporting: CompileFormat | null
  onToggle: () => void
  onPresetChange: (preset: PublishingPreset) => void
  onPrint: () => void
  onCompile: (format: CompileFormat) => void
}) {
  return (
    <div className="relative">
      <button
        type="button"
        onClick={onToggle}
        className={`rounded-full border px-4 py-2 text-sm font-medium ${isDark ? "border-white/10 bg-white/5 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}
      >
        Export
      </button>
      {open ? (
        <div className={`absolute right-0 top-full z-20 mt-2 w-64 rounded-md border p-1.5 ${isDark ? "border-white/10 bg-[#0f1117]" : "border-stone-200 bg-white"}`}>
          <div className="px-3 py-2">
            <p className={`text-3xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Publishing preset</p>
            <select
              value={activePreset}
              onChange={(event) => onPresetChange(event.target.value as PublishingPreset)}
              className={`mt-2 w-full rounded-xl border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
            >
              <option value="standard_manuscript">Standard manuscript</option>
              <option value="trade_paperback">Trade paperback</option>
              <option value="kdp_paperback">6×9 print paperback</option>
            </select>
          </div>
          <button onClick={onPrint} className={`block w-full rounded-xl px-3 py-2 text-left text-sm ${isDark ? "text-slate-200 hover:bg-white/10" : "text-stone-700 hover:bg-stone-100"}`}>Print</button>
          <button onClick={() => onCompile("docx")} disabled={!!exporting} className={`block w-full rounded-xl px-3 py-2 text-left text-sm disabled:opacity-40 ${isDark ? "text-slate-200 hover:bg-white/10" : "text-stone-700 hover:bg-stone-100"}`}>{exporting === "docx" ? "Exporting Word..." : "Compile Word / DOCX"}</button>
          <button onClick={() => onCompile("pdf")} disabled={!!exporting} className={`block w-full rounded-xl px-3 py-2 text-left text-sm disabled:opacity-40 ${isDark ? "text-slate-200 hover:bg-white/10" : "text-stone-700 hover:bg-stone-100"}`}>{exporting === "pdf" ? "Exporting PDF..." : "Compile submission PDF"}</button>
          <button onClick={() => onCompile("epub")} disabled={!!exporting} className={`block w-full rounded-xl px-3 py-2 text-left text-sm disabled:opacity-40 ${isDark ? "text-slate-200 hover:bg-white/10" : "text-stone-700 hover:bg-stone-100"}`}>{exporting === "epub" ? "Exporting EPUB..." : "Compile EPUB"}</button>
          <button onClick={() => onCompile("vault")} disabled={!!exporting} className={`block w-full rounded-xl px-3 py-2 text-left text-sm disabled:opacity-40 ${isDark ? "text-slate-200 hover:bg-white/10" : "text-stone-700 hover:bg-stone-100"}`}>{exporting === "vault" ? "Exporting vault..." : "Export vault"}</button>
        </div>
      ) : null}
    </div>
  )
})
