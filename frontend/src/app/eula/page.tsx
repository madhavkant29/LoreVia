import type { Metadata } from "next"

import { LegalContactBlock, LegalPageShell, LegalRightRail } from "@/components/legal/LegalPageShell"
import { LEGAL_EMAIL, SUPPORT_EMAIL } from "@/lib/constants/contact"

export const metadata: Metadata = {
  title: "End User License Agreement",
  description: "Review the LoreVia software license covering permitted use, restrictions, ownership, updates, and termination.",
  alternates: {
    canonical: "/eula",
  },
}

const effectiveDate = "May 8, 2026"

const sections = [
  {
    title: "License grant",
    bullets: [
      "LoreVia grants you a limited, revocable, non-exclusive, non-transferable license.",
      "Use the website and application for your own internal reading, writing, editorial, study, or business workflows.",
      "Your purchase and the other footer-linked policies on this site are part of this license.",
    ],
  },
  {
    title: "What the license allows",
    bullets: [
      "Upload and process authorized materials through the product features.",
      "Store workspace information in your account and export results.",
      "Use the service across your internal team, paid export results, and related manuscript workflows.",
    ],
  },
  {
    title: "Restrictions",
    bullets: [
      "Do not reverse engineer, decompile, resell, sublicense, mirror, or build competing services.",
      "Do not strip branding or technical controls, or use the software outside its intended purpose.",
      "Do not bypass usage controls, rate limits, security, or authentication.",
    ],
  },
  {
    title: "Ownership of software and user content",
    bullets: [
      "LoreVia and its licensors retain all rights in the platform, software, and designs.",
      "You retain rights to your content. We process it solely to provide the service.",
      "Your rights continue when material is inside your LoreVia workspace.",
    ],
  },
  {
    title: "Updates, betas, and evolving features",
    bullets: [
      "LoreVia may modify, add, remove, or reshape features over time.",
      "Beta features may be experimental and change without notice.",
      "Continued use after updates means you accept the current licensed version.",
    ],
  },
  {
    title: "Open-source components and third-party services",
    bullets: [
      "Parts of the stack may use open-source software or third-party hosted services.",
      "Those components have their own notices or grants that continue to apply.",
      "This EULA governs LoreVia's software and service layer, not those third parties.",
    ],
  },
  {
    title: "Termination and survival",
    bullets: [
      "We may suspend or end access if you violate these terms or for safety, legal, or abuse reasons.",
      "You may stop using LoreVia at any time by closing your account.",
      "Sections on ownership, restrictions, disclaimers, liability, and survival remain in effect.",
    ],
  },
  {
    title: "No transfer of warranty",
    bullets: [
      'LoreVia is provided "as is" and "as available" without warranties.',
      "We don't promise uninterrupted performance or that the service is error-free.",
      "Evaluate the product against your workflow needs, not theoretical perfection.",
    ],
  },
] as const

export default function EulaPage() {
  return (
    <LegalPageShell
      eyebrow="EULA"
      title="The software license behind the LoreVia website and app"
      description="This End User License Agreement explains how you may use the hosted LoreVia software and services, what is allowed, what is restricted, and where ownership begins and ends."
      effectiveDate={effectiveDate}
      sections={sections}
      rightRail={
        <LegalRightRail
          items={[
            {
              label: "License type",
              value: "Limited and non-exclusive",
              detail: "Access depends on an active account and compliance with the terms and law.",
            },
            {
              label: "Not allowed",
              value: "Reverse engineering or resale",
              detail: "You may not reverse engineer, resell, or clone any part of LoreVia or its systems.",
            },
            {
              label: "License questions",
              value: LEGAL_EMAIL,
              href: `mailto:${LEGAL_EMAIL}`,
              detail: "Use legal for commercial-use, licensing, and contract-sensitive questions.",
            },
          ]}
        />
      }
      contactBlock={
        <LegalContactBlock
          title="Need clarification on licensing?"
          description="If you are unsure how these terms apply to your use case, reach out before making commercial or workflow assumptions."
          supportEmail={SUPPORT_EMAIL}
          legalEmail={LEGAL_EMAIL}
        />
      }
    />
  )
}
