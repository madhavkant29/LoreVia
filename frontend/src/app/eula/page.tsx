import type { Metadata } from "next"

import { TrustPage } from "@/components/legal/TrustPage"
import { LEGAL_EMAIL } from "@/lib/constants/contact"
import { TRUST_EFFECTIVE_DATE } from "@/lib/constants/trust"

export const metadata: Metadata = {
  title: "End User License Agreement",
  description: "Review the LoreVia software license covering permitted use, restrictions, ownership, updates, and termination.",
  alternates: {
    canonical: "/eula",
  },
}

const sections = [
  {
    title: "License grant",
    paragraphs: [
      "LoreVia grants you a limited, revocable, non-exclusive, non-transferable license to access and use the website and application for your own lawful reading, writing, editorial, study, or business workflows, subject to the plan you purchased and the other footer-linked policies on this site.",
      "This license is a permission to use the product, not a transfer of ownership in the software. Your right to use LoreVia exists only while you comply with the service terms, plan limits, and any applicable law.",
    ],
  },
  {
    title: "What the license allows",
    paragraphs: [
      "The license allows you to upload and process authorized materials through the ordinary features of the product, store workspace information in your account, generate outputs for your own internal use, and export results where the product provides an export path.",
      "It does not give you a right to copy the service architecture, misrepresent the product as your own, or turn a normal user account into a redistribution channel for the software itself.",
    ],
  },
  {
    title: "Restrictions",
    paragraphs: [
      "Unless applicable law overrides the restriction, you may not reverse engineer, decompile, resell, sublicense, mirror, mass-copy, or use LoreVia to build a competing service based on internal behavior, product outputs, or interface structure. You also may not strip branding or technical controls from exported materials in a way that misstates their origin.",
      "You may not use the service in a way that bypasses usage controls, rate limits, subscription boundaries, authentication protections, or security measures. Restrictions that exist to protect other users and the service itself are part of the license, not optional housekeeping rules.",
    ],
  },
  {
    title: "Ownership of software and user content",
    paragraphs: [
      "LoreVia and its licensors retain all rights, title, and interest in the website, application, visual design, software logic, service infrastructure, trademarks, and documentation except for the limited license granted here. Uploading content into LoreVia does not transfer ownership of your manuscript to LoreVia.",
      "You remain responsible for the rights status of the works you upload. If a manuscript, draft, note collection, or client file carries legal restrictions, those restrictions continue to matter even when the material is inside your LoreVia workspace.",
    ],
  },
  {
    title: "Updates, betas, and evolving features",
    paragraphs: [
      "LoreVia may modify the software over time, including adding, removing, or reshaping features. Some features may be labeled experimental, beta, or early access. Those features may be less stable, may change without notice, and may be removed without any obligation to preserve the exact behavior of the preview.",
      "Continued use of the application after updates means you are using the current licensed version of the service, not preserving a perpetual right to an earlier implementation.",
    ],
  },
  {
    title: "Open-source components and third-party services",
    paragraphs: [
      "Parts of the LoreVia stack may incorporate open-source software or rely on third-party hosted services. Where an open-source license requires its own notices or grants, that underlying license continues to apply to the relevant component. This EULA governs LoreVia's software and service layer, but it does not erase rights that come from independent third-party licenses.",
      "Similarly, third-party service providers used for billing, authentication, analytics, storage, or model-backed processing may have their own customer-facing terms for the roles they perform.",
    ],
  },
  {
    title: "Termination and survival",
    paragraphs: [
      "This license terminates automatically if you materially violate it or if your access to the service is suspended or ended under the Terms of Service. Upon termination, your right to use the software ends, even if some records must still be retained for billing, legal, support, or anti-abuse reasons.",
      "Sections dealing with ownership, restrictions, disclaimers, legal rights, and liability boundaries survive to the extent necessary to remain enforceable after account closure or service termination.",
    ],
  },
  {
    title: "No transfer of warranty",
    paragraphs: [
      "LoreVia is licensed on an as-available basis. The fact that you have a license to use the software does not create a promise that it will be uninterrupted, error-free, fit for every purpose, or suitable for every type of data. The product should be evaluated against the actual workflow you intend to run, not against a theoretical perfect editor or perfect analysis engine.",
      "If you need legal clarification about the license, especially for commercial or client-facing use, contact LoreVia before assuming the answer from generalized SaaS boilerplate found elsewhere online.",
    ],
  },
] as const

export default function EulaPage() {
  return (
    <TrustPage
      currentPath="/eula"
      eyebrow="License"
      title="The software license behind the LoreVia website and app."
      description="The EULA explains what LoreVia lets you do with the application, what remains prohibited, and how software access differs from ownership of the product."
      effectiveDate={TRUST_EFFECTIVE_DATE}
      intro={[
        "This agreement is about the software itself: the website, the app, and the right to use them. It complements the Terms of Service, which cover behavior, billing, and content responsibilities more broadly.",
        "The key point is simple: using LoreVia gives you permission to use a hosted manuscript tool under a defined license. It does not transfer the software, infrastructure, or product rights to you.",
      ]}
      facts={[
        {
          label: "License type",
          value: "Limited, revocable, non-exclusive",
          detail: "Access depends on ongoing compliance with the service terms and applicable law.",
        },
        {
          label: "Not allowed",
          value: "Reverse engineering, resale, cloning",
          detail: "The license does not allow building a competing service out of LoreVia's product behavior or internals.",
        },
        {
          label: "Your uploads",
          value: "Still your responsibility",
          detail: "Using the app does not change the copyright or permissions status of the work you upload.",
        },
        {
          label: "Questions",
          value: LEGAL_EMAIL,
          detail: "Use the legal inbox for licensing questions that matter to a commercial, client, or team workflow.",
        },
      ]}
      sections={[...sections]}
      contacts={[
        {
          title: "License questions",
          description: "Use this inbox if you need clarity on permitted commercial use, team usage questions, or a formal license interpretation issue.",
          ctaLabel: LEGAL_EMAIL,
          ctaHref: `mailto:${LEGAL_EMAIL}`,
        },
      ]}
    />
  )
}
