"use client"

import { Button } from "@/components/ui/Button"

export function CreateFab({
  bookId,
  isDark,
  onAddScene,
  onNavigate,
}: {
  bookId: string
  isDark: boolean
  onAddScene: () => void
  onNavigate: (href: string) => void
}) {
  const itemClass = "rounded-full shadow-[0_18px_44px_-28px_rgba(0,0,0,0.8)]"

  return (
    <div className="group/create fixed bottom-24 right-5 z-40 flex flex-col items-end gap-3 lg:bottom-8 lg:right-8">
      <div className="pointer-events-none flex translate-y-2 flex-col items-end gap-2 opacity-0 transition group-hover/create:pointer-events-auto group-hover/create:translate-y-0 group-hover/create:opacity-100 group-focus-within/create:pointer-events-auto group-focus-within/create:translate-y-0 group-focus-within/create:opacity-100">
        <Button variant="secondary" size="sm" onClick={onAddScene} className={itemClass}>Add Scene</Button>
        <Button variant="secondary" size="sm" onClick={() => onNavigate(`/${bookId}/notes`)} className={itemClass}>Add Note</Button>
        <Button variant="secondary" size="sm" onClick={() => onNavigate(`/${bookId}/characters`)} className={itemClass}>Add Character</Button>
      </div>
      <Button variant="primary" size="sm" className="rounded-full shadow-[0_18px_55px_-28px_rgba(0,0,0,0.9)]">
        + Create
      </Button>
    </div>
  )
}
