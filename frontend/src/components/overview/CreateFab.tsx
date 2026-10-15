"use client"

import { Plus } from "lucide-react"

import { DisclosureMenu } from "@/components/ui/DisclosureMenu"

export function CreateFab({
  bookId,
  inline = false,
  isDark,
  onAddScene,
  onNavigate,
}: {
  inline?: boolean
  bookId: string
  isDark: boolean
  onAddScene: () => void
  onNavigate: (href: string) => void
}) {
  return (
    <div data-lorevia-bottom-floating={inline ? undefined : true} className={inline ? "" : "fixed bottom-24 right-5 z-40 lg:bottom-8 lg:right-8"}>
      <DisclosureMenu
        label="Create project item"
        side={inline ? "bottom" : "top"}
        items={[
          { id: "scene", label: "Add Scene", onSelect: onAddScene },
          { id: "note", label: "Add Note", onSelect: () => onNavigate(`/${bookId}/notes`) },
          { id: "character", label: "Add Character", onSelect: () => onNavigate(`/${bookId}/characters`) },
        ]}
        className={`inline-flex min-h-11 items-center gap-2 rounded-sm border px-4 text-sm font-semibold text-white transition focus-visible:ring-offset-2 ${
          isDark ? "border-teal-300/20 bg-teal-700 hover:bg-teal-600" : "border-teal-800 bg-teal-800 hover:bg-teal-700"
        }`}
        trigger={
          <>
            <Plus className="h-4 w-4" aria-hidden="true" />
            <span>Create</span>
          </>
        }
      />
    </div>
  )
}
