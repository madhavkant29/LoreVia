import {
  countMarkdownHeadings,
  countWikiLinks,
  fileCharacterCount,
  fileWordCount,
} from "./VaultNotesEditor.helpers"

export function VaultNoteMetricsFooter({
  content,
  isDark,
}: {
  content: string
  isDark: boolean
}) {
  return (
    <div className={`flex flex-wrap items-center gap-4 border-t px-4 py-3 text-sm ${isDark ? "border-white/[0.08] bg-[#09111f] text-slate-400" : "border-stone-200 bg-white text-stone-500"}`}>
      <span>{fileWordCount(content).toLocaleString()} words</span>
      <span>{fileCharacterCount(content).toLocaleString()} characters</span>
      <span>{countMarkdownHeadings(content)} headings</span>
      <span>{countWikiLinks(content)} links</span>
      <span>{Math.max(1, Math.ceil(fileWordCount(content) / 250))} min read</span>
      <span className="ml-auto">Markdown</span>
    </div>
  )
}
