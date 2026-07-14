import { useState } from "react"

import type { ManuscriptSelectionAnchor } from "@/lib/utils/manuscriptAnnotations"
import type { ManuscriptAnnotationCategory } from "@/types/book"

export function useManuscriptNoteAnnotationState() {
  const [savingNote, setSavingNote] = useState(false)
  const [noteScope, setNoteScope] = useState<"chapter" | "book">("chapter")
  const [noteTitle, setNoteTitle] = useState("")
  const [noteBody, setNoteBody] = useState("")
  const [noteBodyText, setNoteBodyText] = useState("")
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null)
  const [editNoteTitle, setEditNoteTitle] = useState("")
  const [editNoteBody, setEditNoteBody] = useState("")
  const [editingNoteSaving, setEditingNoteSaving] = useState(false)
  const [annotationAnchor, setAnnotationAnchor] = useState<ManuscriptSelectionAnchor | null>(null)
  const [annotationDraft, setAnnotationDraft] = useState("")
  const [annotationCategory, setAnnotationCategory] = useState<ManuscriptAnnotationCategory>("general")
  const [annotationVisibility, setAnnotationVisibility] = useState<"shared" | "private">("shared")
  const [annotationActionId, setAnnotationActionId] = useState<string | null>(null)
  const [activeAnnotationId, setActiveAnnotationId] = useState<string | null>(null)

  return {
    activeAnnotationId,
    annotationActionId,
    annotationAnchor,
    annotationCategory,
    annotationDraft,
    annotationVisibility,
    editNoteBody,
    editNoteTitle,
    editingNoteId,
    editingNoteSaving,
    noteBody,
    noteBodyText,
    noteScope,
    noteTitle,
    savingNote,
    setActiveAnnotationId,
    setAnnotationActionId,
    setAnnotationAnchor,
    setAnnotationCategory,
    setAnnotationDraft,
    setAnnotationVisibility,
    setEditNoteBody,
    setEditNoteTitle,
    setEditingNoteId,
    setEditingNoteSaving,
    setNoteBody,
    setNoteBodyText,
    setNoteScope,
    setNoteTitle,
    setSavingNote,
  }
}
