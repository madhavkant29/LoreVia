import type { Metadata } from "next"

import { TrustPage } from "@/components/legal/TrustPage"
import { SUPPORT_EMAIL } from "@/lib/constants/contact"
import { TRUST_EFFECTIVE_DATE } from "@/lib/constants/trust"

export const metadata: Metadata = {
  title: "Status",
  description: "See how LoreVia communicates uptime, incidents, maintenance, and service-level expectations.",
  alternates: {
    canonical: "/status",
  },
}

const sections = [
  {
    title: "Where live updates actually appear",
    paragraphs: [
      "LoreVia publishes live operational updates at the public status host rather than trying to make a static legal page do the job of an incident system. If there is an outage, degradation, or planned maintenance event, the most current source is https://status.getlorevia.com.",
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
      "When LoreVia identifies a live incident that meaningfully affects availability, core workflows, or the ability to access important features, the goal is to acknowledge the problem quickly, share what is known, and update the notice as the situation becomes clearer. Early updates may be incomplete because they are written while the issue is still being investigated.",
      "Follow-up updates should describe whether the issue is still active, whether mitigation is in progress, and when the incident has been resolved. The exact cadence depends on the severity and nature of the event.",
    ],
  },
  {
    title: "Planned maintenance and product changes",
    paragraphs: [
      "Some interruptions are deliberate. LoreVia may post maintenance windows when planned work could affect sign-in, uploads, analysis features, exports, or billing-related flows. The goal of a maintenance notice is to give users enough lead time to avoid surprise during important work sessions.",
      "Not every deployment or minor backend change requires a public maintenance notice. The status page is reserved for work that is expected to have visible impact or meaningful service risk.",
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
      "LoreVia aims for a reliable product, but this page does not create a contractual uptime guarantee, service-level agreement, or automatic credit program unless a separate written agreement says otherwise. Publicly visible status reporting is valuable because it is honest about real incidents, but it is not the same thing as an enterprise SLA.",
      "Users with deadline-sensitive work should still maintain sensible local backups and plan for the reality that no online creative tool is perfectly immune to outages or degraded behavior.",
    ],
  },
  {
    title: "If you think the service is down",
    paragraphs: [
      "Check the public status page first. If there is no incident posted and you are still seeing a serious issue, contact support with the affected account, route, and approximate time of failure. That gives us a better starting point for deciding whether the problem is account-specific or broader than one user.",
      "Support reports from multiple users sometimes become the first signal of an emerging incident, so even when the status page is clear, a precise report can still help us find a problem faster.",
    ],
  },
] as const

export default function StatusPage() {
  return (
    <TrustPage
      currentPath="/status"
      eyebrow="Status"
      title="How LoreVia communicates uptime, incidents, and maintenance."
      description="The live operational feed is published at the public status host. This page explains what belongs there, how incident reporting works, and where direct support still matters."
      effectiveDate={TRUST_EFFECTIVE_DATE}
      intro={[
        "A status page should do more than link out and disappear. It should tell users where the authoritative live feed is, what they can expect to see there, and what kinds of problems belong in private support instead.",
        "LoreVia uses a separate public status host for real-time availability updates so that service communication stays current even when the main marketing site is static.",
      ]}
      facts={[
        {
          label: "Live feed",
          value: "status.getlorevia.com",
          detail: "That public host is the authoritative place for current uptime, maintenance notices, and incident history.",
        },
        {
          label: "Best use",
          value: "Broad service-impact events",
          detail: "Status posts are for incidents or maintenance that affect more than one isolated account issue.",
        },
        {
          label: "Security issues",
          value: "Report privately first",
          detail: "Responsible disclosure should go through direct contact, not through a public status expectation.",
        },
        {
          label: "Support path",
          value: SUPPORT_EMAIL,
          detail: "Use support when the status page is clear but your account or workflow is still failing.",
        },
      ]}
      sections={[...sections]}
      contacts={[
        {
          title: "Public status host",
          description: "Check live uptime, active incidents, maintenance windows, and public incident history here.",
          ctaLabel: "Open status page",
          ctaHref: "https://status.getlorevia.com",
        },
        {
          title: "Operational support",
          description: "Use support if you suspect the service is degraded but do not yet see a posted incident.",
          ctaLabel: SUPPORT_EMAIL,
          ctaHref: `mailto:${SUPPORT_EMAIL}`,
        },
      ]}
    />
  )
}
