import type { Metadata } from "next"

import { LegalContactBlock, LegalPageShell, LegalRightRail } from "@/components/legal/LegalPageShell"
import { LEGAL_EMAIL, SUPPORT_EMAIL } from "@/lib/constants/contact"
import { TRUST_EFFECTIVE_DATE } from "@/lib/constants/trust"

export const metadata: Metadata = {
  title: "Status",
  description: "See how LoreVia for authors communicates uptime, incidents, maintenance, and service-level expectations.",
  alternates: {
    canonical: "/status",
  },
}

const sections = [
  {
    title: "Where live updates actually appear",
    paragraphs: [
      "LoreVia publishes operational updates on this status page rather than trying to scatter service communication across support threads or unrelated product screens. If there is an outage, degradation, or planned maintenance event, this page is where users should look first.",
      "This page explains how that status channel should be interpreted. It is the reference page for what sorts of updates you can expect, what belongs on the public status feed, and what should still go through direct support instead.",
    ],
  },
  {
    title: "What the status page is for",
    paragraphs: [
      "The public status page is where LoreVia communicates active incidents, planned maintenance, and notable service disruptions that affect broader product availability. It is meant for operational visibility, not for private support conversations or case-by-case account debugging.",
      "If one user's workspace is behaving strangely while the rest of the service appears healthy, that may be better handled through support than through a public incident notice. The status page is most useful when the event is broader than a single account and should be visible to everyone affected.",
    ],
  },
  {
    title: "How incidents are likely to be communicated",
    paragraphs: [
      "When LoreVia identifies a live incident that meaningfully affects availability, core workflows, or the ability to access important features, the goal is to acknowledge the problem quickly, share what is known, and update the notice as the situation becomes clearer.",
      "Early updates may be incomplete because they are written while the issue is still being investigated. Follow-up updates should describe whether the issue is still active, whether mitigation is in progress, and when the incident has been resolved.",
    ],
  },
  {
    title: "Planned maintenance and product changes",
    paragraphs: [
      "Some interruptions are deliberate. LoreVia may post maintenance windows when planned work could affect sign-in, uploads, analysis features, exports, or billing-related flows.",
      "The goal of a maintenance notice is to give users enough lead time to avoid surprise during important work sessions. Not every deployment or minor backend change requires a public maintenance notice.",
    ],
  },
  {
    title: "Security incidents versus operational incidents",
    paragraphs: [
      "Not every security issue will appear as a fully detailed public incident post while it is still active. Some issues need private containment first. LoreVia may limit public detail during an active security investigation to avoid expanding the blast radius or giving would-be attackers a roadmap before a fix is in place.",
      "If you discover a possible security issue, use direct email instead of waiting for the status page to confirm it. The status page is a communication surface, not the intake channel for responsible disclosure.",
    ],
  },
  {
    title: "Service-level expectations",
    paragraphs: [
      "LoreVia aims for a reliable product, but this page does not create a contractual uptime guarantee, service-level agreement, or automatic credit program unless a separate written agreement says otherwise.",
      "Publicly visible status reporting is valuable because it is honest about real incidents, but it is not the same thing as an enterprise SLA. Users with deadline-sensitive work should still maintain sensible local backups.",
    ],
  },
  {
    title: "If you think the service is down",
    paragraphs: [
      "Check the public status page first. If there is no incident posted and you are still seeing a serious issue, contact support with the affected account, route, and approximate time of failure.",
      "That gives us a better starting point for deciding whether the problem is account-specific or broader than one user. Support reports from multiple users sometimes become the first signal of an emerging incident.",
    ],
  },
  {
    title: "How to contact LoreVia",
    paragraphs: [
      "Use our support channel for issues that are not already covered on the public status feed, including account, content, billing, and workflow problems that persist even though the status page shows no incident.",
      "Use our legal channel for questions about policies, refund terms, data handling, or other compliance topics. Security reports should go through private contact rather than public discussion.",
    ],
  },
] as const

export default function StatusPage() {
  return (
    <LegalPageShell
      eyebrow="Status"
      title="How LoreVia communicates uptime, incidents, and maintenance"
      description="This page explains how LoreVia communicates uptime, incidents, and maintenance, and where direct support still matters."
      effectiveDate={TRUST_EFFECTIVE_DATE}
      notice="The status page is the authoritative live feed for uptime, maintenance notices, and incident history."
      sections={sections}
      rightRail={
        <LegalRightRail
          items={[
            {
              label: "Live feed",
              value: "LoreVia status page",
              href: "/status",
              detail: "The public page for current uptime notes, maintenance notices, and incident history.",
            },
            {
              label: "Best use",
              value: "Broad service-impact events",
              detail: "Status posts are for incidents or maintenance that affect more than one isolated account or feature.",
            },
            {
              label: "Support path",
              value: SUPPORT_EMAIL,
              href: `mailto:${SUPPORT_EMAIL}`,
              detail: "Use support when the status page is clear but your account or workflow is still failing.",
            },
          ]}
        />
      }
      contactBlock={
        <LegalContactBlock
          title="Need help?"
          description="If you have questions about uptime, incidents, security reports, or your account, contact us directly."
          supportEmail={SUPPORT_EMAIL}
          legalEmail={LEGAL_EMAIL}
        />
      }
    />
  )
}
