/** @type {import("next").NextConfig} */
const nextConfig = {
  typedRoutes: true,
  output: "standalone",
  productionBrowserSourceMaps: false,
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
              "img-src 'self' data: blob: https://getlorevia.com https://api.getlorevia.com",
              "font-src 'self'",
              "connect-src 'self' https://getlorevia.com https://api.getlorevia.com https://eu.posthog.com",
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
