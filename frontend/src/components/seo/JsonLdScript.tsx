import { headers } from "next/headers"

type JsonLdScriptProps = {
  id: string
  data: unknown
}

export async function JsonLdScript({ id, data }: JsonLdScriptProps) {
  const nonce = (await headers()).get("x-nonce") ?? undefined

  return (
    <script
      id={id}
      type="application/ld+json"
      nonce={nonce}
      dangerouslySetInnerHTML={{ __html: JSON.stringify(data).replace(/</g, "\\u003c") }}
    />
  )
}
