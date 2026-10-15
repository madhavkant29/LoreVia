import type { Character } from "@/types/character"
import { SurfaceCard } from "./charactersPage.components"
import {
  formatRelationshipType,
  growthChapter,
  growthTitle,
  relationshipChangeKey,
  sentimentLabel,
} from "./charactersPage.helpers"

type CharacterArcTabProps = {
  arcTracker: Character["arc_tracker"] | null | undefined
  character: Character
  growthEvents: NonNullable<Character["growth_events"]>
  isDark: boolean
}

export function CharacterArcTab({
  arcTracker,
  character,
  growthEvents,
  isDark,
}: CharacterArcTabProps) {
  const checkpoints = arcTracker?.major_turning_points?.length ? arcTracker.major_turning_points : growthEvents

  return (
    <div className="mt-5 space-y-4">
      <SurfaceCard title="Arc summary" isDark={isDark}>
        <p className={`text-sm leading-7 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
          {arcTracker?.summary || character.arc_summary || "Current role and progression are still being inferred from the manuscript."}
        </p>
      </SurfaceCard>

      <div className="grid gap-4 xl:grid-cols-2">
        <SurfaceCard title="Core arc profile" isDark={isDark}>
          <dl className="grid gap-3 text-sm">
            <div className="grid grid-cols-[132px_minmax(0,1fr)] gap-3">
              <dt className={isDark ? "text-slate-400" : "text-stone-600"}>Goal</dt>
              <dd className={isDark ? "text-white" : "text-stone-900"}>{arcTracker?.goal || character.goal || "Not recorded"}</dd>
            </div>
            <div className="grid grid-cols-[132px_minmax(0,1fr)] gap-3">
              <dt className={isDark ? "text-slate-400" : "text-stone-600"}>Motivation</dt>
              <dd className={isDark ? "text-white" : "text-stone-900"}>{arcTracker?.motivation || "Not recorded"}</dd>
            </div>
            <div className="grid grid-cols-[132px_minmax(0,1fr)] gap-3">
              <dt className={isDark ? "text-slate-400" : "text-stone-600"}>Fear</dt>
              <dd className={isDark ? "text-white" : "text-stone-900"}>{arcTracker?.fear || "Not recorded"}</dd>
            </div>
            <div className="grid grid-cols-[132px_minmax(0,1fr)] gap-3">
              <dt className={isDark ? "text-slate-400" : "text-stone-600"}>Lie</dt>
              <dd className={isDark ? "text-white" : "text-stone-900"}>{arcTracker?.lie_they_believe || character.lie_they_believe || "Not recorded"}</dd>
            </div>
            <div className="grid grid-cols-[132px_minmax(0,1fr)] gap-3">
              <dt className={isDark ? "text-slate-400" : "text-stone-600"}>Wound</dt>
              <dd className={isDark ? "text-white" : "text-stone-900"}>{arcTracker?.wound_backstory || character.backstory_wound || "Not recorded"}</dd>
            </div>
            <div className="grid grid-cols-[132px_minmax(0,1fr)] gap-3">
              <dt className={isDark ? "text-slate-400" : "text-stone-600"}>Arc type</dt>
              <dd className={isDark ? "text-white" : "text-stone-900"}>{arcTracker?.arc_type || character.arc_type || character.archetype || "Not recorded"}</dd>
            </div>
          </dl>
        </SurfaceCard>

        <SurfaceCard title="Voice markers" isDark={isDark}>
          {(arcTracker?.voice_markers?.length ?? 0) > 0 ? (
            <div className="space-y-2">
              {arcTracker?.voice_markers?.map((marker) => (
                <div key={marker} className={`rounded-sm border px-3 py-2 text-sm ${isDark ? "border-[#17202c] bg-black/20 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                  {marker}
                </div>
              ))}
            </div>
          ) : (
            <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-600"}>No voice markers are grounded yet.</p>
          )}
        </SurfaceCard>
      </div>

      <SurfaceCard title="Arc timeline" isDark={isDark}>
        {(arcTracker?.arc_timeline?.length ?? 0) > 0 ? (
          <div className="space-y-3">
            {arcTracker?.arc_timeline?.map((line) => (
              <div key={line} className={`rounded-sm border px-4 py-3 text-sm leading-6 ${isDark ? "border-[#17202c] bg-black/20 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                {line}
              </div>
            ))}
          </div>
        ) : (
          <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-600"}>No chapter-by-chapter arc timeline has been captured yet.</p>
        )}
      </SurfaceCard>

      <SurfaceCard title="Arc checkpoints" isDark={isDark}>
        {checkpoints.length > 0 ? (
          <div className="space-y-3">
            {checkpoints.map((event, index) => (
              <div key={`${character.id}-growth-${index}`} className={`rounded-sm border px-4 py-3 ${isDark ? "border-[#17202c] bg-black/20" : "border-stone-200 bg-white"}`}>
                <div className="flex flex-wrap items-center gap-2">
                  {("chapter_number" in event ? event.chapter_number : growthChapter(event)) ? (
                    <span className={`rounded-sm px-2 py-0.5 text-xs font-semibold uppercase tracking-[0.16em] ${isDark ? "bg-violet-500/15 text-violet-100" : "bg-violet-100 text-violet-700"}`}>
                      Chapter {"chapter_number" in event ? event.chapter_number : growthChapter(event)}
                    </span>
                  ) : null}
                  {event.is_major ? (
                    <span className={`rounded-sm px-2 py-0.5 text-xs ${isDark ? "bg-amber-500/12 text-amber-200" : "bg-amber-50 text-amber-700"}`}>
                      major shift
                    </span>
                  ) : null}
                </div>
                <p className={`mt-2 text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{"title" in event ? event.title : growthTitle(event)}</p>
                {(event.description || ("impact" in event ? event.impact : null)) ? (
                  <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>
                    {event.description || ("impact" in event ? event.impact : null)}
                  </p>
                ) : null}
              </div>
            ))}
          </div>
        ) : (
          <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-600"}>No explicit arc checkpoints have been captured yet.</p>
        )}
      </SurfaceCard>

      <div className="grid gap-4 xl:grid-cols-2">
        <SurfaceCard title="Relationship changes" isDark={isDark}>
          {(arcTracker?.relationship_changes?.length ?? 0) > 0 ? (
            <div className="space-y-3">
              {arcTracker?.relationship_changes?.map((item, index) => (
                <div key={relationshipChangeKey(item, index)} className={`rounded-sm border px-4 py-3 ${isDark ? "border-[#17202c] bg-black/20" : "border-stone-200 bg-white"}`}>
                  <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>Chapter {item.chapter_number}: {item.counterpart_name}</p>
                  <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>{formatRelationshipType(item.type)} / {sentimentLabel(item.sentiment)}</p>
                  {item.description ? <p className={`mt-2 text-sm leading-6 ${isDark ? "text-slate-300" : "text-stone-600"}`}>{item.description}</p> : null}
                </div>
              ))}
            </div>
          ) : (
            <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-600"}>No explicit relationship shifts are tracked yet.</p>
          )}
        </SurfaceCard>

        <SurfaceCard title="Physical description history" isDark={isDark}>
          {(arcTracker?.physical_description_history?.length ?? 0) > 0 ? (
            <div className="space-y-3">
              {arcTracker?.physical_description_history?.map((item) => (
                <div key={`${item.chapter_number}-${item.trait}-${item.value}`} className={`rounded-sm border px-4 py-3 text-sm ${isDark ? "border-[#17202c] bg-black/20 text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
                  <span className={`text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>Chapter {item.chapter_number}</span>
                  <p className={`mt-1 font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{item.label}</p>
                  <p className="mt-1">{item.previous_value ? `${item.previous_value} -> ${item.value}` : item.value}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className={isDark ? "text-sm text-slate-400" : "text-sm text-stone-600"}>No description history has been tracked yet.</p>
          )}
        </SurfaceCard>
      </div>
    </div>
  )
}
