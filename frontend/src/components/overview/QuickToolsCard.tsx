"use client"

import { Icon } from "./Icon"
import { PanelTitle } from "./PanelTitle"
import type { IconName } from "./types"
import { panelClass } from "./utils"

export function QuickToolsCard({ isDark, bookId, onNavigate }: { isDark: boolean; bookId: string; onNavigate: (href: string) => void }) {
  const tools = [
    { title: "Story Advisor", body: "Get AI feedback on your story", href: `/${bookId}/advisor`, icon: "graph" as IconName, color: "text-teal-700" },
    { title: "Ask the manuscript", body: "Get an evidence-grounded answer", href: `/${bookId}/advisor?mode=ask`, icon: "chat" as IconName, color: "text-blue-400" },
    { title: "World Gap Detection", body: "Find missing or inconsistent details", href: `/${bookId}/world-gap`, icon: "gap" as IconName, color: "text-amber-400" },
    { title: "Character Bible", body: "Manage your characters", href: `/${bookId}/characters`, icon: "file" as IconName, color: "text-emerald-400" },
    { title: "Voice Inconsistency", body: "Detect character voice drift", href: `/${bookId}/voice`, icon: "voice" as IconName, color: "text-rose-400" },
    { title: "Manuscript Editor", body: "Write and edit your manuscript", href: `/${bookId}/manuscript`, icon: "book" as IconName, color: "text-teal-700" },
  ]

  return (
    <section className={panelClass(isDark, "p-4 sm:p-5")}>
      <PanelTitle isDark={isDark}>Quick Tools</PanelTitle>
      <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-2 2xl:grid-cols-3">
        {tools.map((tool) => (
          <button
            key={tool.title}
            onClick={() => onNavigate(tool.href)}
            className={`min-h-32 rounded-md border p-3 text-left transition ${isDark ? "border-white/[0.06] bg-white/[0.025] hover:bg-white/[0.055]" : "border-slate-100 bg-white hover:bg-slate-50"}`}
          >
            <Icon name={tool.icon} className={`h-6 w-6 ${tool.color}`} />
            <p className={`mt-4 text-sm font-semibold ${isDark ? "text-slate-200" : "text-slate-700"}`}>{tool.title}</p>
            <p className={`mt-2 text-xs leading-5 ${isDark ? "text-slate-500" : "text-slate-400"}`}>{tool.body}</p>
          </button>
        ))}
      </div>
    </section>
  )
}
