import { type ButtonHTMLAttributes } from "react"
import { cn } from "@/lib/utils/text"

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger"
  size?: "sm" | "md" | "lg"
}

const variants = {
  primary:   "bg-slate-900 text-white border border-slate-900 hover:bg-slate-800 hover:border-slate-800 dark:bg-white dark:text-slate-900 dark:border-white dark:hover:bg-slate-100 dark:hover:border-slate-100",
  secondary: "bg-white text-slate-900 border border-slate-200 hover:bg-slate-50 hover:border-slate-300 dark:bg-slate-800 dark:text-white dark:border-slate-700 dark:hover:bg-slate-700 dark:hover:border-slate-600",
  ghost:     "text-slate-600 hover:text-slate-900 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-white dark:hover:bg-slate-800",
  danger:    "bg-red-600 text-white border border-red-600 hover:bg-red-700 hover:border-red-700",
}
const sizes = {
  sm: "px-3 py-1.5 text-xs rounded-md",
  md: "px-4 py-2 text-sm rounded-md",
  lg: "px-6 py-2.5 text-base rounded-lg",
}

export function Button({ variant = "primary", size = "md", className, children, ...props }: Props) {
  return (
    <button
      className={cn(
        "font-medium transition-colors duration-150 ease-out disabled:opacity-50 disabled:cursor-not-allowed",
        variants[variant], sizes[size], className
      )}
      {...props}
    >
      {children}
    </button>
  )
}
