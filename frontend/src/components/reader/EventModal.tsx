"use client"

import type { CharacterEvent, MajorEvent } from "@/types/book"

type Props = {
  isDark: boolean
  event: (MajorEvent & { kind: "story" }) | (CharacterEvent & { kind: "character" })
  onClose: () => void
}

export function EventModal({ isDark, event, onClose }: Props) {
  const chapterLabel = `Chapter ${event.chapter_number}${"chapter_title" in event && event.chapter_title ? ` - ${event.chapter_title}` : ""}`

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm" onClick={onClose}>
      <div
        className={`w-full max-w-2xl rounded-lg border p-6 shadow-2xl ${isDark ? "border-white/10 bg-[#0f1117] text-white" : "border-stone-200 bg-white text-stone-900"}`}
        onClick={(eventValue) => eventValue.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>
              {event.kind === "story" ? "Story major event" : `${event.character_name} major event`}
            </p>
            <h3 className={`mt-2 text-2xl font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{event.event_title}</h3>
            <p className={`mt-2 text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{chapterLabel}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className={`rounded-full px-3 py-1.5 text-xs font-medium ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}
          >
            Close
          </button>
        </div>

        <p className={`mt-5 text-base leading-8 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{event.description}</p>

        <div className="mt-5 flex flex-wrap gap-2">
          {"importance" in event ? (
            <span className={`rounded-full px-3 py-1 text-xs font-medium ${isDark ? "bg-indigo-500/15 text-indigo-200" : "bg-indigo-100 text-indigo-700"}`}>
              importance {event.importance}/10
            </span>
          ) : (
            <>
              <span className={`rounded-full px-3 py-1 text-xs font-medium ${isDark ? "bg-indigo-500/15 text-indigo-200" : "bg-indigo-100 text-indigo-700"}`}>
                impact {event.impact_score}/10
              </span>
              <span className={`rounded-full px-3 py-1 text-xs font-medium capitalize ${isDark ? "bg-white/10 text-slate-300" : "bg-stone-100 text-stone-600"}`}>
                {event.growth_direction}
              </span>
              <span className={`rounded-full px-3 py-1 text-xs font-medium ${isDark ? "bg-white/10 text-slate-300" : "bg-stone-100 text-stone-600"}`}>
                growth {event.growth_magnitude}/10
              </span>
            </>
          )}
          {event.kind === "character" && event.role ? (
            <span className={`rounded-full px-3 py-1 text-xs font-medium ${isDark ? "bg-white/10 text-slate-300" : "bg-stone-100 text-stone-600"}`}>
              {event.role}
            </span>
          ) : null}
          {event.kind === "story" && event.event_type ? (
            <span className={`rounded-full px-3 py-1 text-xs font-medium capitalize ${isDark ? "bg-white/10 text-slate-300" : "bg-stone-100 text-stone-600"}`}>
              {event.event_type.replaceAll("_", " ")}
            </span>
          ) : null}
        </div>

        {event.kind === "story" && event.involved_character_names?.length ? (
          <div className="mt-6">
            <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Involved characters</p>
            <div className="mt-3 flex flex-wrap gap-2">
              {event.involved_character_names.map((name) => (
                <span key={name} className={`rounded-full px-3 py-1 text-sm ${isDark ? "bg-white/8 text-slate-200" : "bg-stone-100 text-stone-700"}`}>
                  {name}
                </span>
              ))}
            </div>
          </div>
        ) : null}

        {event.kind === "character" && event.accomplishments.length ? (
          <div className="mt-6">
            <p className={`text-3xs font-semibold uppercase tracking-[0.22em] ${isDark ? "text-slate-500" : "text-stone-400"}`}>Accomplishments</p>
            <div className="mt-3 space-y-2">
              {event.accomplishments.map((item) => (
                <p key={item} className={`text-sm leading-7 ${isDark ? "text-slate-200" : "text-stone-700"}`}>{item}</p>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  )
}
