"use client"

import { CommandPalette } from "@/components/ui/CommandPalette"
import { ConfirmDialogProvider } from "@/components/ui/ConfirmDialog"
import { PromptDialogProvider } from "@/components/ui/PromptDialog"
import { ShortcutHelp } from "@/components/ui/ShortcutHelp"
import { StatusToastProvider } from "@/components/ui/StatusToast"

export function UxRuntimeProvider({ children }: { children: React.ReactNode }) {
  return (
    <ConfirmDialogProvider>
      <PromptDialogProvider>
        <StatusToastProvider>
          <CommandPalette />
          <ShortcutHelp />
          {children}
        </StatusToastProvider>
      </PromptDialogProvider>
    </ConfirmDialogProvider>
  )
}
