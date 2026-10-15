import { RowSkeleton, Skeleton } from "@/components/ui/Skeleton"

export function ExportStudioSkeleton({ isDark }: { isDark: boolean }) {
  return (
    <div className={`min-h-screen ${isDark ? "bg-[#11191a] text-slate-100" : "bg-[#f4f5f3] text-stone-950"}`}>
      <div className="mx-auto max-w-[96rem] px-4 pb-20 pt-8 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <main className="space-y-6" role="status" aria-label="Loading export studio" aria-busy="true">
            <span className="sr-only">Loading export studio</span>
            <section className={`border p-5 ${isDark ? "border-white/10 bg-black/20" : "border-white/70 bg-white/85"}`}>
              <Skeleton className="h-4 w-28" />
              <Skeleton className="mt-4 h-8 w-64 max-w-full" />
              <Skeleton className="mt-3 h-4 w-full max-w-2xl" />
              <div className="mt-5 flex flex-wrap gap-3">
                <Skeleton className="h-10 w-36" />
                <Skeleton className="h-10 w-32" />
              </div>
            </section>
            <div className="space-y-6">
              <div className="space-y-5">
                <RowSkeleton />
                <RowSkeleton />
              </div>
            </div>
          </main>
        </div>
      </div>
    </div>
  )
}

export function ImportCard({
  isDark,
  title,
  description,
  files,
  buttonLabel,
  onChoose,
  onRun,
  disabled,
  onClear,
}: {
  isDark: boolean
  title: string
  description: string
  files: File[]
  buttonLabel: string
  onChoose: () => void
  onRun: () => void
  disabled: boolean
  onClear: () => void
}) {
  return (
    <article className="min-w-0">
      <h3 className={`text-base font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{title}</h3>
      <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{description}</p>
      <div className={`mt-3 border border-dashed px-4 py-3 text-sm ${isDark ? "border-white/10 text-slate-400" : "border-stone-300 text-stone-600"}`}>
        {files.length ? <ul className="space-y-2">{files.map((file, index) => <li key={`${file.name}-${index}`} className="[overflow-wrap:anywhere]">{file.name} <span>({Math.max(1, Math.ceil(file.size / 1024)).toLocaleString()} KB)</span></li>)}</ul> : "No files selected yet."}
      </div>
      <div className="mt-4 flex flex-wrap gap-3">
        <button type="button" aria-label={`Choose ${title} files`} onClick={onChoose} className="app-button-secondary">
          Choose files
        </button>
        {files.length ? <button type="button" className="app-button-secondary" onClick={onClear}>Clear selected files</button> : null}
        <button type="button" onClick={onRun} disabled={disabled} className="app-button-primary">
          {buttonLabel}
        </button>
      </div>
    </article>
  )
}
