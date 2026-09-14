import { forwardRef, type ButtonHTMLAttributes } from "react"
import { cn } from "@/lib/utils/text"

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger"
  size?: "sm" | "md" | "lg"
  busy?: boolean
  busyLabel?: string
}

const variants = {
  primary:   "border border-transparent bg-[rgb(var(--accent))] text-white hover:opacity-95",
  secondary: "border border-[rgba(var(--border),0.5)] bg-white/80 text-[rgb(var(--foreground))] hover:bg-white dark:bg-white/5 dark:hover:bg-white/10",
  ghost:     "text-[rgb(var(--muted-foreground))] hover:text-[rgb(var(--foreground))] hover:bg-[rgba(var(--foreground),0.05)]",
  danger:    "bg-red-600 text-white border border-red-600 hover:bg-red-700 hover:border-red-700",
}
const sizes = {
  sm: "min-h-11 px-3 py-2 text-xs rounded-sm",
  md: "min-h-11 px-4 py-2.5 text-sm rounded-sm",
  lg: "min-h-12 px-6 py-3 text-base rounded-sm",
}

export const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  { variant = "primary", size = "md", busy = false, busyLabel, className, children, disabled, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      className={cn(
        "font-medium tracking-normal transition-all duration-150 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgb(var(--accent))] focus-visible:ring-offset-2 motion-reduce:transition-none disabled:cursor-not-allowed disabled:opacity-50",
        variants[variant], sizes[size], className
      )}
      aria-busy={busy || undefined}
      disabled={disabled || busy}
      {...props}
    >
      {busy && busyLabel ? busyLabel : children}
    </button>
  )
})
