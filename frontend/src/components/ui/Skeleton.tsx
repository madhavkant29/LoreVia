import { cn } from "@/lib/utils/text"

type SkeletonVariant = "text" | "card" | "circle"

interface SkeletonProps {
  variant?: SkeletonVariant
  className?: string
}

const variantClasses: Record<SkeletonVariant, string> = {
  text: "h-4 w-full rounded",
  card: "h-48 w-full rounded-md",
  circle: "h-10 w-10 rounded-full",
}

export function Skeleton({ variant = "text", className }: SkeletonProps) {
  return (
    <div
      aria-hidden="true"
      className={cn(
        "animate-pulse bg-muted",
        variantClasses[variant],
        className
      )}
    />
  )
}

export function CardSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("rounded-md border border-border bg-card/60 p-4", className)}>
      <div className="flex items-start gap-3">
        <Skeleton variant="circle" className="h-10 w-10 rounded-md" />
        <div className="min-w-0 flex-1 space-y-2">
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-3 w-1/2" />
        </div>
      </div>
      <div className="mt-5 space-y-2">
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-5/6" />
        <Skeleton className="h-3 w-2/3" />
      </div>
      <div className="mt-5 flex gap-2">
        <Skeleton className="h-9 w-24 rounded-md" />
        <Skeleton className="h-9 w-20 rounded-md" />
      </div>
    </div>
  )
}

export function RowSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("flex items-center gap-4 rounded-md border border-border bg-card/60 p-4", className)}>
      <Skeleton variant="circle" className="h-11 w-11 rounded-md" />
      <div className="min-w-0 flex-1 space-y-2">
        <Skeleton className="h-4 w-2/5" />
        <Skeleton className="h-3 w-3/5" />
      </div>
      <div className="hidden gap-2 sm:flex">
        <Skeleton className="h-8 w-16 rounded-md" />
        <Skeleton className="h-8 w-20 rounded-md" />
      </div>
    </div>
  )
}

export function MetricCardSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("rounded-md border border-border bg-card/60 p-4", className)}>
      <Skeleton variant="circle" className="h-9 w-9 rounded-md" />
      <Skeleton className="mt-4 h-3 w-24" />
      <Skeleton className="mt-2 h-7 w-16" />
      <Skeleton className="mt-3 h-3 w-32" />
    </div>
  )
}

export function SidebarSkeleton({ className }: { className?: string }) {
  return (
    <aside className={cn("space-y-4 rounded-md border border-border bg-card/60 p-4", className)}>
      <Skeleton variant="circle" className="h-10 w-10 rounded-md" />
      <div className="space-y-2">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-3 w-full" />
      </div>
      <div className="space-y-2 pt-2">
        {Array.from({ length: 6 }).map((_, index) => (
          <Skeleton key={index} className="h-9 w-full rounded-md" />
        ))}
      </div>
    </aside>
  )
}

export function EditorSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("rounded-md border border-border bg-card/60", className)}>
      <div className="flex flex-wrap gap-2 border-b border-border p-3">
        {Array.from({ length: 8 }).map((_, index) => (
          <Skeleton key={index} className="h-8 w-10 rounded-md" />
        ))}
      </div>
      <div className="space-y-3 p-5">
        <Skeleton className="h-5 w-3/4" />
        <Skeleton className="h-5 w-5/6" />
        <Skeleton className="h-5 w-full" />
        <Skeleton className="h-5 w-4/5" />
        <Skeleton className="h-5 w-2/3" />
      </div>
    </div>
  )
}

export function DashboardSkeleton({ className }: { className?: string }) {
  return (
    <div className={cn("space-y-5", className)} role="status" aria-label="Loading dashboard" aria-busy="true">
      <span className="sr-only">Loading dashboard</span>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <MetricCardSkeleton key={index} />
        ))}
      </div>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.3fr)_minmax(18rem,0.7fr)]">
        <CardSkeleton className="min-h-64" />
        <div className="space-y-3">
          <RowSkeleton />
          <RowSkeleton />
          <RowSkeleton />
        </div>
      </div>
      <EditorSkeleton />
    </div>
  )
}
