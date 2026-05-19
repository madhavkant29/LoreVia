import { headers } from "next/headers"
import Script from "next/script"

type JsonLdScriptProps = {
  id: string
  data: unknown
}

export async function JsonLdScript({ id, data }: JsonLdScriptProps) {
  const nonce = (await headers()).get("x-nonce") ?? undefined

  return (
    <Script id={id} type="application/ld+json" strategy="beforeInteractive" nonce={nonce}>
      {JSON.stringify(data).replace(/</g, "\\u003c")}
    </Script>
  )
}
