"use client"

export function UploadWizardSteps({
  isDark,
  activeStep,
  isManagingExisting,
}: {
  isDark: boolean
  activeStep: number
  isManagingExisting: boolean
}) {
  const steps = isManagingExisting
    ? ["Choose source", "Add content", "Process", "Review"]
    : ["Choose source", "Structure", "Details", "Process", "Review"]

  return (
    <div className={`border-b px-6 py-3 ${isDark ? "border-white/10 bg-white/[0.02]" : "border-slate-200/80 bg-slate-50/70"}`}>
      <ol className="flex flex-wrap gap-2">
        {steps.map((step, index) => {
          const active = index <= activeStep
          return (
            <li
              key={step}
              className={`rounded-full border px-3 py-1.5 text-3xs font-semibold uppercase tracking-[0.18em] ${
                active
                  ? isDark ? "border-teal-300/20 bg-teal-500/10 text-teal-200" : "border-teal-200 bg-teal-50 text-teal-700"
                  : isDark ? "border-white/10 bg-white/[0.03] text-slate-500" : "border-slate-200 bg-white text-slate-500"
              }`}
            >
              {index + 1}. {step}
            </li>
          )
        })}
      </ol>
    </div>
  )
}

export function PostImportChecklist({
  isDark,
  hasReview,
  hasReports,
}: {
  isDark: boolean
  hasReview: boolean
  hasReports: boolean
}) {
  const items = [
    { label: "Review imported structure", done: hasReports },
    { label: "Scan continuity notes", done: hasReview },
    { label: "Open the manuscript editor when processing finishes", done: false },
  ]

  return (
    <div className={`mt-4 rounded-xl border p-4 ${isDark ? "border-teal-300/15 bg-teal-500/10" : "border-teal-100 bg-teal-50"}`}>
      <p className={`text-xs font-semibold uppercase tracking-[0.2em] ${isDark ? "text-teal-200" : "text-teal-700"}`}>Post-import checklist</p>
      <div className="mt-3 grid gap-2 sm:grid-cols-3">
        {items.map((item) => (
          <div key={item.label} className={`rounded-lg border px-3 py-3 text-sm ${isDark ? "border-white/10 bg-black/10 text-slate-200" : "border-white bg-white text-stone-700"}`}>
            <span className={item.done ? "font-semibold" : ""}>{item.done ? "Done: " : "Next: "}</span>
            {item.label}
          </div>
        ))}
      </div>
    </div>
  )
}

export function ReportList({
  title,
  items,
  emptyLabel,
  isDark,
}: {
  title: string
  items: string[]
  emptyLabel: string
  isDark: boolean
}) {
  return (
    <div>
      <p className={`mb-2 text-xs font-semibold uppercase tracking-[0.18em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>{title}</p>
      {items.length > 0 ? (
        <div className="space-y-2">
          {items.map((item, index) => (
            <div key={`${title}-${index}-${item}`} className={`rounded-lg border px-3 py-3 text-sm leading-6 ${isDark ? "border-white/10 bg-white/[0.03] text-slate-200" : "border-stone-200 bg-white text-stone-700"}`}>
              {item}
            </div>
          ))}
        </div>
      ) : (
        <p className={`text-sm ${isDark ? "text-slate-400" : "text-stone-500"}`}>{emptyLabel}</p>
      )}
    </div>
  )
}
