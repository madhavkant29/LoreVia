import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function truncate(text: string, max: number) {
  return text.length <= max ? text : text.slice(0, max - 3) + "..."
}

export function highlightQuery(text: string, query: string): string {
  if (!query) return text
  const re = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")})`, "gi")
  return text.replace(re, "<mark>$1</mark>")
}
