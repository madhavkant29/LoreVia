type ManuscriptAnnotationHighlightStylesProps = {
  isDark: boolean
}

export function ManuscriptAnnotationHighlightStyles({
  isDark,
}: ManuscriptAnnotationHighlightStylesProps) {
  return (
    <style>{`
      ::highlight(lorevia-annotation-open) {
        background: ${isDark ? "rgba(251, 191, 36, 0.18)" : "rgba(245, 158, 11, 0.22)"};
        color: inherit;
      }
      ::highlight(lorevia-annotation-resolved) {
        background: ${isDark ? "rgba(148, 163, 184, 0.16)" : "rgba(148, 163, 184, 0.2)"};
        color: inherit;
      }
      ::highlight(lorevia-annotation-active) {
        background: ${isDark ? "rgba(45, 212, 191, 0.26)" : "rgba(20, 184, 166, 0.24)"};
        color: inherit;
      }
    `}</style>
  )
}
