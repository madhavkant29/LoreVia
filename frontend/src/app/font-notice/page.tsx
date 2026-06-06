import type { Metadata } from "next"

import { LegalPageShell, LegalRightRail } from "@/components/legal/LegalPageShell"
import { LEGAL_EMAIL } from "@/lib/constants/contact"

export const metadata: Metadata = {
  title: "Font Notice",
  description: "Font licensing and export font information for LoreVia.",
  alternates: {
    canonical: "/font-notice",
  },
}

const sections = [
  {
    title: "EB Garamond",
    paragraphs: [
      "LoreVia may use EB Garamond by family name in reader and export typography. EB Garamond is licensed under the SIL Open Font License, Version 1.1.",
      "Copyright 2017 The EB Garamond Project Authors. The project is available at https://github.com/octaviopardo/EBGaramond12 and the license text is available at https://openfontlicense.org.",
    ],
  },
  {
    title: "Old Style Serif",
    paragraphs: [
      "Old Style Serif is a LoreVia label for a fallback font stack. It may name fonts such as Iowan Old Style, Palatino Linotype, Book Antiqua, Palatino, Georgia, and generic serif.",
      "LoreVia does not redistribute those proprietary system font files. The user's device, operating system, browser, or document reader chooses the installed font or fallback.",
    ],
  },
  {
    title: "Exports",
    paragraphs: [
      "DOCX and EPUB exports may declare the selected font family. If the selected font is unavailable on the recipient's device, their reader may substitute another font.",
      "PDF exports use built-in PDF font mappings unless an open font file is explicitly bundled. Markdown and vault ZIP exports include a font notice where typography is not embedded.",
    ],
  },
  {
    title: "Redistribution",
    paragraphs: [
      "LoreVia does not grant rights to copy, extract, or redistribute third-party proprietary fonts. If a user uploads or supplies a separate font file, they are responsible for having the needed rights.",
      "Questions about font licensing can be sent to the legal contact listed on this page.",
    ],
  },
] as const

export default function FontNoticePage() {
  return (
    <LegalPageShell
      eyebrow="Font Notice"
      title="Font licensing and export typography"
      description="This page explains how LoreVia handles EB Garamond, Old Style Serif fallback stacks, and selected fonts in exported documents."
      effectiveDate="June 6, 2026"
      notice="LoreVia uses safe font fallback stacks and does not redistribute Apple, Microsoft, Monotype, or other proprietary system font files unless a separate valid license allows it."
      sections={sections}
      rightRail={
        <LegalRightRail
          items={[
            {
              label: "Open font license",
              value: "SIL OFL 1.1",
              href: "https://openfontlicense.org",
              detail: "Primary license reference for EB Garamond.",
            },
            {
              label: "Legal contact",
              value: LEGAL_EMAIL,
              href: `mailto:${LEGAL_EMAIL}`,
              detail: "Use this address for font or licensing questions.",
            },
          ]}
        />
      }
    />
  )
}
