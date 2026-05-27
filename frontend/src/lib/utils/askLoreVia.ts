export function getAskLoreViaScopeLabel(mode: "author" | "reader" | undefined, currentChapter: number) {
  return mode === "author"
    ? `All processed chapters through Chapter ${currentChapter}`
    : `Up to Chapter ${currentChapter}`
}

export function getAskLoreViaDescription(mode: "author" | "reader" | undefined, currentChapter: number) {
  return mode === "author"
    ? `Ask plain-English questions about your story and get a short grounded answer with chapter citations. LoreVia uses all processed chapters through Chapter ${currentChapter}.`
    : `Ask plain-English questions about your story and get a short grounded answer with chapter citations. LoreVia only uses chapters 1-${currentChapter}, so there are no spoilers.`
}

export function getAskLoreViaHelperText(mode: "author" | "reader" | undefined, currentChapter: number) {
  return mode === "author"
    ? `Enter to ask · Shift+Enter for new line · Answers grounded through Chapter ${currentChapter}`
    : `Enter to ask · Shift+Enter for new line · Answers grounded in Chapters 1-${currentChapter}`
}

export function getAskLoreViaAnswerLabel(mode: "author" | "reader" | undefined, currentChapter: number) {
  return mode === "author"
    ? `Answer · Processed through Chapter ${currentChapter}`
    : `Answer · Chapters 1-${currentChapter}`
}
