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

const nextConfig = {
  typedRoutes: true,
  output: "standalone",
  productionBrowserSourceMaps: false,
  async rewrites() {
    const apiOrigin = getApiOrigin()
    if (!apiOrigin) {
      if (process.env.NODE_ENV !== "production") {
        return [
          {
            source: "/api/v1/:path*",
            destination: "http://localhost:8000/api/v1/:path*",
          },
        ]
      }
      return []
    }

    return [
      {
        source: "/api/v1/:path*",
        destination: `${apiOrigin}/api/v1/:path*`,
      },
    ]
  },
}
module.exports = nextConfig
