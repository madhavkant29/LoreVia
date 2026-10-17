"use client"

import { HelpCircle } from "lucide-react"
import { usePathname } from "next/navigation"
import { useEffect, useMemo, useState } from "react"

import { Button } from "@/components/ui/Button"
import { Dialog } from "@/components/ui/Dialog"
import { SUPPORT_EMAIL } from "@/lib/constants/contact"
import { supportApi } from "@/lib/api/support"
import { useAuthStore } from "@/lib/stores/authStore"
import { useUiPreferencesStore } from "@/lib/stores/uiPreferencesStore"
import { getApiErrorDetail } from "@/lib/utils/apiErrors"
import { GLOBAL_SHORTCUTS } from "@/lib/utils/shortcuts"
import type { SupportAnswer, SupportGuideSummary, SupportRecentMessage, SupportUiContext } from "@/types/support"

const COMMAND_PALETTE_EVENT = "lorevia:open-command-palette"
export const SUPPORT_HELP_EVENT = "lorevia:open-support-help"

type ProjectGuideItem = {
  label: string
  description: string
  href: string
  advanced?: boolean
}

type ProjectGuideSection = {
  title: string
  items: ProjectGuideItem[]
}

const PROJECT_GUIDE_SECTIONS: ProjectGuideSection[] = [
  {
    title: "Draft",
    items: [
      { label: "Overview", href: "", description: "See the book's progress, next steps, processing state, and recent story signals." },
      { label: "Preview Draft", href: "/chapter/1", description: "Read the manuscript in a clean reading view and continue from your current chapter." },
      { label: "Chapters", href: "/chapters", description: "Browse chapters, check their processing state, and jump directly into the draft." },
      { label: "Manuscript Editor", href: "/manuscript", description: "Write and revise the working manuscript, then save changes for analysis." },
      { label: "Scene Workspace", href: "/scenes", description: "Break the manuscript into scenes, reorder structure, and review scene-level details." },
      { label: "Notes Workspace", href: "/notes", description: "Keep private book notes, reminders, and reference details beside the draft." },
    ],
  },
  {
    title: "Story Bible",
    items: [
      { label: "Character Bible", href: "/characters", description: "Review extracted characters, edit profiles, and resolve duplicate identities." },
      { label: "Relationships", href: "/graph", description: "Explore connections, alliances, conflicts, and relationship changes." },
      { label: "Timeline", href: "/timeline", description: "Follow events, character presence, and story changes in sequence." },
      { label: "Plot Threads", href: "/plot-threads", description: "Track open, moving, drifting, and unresolved story arcs." },
      { label: "Setup & Payoff", href: "/foreshadowing", description: "Trace planted details to their intended returns and find setups needing a payoff.", advanced: true },
      { label: "World Gaps", href: "/world-gap", description: "Find missing lore, weak canon links, and worldbuilding details that need support.", advanced: true },
      { label: "Series Wiki", href: "/cross-book-wiki", description: "Compare recurring characters and lore across books in the same series.", advanced: true },
    ],
  },
  {
    title: "Analyze",
    items: [
      { label: "Story Advisor", href: "/advisor", description: "Ask story questions and review continuity risks or unresolved pressure points." },
      { label: "Findings", href: "/analysis", description: "Triage evidence from analysis and choose the review that matches your decision." },
      { label: "Editorial Review", href: "/editorial-review", description: "Review clarity, pacing, and prose-level friction in an editorial pass." },
      { label: "AI Beta Reader", href: "/ai-beta-reader", description: "Simulate reader reactions, repeated language, and character-voice comparisons." },
      { label: "Ask LoreVia", href: "/ask", description: "Ask questions grounded in the current manuscript and story context." },
      { label: "Search Passages", href: "/search", description: "Find passages, names, and story evidence across the book." },
      { label: "Voice Consistency", href: "/voice", description: "Check whether a character's voice stays consistent across scenes." },
      { label: "Chapter Reports", href: "/analysis?view=chapters", description: "Review chapter-level evidence, new characters, and thread movement." },
    ],
  },
  {
    title: "Share & Export",
    items: [
      { label: "Collaborators", href: "/collaboration", description: "Manage collaborators and their access to the book." },
      { label: "Beta Feedback", href: "/beta-feedback", description: "Review comments and assignment feedback from beta readers." },
      { label: "Files & Export", href: "/export", description: "Create manuscript, reader, reference, or backup files." },
      { label: "Access & Visibility", href: "/visibility", description: "Review who can access the book and whether public sharing is active." },
    ],
  },
]

function projectGuideHref(pathname: string | null, suffix: string) {
  const firstSegment = (pathname ?? "").split("/").filter(Boolean)[0]
  const globalRoutes = new Set(["library", "notifications", "settings", "upgrade", "support"])
  return firstSegment && !globalRoutes.has(firstSegment) ? `/${firstSegment}${suffix}` : null
}

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

