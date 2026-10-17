"use client"

import { createContext, useContext, useEffect, useState, type ReactNode } from "react"
import {
  BarChart3,
  BookOpen,
  Bookmark,
  CheckCircle2,
  Globe2,
  LogOut,
  Mail,
  Moon,
  Paintbrush,
  ShieldAlert,
  ShieldCheck,
  SlidersHorizontal,
  Sun,
  Target,
  UserRound,
  Users,
  Zap,
  type LucideIcon,
} from "lucide-react"
import type { ComplexityMode } from "@/types/uiPreferences"

export const SettingsSearchContext = createContext<Set<string> | null>(null)

export const MODES = [
  { value: "casual", label: "Casual", desc: "Quick summaries and light guidance." },
  { value: "analyst", label: "Analyst", desc: "Deeper context and richer breakdowns." },
  { value: "speed", label: "Speed", desc: "Minimal output for fast sessions." },
]

export const SETTINGS_NAV = [
  { id: "account", label: "Account", icon: <IdentityIcon /> },
  { id: "identity", label: "Public identity", icon: <IdentityIcon /> },
  { id: "appearance", label: "Appearance", icon: <AppearanceIcon /> },
  { id: "workspace", label: "Workspace visibility", icon: <SettingsSlidersIcon /> },
  { id: "reading", label: "Reading behavior", icon: <ReadingIcon /> },
  { id: "privacy", label: "Privacy", icon: <PrivacyIcon /> },
  { id: "emails", label: "Emails", icon: <MailIcon /> },
  { id: "goals", label: "Writing goals", icon: <GoalIcon /> },
  { id: "session", label: "Session", icon: <SignOutIcon /> },
  { id: "danger", label: "Danger Zone", icon: <ShieldIcon /> },
]

export const COMPLEXITY_OPTIONS: Array<{ value: ComplexityMode; label: string; desc: string; icon: ReactNode }> = [
  { value: "focused", label: "Focused", desc: "Keep the workspace centered on frequent drafting and review actions.", icon: <BoltIcon /> },
  { value: "standard", label: "Standard", desc: "Use the familiar full workspace layout for regular author work.", icon: <BarsIcon /> },
  { value: "power", label: "Power", desc: "Expose all eligible advanced tools across the workspace.", icon: <SettingsSlidersIcon /> },
]

export const SETTINGS_SEARCH_TERMS: Record<string, string> = {
  account: "account billing plan subscription payment invoices cancel",
  identity: "identity username public profile author pen name",
  appearance: "appearance theme light dark workspace",
  workspace: "workspace visibility hidden tools focused standard power layout",
  reading: "reading writing behavior mode casual analyst speed",
  privacy: "privacy data analytics direct messages permissions",
  emails: "notifications email product updates marketing security billing",
  goals: "writing goals daily words progress streak",
  session: "security session sign out logout device",
  danger: "privacy data export delete account security",
}

export function modeLabel(mode: string) {
  return MODES.find((item) => item.value === mode)?.label ?? "Casual"
}

export function useActiveSettingsSection(query = "", hydrated = true) {
  const [activeSectionId, setActiveSectionId] = useState(SETTINGS_NAV[0].id)

  useEffect(() => {
    let frameId: number | null = null

    const updateActiveSection = () => {
      const anchorY = Math.min(window.innerHeight * 0.22, 160)
      const activationY = Math.min(window.innerHeight * 0.16, 112)
      const sections = SETTINGS_NAV
        .map((item) => {
          const element = document.getElementById(item.id)
          return element ? { id: element.id, rect: element.getBoundingClientRect() } : null
        })
        .filter((section): section is { id: string; rect: DOMRect } => Boolean(section))

      if (!sections.length) return

      const visibleSections = sections.filter((section) => section.rect.bottom > 0 && section.rect.top < window.innerHeight)
      const candidates = visibleSections.length ? visibleSections : sections
      const activeAtHeader = candidates.filter((section) => section.rect.top <= activationY && section.rect.bottom > activationY)
      const activeSection = activeAtHeader.at(-1)
        ?? [...candidates].sort(
          (first, second) => Math.abs(first.rect.top - anchorY) - Math.abs(second.rect.top - anchorY),
        )[0]

      setActiveSectionId(activeSection.id)
    }

    const scheduleUpdate = () => {
      if (frameId !== null) return
      frameId = window.requestAnimationFrame(() => {
        frameId = null
        updateActiveSection()
      })
    }

    updateActiveSection()
    window.addEventListener("scroll", scheduleUpdate, { passive: true })
    window.addEventListener("resize", scheduleUpdate)
    window.addEventListener("scrollend", scheduleUpdate)
    document.addEventListener("scroll", scheduleUpdate, { capture: true, passive: true })
    const sectionObserver =
      typeof window.IntersectionObserver === "function"
        ? new IntersectionObserver(scheduleUpdate, {
            root: null,
            rootMargin: "-25% 0px -55% 0px",
            threshold: [0, 0.25, 0.5, 0.75, 1],
          })
        : null
    const resizeObserver =
      typeof window.ResizeObserver === "function" ? new ResizeObserver(scheduleUpdate) : null
    const observedSections = SETTINGS_NAV
      .map((item) => document.getElementById(item.id))
      .filter((element): element is HTMLElement => Boolean(element))
    observedSections.forEach((section) => {
      sectionObserver?.observe(section)
      resizeObserver?.observe(section)
    })
    resizeObserver?.observe(document.body)

    return () => {
      if (frameId !== null) {
        window.cancelAnimationFrame(frameId)
      }
      window.removeEventListener("scroll", scheduleUpdate)
      window.removeEventListener("resize", scheduleUpdate)
      window.removeEventListener("scrollend", scheduleUpdate)
      document.removeEventListener("scroll", scheduleUpdate, { capture: true })
      sectionObserver?.disconnect()
      resizeObserver?.disconnect()
    }
  }, [query, hydrated])

  return { activeSectionId, setActiveSectionId }
}

