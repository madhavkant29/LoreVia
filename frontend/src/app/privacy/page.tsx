import type { Metadata } from "next"

import { LegalPageShell, LegalRightRail } from "@/components/legal/LegalPageShell"
import { SUPPORT_EMAIL } from "@/lib/constants/contact"
import { TRUST_EFFECTIVE_DATE } from "@/lib/constants/trust"

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "Learn how LoreVia handles account data, manuscript uploads, analytics preferences, and third-party processing.",
  alternates: {
    canonical: "/privacy",
  },
}

const sections = [
  {
    title: "What this policy covers",
    paragraphs: [
      "This Privacy Policy explains how LoreVia handles information when someone interacts with the product, including accounts, manuscripts, workspace activity, support, and website usage. It applies to everyone who creates an account, uses our services, or visits our website.",
    ],
  },
  {
    title: "Information LoreVia collects",
    paragraphs: [
      "We collect information you provide, such as account details and manuscripts, as well as information created through your use of the product.",
    ],
    bullets: [
      "Account and profile data, including name, email, and organization",
      "Manuscripts, content, metadata, and derived outputs",
      "Usage and activity data, including features used and device information",
      "Support communications and preferences",
      "Technical data, including IP address, browser, cookies, and analytics",
    ],
  },
  {
    title: "How LoreVia uses that information",
    paragraphs: [
      "We use information to operate and improve the product, personalize your experience, and keep your account secure.",
    ],
    bullets: [
      "Provide, maintain, and improve LoreVia",
      "Process manuscripts and generate outputs",
      "Personalize features and remember preferences",
      "Communicate with you about your account or updates",
      "Detect, investigate, and prevent abuse and security risks",
    ],
  },
  {
    title: "Manuscript processing and AI features",
    paragraphs: [
      "LoreVia processes your manuscripts using our systems and trusted AI models to provide features like analysis, tools, and content generation.",
    ],
    bullets: [
      "Manuscripts are processed only to deliver the functionality you request",
      "We do not use your manuscripts to train public AI models",
      "Outputs are returned to you and are not used for other customers",
      "You can delete manuscripts and outputs at any time",
    ],
  },
  {
    title: "Cookies, analytics, and website preferences",
    paragraphs: [
      "We use cookies and similar technologies to keep the site working, remember preferences, and help us understand usage.",
    ],
    bullets: [
      "Essential cookies are required for the site to function",
      "Analytics cookies help us improve performance and usability",
      "You can manage cookie preferences in your browser settings",
    ],
  },
  {
    title: "Sharing, vendors, and subprocessors",
    paragraphs: [
      "We do not sell your personal data. LoreVia works with trusted vendors to operate and improve the service.",
    ],
    bullets: [
      "Cloud hosting and storage providers",
      "AI service providers used to power product features",
      "Analytics and monitoring providers",
      "Support and communication tools",
    ],
  },
  {
    title: "Retention and deletion",
    paragraphs: [
      "We keep data only as long as needed to provide the service or as required by law.",
    ],
    bullets: [
      "Account data is retained while your account is active",
      "Manuscripts and outputs are retained until you delete them",
      "You can export or delete data at any time from your account settings",
      "After deletion, data is removed from active systems within 30 days and backups within 90 days",
    ],
  },
  {
    title: "Security boundaries and sensitive data",
    paragraphs: [
      "We use technical and organizational safeguards to protect your data.",
    ],
    bullets: [
      "Encryption in transit and at rest",
      "Access controls and least-privilege access",
      "Regular security reviews and monitoring",
      "The service is not intended for protected health information or other highly sensitive data unless agreed in writing",
    ],
  },
  {
    title: "Questions, requests, and policy changes",
    paragraphs: [
      "You can ask questions, request access, or update your preferences anytime.",
    ],
    bullets: [
      "Contact us for access, correction, or deletion requests",
      "We may update this policy from time to time",
      "Material changes will be communicated via email or in-product notice",
    ],
  },
] as const

export default function PrivacyPage() {
  return (
    <LegalPageShell
      eyebrow="Privacy"
      title="Privacy policy for a manuscript-first product"
      description="LoreVia handles account data, manuscripts, and workspace activity to power product functionality and provide a secure experience."
      effectiveDate={TRUST_EFFECTIVE_DATE}
      notice="LoreVia is designed for authors, readers, and editorial workflows that need more than a simple file upload box. This policy is specific to the website and application as they exist today."
      sections={sections}
      rightRail={
        <LegalRightRail
          items={[
            {
              label: "What we collect",
              value: "Accounts, manuscripts, workspace activity, and technical data.",
              href: "#section-2",
              detail: "Accounts, manuscripts, workspace activity, and technical data.",
            },
            {
              label: "How data is used",
              value: "Product operation and security",
              href: "#section-3",
              detail: "To run the product, improve quality, and keep your account secure.",
            },
            {
              label: "Questions",
              value: SUPPORT_EMAIL,
              href: `mailto:${SUPPORT_EMAIL}`,
              detail: "Use support for account, data, or privacy-choice questions.",
            },
          ]}
        />
      }
    />
  )
}
