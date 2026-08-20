import { ImageResponse } from "next/og"
import { notFound } from "next/navigation"

import { getAnswerPageBySlug } from "@/lib/content"
import { toAbsoluteUrl } from "@/lib/seo"

export const alt = "Answer from LoreVia Editorial"
export const size = { width: 1200, height: 630 }
export const contentType = "image/png"

export default async function OpenGraphImage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params
  const answer = getAnswerPageBySlug(slug)
  if (!answer) notFound()

  return new ImageResponse(
    <div
      style={{
        width: "100%",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        background: "#f6f1e8",
        color: "#171b1d",
        padding: "68px 76px",
        borderTop: "14px solid #21615e",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
        <img src={toAbsoluteUrl("/image.png")} alt="" width="54" height="54" style={{ objectFit: "contain" }} />
        <span style={{ fontSize: 25, fontWeight: 700, letterSpacing: "0.02em" }}>LoreVia Editorial</span>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 22, maxWidth: 1020 }}>
        <span style={{ color: "#21615e", fontSize: 22, fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase" }}>
          {answer.category}
        </span>
        <div style={{ fontFamily: "Georgia", fontSize: answer.title.length > 58 ? 58 : 68, lineHeight: 1.04, letterSpacing: "-0.035em" }}>
          {answer.title}
        </div>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", color: "#5c625f", fontSize: 20 }}>
        <span>A practical answer for fiction revision</span>
        <span>getlorevia.com/answers</span>
      </div>
    </div>,
    size,
  )
}
