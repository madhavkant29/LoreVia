"use client"

import { cloneElement, isValidElement, useId, type ReactElement, type ReactNode } from "react"

import { cn } from "@/lib/utils/text"

type TooltipSide = "top" | "bottom"
type TooltipAlign = "start" | "center" | "end"

type TooltipProps = {
  content: string
  children: ReactNode
  className?: string
  side?: TooltipSide
  align?: TooltipAlign
}

const sideClasses: Record<TooltipSide, string> = {
  top: "bottom-full mb-2",
  bottom: "top-full mt-2",
}

const alignClasses: Record<TooltipAlign, string> = {
  start: "left-0",
  center: "left-1/2 -translate-x-1/2",
  end: "right-0",
}

export function Tooltip({ content, children, className, side = "top", align = "center" }: TooltipProps) {
  const tooltipId = useId()
  const trigger = isValidElement(children)
    ? cloneElement(children as ReactElement<{ "aria-describedby"?: string }>, {
        "aria-describedby": [
          (children as ReactElement<{ "aria-describedby"?: string }>).props["aria-describedby"],
          tooltipId,
        ].filter(Boolean).join(" "),
      })
    : children

  return (
    <span className={cn("group/tooltip relative inline-flex", className)}>
      {trigger}
      <span
        id={tooltipId}
        role="tooltip"
        className={cn(
          "pointer-events-none absolute z-50 hidden w-max max-w-56 whitespace-normal rounded-none bg-[rgb(var(--surface))] px-2.5 py-1.5 text-xs font-medium text-[rgb(var(--foreground))] shadow-sm group-focus-within/tooltip:block group-hover/tooltip:block",
          sideClasses[side],
          alignClasses[align],
        )}
      >
        {content}
      </span>
    </span>
  )
}
