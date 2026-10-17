import { useEffect, useId, useRef, type ReactNode } from "react"
import { SUPPORT_HELP_EVENT } from "@/components/ui/ShortcutHelp"

import { CardSkeleton, RowSkeleton, SidebarSkeleton, Skeleton } from "@/components/ui/Skeleton"

export type CharacterBibleStat = {
  label: string
  value: string
  detail?: string
  icon: "characters" | "relationships" | "chapter" | "merge" | "review"
  tone: "violet" | "teal" | "amber" | "rose" | "default"
}

export type MenuAction = {
  label: string
  onClick: () => void
  danger?: boolean
  disabled?: boolean
  dividerBefore?: boolean
}

export function iconButtonClasses(isDark: boolean) {
  return `inline-flex h-10 w-10 items-center justify-center rounded-sm border transition-colors ${
    isDark ? "border-[#202a38] bg-[#121823] text-slate-200 hover:border-[#2b3747] hover:bg-[#182131]" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"
  }`
}

export function actionButtonClasses(isDark: boolean) {
  return `inline-flex items-center rounded-sm border px-4 py-2.5 text-sm font-medium transition-colors ${
    isDark ? "border-[#202a38] bg-[#121823] text-slate-100 hover:border-[#2b3747] hover:bg-[#182131]" : "border-stone-200 bg-white text-stone-700 hover:bg-stone-50"
  }`
}

export function menuPanelClasses(isDark: boolean) {
  return `absolute right-0 top-full z-30 mt-2 w-60 overflow-hidden rounded-md border p-1 ${
    isDark ? "border-[#202a38] bg-[#0b1018]" : "border-stone-200 bg-white"
  }`
}

export function workspaceActionButtonClasses(
  isDark: boolean,
  {
    active = false,
    tone = "default",
  }: {
    active?: boolean
    tone?: "default" | "teal" | "violet" | "amber"
  } = {},
) {
  if (active) {
    if (tone === "teal") {
      return "border border-teal-500 bg-[#1f615d] text-white"
    }
    if (tone === "violet") {
      return "border border-violet-500 bg-violet-700 text-white"
    }
    if (tone === "amber") {
      return "border border-amber-500 bg-amber-600 text-white"
    }
    return "border border-[#2b3747] bg-white/[0.08] text-white"
  }

  return isDark
    ? "border border-[#202a38] bg-[#121823] text-slate-100 hover:border-[#2b3747] hover:bg-[#182131]"
    : "border border-stone-200 bg-white text-stone-700 hover:bg-stone-50"
}

export function fieldClasses(isDark: boolean) {
  return isDark
    ? "w-full rounded-sm border border-[#202a38] bg-[#0c1119] px-3 py-2.5 text-sm text-white outline-none transition-colors focus:border-violet-400/40 focus:ring-2 focus:ring-violet-400/20"
    : "w-full rounded-sm border border-stone-200 bg-white px-3 py-2.5 text-sm text-stone-900 outline-none transition-colors focus:border-violet-300 focus:ring-2 focus:ring-violet-200/70"
}

export function sectionEyebrowClasses(isDark: boolean, tone: "default" | "teal" | "violet" | "amber" = "default") {
  if (tone === "teal") return isDark ? "text-teal-300" : "text-teal-700"
  if (tone === "violet") return isDark ? "text-violet-300" : "text-violet-700"
  if (tone === "amber") return isDark ? "text-amber-300" : "text-amber-700"
  return isDark ? "text-slate-400" : "text-stone-600"
}

