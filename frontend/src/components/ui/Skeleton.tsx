interface Props {
  className?: string
}

export function Skeleton({ className = "" }: Props) {
  return (
    <div
      className={`animate-pulse rounded-md bg-slate-200 dark:bg-slate-800 ${className}`}
      aria-hidden="true"
    />
  )
}
