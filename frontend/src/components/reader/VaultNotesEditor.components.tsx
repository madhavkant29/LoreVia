import type { ReactNode } from "react"

import { parseNotesDragItem, type FolderNode } from "./VaultNotesEditor.helpers"
import { IconArrowRight, IconChevron, IconFolder, IconPlus } from "./VaultNotesEditor.icons"

export function FolderList({
  node,
  activePath,
  collapsed,
  onToggleFolder,
  onSelect,
  onCreateFolder,
  onDropNote,
  dropTargetPath,
  onDropTargetChange,
  isDark,
  depth = 0,
}: {
  node: FolderNode
  activePath: string | null
  collapsed: Record<string, boolean>
  onToggleFolder: (path: string) => void
  onSelect: (path: string) => void
  onCreateFolder: (path: string) => void
  onDropNote: (notePath: string, folderPath: string) => void
  dropTargetPath: string | null
  onDropTargetChange: (path: string | null) => void
  isDark: boolean
  depth?: number
}) {
  return (
    <div className="space-y-1">
      {[...node.folders.values()].map((child) => {
        const isCollapsed = Boolean(collapsed[child.path])
        const active = child.path === activePath
        return (
          <div key={child.path}>
            <div className="flex items-center gap-1">
              <button
                type="button"
                aria-label={`${isCollapsed ? "Expand" : "Collapse"} ${child.name}`}
                aria-expanded={!isCollapsed}
                onClick={() => onToggleFolder(child.path)}
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-sm ${isDark ? "text-slate-400 hover:bg-white/[0.05] hover:text-slate-200" : "text-stone-600 hover:bg-stone-100 hover:text-stone-700"}`}
                style={{ marginLeft: `${depth * 12}px` }}
              >
                <IconChevron open={!isCollapsed} />
              </button>
              <button
                type="button"
                onClick={() => onSelect(child.path)}
                onDragOver={(event) => {
                  if (!parseNotesDragItem(event)) return
                  event.preventDefault()
                  onDropTargetChange(child.path)
                }}
                onDragLeave={() => onDropTargetChange(null)}
                onDrop={(event) => {
                  const dragItem = parseNotesDragItem(event)
                  if (!dragItem) return
                  event.preventDefault()
                  onDropNote(dragItem.path, child.path)
                }}
                className={`flex min-w-0 flex-1 items-center justify-between rounded-sm px-3 py-2 text-left text-sm transition ${
                  active
                    ? isDark
                      ? "bg-emerald-500/12 text-emerald-100"
                      : "bg-emerald-50 text-emerald-800"
                    : isDark
                      ? "text-slate-300 hover:bg-white/[0.04]"
                      : "text-stone-700 hover:bg-stone-100"
                } ${dropTargetPath === child.path ? (isDark ? "ring-1 ring-sky-400/60" : "ring-1 ring-sky-300") : ""}`}
              >
                <span className="flex min-w-0 items-center gap-2">
                  <IconFolder />
                  <span className="break-words font-medium">{child.name}</span>
                </span>
                <span className={`text-xs ${active ? (isDark ? "text-emerald-200/80" : "text-emerald-700/80") : isDark ? "text-slate-400" : "text-stone-600"}`}>{child.itemCount}</span>
              </button>
              <button
                type="button"
                onClick={() => onCreateFolder(child.path)}
                className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-sm ${isDark ? "text-slate-400 hover:bg-white/[0.05] hover:text-white" : "text-stone-600 hover:bg-stone-100 hover:text-stone-800"}`}
                title={`Create a folder inside ${child.name}`}
              >
                <IconPlus />
              </button>
            </div>
            {!isCollapsed ? (
              <div className="mt-1">
                <FolderList
                  node={child}
                  activePath={activePath}
                  collapsed={collapsed}
                  onToggleFolder={onToggleFolder}
                  onSelect={onSelect}
                  onCreateFolder={onCreateFolder}
                  onDropNote={onDropNote}
                  dropTargetPath={dropTargetPath}
                  onDropTargetChange={onDropTargetChange}
                  isDark={isDark}
                  depth={depth + 1}
                />
              </div>
            ) : null}
          </div>
        )
      })}
    </div>
  )
}

export function PanelCard({
  title,
  count,
  action,
  isDark,
  children,
}: {
  title: string
  count?: number
  action?: ReactNode
  isDark: boolean
  children: ReactNode
}) {
  return (
    <section className={`overflow-hidden rounded-sm border p-4 ${isDark ? "border-white/[0.08] bg-[#07101d]/88" : "border-stone-200 bg-white/90"}`}>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <p className={`text-xs font-semibold uppercase tracking-wide ${isDark ? "text-slate-400" : "text-stone-600"}`}>{title}</p>
        <div className="flex items-center gap-2 shrink-0">
          {typeof count === "number" ? (
            <span className={`inline-flex h-6 min-w-6 items-center justify-center rounded-full px-2 text-xs font-semibold ${isDark ? "bg-white/[0.05] text-slate-300" : "bg-stone-100 text-stone-700"}`}>
              {count}
            </span>
          ) : null}
          {action}
        </div>
      </div>
      {children}
    </section>
  )
}