export function RelationshipGraphLoading() {
  return (
    <div className="min-h-[32rem] rounded-lg border border-dashed p-5" role="status" aria-label="Loading relationship graph" aria-busy="true">
      <span className="sr-only">Loading relationship graph</span>
      <Skeleton className="h-4 w-40" />
      <div className="relative mt-8 h-80">
        <Skeleton variant="circle" className="absolute left-[12%] top-[18%] h-14 w-14" />
        <Skeleton variant="circle" className="absolute left-[38%] top-[8%] h-10 w-10" />
        <Skeleton variant="circle" className="absolute left-[52%] top-[44%] h-16 w-16" />
        <Skeleton variant="circle" className="absolute right-[16%] top-[24%] h-12 w-12" />
        <Skeleton className="absolute left-[20%] top-[34%] h-px w-52 rotate-12" />
        <Skeleton className="absolute left-[50%] top-[50%] h-px w-44 -rotate-12" />
      </div>
    </div>
  )
}

export function SectionChevron({ className = "" }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
      <path fillRule="evenodd" d="M7.22 4.22a.75.75 0 0 1 1.06 0l5 5a.75.75 0 0 1 0 1.06l-5 5a.75.75 0 1 1-1.06-1.06L11.69 10 7.22 5.28a.75.75 0 0 1 0-1.06Z" clipRule="evenodd" />
    </svg>
  )
}

export function ShellIcon({
  name,
  className = "h-4 w-4",
}: {
  name: "characters" | "relationships" | "chapter" | "merge" | "add" | "review" | "repair" | "search" | "compare" | "split"
  className?: string
}) {
  if (name === "characters") {
    return (
      <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
        <path d="M6.5 8.25a2.75 2.75 0 1 0 0-5.5 2.75 2.75 0 0 0 0 5.5ZM13.5 9.25a2.25 2.25 0 1 0 0-4.5 2.25 2.25 0 0 0 0 4.5Z" />
        <path d="M2.75 16.25c0-2.28 2.16-4.13 4.83-4.13s4.84 1.85 4.84 4.13M12.08 16.25c0-1.84 1.63-3.34 3.67-3.34 1.06 0 2.01.4 2.67 1.05" strokeLinecap="round" />
      </svg>
    )
  }
  if (name === "relationships") {
    return (
      <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
        <circle cx="4.5" cy="10" r="1.75" />
        <circle cx="15.5" cy="5" r="1.75" />
        <circle cx="15.5" cy="15" r="1.75" />
        <path d="m6.16 9.2 7.61-3.33M6.16 10.8l7.61 3.33" strokeLinecap="round" />
      </svg>
    )
  }
  if (name === "chapter") {
    return (
      <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
        <path d="M4.25 4.25h4.5a2 2 0 0 1 2 2v9H6a1.75 1.75 0 0 0-1.75 1.75V6a1.75 1.75 0 0 1 1.75-1.75Zm11.5 0h-4.5a2 2 0 0 0-2 2v9H14a1.75 1.75 0 0 1 1.75 1.75V6A1.75 1.75 0 0 0 14 4.25Z" strokeLinejoin="round" />
      </svg>
    )
  }
  if (name === "merge") {
    return (
      <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
        <path d="M7 5.5a2.5 2.5 0 1 0-2.5 2.5A2.5 2.5 0 0 0 7 5.5Zm8.5 0A2.5 2.5 0 1 0 13 8a2.5 2.5 0 0 0 2.5-2.5ZM11 14.5a2.5 2.5 0 1 0 5 0 2.5 2.5 0 0 0-5 0Z" />
        <path d="M6.7 7.1 11.2 12M13 8v4" strokeLinecap="round" />
      </svg>
    )
  }
  if (name === "add") {
    return (
      <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
        <path d="M10 4v12M4 10h12" strokeLinecap="round" />
      </svg>
    )
  }
  if (name === "review") {
    return (
      <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
        <path d="M4 5.5h12M4 10h12M4 14.5h12" strokeLinecap="round" />
        <path d="M2.75 5.5h.01M2.75 10h.01M2.75 14.5h.01" strokeLinecap="round" />
      </svg>
    )
  }
  if (name === "repair") {
    return (
      <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
        <path d="m11.88 4.16 3.96 3.96M12.96 3.08l3.96 3.96-7.84 7.84-4.48.52.52-4.48 7.84-7.84Z" strokeLinejoin="round" />
      </svg>
    )
  }
  if (name === "search") {
    return (
      <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
        <circle cx="8.5" cy="8.5" r="4.75" />
        <path d="m12 12 4.25 4.25" strokeLinecap="round" />
      </svg>
    )
  }
  if (name === "compare") {
    return (
      <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
        <path d="M6 4.75h4v10.5H6zM10 7.25h4v8H10z" strokeLinejoin="round" />
      </svg>
    )
  }
  return (
    <svg className={className} viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="1.7" aria-hidden="true">
      <path d="M6.25 5.5h7.5M6.25 9.5h7.5M6.25 13.5h4.5" strokeLinecap="round" />
      <path d="m13 13 3 3m0-3-3 3" strokeLinecap="round" />
    </svg>
  )
}

