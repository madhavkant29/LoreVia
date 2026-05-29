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
      className={cn(
        "animate-pulse bg-muted",
        variantClasses[variant],
        className
      )}
    />
  )
}
