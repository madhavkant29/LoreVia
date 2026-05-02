/** @type {import("next").NextConfig} */
function getApiOrigin() {
  const apiUrl = process.env.NEXT_PUBLIC_API_URL
  if (!apiUrl) return null

  try {
    return new URL(apiUrl).origin
  } catch {
    return null
  }
}

function getApiRewriteOrigin() {
  return getApiOrigin() ?? "http://localhost:8000"
}

const nextConfig = {
  typedRoutes: true,
  output: "standalone",
  productionBrowserSourceMaps: false,
  async rewrites() {
    const apiOrigin = getApiRewriteOrigin()
    return [
      {
        source: "/api/v1/:path*",
        destination: `${apiOrigin}/api/v1/:path*`,
      },
    ]
  },
  async headers() {
    // In `next dev`, Next injects inline scripts + HMR connections that a strict CSP
    // will block, causing a brief render then a blank page. Keep CSP for production.
    if (process.env.NODE_ENV !== "production") return []

    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
          {
            key: "Content-Security-Policy",
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-eval' https://eu.posthog.com",
              "style-src 'self' 'unsafe-inline'",
              [
                "img-src 'self' data: blob: https://getlorevia.com https://api.getlorevia.com",
                getApiOrigin(),
              ]
                .filter(Boolean)
                .join(" "),
              "font-src 'self'",
              [
                "connect-src 'self' https://getlorevia.com https://api.getlorevia.com https://eu.posthog.com",
                getApiOrigin(),
              ]
                .filter(Boolean)
                .join(" "),
              "frame-ancestors 'none'",
              "base-uri 'self'",
              "form-action 'self'",
              "object-src 'none'",
            ].join("; "),
          },
        ],
      },
    ]
  },
}
module.exports = nextConfig
