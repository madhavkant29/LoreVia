import { type ButtonHTMLAttributes } from "react"
import { cn } from "@/lib/utils/text"

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger"
  size?: "sm" | "md" | "lg"
}

const variants = {
  primary:   "border border-transparent bg-[rgb(var(--accent))] text-white shadow-[0_18px_40px_-24px_rgba(var(--accent),0.72)] hover:translate-y-[-1px] hover:opacity-95",
  secondary: "border border-[rgba(var(--border),0.9)] bg-white/80 text-[rgb(var(--foreground))] hover:translate-y-[-1px] hover:bg-white dark:bg-white/5 dark:hover:bg-white/10",
  ghost:     "text-[rgb(var(--muted-foreground))] hover:text-[rgb(var(--foreground))] hover:bg-[rgba(var(--foreground),0.05)]",
  danger:    "bg-red-600 text-white border border-red-600 hover:bg-red-700 hover:border-red-700",
}
const sizes = {
  sm: "px-3 py-2 text-xs rounded-xl",
  md: "px-4 py-2.5 text-sm rounded-xl",
  lg: "px-6 py-3 text-base rounded-2xl",
}

export function Button({ variant = "primary", size = "md", className, children, ...props }: Props) {
  return (
    <button
      className={cn(
        "font-medium transition-all duration-150 ease-out disabled:cursor-not-allowed disabled:opacity-50",
        variants[variant], sizes[size], className
      )}
      {...props}
    >
      {children}
    </button>
  )
}
