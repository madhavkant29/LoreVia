import type { Dispatch, SetStateAction } from "react"

import type { ManuscriptFrontMatter, WriterWorkspace } from "@/types/book"

type UseManuscriptFrontMatterActionsOptions = {
  setWriterWorkspace: Dispatch<SetStateAction<WriterWorkspace | null>>
}

export function useManuscriptFrontMatterActions({ setWriterWorkspace }: UseManuscriptFrontMatterActionsOptions) {
  const updateFrontMatter = <K extends keyof ManuscriptFrontMatter>(key: K, value: ManuscriptFrontMatter[K]) => {
    setWriterWorkspace((current) => {
      if (!current) return current
      return {
        ...current,
        manuscript_front_matter: {
          ...current.manuscript_front_matter,
          [key]: value,
        },
      }
    })
  }

  return { updateFrontMatter }
}
