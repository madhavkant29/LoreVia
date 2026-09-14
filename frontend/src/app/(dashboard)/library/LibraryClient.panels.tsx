"use client"

import type { ReactNode } from "react"
import Link from "next/link"

import { Button } from "@/components/ui/Button"
import { Skeleton } from "@/components/ui/Skeleton"
import { useUiPreferencesStore } from "@/lib/stores/uiPreferencesStore"
import type { NextBestAction } from "@/types/ux"

import { formatNumber, type MetricTone } from "./LibraryClient.helpers"
import { CalendarMetricIcon, DraftMetricIcon, PulseMetricIcon } from "./LibraryClient.icons"

export function NextActionPanel({
  isDark,
  actions,
}: {
  isDark: boolean
  actions: NextBestAction[]
}) {
  const primary = actions[0]
  const snoozeRecommendation = useUiPreferencesStore((state) => state.snoozeRecommendation)
  const dismissRecommendation = useUiPreferencesStore((state) => state.dismissRecommendation)

  return (
    <section className={`rounded-sm border p-5 ${isDark ? "border-white/[0.08] bg-[#101b24]" : "border-stone-200 bg-white"}`}>
      <p className="app-eyebrow">Next best action</p>
      {primary ? (
        <>
          <p className={`mt-3 text-xl font-semibold ${isDark ? "text-[#f5f0e8]" : "text-stone-950"}`}>{primary.label}</p>
          {primary.description ? <p className={`mt-2 text-sm leading-7 ${isDark ? "text-[#a6a39b]" : "text-stone-600"}`}>{primary.description}</p> : null}
          {primary.href ? (
            <Link href={primary.href} className="app-button-secondary mt-5">
              Open
            </Link>
          ) : (
            <Button type="button" variant="secondary" onClick={primary.onSelect} className="mt-5 rounded-sm">
              {primary.label}
            </Button>
          )}
          {primary.fingerprint ? (
            <div className="mt-4 flex flex-wrap gap-2">
              <Button type="button" variant="ghost" size="sm" onClick={() => void snoozeRecommendation(primary.id, primary.fingerprint as string)}>
                Snooze 24 hours
              </Button>
              <Button type="button" variant="ghost" size="sm" onClick={() => void dismissRecommendation(primary.id, primary.fingerprint as string)}>
                Dismiss
              </Button>
            </div>
          ) : null}
        </>
      ) : (
        <p className={`mt-3 text-sm leading-7 ${isDark ? "text-[#a6a39b]" : "text-stone-600"}`}>
          Your workspace is current. Use search, filters, or the command palette to jump into a project.
        </p>
      )}
    </section>
  )
}

export function FirstManuscriptHero({
  isDark,
  onUpload,
}: {
  isDark: boolean
  onUpload: () => void
}) {
  return (
    <section
      className={`overflow-hidden rounded-sm border px-6 py-10 sm:px-10 sm:py-14 ${
        isDark
          ? "border-teal-300/15 bg-[linear-gradient(135deg,#101b24_0%,#102a2b_100%)]"
          : "border-teal-900/10 bg-[linear-gradient(135deg,#ffffff_0%,#edf9f6_100%)]"
      }`}
      data-testid="first-manuscript-hero"
    >
      <div className="max-w-3xl">
        <p className="app-eyebrow text-teal-600">A thoughtful first reader for your draft</p>
        <h1 className={`mt-4 text-3xl font-semibold tracking-[-0.035em] sm:text-5xl ${isDark ? "text-[#f5f0e8]" : "text-stone-950"}`}>
          Upload your manuscript for a first read
        </h1>
        <p className={`mt-5 max-w-2xl text-base leading-8 sm:text-lg ${isDark ? "text-[#c8c2b8]" : "text-stone-600"}`}>
          LoreVia begins with what is working—your characters, scenes, voice, themes, and emotional core—then moves into evidence-backed revision opportunities.
        </p>
        <div className={`mt-6 flex flex-wrap gap-x-5 gap-y-2 text-sm ${isDark ? "text-[#aaa69e]" : "text-stone-600"}`} aria-label="First read sequence">
          <span>Validate what works</span>
          <span aria-hidden="true">→</span>
          <span>Understand the story</span>
          <span aria-hidden="true">→</span>
          <span>Critique with evidence</span>
          <span aria-hidden="true">→</span>
          <span>Plan improvements</span>
        </div>
        <Button type="button" onClick={onUpload} className="mt-8 rounded-sm bg-teal-700 px-5 text-white hover:bg-teal-600">
          Upload manuscript
        </Button>
        <p className={`mt-3 text-xs ${isDark ? "text-[#8e8b85]" : "text-stone-500"}`}>
          The supportive full-manuscript read begins automatically after extraction. Your draft stays private.
        </p>
      </div>
    </section>
  )
}

