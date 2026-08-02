import type { Dispatch, SetStateAction } from "react"

import type { Character } from "@/types/character"

type SelectionMenu = { text: string; top: number; left: number } | null

type UseManuscriptPageActionsArgs = {
  selectionMenu: SelectionMenu
  setAddCharacterOpen: Dispatch<SetStateAction<boolean>>
  setAddCharacterText: Dispatch<SetStateAction<string>>
  setCharacters: Dispatch<SetStateAction<Character[]>>
  setSelectionMenu: Dispatch<SetStateAction<SelectionMenu>>
  setStatusMessage: Dispatch<SetStateAction<string | null>>
}

export function useManuscriptPageActions({
  selectionMenu,
  setAddCharacterOpen,
  setAddCharacterText,
  setCharacters,
  setSelectionMenu,
  setStatusMessage,
}: UseManuscriptPageActionsArgs) {
  function openAddCharacterFromSelection() {
    if (!selectionMenu?.text) {
      setStatusMessage("Select a character name in the manuscript first.")
      return
    }
    setAddCharacterText(selectionMenu.text)
    setAddCharacterOpen(true)
    setSelectionMenu(null)
  }

  function handleCharacterCreated(character: Character) {
    setCharacters((current) => [...current, character])
    setStatusMessage(`Character "${character.name}" added to the story bible.`)
  }

  function printManuscript() {
    window.print()
  }

  return {
    handleCharacterCreated,
    openAddCharacterFromSelection,
    printManuscript,
  }
}
