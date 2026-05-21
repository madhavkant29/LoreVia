import { resolveApiOrigin } from "@/lib/constants"

type MediaAssetLike = {
  url?: string | null
  content_base64?: string | null
  content_type?: string | null
}

export function resolveAssetUrl(assetUrl: string | null | undefined): string | null {
  if (!assetUrl) return null
  if (/^(?:https?:)?\/\//i.test(assetUrl)) return assetUrl
  if (/^(?:data|blob):/i.test(assetUrl)) return assetUrl
  try {
    return new URL(assetUrl, resolveApiOrigin()).toString()
  } catch {
    return assetUrl
  }
}

export function resolveMediaAssetSrc(item: MediaAssetLike): string {
  const resolvedUrl = resolveAssetUrl(item.url)
  if (resolvedUrl) return resolvedUrl
  if (item.content_base64 && item.content_type) {
    return `data:${item.content_type};base64,${item.content_base64}`
  }
  return ""
}
