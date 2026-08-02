import { ErrorCard } from "@/components/ui/ErrorCard"

export function LibraryAuthLoadingState({
  isDark,
  pageBackground,
}: {
  isDark: boolean
  pageBackground: string
}) {
  return (
    <div className={`min-h-screen transition-colors duration-300 ${pageBackground}`}>
      <div className="w-full pb-20">
        <div className="mx-auto max-w-7xl space-y-7 px-4 pt-8">
          <div className={`h-10 w-48 rounded-sm ${isDark ? "bg-white/5" : "bg-stone-100"}`} />
          <div className="grid gap-4 md:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <div key={i} className={`h-28 rounded-sm border ${isDark ? "border-white/5 bg-white/[0.03]" : "border-stone-200 bg-white"}`} />
            ))}
          </div>
          <div className="grid gap-4 xl:grid-cols-3">
            {[0, 1, 2].map((i) => (
              <div key={i} className={`h-64 rounded-sm border ${isDark ? "border-white/5 bg-white/[0.03]" : "border-stone-200 bg-white"}`} />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

export function LibraryErrorState({
  isDark,
  pageBackground,
  onRetry,
}: {
  isDark: boolean
  pageBackground: string
  onRetry: () => void
}) {
  return (
    <div className={`min-h-screen transition-colors duration-300 ${pageBackground}`}>
      <div className="w-full pb-20">
        <div className="mx-auto max-w-7xl px-4 pt-8">
          <ErrorCard
            title="Failed to load library"
            message="Something went wrong while loading your library. Check your connection and try again."
            onRetry={onRetry}
            isDark={isDark}
            variant="full"
          />
        </div>
      </div>
    </div>
  )
}
