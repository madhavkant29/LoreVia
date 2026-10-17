import { Skeleton } from "@/components/ui/Skeleton"

import type { ViewMode } from "./LibraryClient.helpers"

export function ProjectSkeletons({ isDark, viewMode, label }: { isDark: boolean; viewMode: ViewMode; label: string }) {
  const items = [0, 1, 2]

  if (viewMode === "list") {
    return (
      <div className="space-y-3" role="status" aria-label={label} aria-busy="true">
        <span className="sr-only">{label}</span>
        {items.map((item) => (
          <ProjectRowSkeleton key={item} isDark={isDark} />
        ))}
      </div>
    )
  }

  return (
    <div className="grid gap-4 md:grid-cols-2 2xl:grid-cols-3" role="status" aria-label={label} aria-busy="true">
      <span className="sr-only">{label}</span>
      {items.map((item) => (
        <ProjectCardSkeleton key={item} isDark={isDark} />
      ))}
    </div>
  )
}

function ProjectCardSkeleton({ isDark }: { isDark: boolean }) {
  return (
    <div className={`rounded-sm border p-5 ${isDark ? "border-white/[0.08] bg-[#101b24]" : "border-stone-200 bg-white"}`}>
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-start gap-4">
          <Skeleton variant="circle" className="h-12 w-12 rounded-md" />
          <div className="min-w-0 flex-1 space-y-2.5">
            <Skeleton variant="text" className="h-5 w-36" />
            <Skeleton variant="text" className="h-3.5 w-24" />
          </div>
        </div>
        <Skeleton variant="circle" className="h-8 w-8 rounded-sm" />
      </div>
      <Skeleton variant="text" className="mt-5 h-4 w-3/4" />
      <Skeleton variant="text" className="mt-5 h-1.5 w-full" />
      <div className="mt-3 flex items-center justify-between gap-4">
        <Skeleton variant="text" className="h-3.5 w-32" />
        <Skeleton variant="text" className="h-3.5 w-20" />
      </div>
      <Skeleton variant="text" className="mt-2 h-3 w-28" />
      <div className={`mt-5 flex flex-wrap items-center gap-x-5 gap-y-2 border-t pt-4 ${isDark ? "border-white/[0.08]" : "border-stone-200"}`}>
        <Skeleton variant="text" className="h-3 w-16" />
        <Skeleton variant="text" className="h-3 w-16" />
        <Skeleton variant="text" className="h-3 w-20" />
      </div>
    </div>
  )
}

function ProjectRowSkeleton({ isDark }: { isDark: boolean }) {
  return (
    <div className={`rounded-sm border px-5 py-5 ${isDark ? "border-white/[0.08] bg-[#101b24]" : "border-stone-200 bg-white"}`}>
      <div className="flex flex-col gap-5 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex min-w-0 items-center gap-4">
          <Skeleton variant="circle" className="h-12 w-12 rounded-md" />
          <div className="min-w-0 flex-1 space-y-2.5">
            <Skeleton variant="text" className="h-5 w-40" />
            <Skeleton variant="text" className="h-3.5 w-28" />
            <Skeleton variant="text" className="h-3.5 w-48" />
          </div>
        </div>

        <div className="flex flex-1 flex-col gap-3 xl:max-w-[32rem]">
          <Skeleton variant="text" className="h-1.5 w-full" />
          <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
            <Skeleton variant="text" className="h-3.5 w-32" />
            <Skeleton variant="text" className="h-3.5 w-20" />
            <Skeleton variant="text" className="h-3.5 w-24" />
          </div>
        </div>

        <div className="flex items-center justify-end gap-3">
          <Skeleton variant="text" className="h-9 w-24 rounded-sm" />
          <Skeleton variant="circle" className="h-9 w-9 rounded-sm" />
        </div>
      </div>
    </div>
  )
}