export function PanelLink({ children, isDark }: { children: ReactNode; isDark: boolean }) {
  return (
    <button
      type="button"
      className={`mt-3 inline-flex items-center gap-2 text-sm font-medium ${isDark ? "text-sky-300 hover:text-sky-200" : "text-sky-700 hover:text-sky-800"}`}
    >
      {children}
      <IconArrowRight />
    </button>
  )
}

export function InfoLine({
  label,
  value,
  isDark,
  tone,
  activeDot,
}: {
  label: string
  value: string
  isDark: boolean
  tone?: boolean
  activeDot?: boolean
}) {
  const valueClass = tone
    ? isDark
      ? "rounded-full bg-sky-500/14 px-2.5 py-1 text-sky-200"
      : "rounded-full bg-sky-50 px-2.5 py-1 text-sky-700"
    : isDark
      ? "text-slate-100"
      : "text-stone-900"

  return (
    <div className="mb-3 flex items-start justify-between gap-3 text-sm">
      <span className={isDark ? "text-slate-400" : "text-stone-600"}>{label}</span>
      <span className={`max-w-[10rem] break-words text-right ${valueClass} ${activeDot ? "inline-flex items-center gap-2" : ""}`}>
        {activeDot ? <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" /> : null}
        {value}
      </span>
    </div>
  )
}

export function RelationStack({
  items,
  emptyLabel,
  onOpen,
  isDark,
}: {
  items: { id: string; label: string; secondary?: string | null; reference: string }[]
  emptyLabel: string
  onOpen: (reference: string) => void
  isDark: boolean
}) {
  if (!items.length) {
    return <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-600"}`}>{emptyLabel}</p>
  }

  return (
    <div className="space-y-2">
      {items.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onOpen(item.reference)}
          className={`flex w-full items-center justify-between gap-3 rounded-sm px-3 py-2.5 text-left text-sm transition ${isDark ? "bg-white/[0.03] text-slate-100 hover:bg-white/[0.06]" : "bg-stone-50 text-stone-800 hover:bg-stone-100"}`}
        >
          <span className="min-w-0 break-words">{item.label}</span>
          {item.secondary ? <span className={`shrink-0 text-xs ${isDark ? "text-slate-400" : "text-stone-600"}`}>{item.secondary}</span> : null}
        </button>
      ))}
    </div>
  )
}

export function MiniGraphPreview({
  currentLabel,
  nodes,
  isDark,
}: {
  currentLabel: string
  nodes: { id: string; label: string }[]
  isDark: boolean
}) {
  const positions = [
    { left: 20, top: 23, tone: "border-teal-400/20 bg-teal-500/12 text-teal-200" },
    { left: 80, top: 23, tone: "border-violet-400/20 bg-violet-500/12 text-violet-200" },
    { left: 18, top: 76, tone: "border-sky-400/20 bg-sky-500/12 text-sky-200" },
    { left: 82, top: 77, tone: "border-amber-400/20 bg-amber-500/12 text-amber-100" },
  ] as const

  if (!nodes.length) {
    return (
      <div className={`flex min-h-[13rem] items-center justify-center rounded-sm border border-dashed text-sm ${isDark ? "border-white/[0.08] text-slate-400" : "border-stone-300 text-stone-600"}`}>
        Link a few notes to see the mini graph preview.
      </div>
    )
  }

  return (
    <div className={`relative min-h-[13rem] overflow-hidden rounded-sm border ${isDark ? "border-white/[0.08] bg-[#091321]" : "border-stone-200 bg-stone-50"}`}>
      <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
        {nodes.map((node, index) => {
          const position = positions[index]
          return (
            <line
              key={node.id}
              x1="50"
              y1="54"
              x2={String(position.left)}
              y2={String(position.top)}
              stroke={isDark ? "rgba(56,189,248,0.28)" : "rgba(59,130,246,0.24)"}
              strokeWidth="0.7"
            />
          )
        })}
      </svg>

      <div className="absolute left-1/2 top-[54%] z-10 -translate-x-1/2 -translate-y-1/2">
        <div className={`flex h-[5.3rem] w-[5.3rem] items-center justify-center rounded-full border text-center ${isDark ? "border-emerald-400/55 bg-emerald-500/18 text-white" : "border-emerald-300 bg-emerald-50 text-emerald-900"}`}>
          <span className="max-w-[4rem] text-xs font-medium leading-4">{currentLabel}</span>
        </div>
      </div>

      {nodes.map((node, index) => {
        const position = positions[index]
        return (
          <div
            key={node.id}
            className="absolute z-10"
            style={{ left: `${position.left}%`, top: `${position.top}%`, transform: "translate(-50%, -50%)" }}
          >
            <div className={`max-w-[8rem] rounded-full border px-3 py-2 text-xs font-medium leading-4 ${isDark ? position.tone : "border-stone-200 bg-white text-stone-700"}`}>
              {node.label}
            </div>
          </div>
        )
      })}
    </div>
  )
}
