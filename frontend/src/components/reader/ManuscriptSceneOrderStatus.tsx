export type SceneOrderSaveState = "idle" | "saving" | "saved" | "failed"

export function ManuscriptSceneOrderStatus({
  isDark,
  isDragging,
  state,
}: {
  isDark: boolean
  isDragging: boolean
  state: SceneOrderSaveState
}) {
  if (state === "idle" && !isDragging) return null

  return (
    <span className={`rounded-full border px-2.5 py-1 text-3xs font-semibold uppercase tracking-[0.16em] ${getSceneOrderStatusTone(state, isDark)}`}>
      {getSceneOrderStatusLabel(state, isDragging)}
    </span>
  )
}

function getSceneOrderStatusLabel(state: SceneOrderSaveState, isDragging: boolean) {
  if (state === "saving") return "Saving order..."
  if (state === "saved") return "Order saved"
  if (state === "failed") return "Could not save order"
  if (isDragging) return "Drop between scenes to place it"
  return ""
}

function getSceneOrderStatusTone(state: SceneOrderSaveState, isDark: boolean) {
  if (state === "failed") {
    return isDark ? "border-rose-400/20 bg-rose-500/10 text-rose-200" : "border-rose-200 bg-rose-50 text-rose-700"
  }
  if (state === "saved") {
    return isDark ? "border-emerald-400/20 bg-emerald-500/10 text-emerald-200" : "border-emerald-200 bg-emerald-50 text-emerald-700"
  }
  if (state === "saving") {
    return isDark ? "border-sky-400/20 bg-sky-500/10 text-sky-200" : "border-sky-200 bg-sky-50 text-sky-700"
  }
  return isDark ? "border-white/10 bg-white/[0.04] text-slate-400" : "border-stone-200 bg-stone-50 text-stone-500"
}
