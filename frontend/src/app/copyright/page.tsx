import type { Metadata } from "next"

import { LegalPageShell, LegalRightRail } from "@/components/legal/LegalPageShell"
import { COPYRIGHT_EMAIL, SUPPORT_EMAIL } from "@/lib/constants/contact"

export const metadata: Metadata = {
  title: "Copyright Reports",
  description: "Report copyright or policy issues involving public books on LoreVia.",
  alternates: {
    canonical: "/copyright",
  },
}

const sections = [
  {
    title: "How LoreVia handles rights reports",
    paragraphs: [
      "LoreVia respects intellectual property rights. If you believe content on LoreVia infringes your copyright or other rights, please report it to us.",
      "LoreVia does not currently claim formal DMCA agent registration on this page. This is a copyright reporting and takedown contact channel.",
    ],
  },
  {
    title: "What to include in a report",
    bullets: [
      "Your name",
      "Your email address",
      "The URL of the allegedly infringing LoreVia book",
      "A description of the copyrighted work",
      "An explanation of why the upload is unauthorized",
      "A statement that the report is accurate",
      "A statement that you are the rights owner or authorized to act on the owner's behalf",
    ],
  },
  {
    title: "What LoreVia may do next",
    bullets: [
      "Remove or disable access to reported content",
      "Contact the uploader for additional context",
      "Reject false, incomplete, or abusive reports",
      "Suspend repeat infringers or disable public publishing privileges",
    ],
  },
] as const

export default function CopyrightPage() {
  return (
    <LegalPageShell
      eyebrow="Copyright"
      title="Report a copyright or policy issue"
      description="Use this page if a public LoreVia book appears to infringe your rights or violates our publishing rules."
      effectiveDate="May 19, 2026"
      notice={`Send reports to ${COPYRIGHT_EMAIL}. Include enough detail for us to identify the work, evaluate the claim, and contact you if clarification is needed.`}
      sections={sections}
      rightRail={
        <LegalRightRail
          items={[
            {
              label: "Copyright contact",
              value: COPYRIGHT_EMAIL,
              href: `mailto:${COPYRIGHT_EMAIL}`,
              detail: "Primary inbox for copyright and public-content complaints.",
            },
            {
              label: "General support",
              value: SUPPORT_EMAIL,
              href: `mailto:${SUPPORT_EMAIL}`,
              detail: "Use support for account, billing, or product questions instead.",
            },
          ]}
        />
      }
    />
  )
}
