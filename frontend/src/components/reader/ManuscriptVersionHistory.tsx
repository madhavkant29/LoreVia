import type { ChapterVersion, ChapterVersionDetail } from "@/types/book"

export function ManuscriptVersionHistory({
  chapterNumber,
  chapterVersionDetail,
  chapterVersionNameDraft,
  chapterVersions,
  currentText,
  isDark,
  restoringVersionId,
  onCreateSnapshot,
  onPreviewSnapshot,
  onRestoreSnapshot,
  onVersionNameChange,
}: {
  chapterNumber: number
  chapterVersionDetail: ChapterVersionDetail | null
  chapterVersionNameDraft: string
  chapterVersions: ChapterVersion[]
  currentText: string
  isDark: boolean
  restoringVersionId: string | null
  onCreateSnapshot: () => void
  onPreviewSnapshot: (versionId: string) => void
  onRestoreSnapshot: (versionId: string) => void
  onVersionNameChange: (value: string) => void
}) {
  return (
    <div className="mt-4">
      <div className="flex items-center justify-between gap-3">
        <p className={`text-3xs font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-stone-400"}`}>Version history</p>
        <button onClick={onCreateSnapshot} className={`rounded-md px-3 py-1.5 text-3xs font-semibold ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}>Save named version</button>
      </div>
      <label className="mt-2 block">
        <span className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>Name this snapshot, for example: Before rewrite of chapter {chapterNumber}.</span>
        <input
          type="text"
          value={chapterVersionNameDraft}
          onChange={(event) => onVersionNameChange(event.target.value)}
          className={`mt-2 w-full rounded-md border px-3 py-2 text-sm ${isDark ? "border-white/10 bg-black/30 text-slate-100" : "border-stone-200 bg-white text-stone-900"}`}
        />
      </label>
      <div className="mt-2 space-y-2">
        {chapterVersions.map((version) => (
          <div key={version.id} className={`rounded-sm px-3 py-3 ${isDark ? "bg-white/[0.03]" : "bg-stone-50"}`}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className={`text-sm font-medium ${isDark ? "text-white" : "text-stone-900"}`}>{version.note || "Previous draft"}</p>
                <p className={`mt-1 text-xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                  {new Date(version.created_at).toLocaleString()} {version.word_count ? `/ ${version.word_count} words` : ""}
                </p>
                <p className={`mt-1 text-3xs uppercase tracking-[0.12em] ${isDark ? "text-slate-500" : "text-stone-500"}`}>{(version.snapshot_kind || "manual").replaceAll("_", " ")}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  onClick={() => onRestoreSnapshot(version.id)}
                  disabled={restoringVersionId === version.id}
                  className={`rounded-none px-3 py-1.5 text-3xs font-semibold ${isDark ? "bg-amber-500/10 text-amber-200 disabled:opacity-50" : "bg-amber-50 text-amber-700 disabled:opacity-50"}`}
                >
                  {restoringVersionId === version.id ? "Restoring..." : "Restore"}
                </button>
                <button
                  onClick={() => onPreviewSnapshot(version.id)}
                  className={`rounded-none px-3 py-1.5 text-3xs font-semibold ${isDark ? "bg-white/10 text-slate-200" : "bg-stone-100 text-stone-700"}`}
                >
                  Compare
                </button>
              </div>
            </div>
            {chapterVersionDetail?.id === version.id ? (
              <div className="mt-3 grid gap-3">
                <p className={`text-3xs ${isDark ? "text-slate-400" : "text-stone-500"}`}>
                  {chapterVersionDetail.text === currentText ? "Matches the current draft." : "Compared with the current draft below."}
                </p>
                <div className="grid gap-3 xl:grid-cols-2">
                  <VersionTextPanel isDark={isDark} label="Saved version" text={chapterVersionDetail.text || "No text stored in this snapshot."} />
                  <VersionTextPanel isDark={isDark} label="Current draft" text={currentText || "No draft text yet."} />
                </div>
              </div>
            ) : null}
          </div>
        ))}
        {chapterVersions.length === 0 ? <p className={`text-xs ${isDark ? "text-slate-500" : "text-stone-500"}`}>No snapshots saved for this chapter yet.</p> : null}
      </div>
    </div>
  )
}

function VersionTextPanel({ isDark, label, text }: { isDark: boolean; label: string; text: string }) {
  return (
    <details open className={`rounded-sm border px-3 py-2 ${isDark ? "border-white/10 bg-black/30" : "border-stone-200 bg-white"}`}>
      <summary className={`cursor-pointer text-3xs font-semibold uppercase tracking-[0.16em] ${isDark ? "text-slate-400" : "text-stone-500"}`}>{label}</summary>
      <div className={`mt-2 max-h-44 overflow-y-auto whitespace-pre-wrap text-xs leading-5 ${isDark ? "text-slate-300" : "text-stone-700"}`}>{text}</div>
    </details>
  )
}