export function CharacterBibleSkeleton({ isDark, atmosphere }: { isDark: boolean; atmosphere: string }) {
  const panelClass = isDark ? "border-[#202a38] bg-black/20" : "border-stone-200 bg-white/85"

  return (
    <div className={`min-h-screen ${atmosphere}`}>
      <div className="mx-auto max-w-[1500px] px-4 pb-8 pt-5 sm:px-6 lg:px-8" role="status" aria-label="Loading Character Bible" aria-busy="true">
        <span className="sr-only">Loading Character Bible</span>
        <section className={`rounded-lg border p-5 ${panelClass}`}>
          <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
            <div className="min-w-0 flex-1">
              <Skeleton className="h-4 w-36" />
              <Skeleton className="mt-4 h-9 w-64 max-w-full" />
              <Skeleton className="mt-3 h-4 w-full max-w-2xl" />
            </div>
            <div className="grid w-full grid-cols-2 gap-3 md:grid-cols-4 xl:max-w-xl">
              {Array.from({ length: 4 }).map((_, index) => (
                <Skeleton key={index} className="h-20 rounded-md" />
              ))}
            </div>
          </div>
        </section>

        <div className="mt-5 grid gap-5 lg:grid-cols-[20rem_minmax(0,1fr)_18rem]">
          <SidebarSkeleton className={panelClass} />
          <div className="space-y-5">
            <CardSkeleton className={panelClass} />
            <div className="grid gap-4 md:grid-cols-2">
              <CardSkeleton className={panelClass} />
              <CardSkeleton className={panelClass} />
            </div>
            <div className={`rounded-md border p-4 ${panelClass}`}>
              <Skeleton className="h-4 w-32" />
              <div className="mt-4 space-y-3">
                <RowSkeleton />
                <RowSkeleton />
              </div>
            </div>
          </div>
          <div className="space-y-3">
            <CardSkeleton className={panelClass} />
            <CardSkeleton className={panelClass} />
          </div>
        </div>
      </div>
    </div>
  )
}

export function StatCard({ stat, isDark }: { stat: CharacterBibleStat; isDark: boolean }) {
  return (
    <div className={`min-h-[82px] rounded-md border px-4 py-3 ${isDark ? "border-[#202a38] bg-[#0b1018]" : "border-stone-200 bg-white"}`}>
      <div className="flex items-start justify-between gap-3">
        <span className={`inline-flex h-9 w-9 items-center justify-center rounded-sm ${
          stat.tone === "violet"
            ? isDark ? "bg-violet-500/12 text-violet-200" : "bg-violet-50 text-violet-700"
            : stat.tone === "teal"
              ? isDark ? "bg-teal-500/12 text-teal-200" : "bg-teal-50 text-teal-700"
              : stat.tone === "amber"
                ? isDark ? "bg-amber-500/12 text-amber-200" : "bg-amber-50 text-amber-700"
                : stat.tone === "rose"
                  ? isDark ? "bg-rose-500/12 text-rose-200" : "bg-rose-50 text-rose-700"
                : isDark ? "bg-white/[0.05] text-slate-200" : "bg-stone-100 text-stone-700"
        }`}>
          <ShellIcon name={stat.icon} className="h-[18px] w-[18px]" />
        </span>
        {stat.detail ? <span className={`mt-1 text-xs font-semibold ${isDark ? "text-slate-400" : "text-stone-600"}`}>{stat.detail}</span> : null}
      </div>
      <div className="mt-3">
        <p className={`text-3xl font-semibold leading-none tracking-tight ${isDark ? "text-white" : "text-stone-950"}`}>{stat.value}</p>
        <p className={`mt-1 text-xs font-semibold ${isDark ? "text-slate-400" : "text-stone-600"}`}>{stat.label}</p>
      </div>
    </div>
  )
}

