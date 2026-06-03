export function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value))
}

export function formatNumber(value: number | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value)) return "Syncing"
  return value.toLocaleString()
}

export function formatDate(value: string | null | undefined) {
  if (!value) return "Today"
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return "Today"
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })
}

export function panelClass(isDark: boolean, extra = "") {
  return `rounded-md border ${
    isDark ? "border-white/[0.065] bg-[#0d141c]" : "border-slate-200/70 bg-white"
  } ${extra}`
}

export function severityClass(severity: string, isDark: boolean) {
  if (severity === "High") return isDark ? "bg-rose-500/10 text-rose-300" : "bg-rose-50 text-rose-600"
  if (severity === "Medium") return isDark ? "bg-amber-500/10 text-amber-300" : "bg-amber-50 text-amber-600"
  return isDark ? "bg-emerald-500/10 text-emerald-300" : "bg-emerald-50 text-emerald-600"
}

export function formatDateInputValue(date: Date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, "0")
  const day = String(date.getDate()).padStart(2, "0")
  return `${year}-${month}-${day}`
}

export function todayDateValue() {
  return formatDateInputValue(new Date())
}

export function monthValueFromDate(dateValue: string) {
  return /^\d{4}-\d{2}-\d{2}$/.test(dateValue) ? dateValue.slice(0, 7) : todayDateValue().slice(0, 7)
}

export function monthStartFromValue(monthValue: string) {
  const match = monthValue.match(/^(\d{4})-(\d{2})$/)
  const year = match ? Number(match[1]) : new Date().getFullYear()
  const monthIndex = match ? Math.max(0, Number(match[2]) - 1) : new Date().getMonth()
  return new Date(year, monthIndex, 1)
}

export function shiftMonthValue(monthValue: string, delta: number) {
  const next = monthStartFromValue(monthValue)
  next.setMonth(next.getMonth() + delta)
  return formatDateInputValue(next).slice(0, 7)
}

export function formatPlannerDate(dateValue: string) {
  const match = dateValue.match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (!match) return "Select a day"
  const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]))
  return date.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })
}

export function formatPlannerMonth(monthValue: string) {
  return monthStartFromValue(monthValue).toLocaleDateString(undefined, { month: "long", year: "numeric" })
}

export function buildCalendarDays(monthValue: string) {
  const monthStart = monthStartFromValue(monthValue)
  const gridStart = new Date(monthStart)
  gridStart.setDate(1 - monthStart.getDay())

  return Array.from({ length: 42 }, (_, index) => {
    const day = new Date(gridStart)
    day.setDate(gridStart.getDate() + index)
    return {
      value: formatDateInputValue(day),
      label: String(day.getDate()),
      inMonth: day.getMonth() === monthStart.getMonth(),
    }
  })
}

export function createCalendarItemId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID()
  return `goal-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

export function formatQuotaLabel(value: number | null | undefined, unit: string | null | undefined) {
  if (typeof value !== "number" || Number.isNaN(value) || value <= 0) return null
  const cleanUnit = (unit || "items").trim() || "items"
  return `${value.toLocaleString()} ${cleanUnit}`
}
