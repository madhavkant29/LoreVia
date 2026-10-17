"use client"

import { useParams } from "next/navigation"

import { WorldbuildingWorkspace } from "@/components/reader/WorldbuildingWorkspace"
import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { WorkspacePage } from "@/components/ui/Workspace"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"
import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"

export default function WorldGapPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  return (
    <WorkspacePage className={isDark ? "text-slate-100" : "text-stone-950"}>
      <div data-world-workspace className="mx-auto max-w-[1480px] px-0 pb-10 pt-6 sm:px-2 lg:px-4">
        <WorkspaceFamilyHeader
          active="world-gap"
          bookId={bookId}
          family="story-bible"
          title="World gaps"
          description="Review conflicts between your canon sources and manuscript evidence, then turn confirmed gaps into a focused cleanup queue."
          actions={<button type="button" className="app-button-secondary" onClick={() => window.dispatchEvent(new Event(SUPPORT_HELP_EVENT))}>Help</button>}
        />
        <div className="mt-6">
          <WorldbuildingWorkspace key={bookId} bookId={bookId} isDark={isDark} focus="gap" />
        </div>
      </div>
    </WorkspacePage>
  )
}
