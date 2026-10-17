import { Skeleton } from "@/components/ui/Skeleton"

export function BookOpenIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M4 5.5c0-1 0-1.5.3-1.8.3-.2.8-.2 1.8-.2h3.1c1.5 0 2.4.4 2.8 1.2.4-.8 1.3-1.2 2.8-1.2h3.1c1 0 1.5 0 1.8.2.3.3.3.8.3 1.8v12c0 1 0 1.5-.3 1.8-.3.2-.8.2-1.8.2h-3.3c-1.4 0-2.2.3-2.6 1-.4-.7-1.2-1-2.6-1H6.1c-1 0-1.5 0-1.8-.2-.3-.3-.3-.8-.3-1.8v-12Z" />
      <path d="M12 5v15" />
    </svg>
  )
}

export function ManuscriptEditorSkeleton({ isDark }: { isDark: boolean }) {
  const shellClass = isDark ? "bg-[#101416] text-slate-100" : "bg-[#f4f5f3] text-stone-950"
  const panelClass = isDark ? "border-white/10 bg-[#11171a]" : "border-stone-200 bg-white/90"
  const canvasClass = isDark ? "border-white/10 bg-[#0b1114]" : "border-stone-200 bg-[#faf8f4]"

  return (
    <div role="status" aria-label="Loading manuscript" aria-busy="true" className={`min-h-screen overflow-hidden ${shellClass}`}>
      <header className={`sticky top-0 z-40 border-b ${panelClass}`}>
        <div className="flex min-h-[4.25rem] items-center justify-between px-6">
          <div className="flex min-w-0 items-center gap-3">
            <Skeleton className="h-7 w-7 rounded-sm" />
            <Skeleton className="h-5 w-52" />
          </div>
          <div className="hidden items-center gap-3 sm:flex">
            <Skeleton className="h-4 w-24" />
            <Skeleton className="h-10 w-20 rounded-sm" />
            <Skeleton className="h-10 w-28 rounded-sm" />
            <Skeleton className="h-10 w-10 rounded-sm" />
          </div>
        </div>
        <div className={`flex items-center justify-between border-t px-6 py-2 ${isDark ? "border-white/10" : "border-stone-200"}`}>
          <div className="flex gap-8">
            <Skeleton className="h-8 w-12" />
            <Skeleton className="h-8 w-10" />
            <Skeleton className="h-8 w-16" />
            <Skeleton className="h-8 w-20" />
          </div>
          <div className="hidden gap-4 lg:flex">
            <Skeleton className="h-10 w-44 rounded-sm" />
            <Skeleton className="h-10 w-44 rounded-sm" />
          </div>
        </div>
      </header>

      <div className="grid min-w-0 xl:grid-cols-[22rem_minmax(0,1fr)_23.5rem]">
        <aside className={`hidden min-h-[calc(100vh-8.25rem)] border-r p-5 xl:block ${panelClass}`}>
          <Skeleton className="h-4 w-24" />
          <div className="mt-5 grid grid-cols-2 gap-2">
            <Skeleton className="h-10 rounded-sm" />
            <Skeleton className="h-10 rounded-sm" />
          </div>
          <Skeleton variant="card" className="mt-5 h-32 rounded-sm" />
          <Skeleton className="mt-4 h-10 rounded-sm" />
          <div className="mt-6 space-y-3">
            <Skeleton className="h-24 rounded-sm" />
            <Skeleton className="h-24 rounded-sm" />
            <Skeleton className="h-24 rounded-sm" />
          </div>
        </aside>

        <main className={`min-h-[calc(100vh-8.25rem)] border-r ${canvasClass}`}>
          <div className={`border-b px-7 py-6 ${isDark ? "border-white/10 bg-[#111721]" : "border-stone-200 bg-white"}`}>
            <Skeleton className="h-3 w-44" />
            <Skeleton className="mt-4 h-11 w-96 max-w-full" />
            <div className="mt-4 flex gap-4">
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-4 w-20" />
              <Skeleton className="h-4 w-24" />
            </div>
          </div>
          <div className={`border-b px-3 py-3 ${isDark ? "border-white/10 bg-[#0c1118]" : "border-stone-200 bg-white"}`}>
            <Skeleton className="h-11 w-full rounded-sm" />
          </div>
          <div className="px-8 py-10">
            <div className="mx-auto max-w-[780px] space-y-5">
              <Skeleton className="h-5 w-5/6" />
              <Skeleton className="h-5 w-4/6" />
              <Skeleton className="h-5 w-full" />
              <Skeleton className="h-5 w-11/12" />
              <Skeleton className="h-5 w-3/4" />
            </div>
          </div>
        </main>

        <aside className={`hidden min-h-[calc(100vh-8.25rem)] xl:block ${panelClass}`}>
          <div className={`border-b px-4 ${isDark ? "border-white/10" : "border-stone-200"}`}>
            <Skeleton className="h-12 w-full" />
          </div>
          <div className="space-y-0">
            <Skeleton className="h-40 rounded-none" />
            <Skeleton className="h-36 rounded-none" />
            <Skeleton className="h-36 rounded-none" />
            <Skeleton className="h-44 rounded-none" />
          </div>
        </aside>
      </div>
    </div>
  )
}

export function DeferredPanelLoadingState({ label }: { label: string }) {
  return (
    <div className="flex min-h-[12rem] flex-col items-center justify-center gap-3 rounded-md border border-border bg-card/60 p-6">
      <Skeleton variant="card" className="w-full min-h-44" />
      <p className="text-sm text-muted-foreground">{label}</p>
    </div>
  )
}

export function InlineLoadingRows({ isDark, label, rows = 3 }: { isDark: boolean; label: string; rows?: number }) {
  return (
    <div className="space-y-2" role="status" aria-label={label} aria-busy="true">
      <span className="sr-only">{label}</span>
      {Array.from({ length: rows }).map((_, index) => (
        <Skeleton
          key={`${label}-${index}`}
          className={`${index === rows - 1 ? "w-2/3" : "w-full"} h-3 ${isDark ? "bg-white/[0.08]" : "bg-stone-200/80"}`}
        />
      ))}
    </div>
  )
}
