"use client"

import React from "react"
import { useState } from "react"

import { resolveAssetUrl } from "@/lib/utils/assetUrls"
import { cn } from "@/lib/utils/text"

interface SmartBookCoverProps {
  src?: string | null
  title: string
  isDark?: boolean
  className?: string
  imageClassName?: string
}

export function SmartBookCover({
  src,
  title,
  isDark = false,
  className,
  imageClassName,
}: SmartBookCoverProps) {
  const [failed, setFailed] = useState(false)

  const activeSrc = !failed ? resolveAssetUrl(src) : null

  const hasImage = Boolean(activeSrc)
  const imageSrc = activeSrc ?? ""

  return (
    <div
      className={cn("relative overflow-hidden", className)}
    >
      {hasImage ? (
        <img
          src={imageSrc}
          alt={`${title} cover`}
          loading="lazy"
          decoding="async"
          className={cn("absolute inset-0 z-10 h-full w-full", imageClassName ?? "object-cover object-center")}
          onError={() => setFailed(true)}
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

function titleInitials(title: string) {
  return title
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("")
}
