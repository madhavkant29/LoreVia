import type { Character } from "@/types/character"
import { SurfaceCard } from "./charactersPage.components"
import {
  bookCoverageLabel,
  chapterAppearanceLabel,
  growthChapter,
  growthTitle,
} from "./charactersPage.helpers"

type CharacterTimelineTabProps = {
  arcTracker: Character["arc_tracker"] | null | undefined
  character: Character
  chapterAppearanceText: (chapter: number | null | undefined) => string
  growthEvents: NonNullable<Character["growth_events"]>
  isDark: boolean
  totalChapters?: number | null
}

export function CharacterTimelineTab({
  arcTracker,
  character,
  chapterAppearanceText,
  growthEvents,
  isDark,
  totalChapters,
}: CharacterTimelineTabProps) {
  const timelineLines = arcTracker?.arc_timeline?.length
    ? arcTracker.arc_timeline
    : growthEvents.map((event) => `${chapterAppearanceLabel(growthChapter(event))}: ${growthTitle(event)}`)

  return (
    <div className="mt-5 space-y-4">
      <SurfaceCard title="Timeline anchors" isDark={isDark}>
        <div className="grid gap-3 md:grid-cols-3">
          {[
            ["First appearance", chapterAppearanceText(character.first_chapter)],
            ["Latest appearance", chapterAppearanceText(character.last_seen_chapter ?? character.first_chapter)],
            ["Coverage", bookCoverageLabel(character, totalChapters)],
          ].map(([label, value]) => (
            <div key={label} className={`rounded-sm border px-4 py-3 ${isDark ? "border-[#17202c] bg-black/20" : "border-stone-200 bg-white"}`}>
              <p className={`text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>{label}</p>
              <p className={`mt-1 text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{value}</p>
            </div>
          ))}
        </div>
      </SurfaceCard>

      <SurfaceCard title="Timeline" isDark={isDark}>
        {timelineLines.length > 0 ? (
          <div className="space-y-3">
            {timelineLines.map((line) => (
              <div key={line} className={`rounded-sm border px-4 py-3 text-sm leading-6 ${isDark ? "border-[#17202c] bg-black/20 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                {line}
              </div>
            ))}
          </div>
        ) : (
          <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-600"}>No timeline events have been captured yet.</p>
        )}
      </SurfaceCard>
    </div>
  )
}
