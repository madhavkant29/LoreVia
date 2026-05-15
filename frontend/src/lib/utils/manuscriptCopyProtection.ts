export const PRIVATE_SHARE_COPY_NOTICE = "Copy is disabled for this private manuscript share."

export function preventProtectedManuscriptCopy(
  event: { preventDefault: () => void },
  canCopyManuscript: boolean
) {
  if (canCopyManuscript) return false
  event.preventDefault()
  return true
}
