"use client"

import Link from "next/link"

import { Button } from "@/components/ui/Button"
import type { NextBestAction } from "@/types/ux"

export function MobileActionBar({ actions }: { actions: NextBestAction[] }) {
  if (actions.length === 0) return null

  return (
    <div className="fixed inset-x-0 bottom-0 z-40 border-t border-[rgba(var(--border),0.9)] bg-[rgb(var(--card))]/95 px-4 py-3 backdrop-blur md:hidden">
      <div className="mx-auto flex max-w-xl gap-2">
        {actions.slice(0, 2).map((action) => {
          const variant = action.tone === "danger" ? "danger" : action.tone === "secondary" ? "secondary" : "primary"
          if (action.href) {
            return (
              <Link
                key={action.id}
                href={action.href}
                className={variant === "primary" ? "app-button-primary flex-1 py-3" : "app-button-secondary flex-1 py-3"}
              >
                {action.label}
              </Link>
            )
          }
          return (
            <Button key={action.id} type="button" variant={variant} onClick={action.onSelect} className="flex-1">
              {action.label}
            </Button>
          )
        })}
      </div>
    </div>
  )
}