export function MetricStrip({
  isDark,
  loading,
  totalProjects,
  activeDrafts,
  processing,
}: {
  isDark: boolean
  loading: boolean
  totalProjects: number
  activeDrafts: number
  processing: number
}) {
  const shellClass = isDark ? "border-white/[0.08] bg-[#101b24]" : "border-stone-200 bg-white"

  return (
    <section className={`grid overflow-hidden rounded-sm border ${shellClass} md:grid-cols-3`}>
      <MetricCell
        isDark={isDark}
        loading={loading}
        tone="slate"
        icon={<CalendarMetricIcon />}
        label="Total projects"
        value={totalProjects}
        detail="Across active workspaces"
      />
      <MetricCell
        isDark={isDark}
        loading={loading}
        tone="teal"
        icon={<DraftMetricIcon />}
        label="Active drafts"
        value={activeDrafts}
        detail="Author projects in motion"
      />
      <MetricCell
        isDark={isDark}
        loading={loading}
        tone="violet"
        icon={<PulseMetricIcon />}
        label="Processing"
        value={processing}
        detail="AI analysis in progress"
      />
    </section>
  )
}

function MetricCell({
  isDark,
  loading,
  tone,
  icon,
  label,
  value,
  detail,
}: {
  isDark: boolean
  loading: boolean
  tone: MetricTone
  icon: ReactNode
  label: string
  value: number
  detail: string
}) {
  const toneClass: Record<MetricTone, string> = {
    slate: isDark ? "bg-slate-400/10 text-slate-200" : "bg-slate-100 text-slate-700",
    teal: isDark ? "bg-teal-400/10 text-teal-200" : "bg-teal-50 text-teal-700",
    violet: isDark ? "bg-violet-400/10 text-violet-200" : "bg-violet-50 text-violet-700",
    amber: isDark ? "bg-amber-300/10 text-amber-200" : "bg-amber-50 text-amber-700",
  }

  return (
    <div className={`flex min-h-[7.25rem] gap-4 border-b p-4 xl:border-b-0 xl:border-r xl:last:border-r-0 ${isDark ? "border-white/[0.08]" : "border-stone-200"}`}>
      <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-md ${toneClass[tone]}`}>
        {icon}
      </div>
      <div className="min-w-0">
        <p className={`text-sm ${isDark ? "text-[#a6a39b]" : "text-stone-600"}`}>{label}</p>
        {loading ? (
          <Skeleton variant="text" className="mt-2 h-7 w-14" />
        ) : (
          <p className={`mt-1 text-2xl font-semibold tracking-[-0.03em] ${isDark ? "text-[#f5f0e8]" : "text-stone-950"}`}>{formatNumber(value)}</p>
        )}
        <p className={`mt-2 flex items-center gap-2 text-xs ${isDark ? "text-[#9f9b94]" : "text-stone-500"}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${tone === "amber" ? "bg-amber-400" : tone === "violet" ? "bg-violet-400" : tone === "teal" ? "bg-teal-400" : "bg-slate-400"}`} />
          {detail}
        </p>
      </div>
    </div>
  )
}

export function SectionHeading({
  icon,
  title,
  helperText,
  isDark,
}: {
  icon: ReactNode
  title: string
  helperText?: string
  isDark: boolean
}) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-center gap-2.5">
        {icon}
        <h2 className={`text-[1.08rem] font-semibold tracking-[-0.01em] ${isDark ? "text-[#f5f0e8]" : "text-stone-900"}`}>{title}</h2>
      </div>

      {helperText ? <p className={`text-sm ${isDark ? "text-[#9e998f]" : "text-stone-600"}`}>{helperText}</p> : null}
    </div>
  )
}
