import type { Metadata } from "next"

import { LegalPageShell, LegalRightRail } from "@/components/legal/LegalPageShell"
import { COPYRIGHT_EMAIL, DELETION_REQUEST_EMAIL, SUPPORT_EMAIL } from "@/lib/constants/contact"
import { TRUST_EFFECTIVE_DATE } from "@/lib/constants/trust"

export const metadata: Metadata = {
  title: "Privacy Policy",
  description: "Learn how LoreVia for authors handles account data, manuscript uploads, analytics preferences, and third-party processing.",
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
      "A device identifier stored or derived on your device to help recognize repeat signups from the same device",
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
      "Limit repeated account creation from the same device, including enforcing a maximum of two accounts per device where that limit applies",
    ],
  },
  {
    title: "Manuscript processing and AI features",
    paragraphs: [
      "LoreVia processes manuscripts, notes, and related workspace content using our systems and trusted AI models to provide analysis, organization, and drafting features.",
    ],
    bullets: [
      "Manuscripts are processed only to deliver the functionality you request",
      "We do not use your manuscripts to train public AI models",
      "Outputs and derived metadata such as embeddings may be stored to support requested product features",
      "Private manuscripts are not public books unless you explicitly publish them",
      "You can request deletion of manuscripts and related outputs",
    ],
  },
  {
    title: "Public books versus private workspaces",
    paragraphs: [
      "LoreVia separates private author workspaces from public books. Uploading a manuscript does not by itself make it public.",
      "If you choose to publish a public book, that book may be displayed to other users, indexed, and linked from public LoreVia pages while it remains published and in good standing.",
    ],
    bullets: [
      "Private manuscripts remain accessible only through authenticated product workflows and authorized sharing features",
      "Public-domain demo books may be surfaced by LoreVia for onboarding, search, and showcase purposes",
      "Public books may be hidden, removed, or restricted if they are reported or violate policy",
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
      "We keep data only as long as needed to provide the service or as required by law. You may request deletion of your personal data and uploaded manuscript data by using the account deletion option in LoreVia settings or by contacting support@mail.getlorevia.com. We may retain limited information where required for legal, tax, billing, security, or fraud-prevention purposes.",
    ],
    bullets: [
      "Account data is retained while your account is active",
      "Manuscripts, notes, and outputs are retained until you delete them or request deletion",
      "Public books may remain visible until unpublished, removed, or deleted",
      `To request deletion of your account or manuscript data, email ${DELETION_REQUEST_EMAIL}`,
      "Account deletion makes the account inaccessible immediately and queues hard deletion of product and manuscript data after 30 days",
      "Billing invoices, tax records, fraud-prevention records, and security logs may be retained where legally required and detached from product data where possible",
    ],
  },
  {
    title: "Your privacy rights",
    paragraphs: [
      "Depending on where you live, including under GDPR-style data rights, you may have the right to access, erase, correct, object to certain processing, and receive a portable copy of personal data you provided.",
    ],
    bullets: [
      "The Right to Access: you can ask to see what data LoreVia holds about you and how it is used",
      "The Right to Erasure: you can request deletion of personal data and uploaded manuscript data under applicable circumstances",
      "The Right to Rectification: you can request correction of inaccurate or incomplete data",
      "The Right to Object: you can object to specific processing such as optional analytics or direct marketing",
      "Data Portability: you can obtain a machine-readable export of your data from Settings or by contacting support",
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
      `Use ${COPYRIGHT_EMAIL} for copyright or public-content complaints`,
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
