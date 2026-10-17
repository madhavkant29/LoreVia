import axios from "axios"

export function safeFileBase(value: string | undefined, fallback: string) {
  return (value || fallback).replace(/[^\w\s-]/g, "").trim().replace(/\s+/g, "-") || fallback
}

export function downloadExportBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement("a")
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export async function exportErrorMessage(error: unknown, fallback: string): Promise<string> {
  if (!axios.isAxiosError(error)) return fallback
  let data: unknown = error.response?.data
  if (data instanceof Blob) { try { data = JSON.parse(await data.text()) } catch { return fallback } }
  if (data && typeof data === "object" && "detail" in data && typeof data.detail === "string") return `${fallback} ${data.detail}`
  if ([403, 404].includes(error.response?.status ?? 0)) return `${fallback} Check your project access and plan.`
  return fallback
}