export function buildSupportComposeUrl(summary: string, context: SupportUiContext) {
  const subject = `LoreVia support request: ${inferSupportCategory(summary)}`
  const body = [
    "Hello LoreVia support,",
    "",
    "I need help with the following issue:",
    summary.slice(0, 1000),
    "",
    `Route: ${context.route}`,
    context.book_id ? `Book ID: ${context.book_id}` : null,
    context.workspace_shell ? `Workspace: ${context.workspace_shell}` : null,
    "",
    "Please do not include private manuscript text, passwords, payment details, or access tokens.",
  ].filter((line): line is string => Boolean(line)).join("\n")

  return `https://mail.google.com/mail/?view=cm&fs=1&to=${encodeURIComponent(SUPPORT_EMAIL)}&su=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`
}

export function ShortcutHelp() {
  const pathname = usePathname()
  const guidance = useMemo(() => guidanceForPath(pathname), [pathname])
  const user = useAuthStore((state) => state.user)
  const [dialog, setDialog] = useState<"shortcuts" | "guidance" | "guide" | "support" | null>(null)
  const [guides, setGuides] = useState<SupportGuideSummary[]>([])
  const [supportMessage, setSupportMessage] = useState("")
  const [supportAnswer, setSupportAnswer] = useState<SupportAnswer | null>(null)
  const [supportHistory, setSupportHistory] = useState<SupportRecentMessage[]>([])
  const [supportBusy, setSupportBusy] = useState(false)
  const [supportError, setSupportError] = useState<string | null>(null)
  const dismissGuidance = useUiPreferencesStore((state) => state.dismissGuidance)
  const restartGuidance = useUiPreferencesStore((state) => state.restartGuidance)

  useEffect(() => {
    const openSupport = () => setDialog("support")
    window.addEventListener(SUPPORT_HELP_EVENT, openSupport)
    return () => window.removeEventListener(SUPPORT_HELP_EVENT, openSupport)
  }, [])

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
    void supportApi.guides()
      .then((nextGuides) => {
        if (cancelled) return
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

  const supportSummary = supportMessage.trim() || supportAnswer?.answer || guidance.body
  const supportComposeUrl = buildSupportComposeUrl(supportSummary, supportContext)

  if (pathname === "/upgrade") return null

  return (
    <>
      {!pathname?.endsWith("/manuscript") ? <div data-floating-help data-lorevia-bottom-floating className="fixed bottom-20 left-4 z-[65] md:bottom-6 lg:left-[16.5rem]">
        <button
          type="button"
          aria-label="Help"
          onClick={() => setDialog("support")}
          className="inline-flex min-h-11 items-center gap-2 rounded-sm bg-[rgb(var(--card))] px-3 text-sm font-semibold text-[rgb(var(--foreground))] shadow-[var(--shadow-dropdown)]"
        >
          <HelpCircle className="h-4 w-4" aria-hidden="true" />
          <span>Help</span>
        </button>
      </div> : null}

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
        open={dialog === "guide"}
        onClose={() => setDialog(null)}
        title="Project guide"
        description="A quick map of the pages in this project, including the advanced tools revealed from the workspace navigation."
        eyebrow="Help"
        size="lg"
        className="rounded-sm border-0"
        footer={<div className="flex justify-end"><Button variant="secondary" onClick={() => setDialog(null)}>Close</Button></div>}
      >
        <div className="mt-5 space-y-6">
          {PROJECT_GUIDE_SECTIONS.map((section) => (
            <section key={section.title} aria-labelledby={`project-guide-${section.title.toLowerCase().replaceAll(" ", "-")}`}>
              <h3 id={`project-guide-${section.title.toLowerCase().replaceAll(" ", "-")}`} className="text-sm font-semibold">{section.title}</h3>
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                {section.items.map((item) => {
                  const href = projectGuideHref(pathname, item.href)
                  return (
                    <div key={item.label} className="rounded-sm bg-[rgba(var(--foreground),0.03)] p-3">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-semibold">{item.label}</p>
                        {item.advanced ? <span className="rounded-full bg-amber-500/10 px-2 py-0.5 text-[0.65rem] font-semibold uppercase tracking-[0.12em] text-amber-700 dark:text-amber-300">Advanced</span> : null}
                      </div>
                      <p className="mt-1 text-xs leading-5 text-[rgb(var(--muted-foreground))]">{item.description}</p>
                      {href ? (
                        <a
                          href={href}
                          onClick={() => setDialog(null)}
                          className="mt-2 inline-flex text-xs font-semibold text-[rgb(var(--accent))] hover:underline"
                        >
                          Open page
                        </a>
                      ) : null}
                    </div>
                  )
                })}
              </div>
            </section>
          ))}
        </div>
      </Dialog>

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
            <Button type="button" variant="secondary" size="sm" className="border-transparent" onClick={() => setDialog("guide")}>
              Guide
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
              <a
                href={supportComposeUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex min-h-11 items-center rounded-sm border border-[rgba(var(--border),0.5)] bg-white/80 px-4 py-2.5 text-sm font-medium tracking-normal text-[rgb(var(--foreground))] transition-[background-color,border-color,color,opacity] duration-150 ease-out hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgb(var(--accent))] focus-visible:ring-offset-2 dark:bg-white/5 dark:hover:bg-white/10"
              >
                Create support case
              </a>
            </div>
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
