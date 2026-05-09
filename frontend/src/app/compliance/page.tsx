import type { Metadata } from "next"

import { LegalContactBlock, LegalPageShell, LegalRightRail } from "@/components/legal/LegalPageShell"
import { LEGAL_EMAIL, SUPPORT_EMAIL } from "@/lib/constants/contact"

export const metadata: Metadata = {
  title: "Security & Compliance",
  description: "Read LoreVia's practical security posture, data-handling boundaries, vendor roles, and workload fit.",
  alternates: {
    canonical: "/compliance",
  },
}

const effectiveDate = "May 8, 2026"

const sections = [
  {
    title: "What this page is for",
    body:
      "This page is for teams and individuals evaluating whether LoreVia is appropriate for their manuscript workflows. It provides a clear overview of the product's practical security posture, data handling approach, and the boundaries of the service so you can make an informed decision.",
  },
  {
    title: "Security design priorities",
    body:
      "LoreVia prioritizes authenticated accounts, strong session handling, scoped access controls, and clear boundaries around uploads, processing, and billing. We use proven third-party services for core functions so we can focus on manuscript intelligence. Billing is handled through a third-party provider rather than storing raw payment card data in the main application.",
  },
  {
    title: "How manuscript data moves through the product",
    body:
      "When you upload text into LoreVia, your manuscript may be stored, processed, and analyzed to provide continuity tools, summaries, and other product features. Content moves through standard application workflows, secure storage, and model-assisted processing where applicable to deliver insights, notes, and outputs you request.",
  },
  {
    title: "Current vendor roles in the stack",
    body:
      "LoreVia uses third-party providers for authentication, storage, payments, and infrastructure. Each provider handles a specific part of the workflow, such as secure sign-in, data storage, processing capacity, or billing. Paddle is used to manage payments so we do not store raw payment card data.",
  },
  {
    title: "What LoreVia is appropriate for",
    body:
      "LoreVia is intended for creative and editorial workflows including draft review, continuity checking, note-taking, and manuscript intelligence. It is not designed for highly regulated, classified, or unusually sensitive workloads unless those use cases are reviewed and approved separately.",
  },
  {
    title: "Shared responsibility still applies",
    body:
      "You remain responsible for what you upload, how you secure your account, and how you classify or handle sensitive content inside your organization. We provide the platform and operational safeguards; you apply your own internal policies, approvals, and risk decisions.",
  },
  {
    title: "Reporting incidents and security concerns",
    body:
      "If you believe you have found a security issue, exposed data, account compromise, or policy mismatch, contact LoreVia directly using the addresses below. Operational incidents are communicated through our public status page so you can investigate without turning an active issue into a wider risk event.",
  },
  {
    title: "Procurement and trust questions",
    body:
      "Teams can contact LoreVia with concrete trust, compliance, or procurement questions. Narrow, workflow-specific questions are usually more useful than generic security questionnaires. We are happy to discuss how LoreVia fits into your environment.",
  },
] as const

export default function CompliancePage() {
  return (
    <LegalPageShell
      eyebrow="Security"
      title="Security & Compliance"
      description="LoreVia is a manuscript-processing product. This page explains our practical security posture, how your data moves through the product, and what LoreVia is and is not designed for."
      effectiveDate={effectiveDate}
      notice="This page explains LoreVia's practical trust posture, not a blanket certification claim."
      sections={sections}
      rightRail={
        <LegalRightRail
          items={[
            {
              label: "Best fit",
              value: "Creative and editorial workflows",
              detail: "Draft review, continuity checking, note-taking, and manuscript intelligence.",
            },
            {
              label: "Not intended for",
              value: "Highly regulated workloads",
              detail: "Classified, protected health, or unusually sensitive data requires separate review.",
            },
            {
              label: "Security reports",
              value: LEGAL_EMAIL,
              href: `mailto:${LEGAL_EMAIL}`,
              detail: "Report vulnerabilities privately so they can be verified and contained.",
            },
          ]}
        />
      }
      contactBlock={
        <LegalContactBlock
          title="Need help?"
          description="If you have questions about trust, security, compliance, or procurement, contact LoreVia directly."
          supportEmail={SUPPORT_EMAIL}
          legalEmail={LEGAL_EMAIL}
        />
      }
    />
  )
}