export function SettingsPanel({ id, title, compact = false, children }: { id: string; title: string; compact?: boolean; children: ReactNode }) {
  const visibleSectionIds = useContext(SettingsSearchContext)
  if (visibleSectionIds && !visibleSectionIds.has(id)) return null
  return (
    <section id={id} aria-labelledby={`${id}-title`} className={compact ? "settings-panel settings-panel--compact" : "settings-panel"}>
      <h2 id={`${id}-title`} className="settings-panel__title">{title}</h2>
      <div className={compact ? "mt-3" : "mt-5"}>{children}</div>
    </section>
  )
}

export function SummaryCard({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return (
    <div className="settings-panel settings-panel--compact">
      <div className="flex items-center gap-3">
        <span className="settings-choice__icon">{icon}</span>
        <div>
          <p className="settings-label">{label}</p>
          <p className="settings-info-value">{value}</p>
        </div>
      </div>
    </div>
  )
}

export function InfoItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="settings-label">{label}</p>
      <p className="settings-info-value">{value}</p>
    </div>
  )
}

export function SelectableCard({
  active,
  title,
  description,
  icon,
  disabled = false,
  onClick,
}: {
  active: boolean
  title: string
  description: string
  icon: ReactNode
  disabled?: boolean
  onClick: () => void
}) {
  return (
    <button type="button" aria-pressed={active} onClick={onClick} disabled={disabled} className={active ? "settings-choice settings-choice--active" : "settings-choice"}>
      <span className="settings-choice__row">
        <span className="settings-choice__content">
          <span className="settings-choice__icon">{icon}</span>
          <span>
            <span className="settings-choice__title">{title}</span>
            <span className="settings-choice__description">{description}</span>
          </span>
        </span>
        <span className="settings-radio">{active ? <span className="settings-radio__dot" /> : null}</span>
      </span>
    </button>
  )
}

export function InlineMessage({ message, tone, className = "" }: { message: string; tone: "warning" | "neutral"; className?: string }) {
  return <div role={tone === "warning" ? "alert" : "status"} className={`settings-message ${tone === "warning" ? "settings-message--warning" : ""} ${className}`.trim()}>{message}</div>
}

export function GoalRing({ progress }: { progress: number }) {
  const circumference = 2 * Math.PI * 34
  const dashOffset = circumference - (progress / 100) * circumference

  return (
    <div className="relative mt-3 flex h-28 w-28 items-center justify-center">
      <svg className="h-28 w-28 -rotate-90" viewBox="0 0 84 84" aria-hidden="true">
        <circle cx="42" cy="42" r="34" fill="none" stroke="rgba(148, 163, 184, 0.22)" strokeWidth="8" />
        <circle
          cx="42"
          cy="42"
          r="34"
          fill="none"
          stroke="#54dfc8"
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={dashOffset}
        />
      </svg>
      <div className="absolute text-center">
        <p className="settings-ring-number">{progress}%</p>
        <p className="text-xs text-slate-400">of goal</p>
      </div>
    </div>
  )
}


function SettingsIcon({ icon: Icon }: { icon: LucideIcon }) {
  return <Icon className="h-5 w-5" aria-hidden="true" />
}

export function PlanIcon() { return <SettingsIcon icon={Bookmark} /> }
export function ReadingIcon() { return <SettingsIcon icon={BookOpen} /> }
export function ThemeIcon({ dark }: { dark: boolean }) { return <SettingsIcon icon={dark ? Moon : Sun} /> }
export function SunIcon() { return <SettingsIcon icon={Sun} /> }
export function MoonIcon() { return <SettingsIcon icon={Moon} /> }
export function IdentityIcon() { return <SettingsIcon icon={UserRound} /> }
export function AppearanceIcon() { return <SettingsIcon icon={Paintbrush} /> }
export function SettingsSlidersIcon() { return <SettingsIcon icon={SlidersHorizontal} /> }
export function PrivacyIcon() { return <SettingsIcon icon={ShieldCheck} /> }
export function MailIcon() { return <SettingsIcon icon={Mail} /> }
export function GoalIcon() { return <SettingsIcon icon={Target} /> }
export function SignOutIcon() { return <SettingsIcon icon={LogOut} /> }
export function BarsIcon() { return <SettingsIcon icon={BarChart3} /> }
export function BoltIcon() { return <SettingsIcon icon={Zap} /> }
export function GlobeIcon() { return <SettingsIcon icon={Globe2} /> }
export function FriendsIcon() { return <SettingsIcon icon={Users} /> }
export function ShieldIcon() { return <SettingsIcon icon={ShieldAlert} /> }
export function CheckCircleIcon() { return <SettingsIcon icon={CheckCircle2} /> }
