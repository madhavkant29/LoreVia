import type { Metadata } from "next"

import { TrustPage } from "@/components/legal/TrustPage"
import { LEGAL_EMAIL, SUPPORT_EMAIL } from "@/lib/constants/contact"
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
      "This Privacy Policy explains how LoreVia handles information when someone browses the marketing site, creates an account, uploads manuscripts, uses reading and analysis features, contacts support, or purchases a subscription. It is written for the actual way LoreVia works today: a manuscript intelligence product that stores account data, processes user-uploaded text, and generates structured outputs such as summaries, continuity notes, and character insights.",
      "This page is meant to help users understand the product before they trust it with creative work. It does not grant extra contractual rights beyond the Terms of Service or a separate written agreement, but it does describe the categories of data we handle, why we handle them, and where third-party service providers may be involved in delivering the product.",
    ],
  },
  {
    title: "Information LoreVia collects",
    paragraphs: [
      "LoreVia collects a combination of information you provide directly and information created as part of operating the service. That includes account identifiers such as email address, username, authentication state, and subscription tier. It also includes the manuscripts, chapters, notes, worldbuilding material, and related content you choose to upload or generate inside the product.",
      "We also collect operational data required to keep the service working, such as request logs, error diagnostics, feature usage events, browser and device context, and limited billing state needed to confirm whether a paid feature should be available. When you contact support or legal, we also receive the message contents and any attachments you choose to send.",
    ],
    bullets: [
      "Account and sign-in data, including standard registration details and OAuth-based sign-in information when you use supported providers.",
      "Manuscript content, notes, metadata, and derived outputs such as summaries, extracted entities, plot signals, and workspace state.",
      "Subscription and billing status provided through our payment flow, without storing raw payment card details in the main app.",
      "Operational telemetry, abuse-prevention signals, support correspondence, and system diagnostics needed to run and improve the service.",
    ],
  },
  {
    title: "How LoreVia uses that information",
    paragraphs: [
      "We use account information to create and secure your profile, authenticate sessions, remember settings, and determine what features should be available on your plan. We use manuscript and workspace content to power the core product experience: indexing your material, generating analysis, answering grounded questions, and helping you navigate long-form narrative information more efficiently.",
      "We also use operational data to keep the product reliable. That includes debugging failures, monitoring abuse, understanding which workflows are breaking, and measuring whether features are actually helping users. In some cases, we may review a limited amount of account or content context while responding to a support request, investigating misuse, or diagnosing a defect that you asked us to investigate.",
    ],
  },
  {
    title: "Manuscript processing and AI features",
    paragraphs: [
      "LoreVia exists to process user-submitted creative text. When you upload a manuscript or use analysis tools, the service may store the content, segment it, derive structured metadata from it, and send relevant excerpts or transformed prompts through model-backed systems in order to generate answers, summaries, advisor responses, continuity signals, and related outputs.",
      "That processing is part of the core service, not an incidental background feature. You should only upload work that you own, control, or are otherwise authorized to process in this way. If your internal rules, publishing agreement, client contract, or legal obligations do not allow that processing, you should not submit the material to LoreVia.",
      "AI-generated outputs are also inherently probabilistic. LoreVia can help you reason about a story, but it should not be treated as a substitute for your own editorial judgment, legal review, or rights analysis.",
    ],
  },
  {
    title: "Cookies, analytics, and website preferences",
    paragraphs: [
      "LoreVia uses technical mechanisms that are necessary to keep accounts signed in and the application functioning. Those essential session controls are different from optional analytics. On the marketing and product site, optional usage analytics are gated behind user consent, and the current analytics preference is stored using a consent cookie so the site can remember your choice.",
      "If you accept analytics cookies, LoreVia may initialize product analytics tooling to help us understand which flows people use, where they encounter friction, and whether releases introduce regressions. Declining analytics cookies should not block basic use of the product site. It only limits optional measurement that helps us improve the service.",
    ],
    bullets: [
      "Essential sign-in and application state handling may rely on first-party cookies or similar browser storage needed for account use.",
      "Optional analytics consent is currently tracked through a dedicated site preference cookie so the site can remember whether analytics were allowed.",
      "You can change your analytics choice by clearing the consent cookie and responding to the prompt again when it reappears.",
    ],
  },
  {
    title: "Sharing, vendors, and subprocessors",
    paragraphs: [
      "LoreVia does not treat your manuscript as public marketing material or community content by default. We share information externally only where it is necessary to run the product, process payments, authenticate users, store data, generate model-backed features, comply with law, or protect the service from abuse.",
      "Based on the current product architecture, that may include service providers used for authentication or OAuth handling, object storage, model-backed processing, billing, and optional analytics. At the time of writing, the codebase reflects integrations associated with Supabase, S3-compatible storage, OpenAI-powered processing, Paddle billing infrastructure, and PostHog analytics. Those providers receive only the data needed for their role in delivering the service.",
    ],
  },
  {
    title: "Retention, deletion, and support handling",
    paragraphs: [
      "LoreVia keeps information for as long as it is needed to operate the account, preserve user workspaces, meet legal obligations, resolve disputes, investigate abuse, or restore service from backups. Different categories of data may follow different timelines. For example, billing records may need to persist longer than a draft note, and short-lived logs may expire much sooner than core account records.",
      "If you delete content from the product or ask to close your account, we will handle that request in line with the live product state, reasonable backup cycles, and any legal or anti-fraud obligations that still apply. If you need deletion help or want to understand what can be removed, contact support with the account email and enough context for us to locate the relevant material.",
    ],
  },
  {
    title: "Security boundaries and sensitive data expectations",
    paragraphs: [
      "LoreVia is built for creative and editorial workflows, not as a general-purpose vault for every category of confidential information. Please do not treat the service as approved for medical records, payment card data, government-classified material, export-controlled data, or other high-regulation workloads unless LoreVia has explicitly agreed to support that use in writing.",
      "Users are also responsible for the sensitivity of the text they upload. If a manuscript contains embedded personal data, client secrets, or contractual information that should never be processed by application infrastructure or model-backed systems, the safest choice is not to submit it.",
    ],
  },
  {
    title: "Questions, requests, and policy changes",
    paragraphs: [
      "If you have privacy questions, support issues, or a request related to your account or uploaded content, contact LoreVia directly. We may update this policy as the product evolves, adds integrations, changes workflows, or refines how features are delivered. When that happens, the effective date on this page will change to reflect the current published version.",
      "If a change materially alters how the product handles user data, we aim to update the written policy before or alongside that product change so the documentation stays aligned with reality rather than lagging behind it.",
    ],
  },
] as const

