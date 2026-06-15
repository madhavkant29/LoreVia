"use client"

import Link from "next/link"
import dynamic from "next/dynamic"
import { useParams } from "next/navigation"

import { WorkspaceFamilyHeader } from "@/components/reader/WorkspaceFamilyHeader"
import { WorkspacePage } from "@/components/ui/Workspace"
import { usePreferencesStore } from "@/lib/stores/preferencesStore"

const WorldbuildingWorkspace = dynamic(
  () => import("@/components/reader/WorldbuildingWorkspace").then((module) => module.WorldbuildingWorkspace),
  {
    loading: () => <div className="app-panel min-h-[28rem] animate-pulse" aria-label="Loading worldbuilding workspace" />,
  }
)

export default function WorldGapPage() {
  const { bookId } = useParams<{ bookId: string }>()
  const { theme } = usePreferencesStore()
  const isDark = theme === "dark"

  return (
    <WorkspacePage className={isDark ? "text-slate-100" : "text-stone-950"}>
      <div className="mx-auto max-w-[1480px] px-0 pb-10 pt-6 sm:px-2 lg:px-4">
        <WorkspaceFamilyHeader
          active="world-gap"
          bookId={bookId}
          family="story-bible"
          title="Worldbuilding corpus vs. manuscript"
          description="Keep reference lore independent from the draft. Compare both sources to find missing context, inconsistencies, and opportunities."
          actions={(
            <>
              <Link href={`/${bookId}/manuscript`} className="app-button-secondary">Manuscript</Link>
              <Link href={`/${bookId}/advisor`} className="app-button-primary">Story advisor</Link>
            </>
          )}
        />
        <div className="mt-6">
          <WorldbuildingWorkspace bookId={bookId} isDark={isDark} focus="gap" />
        </div>
      </div>
    </WorkspacePage>
  )
}
