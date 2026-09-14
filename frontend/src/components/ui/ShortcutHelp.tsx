"use client"

import { HelpCircle } from "lucide-react"
import { usePathname } from "next/navigation"
import { useEffect, useMemo, useState } from "react"

import { Button } from "@/components/ui/Button"
import { Dialog } from "@/components/ui/Dialog"
import { supportApi } from "@/lib/api/support"
import { useAuthStore } from "@/lib/stores/authStore"
import { useUiPreferencesStore } from "@/lib/stores/uiPreferencesStore"
import { getApiErrorDetail } from "@/lib/utils/apiErrors"
import { GLOBAL_SHORTCUTS } from "@/lib/utils/shortcuts"
import type { SupportAnswer, SupportConfig, SupportGuideSummary, SupportRecentMessage, SupportUiContext } from "@/types/support"

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

function deviceClass(): SupportUiContext["device_class"] {
  if (typeof window === "undefined") return "unknown"
  if (window.innerWidth < 640) return "mobile"
  if (window.innerWidth < 1024) return "tablet"
  return "desktop"
}

function inferSupportCategory(message: string): "navigation" | "chapter_save" | "upload" | "processing" | "billing" | "permissions" | "account" | "other" {
  const text = message.toLowerCase()
  if (text.includes("save") || text.includes("chapter")) return "chapter_save"
  if (text.includes("upload") || text.includes("import")) return "upload"
  if (text.includes("process") || text.includes("reprocess")) return "processing"
  if (text.includes("bill") || text.includes("plan") || text.includes("subscription")) return "billing"
  if (text.includes("permission") || text.includes("collaborator") || text.includes("access")) return "permissions"
  if (text.includes("login") || text.includes("account") || text.includes("email")) return "account"
  if (text.includes("where") || text.includes("find") || text.includes("navigate") || text.includes("home")) return "navigation"
  return "other"
}

