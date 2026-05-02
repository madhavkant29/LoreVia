"use client"

import { useState } from "react"

import { cn } from "@/lib/utils/text"

type EdgeColors = {
  top?: string | null
  bottom?: string | null
  left?: string | null
  right?: string | null
  dominant?: string | null
}

interface SmartBookCoverProps {
  src?: string | null
  processedSrc?: string | null
  edgeColors?: EdgeColors | null
  title: string
  isDark?: boolean
  className?: string
  imageClassName?: string
}

export function SmartBookCover({
  src,
  processedSrc,
  edgeColors,
  title,
  isDark = false,
  className,
  imageClassName,
}: SmartBookCoverProps) {
  const [failed, setFailed] = useState(false)
  const [attempt, setAttempt] = useState<"processed" | "original" | "fallback">("processed")

  const processed = resolveCoverUrl(processedSrc)
  const original = resolveCoverUrl(src)
  const activeSrc = !failed
    ? attempt === "processed"
      ? processed ?? original
      : attempt === "original"
        ? original
        : null
    : null

  const hasImage = Boolean(activeSrc)
  const imageSrc = activeSrc ?? ""
  const colors = normalizeColors(edgeColors)
  const fallbackStyle = colors
    ? {
        backgroundImage: `linear-gradient(160deg, ${colors.top} 0%, ${colors.dominant} 52%, ${colors.bottom} 100%)`,
        backgroundColor: colors.dominant,
      }
    : undefined

  return (
    <div
      className={cn("relative overflow-hidden", className)}
      style={fallbackStyle}
    >
      {hasImage ? (
        <img
          src={imageSrc}
          alt={`${title} cover`}
          className={cn("absolute inset-0 z-10 h-full w-full", imageClassName ?? "object-cover object-center")}
          onError={() => {
            if (attempt === "processed" && original && original !== processed) {
              setAttempt("original")
              return
            }
            setFailed(true)
          }}
        />
      ) : (
        <div
          className={cn(
            "relative z-10 flex h-full w-full flex-col justify-between p-5",
            isDark ? "bg-[#0D0D0D] text-[#E0E0E0]" : "bg-[linear-gradient(150deg,#f4ecda,#ffffff_60%,#ecebff)] text-stone-900",
          )}
        >
          <span className={cn("text-[0.65rem] font-semibold uppercase tracking-[0.28em]", isDark ? "text-[#808080]" : "text-violet-600")}>LoreVia</span>
          <div>
            <p className="text-3xl font-semibold leading-none">{titleInitials(title)}</p>
            <p className={cn("mt-3 line-clamp-3 text-sm leading-6", isDark ? "text-[#A0A0A0]" : "text-stone-600")}>{title}</p>
          </div>
        </div>
      )}
    </div>
  )
}

function resolveCoverUrl(coverUrl: string | null | undefined) {
  if (!coverUrl) return null
  if (/^https?:\/\//i.test(coverUrl)) return coverUrl
  try {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL
    if (apiUrl) {
      return new URL(coverUrl, apiUrl).toString()
    }
    if (typeof window !== "undefined") {
      return new URL(coverUrl, window.location.origin).toString()
    }
    return coverUrl
  } catch {
    return coverUrl
  }
}

function normalizeColors(edgeColors: EdgeColors | null | undefined) {
  if (!edgeColors) return null
  const top = edgeColors.top ?? edgeColors.dominant ?? "#1f2937"
  const bottom = edgeColors.bottom ?? edgeColors.dominant ?? "#111827"
  const dominant = edgeColors.dominant ?? top
  return { top, bottom, dominant }
}

function titleInitials(title: string) {
  return title
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("")
}
