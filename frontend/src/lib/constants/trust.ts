import type { Route } from "next"

export const TRUST_EFFECTIVE_DATE = "May 6, 2026"

export const TRUST_RESOURCE_LINKS: Array<{
  href: Route
  label: string
  title: string
  description: string
}> = [
  {
    href: "/contact",
    label: "Contact",
    title: "Contact and support",
    description: "How to reach LoreVia for support, legal requests, billing questions, and security reports.",
  },
  {
    href: "/terms",
    label: "Terms",
    title: "Terms of service",
    description: "The rules for using LoreVia, including account, content, billing, and acceptable-use obligations.",
  },
  {
    href: "/privacy",
    label: "Privacy",
    title: "Privacy policy",
    description: "What data LoreVia handles, how manuscript content is processed, and what choices users have.",
  },
  {
    href: "/status",
    label: "Status",
    title: "Service status",
    description: "Where live uptime, incident notices, planned maintenance, and operational updates are published.",
  },
  {
    href: "/compliance",
    label: "Security",
    title: "Security and compliance",
    description: "How LoreVia approaches trust, responsible workloads, vendor handling, and shared security duties.",
  },
  {
    href: "/refund",
    label: "Refund",
    title: "Refund policy",
    description: "How subscription cancellation works, when refunds may be reviewed, and how approved refunds are processed.",
  },
  {
    href: "/eula",
    label: "EULA",
    title: "End user license agreement",
    description: "The software license covering permitted use, restrictions, ownership, updates, and termination.",
  },
]