export function CharacterBibleHeaderStats({
  isDark,
  stats,
}: {
  isDark: boolean
  stats: CharacterBibleStat[]
}) {
  return (
    <dl className={`flex max-w-full flex-wrap items-center gap-0 border-y text-sm ${isDark ? "border-[#202a38]" : "border-stone-200"}`}>
      {stats.map((stat) => (
        <div key={stat.label} className={`flex min-w-max items-baseline gap-2 border-r px-4 py-2.5 first:pl-0 last:border-r-0 ${isDark ? "border-[#202a38]" : "border-stone-200"}`}>
          <dt className={isDark ? "text-slate-400" : "text-stone-600"}>{stat.label}</dt>
          <dd className={`font-semibold ${isDark ? "text-white" : "text-stone-950"}`}>{stat.value}
            {stat.detail && stat.detail !== "View" ? <span className={`ml-2 text-xs font-normal ${isDark ? "text-slate-400" : "text-stone-600"}`}>{stat.detail}</span> : null}
          </dd>
        </div>
      ))}
    </dl>
  )
}

export function CharacterBibleHeaderActions({
  creating,
  isAuthorMode,
  isDark,
  pageMenuActions,
  pageMenuOpen,
  workspaceMode,
  onCreateCharacter,
  onOpenReviewQueue,
  onReviewDataIntent,
  onTogglePageMenu,
}: {
  creating: boolean
  isAuthorMode: boolean
  isDark: boolean
  pageMenuActions: MenuAction[]
  pageMenuOpen: boolean
  workspaceMode: "profile" | "review" | "duplicates" | "repair"
  onCreateCharacter: () => void
  onOpenDuplicateReview: () => void
  onOpenRepairWorkspace: () => void
  onOpenReviewQueue: () => void
  onReviewDataIntent: () => void
  onTogglePageMenu: () => void
}) {
  return (
    <div className="flex flex-wrap items-center justify-start gap-2 xl:justify-end">
      {isAuthorMode ? (
        <button
          type="button"
          onClick={onCreateCharacter}
          aria-pressed={creating}
          className={`inline-flex h-10 items-center gap-2 rounded-sm border px-4 text-sm font-semibold transition-colors ${creating ? "border-teal-500 bg-teal-700 text-white" : "border-teal-700 bg-[#1f615d] text-white hover:bg-[#174c49]"}`}
        >
          <ShellIcon name="add" className="h-4 w-4" />
          Add character
        </button>
      ) : null}
      <button
        type="button"
        onClick={onOpenReviewQueue}
        aria-pressed={workspaceMode === "review"}
        onMouseEnter={onReviewDataIntent}
        onFocus={onReviewDataIntent}
        className={`inline-flex h-10 items-center gap-2 rounded-sm px-4 text-sm font-semibold transition-colors ${workspaceActionButtonClasses(isDark, { active: workspaceMode === "review", tone: "teal" })}`}
      >
        <ShellIcon name="review" className="h-4 w-4" />
        Review queue
      </button>
      <OverflowMenu isDark={isDark} open={pageMenuOpen} onToggle={onTogglePageMenu} actions={pageMenuActions} />
      <button type="button" className="min-h-10 px-2 text-sm underline underline-offset-4" onClick={() => window.dispatchEvent(new Event(SUPPORT_HELP_EVENT))}>Help</button>
    </div>
  )
}

