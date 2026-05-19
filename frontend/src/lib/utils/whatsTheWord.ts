export const WHATS_THE_WORD_MIN_DESCRIPTION_WORDS = 5

const WORD_PATTERN = /[A-Za-z0-9']+/g

export function countWhatsTheWordDescriptionWords(value: string) {
  return value.match(WORD_PATTERN)?.length ?? 0
}

export function canSubmitWhatsTheWordDescription(value: string) {
  return countWhatsTheWordDescriptionWords(value) >= WHATS_THE_WORD_MIN_DESCRIPTION_WORDS
}
