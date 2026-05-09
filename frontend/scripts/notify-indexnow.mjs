const SITE_URL = "https://getlorevia.com"
const INDEXNOW_KEY_PATH = "/indexnow-key.txt"
const STATIC_PUBLIC_ROUTES = [
  "/",
  "/compliance",
  "/contact",
  "/eula",
  "/privacy",
  "/pricing",
  "/refund",
  "/status",
  "/terms",
]

function toAbsoluteUrl(path) {
  return new URL(path, SITE_URL).toString()
}

async function main() {
  const key = process.env.INDEXNOW_KEY?.trim()

  if (!key) {
    console.error("Missing INDEXNOW_KEY.")
    process.exit(1)
  }

  const body = {
    host: new URL(SITE_URL).host,
    key,
    keyLocation: toAbsoluteUrl(INDEXNOW_KEY_PATH),
    urlList: STATIC_PUBLIC_ROUTES.map(toAbsoluteUrl),
  }

  const response = await fetch("https://api.indexnow.org/indexnow", {
    method: "POST",
    headers: {
      "Content-Type": "application/json; charset=utf-8",
    },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    const errorText = await response.text()
    console.error(`IndexNow submit failed (${response.status}): ${errorText}`)
    process.exit(1)
  }

  console.log(`Submitted ${body.urlList.length} URLs to IndexNow.`)
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
