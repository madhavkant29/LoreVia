"use client"

import { HelpCircle } from "lucide-react"
import { usePathname } from "next/navigation"
import { useEffect, useMemo, useState } from "react"

import { Button } from "@/components/ui/Button"
import { Dialog } from "@/components/ui/Dialog"
import { DisclosureMenu } from "@/components/ui/DisclosureMenu"
import { GLOBAL_SHORTCUTS } from "@/lib/utils/shortcuts"
import { useUiPreferencesStore } from "@/lib/stores/uiPreferencesStore"

const COMMAND_PALETTE_EVENT = "lorevia:open-command-palette"

function guidanceForPath(pathname: string | null) {
  const path = pathname ?? "/"
  if (path === "/library") return { id: "library", title: "Library guidance", body: "Use project status and the next action panel to resume work. Hidden workspace links remain available from command search." }
  if (path.includes("/manuscript")) return { id: "manuscript", title: "Manuscript guidance", body: "Draft and revise here. Story analysis continues to use saved manuscript content and processing state." }
  if (path.includes("/advisor")) return { id: "advisor", title: "Advisor guidance", body: "Start with the current story question, then move findings into the manuscript or story bible when they are actionable." }
  if (path.includes("/characters")) return { id: "characters", title: "Character Bible guidance", body: "Profiles combine extracted evidence with your edits. Permission and processing limits remain separate from workspace visibility." }
  if (path.includes("/export")) return { id: "export", title: "Export guidance", body: "Review rights, visibility, and processing readiness before creating a shareable file." }
  return { id: "overview", title: "Workspace guidance", body: "Use presets to match the current task. Hidden tools remain recoverable from command search, More actions, Settings, or a direct URL." }
}

export function ShortcutHelp() {
  const pathname = usePathname()
  const guidance = useMemo(() => guidanceForPath(pathname), [pathname])
  const [dialog, setDialog] = useState<"shortcuts" | "guidance" | null>(null)
  const dismissGuidance = useUiPreferencesStore((state) => state.dismissGuidance)
  const restartGuidance = useUiPreferencesStore((state) => state.restartGuidance)

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "?" && !event.metaKey && !event.ctrlKey && !event.altKey) {
        setDialog("shortcuts")
      }
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [])

  const openCommandSearch = () => window.dispatchEvent(new CustomEvent(COMMAND_PALETTE_EVENT))

  return (
    <>
      <div className="fixed bottom-20 left-4 z-[65] md:bottom-5">
        <DisclosureMenu
          label="Help"
          side="top"
          align="start"
          items={[
            { id: "commands", label: "Command search", description: "Find visible, hidden, and locked tools.", onSelect: openCommandSearch },
            { id: "shortcuts", label: "Keyboard shortcuts", onSelect: () => setDialog("shortcuts") },
            { id: "guidance", label: "Contextual guidance", onSelect: () => setDialog("guidance") },
            { id: "restart", label: "Restart onboarding", onSelect: () => { void restartGuidance(); setDialog("guidance") } },
          ]}
          className="inline-flex min-h-11 items-center gap-2 rounded-md border border-[rgba(var(--border),0.9)] bg-[rgb(var(--card))] px-3 text-sm font-semibold text-[rgb(var(--foreground))] shadow-[var(--shadow-dropdown)]"
          trigger={
            <>
              <HelpCircle className="h-4 w-4" aria-hidden="true" />
              <span>Help</span>
            </>
          }
        />
      </div>

      <Dialog
        open={dialog === "shortcuts"}
        onClose={() => setDialog(null)}
        title="Keyboard shortcuts"
        eyebrow="Help"
        footer={<div className="flex justify-end"><Button variant="secondary" onClick={() => setDialog(null)}>Close</Button></div>}
      >
        <div className="mt-5 space-y-2">
          {GLOBAL_SHORTCUTS.map((shortcut) => (
            <div key={shortcut.id} className="flex items-center justify-between gap-4 text-sm">
              <span>{shortcut.label}</span>
              <kbd className="rounded-md border border-[rgba(var(--border),0.9)] px-2 py-1 text-xs text-[rgb(var(--muted-foreground))]">
                {shortcut.keys}
              </kbd>
            </div>
          ))}
        </div>
      </Dialog>

      <Dialog
        open={dialog === "guidance"}
        onClose={() => setDialog(null)}
        title={guidance.title}
        description={guidance.body}
        eyebrow="Contextual guidance"
        footer={
          <div className="flex flex-wrap justify-end gap-2">
            <Button
              variant="ghost"
              onClick={() => {
                void dismissGuidance(guidance.id, pathname ?? "/")
                setDialog(null)
              }}
            >
              Dismiss for this view
            </Button>
            <Button variant="secondary" onClick={() => setDialog(null)}>Close</Button>
          </div>
        }
      />
    </>
  )
}

export { COMMAND_PALETTE_EVENT }