export default function PrivacyPage() {
  return (
    <TrustPage
      currentPath="/privacy"
      eyebrow="Privacy"
      title="Privacy policy for a manuscript-first product."
      description="LoreVia handles account data, uploaded manuscripts, workspace activity, and model-backed processing in order to deliver story analysis tools. This page explains what that means in practical terms."
      effectiveDate={TRUST_EFFECTIVE_DATE}
      intro={[
        "LoreVia is designed for authors, readers, and editorial workflows that need more than a simple file upload box. That means privacy here is not abstract. It has to account for long manuscripts, sensitive drafts, analysis workflows, and optional analytics without pretending the product is something it is not.",
        "This policy is intentionally specific to the website and application as they exist today. It avoids broad promises that the product does not currently make, and it explains the tradeoffs that come with using AI-assisted manuscript tooling on a live web platform.",
      ]}
      facts={[
        {
          label: "Core data",
          value: "Accounts, manuscripts, workspace state",
          detail: "LoreVia needs both identity data and uploaded narrative content to deliver its main features.",
        },
        {
          label: "Processing model",
          value: "Storage plus model-backed analysis",
          detail: "Uploaded material may be stored, transformed, and processed to create summaries, insights, and grounded responses.",
        },
        {
          label: "Optional analytics",
          value: "Consent-based site analytics",
          detail: "The site supports an optional analytics flow instead of assuming every visitor agrees to tracking.",
        },
        {
          label: "Questions",
          value: `${SUPPORT_EMAIL} / ${LEGAL_EMAIL}`,
          detail: "Use support for account and product help, or legal for formal privacy and rights questions.",
        },
      ]}
      sections={[...sections]}
      contacts={[
        {
          title: "Privacy and account support",
          description: "Use this inbox for deletion questions, account troubleshooting, manuscript handling questions, or general product support.",
          ctaLabel: SUPPORT_EMAIL,
          ctaHref: `mailto:${SUPPORT_EMAIL}`,
        },
        {
          title: "Formal legal requests",
          description: "Use this inbox for formal privacy, rights, or legal notices that should be handled outside the normal support queue.",
          ctaLabel: LEGAL_EMAIL,
          ctaHref: `mailto:${LEGAL_EMAIL}`,
        },
      ]}
    />
  )
}
