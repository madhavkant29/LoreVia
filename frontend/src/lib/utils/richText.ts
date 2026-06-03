const SAFE_TAGS = new Set([
  "p",
  "br",
  "strong",
  "b",
  "em",
  "i",
  "u",
  "s",
  "strike",
  "h1",
  "h2",
  "h3",
  "blockquote",
  "ul",
  "ol",
  "li",
  "div",
  "span",
  "a",
  "img",
  "mark",
  "hr",
])

const SAFE_ALIGNMENTS = new Set(["left", "center", "right", "justify"])

const MAX_PLAIN_TEXT_LENGTH = 500_000

export function htmlToPlainText(html: string) {
  if (typeof window === "undefined") return html.replace(/<[^>]+>/g, " ").slice(0, MAX_PLAIN_TEXT_LENGTH)
  const container = document.createElement("div")
  container.innerHTML = html.slice(0, MAX_PLAIN_TEXT_LENGTH)
  const blocks = Array.from(container.querySelectorAll("h1,h2,h3,p,blockquote,li,div"))
    .map((node) => node.textContent?.trim() ?? "")
    .filter(Boolean)
  return blocks.length ? blocks.join("\n\n") : (container.textContent ?? "").trim()
}

export function renderRichTextHtml(value: string, onCharacterClick?: (characterName: string) => void) {
  const normalized = /<[^>]+>/.test(value) ? value : plainTextToHtml(value)
  return sanitizeRichTextHtml(normalized, onCharacterClick)
}

export function renderMarkdownHtml(value: string) {
  const cleaned = value.trim()
  if (!cleaned) return "<p></p>"

  const markdownHtml = cleaned
    .split(/\n{2,}/)
    .map((paragraph) => `<p>${inlineMarkdownToHtml(paragraph).replace(/\n/g, "<br>")}</p>`)
    .join("")

  return sanitizeRichTextHtml(markdownHtml)
}

export function sanitizeRichTextHtml(html: string, onCharacterClick?: (characterName: string) => void) {
  if (typeof window === "undefined") return serverSafeHtmlFallback(html)
  const container = document.createElement("div")
  container.innerHTML = html

  for (const node of Array.from(container.querySelectorAll("*"))) {
    const tag = node.tagName.toLowerCase()
    if (!SAFE_TAGS.has(tag)) {
      node.replaceWith(...Array.from(node.childNodes))
      continue
    }

    const element = node as HTMLElement
    const textAlign = element.style.textAlign
    const href = tag === "a" ? node.getAttribute("href") : null
    const src = tag === "img" ? node.getAttribute("src") : null
    const alt = tag === "img" ? node.getAttribute("alt") : null
    const mention = tag === "span" ? node.getAttribute("data-mention") : null
    const className = tag === "span" && element.classList.contains("mention-token") ? "mention-token" : null
    const sceneBreak = tag === "div" && node.getAttribute("data-scene-break") === "true"
    const pageBreak = tag === "div" && node.getAttribute("data-page-break") === "true"
    const color = element.style.color
    const backgroundColor = element.style.backgroundColor
    const fontFamily = element.style.fontFamily
    const fontSize = element.style.fontSize
    const lineHeight = element.style.lineHeight
    const marginBottom = element.style.marginBottom
    const textIndent = element.style.textIndent

    Array.from(node.attributes).forEach((attribute) => node.removeAttribute(attribute.name))

    if (textAlign && SAFE_ALIGNMENTS.has(textAlign)) {
      element.style.textAlign = textAlign
    }

    if (color) element.style.color = color
    if (backgroundColor) element.style.backgroundColor = backgroundColor
    if (fontFamily) element.style.fontFamily = fontFamily
    if (fontSize) element.style.fontSize = fontSize
    if (lineHeight) element.style.lineHeight = lineHeight
    if (marginBottom) element.style.marginBottom = marginBottom
    if (textIndent) element.style.textIndent = textIndent

    if (tag === "a" && href) {
      const safeHref = sanitizeHref(href)
      if (safeHref) {
        node.setAttribute("href", safeHref)
        node.setAttribute("target", "_blank")
        node.setAttribute("rel", "noreferrer noopener")
      } else {
        node.replaceWith(...Array.from(node.childNodes))
      }
    }

    if (tag === "img") {
      const safeSrc = sanitizeImageSrc(src)
      if (!safeSrc) {
        node.remove()
        continue
      }
      node.setAttribute("src", safeSrc)
      node.setAttribute("alt", alt?.slice(0, 160) || "Embedded image")
      node.setAttribute("loading", "lazy")
    }

    if (tag === "span" && mention && className) {
      node.setAttribute("data-mention", mention)
      node.setAttribute("class", className)
      if (onCharacterClick) {
        element.style.cursor = "pointer"
        element.onclick = () => onCharacterClick(mention)
      }
    }

    if (sceneBreak) {
      node.setAttribute("data-scene-break", "true")
      node.setAttribute("class", "scene-break-node")
      node.textContent = "***"
    }

    if (pageBreak) {
      node.setAttribute("data-page-break", "true")
      node.setAttribute("class", "page-break-node")
      node.textContent = "Page break"
    }
  }

  const normalized = container.innerHTML.trim()
  return normalized || "<p></p>"
}

function plainTextToHtml(text: string) {
  const cleaned = text.trim()
  if (!cleaned) return "<p></p>"
  return cleaned
    .split(/\n{2,}/)
    .map((paragraph) => `<p>${escapeHtml(paragraph).replace(/\n/g, "<br>")}</p>`)
    .join("")
}

function inlineMarkdownToHtml(value: string) {
  const escaped = escapeHtml(value)
  return escaped
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
}

function sanitizeHref(value: string) {
  const trimmed = value.trim()
  if (/^(https?:|mailto:|tel:|#)/i.test(trimmed)) return trimmed
  if (trimmed.startsWith("/") && !trimmed.startsWith("//")) return trimmed
  return null
}

function sanitizeImageSrc(value: string | null) {
  if (!value) return null
  const trimmed = value.trim()
  if (/^https?:\/\//i.test(trimmed)) return trimmed
  if (trimmed.startsWith("/") && !trimmed.startsWith("//")) return trimmed
  if (/^data:image\/(?:png|jpe?g|gif|webp);base64,[a-z0-9+/=]+$/i.test(trimmed)) return trimmed
  return null
}

function serverSafeHtmlFallback(value: string) {
  const text = value
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/(?:p|div|h[1-3]|blockquote|li)>/gi, "\n\n")
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim()
  return plainTextToHtml(text)
}

function escapeHtml(value: string) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
}