export function ShortcutHelp() {
  const pathname = usePathname()
  const guidance = useMemo(() => guidanceForPath(pathname), [pathname])
  const user = useAuthStore((state) => state.user)
  const [dialog, setDialog] = useState<"shortcuts" | "guidance" | "support" | null>(null)
  const [supportConfig, setSupportConfig] = useState<SupportConfig | null>(null)
  const [guides, setGuides] = useState<SupportGuideSummary[]>([])
  const [supportMessage, setSupportMessage] = useState("")
  const [supportAnswer, setSupportAnswer] = useState<SupportAnswer | null>(null)
  const [supportHistory, setSupportHistory] = useState<SupportRecentMessage[]>([])
  const [supportBusy, setSupportBusy] = useState(false)
  const [supportCaseRef, setSupportCaseRef] = useState<string | null>(null)
  const [supportError, setSupportError] = useState<string | null>(null)
  const dismissGuidance = useUiPreferencesStore((state) => state.dismissGuidance)
  const restartGuidance = useUiPreferencesStore((state) => state.restartGuidance)

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target
      const isEditing = target instanceof HTMLElement
        && (target.isContentEditable || target.matches("input, textarea, select"))
      if (isEditing) return
      if (event.key === "?" && !event.metaKey && !event.ctrlKey && !event.altKey) {
        setDialog("shortcuts")
      }
    }
    window.addEventListener("keydown", onKeyDown)
    return () => window.removeEventListener("keydown", onKeyDown)
  }, [])

  const openCommandSearch = () => window.dispatchEvent(new CustomEvent(COMMAND_PALETTE_EVENT))
  const supportContext = useMemo<SupportUiContext>(() => {
    const path = pathname ?? "/"
    const bookMatch = path.match(/^\/([0-9a-f-]{36})/i)
    const bookId = bookMatch ? bookMatch[1] : null
    const workspaceShell = path.includes("/manuscript") || path.includes("/characters") || path.includes("/advisor") || path.includes("/export") || path.includes("/reports") || path.includes("/analysis") || path.includes("/ask")
      ? "author"
      : path.includes("/chapter/") || path.includes("/notes") || path.includes("/quotes")
        ? "reader"
        : null
    return {
      route: path,
      book_id: bookId,
      workspace_shell: workspaceShell,
      account_tier: user?.tier ?? null,
      device_class: deviceClass(),
    }
  }, [pathname, user?.tier])

  useEffect(() => {
    if (dialog !== "support") return
    let cancelled = false
    setSupportError(null)
    void Promise.all([supportApi.config(), supportApi.guides()])
      .then(([config, nextGuides]) => {
        if (cancelled) return
        setSupportConfig(config)
        setGuides(nextGuides)
      })
      .catch(() => {
        if (!cancelled) setSupportError("Support guides could not load. You can still describe the issue and create a support case.")
      })
    return () => {
      cancelled = true
    }
  }, [dialog])

  const askSupport = async () => {
    const message = supportMessage.trim()
    if (!message || supportBusy) return
    setSupportBusy(true)
    setSupportError(null)
    setSupportCaseRef(null)
    setSupportAnswer(null)
    try {
      const answer = await supportApi.ask(message, supportContext, supportHistory)
      setSupportAnswer(answer)
      setSupportHistory((current) => {
        const nextMessages: SupportRecentMessage[] = [
          ...current,
          { role: "user", content: message },
          { role: "assistant", content: answer.answer },
        ]
        return nextMessages.slice(-10)
      })
    } catch (error) {
      setSupportError(getApiErrorDetail(error) ?? "Support assistant could not answer right now. Create a support case and include what you were trying to do.")
    } finally {
      setSupportBusy(false)
    }
  }

  const createSupportCase = async () => {
    const summary = supportMessage.trim() || supportAnswer?.answer || guidance.body
    setSupportBusy(true)
    setSupportError(null)
    try {
      const incident = await supportApi.createIncident({
        category: inferSupportCategory(summary),
        feature: guidance.id,
        summary: summary.slice(0, 1000),
        context: supportContext,
      })
      setSupportCaseRef(incident.reference)
    } catch {
      setSupportError("Support case could not be created. Please try again or email support with the screen and error you see.")
    } finally {
      setSupportBusy(false)
    }
  }

  return (
    <>
      <div data-lorevia-bottom-floating className="fixed bottom-20 left-4 z-[65] md:bottom-6 lg:left-[16.5rem]">
        <button
          type="button"
          aria-label="Help"
          onClick={() => setDialog("support")}
          className="inline-flex min-h-11 items-center gap-2 rounded-sm bg-[rgb(var(--card))] px-3 text-sm font-semibold text-[rgb(var(--foreground))] shadow-[var(--shadow-dropdown)]"
        >
          <HelpCircle className="h-4 w-4" aria-hidden="true" />
          <span>Help</span>
        </button>
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
              <kbd className="rounded-sm bg-[rgba(var(--foreground),0.06)] px-2 py-1 text-xs text-[rgb(var(--muted-foreground))]">
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

      <Dialog
        open={dialog === "support"}
        onClose={() => setDialog(null)}
        title="LoreVia Support"
        description="Ask how to use the app, troubleshoot upload or save problems, or find the right workspace. Do not paste private manuscript text here."
        eyebrow="Help center"
        size="lg"
        className="rounded-sm border-0"
        footer={<div className="flex justify-end"><Button variant="secondary" className="border-transparent" onClick={() => setDialog(null)}>Close</Button></div>}
      >
        <div className="mt-5 space-y-5">
          <div className="flex flex-wrap gap-2" aria-label="Help tools">
            <Button type="button" variant="secondary" size="sm" className="border-transparent" onClick={() => { setDialog(null); openCommandSearch() }}>
              Command search
            </Button>
            <Button type="button" variant="secondary" size="sm" className="border-transparent" onClick={() => setDialog("shortcuts")}>
              Keyboard shortcuts
            </Button>
            <Button type="button" variant="secondary" size="sm" className="border-transparent" onClick={() => setDialog("guidance")}>
              Contextual guidance
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => { void restartGuidance(); setDialog("guidance") }}>
              Restart onboarding
            </Button>
          </div>
          {supportError ? (
            <p className="rounded-sm bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:bg-amber-400/10 dark:text-amber-100">
              {supportError}
            </p>
          ) : null}
          <div>
            <label htmlFor="lorevia-support-question" className="text-sm font-semibold">What do you need help with?</label>
            <textarea
              id="lorevia-support-question"
              value={supportMessage}
              onChange={(event) => setSupportMessage(event.target.value)}
              rows={4}
              maxLength={2000}
              placeholder="Example: I pasted chapter 4 and Save did not work. What should I check?"
              className="mt-2 w-full rounded-sm border-0 bg-[rgb(var(--background))] px-3 py-2 text-sm shadow-inner outline-none focus:ring-2 focus:ring-[rgb(var(--accent))]"
            />
            <div className="mt-3 flex flex-wrap gap-2">
              <Button type="button" onClick={() => void askSupport()} busy={supportBusy} busyLabel="Checking guides..." disabled={!supportMessage.trim()}>
                Ask support assistant
              </Button>
              <Button type="button" variant="secondary" className="border-transparent" onClick={() => void createSupportCase()} busy={supportBusy} busyLabel="Creating case...">
                Create support case
              </Button>
              {supportConfig?.community_url ? (
                <a
                  href={supportConfig.community_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex min-h-11 items-center rounded-sm bg-white/80 px-4 py-2.5 text-sm font-medium text-[rgb(var(--foreground))] hover:bg-white dark:bg-white/5 dark:hover:bg-white/10"
                >
                  Join Discord
                </a>
              ) : null}
            </div>
            {supportCaseRef ? <p className="mt-2 text-sm text-[rgb(var(--muted-foreground))]">Support case created: {supportCaseRef}</p> : null}
          </div>

          {supportAnswer ? (
            <div className="rounded-sm bg-[rgba(var(--foreground),0.03)] p-4">
              <p className="text-sm leading-7 whitespace-pre-line">{supportAnswer.answer}</p>
              {supportAnswer.sources.length > 0 ? (
                <div className="mt-4">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[rgb(var(--muted-foreground))]">Sources</p>
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-[rgb(var(--muted-foreground))]">
                    {supportAnswer.sources.map((source) => <li key={source.slug}>{source.title}</li>)}
                  </ul>
                </div>
              ) : null}
              {supportAnswer.actions.length > 0 ? (
                <div className="mt-4 flex flex-wrap gap-2">
                  {supportAnswer.actions.map((action) => (
                    <a key={`${action.label}:${action.href}`} href={action.href} target={action.external ? "_blank" : undefined} rel={action.external ? "noreferrer" : undefined} className="text-sm font-semibold text-[rgb(var(--accent))] hover:underline">
                      {action.label}
                    </a>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}

          {guides.length > 0 ? (
            <div>
              <p className="text-sm font-semibold">Common guides</p>
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                {guides.slice(0, 6).map((guide) => (
                  <button
                    type="button"
                    key={guide.slug}
                    onClick={() => setSupportMessage(guide.title)}
                    className="rounded-sm p-3 text-left text-sm hover:bg-[rgba(var(--foreground),0.04)]"
                  >
                    <span className="font-medium">{guide.title}</span>
                    <span className="mt-1 block text-xs leading-5 text-[rgb(var(--muted-foreground))]">{guide.summary}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : null}
        </div>
      </Dialog>
    </>
  )
}

export { COMMAND_PALETTE_EVENT }
