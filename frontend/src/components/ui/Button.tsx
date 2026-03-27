import { type ButtonHTMLAttributes } from "react"
import { cn } from "@/lib/utils/text"

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger"
  size?: "sm" | "md" | "lg"
}

const variants = {
  primary:   "bg-indigo-600 text-white hover:bg-indigo-700",
  secondary: "bg-white text-gray-900 border border-gray-300 hover:bg-gray-50",
  ghost:     "text-gray-600 hover:text-gray-900 hover:bg-gray-100",
  danger:    "bg-red-600 text-white hover:bg-red-700",
}
const sizes = {
  sm: "px-3 py-1.5 text-xs rounded-lg",
  md: "px-4 py-2 text-sm rounded-lg",
  lg: "px-6 py-3 text-base rounded-xl",
}

export function Button({ variant = "primary", size = "md", className, children, ...props }: Props) {
  return (
    <button
      className={cn(
        "font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed",
        variants[variant], sizes[size], className
      )}
      {...props}
    >
      {children}
    </button>
  )
}