export function SurfaceCard({
  title,
  children,
  isDark,
  className = "",
}: {
  title: string
  children: ReactNode
  isDark: boolean
  className?: string
}) {
  return (
    <section className={`border-b px-1 py-5 last:border-b-0 ${isDark ? "border-[#202a38]" : "border-stone-200"} ${className}`}>
      <h3 className={`text-sm font-semibold ${isDark ? "text-slate-200" : "text-stone-800"}`}>{title}</h3>
      <div className="mt-3">{children}</div>
    </section>
  )
}

export function OverflowMenu({
  isDark,
  open,
  onToggle,
  actions,
  label = "Open menu",
}: {
  isDark: boolean
  open: boolean
  onToggle: () => void
  actions: MenuAction[]
  label?: string
}) {
  const root = useRef<HTMLDivElement>(null)
  const trigger = useRef<HTMLButtonElement>(null)
  const id = useId()
  useEffect(() => {
    if (!open) return
    function pointer(event: PointerEvent) {
      if (!root.current?.contains(event.target as Node)) onToggle()
    }
    function key(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault()
        onToggle()
        trigger.current?.focus()
      }
    }
    document.addEventListener("pointerdown", pointer)
    document.addEventListener("keydown", key)
    return () => {
      document.removeEventListener("pointerdown", pointer)
      document.removeEventListener("keydown", key)
    }
  }, [open, onToggle])
  return (
    <div ref={root} className="relative">
      <button ref={trigger} type="button" onClick={onToggle} className={iconButtonClasses(isDark)} aria-label={label} aria-expanded={open} aria-controls={id}>
        <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
          <path d="M10 4.75a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3ZM10 11.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3ZM10 18.25a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z" />
        </svg>
      </button>

      {open ? (
        <div id={id} className={menuPanelClasses(isDark)}>
          {actions.map((action, index) => (
            <div key={`${action.label}-${index}`} className={action.dividerBefore ? `mt-1 border-t pt-1 ${isDark ? "border-[#202a38]" : "border-stone-200"}` : ""}>
              <button
                type="button"
                disabled={action.disabled}
                onClick={action.onClick}
                className={`block w-full rounded-sm px-4 py-2.5 text-left text-sm transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
                  action.danger
                    ? isDark ? "text-rose-300 hover:bg-rose-500/12" : "text-rose-700 hover:bg-rose-50"
                    : isDark ? "text-slate-200 hover:bg-white/[0.06]" : "text-stone-700 hover:bg-stone-50"
                }`}
              >
                {action.label}
              </button>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  )
}

export function QuickActionTile({
  isDark,
  title,
  description,
  onClick,
  icon,
}: {
  isDark: boolean
  title: string
  description: string
  onClick: () => void
  icon?: "search" | "relationships" | "merge" | "review" | "split" | "compare"
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-md border p-3 text-left transition ${isDark ? "border-[#202a38] bg-[#0d121a] hover:border-[#2b3747] hover:bg-[#131c29]" : "border-stone-200 bg-white hover:bg-stone-50"}`}
    >
      {icon ? (
        <span className={`mb-3 inline-flex h-9 w-9 items-center justify-center rounded-sm ${isDark ? "bg-white/[0.05] text-slate-200" : "bg-stone-100 text-stone-700"}`}>
          <ShellIcon name={icon === "relationships" ? "relationships" : icon === "merge" ? "merge" : icon === "review" ? "review" : icon === "split" ? "split" : icon === "compare" ? "compare" : "search"} className="h-4 w-4" />
        </span>
      ) : null}
      <p className={`text-sm font-semibold ${isDark ? "text-white" : "text-stone-900"}`}>{title}</p>
      <p className={`mt-1 text-xs leading-5 ${isDark ? "text-slate-400" : "text-stone-600"}`}>{description}</p>
    </button>
  )
}
