/** @type {import("next").NextConfig} */
function getApiOrigin() {
  const apiUrl = process.env.API_ORIGIN || process.env.NEXT_PUBLIC_API_URL
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
  transpilePackages: ["next-mdx-remote"],
  outputFileTracingIncludes: {
    "/*": ["./src/content/**/*.mdx"],
  },
  productionBrowserSourceMaps: false,
  experimental: {
    webpackBuildWorker: false,
    optimizePackageImports: [
      "@tiptap/core",
      "@tiptap/react",
      "@tiptap/starter-kit",
      "@tiptap/extension-color",
      "@tiptap/extension-highlight",
      "@tiptap/extension-image",
      "@tiptap/extension-link",
      "@tiptap/extension-task-item",
      "@tiptap/extension-task-list",
      "@tiptap/extension-text-align",
      "@tiptap/extension-text-style",
      "@tiptap/extension-underline",
    ],
  },
  allowedDevOrigins: [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
  ],
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

if (process.env.E2E_NEXT_DIST_DIR) {
  if (!/^\.next-e2e-\d+$/.test(process.env.E2E_NEXT_DIST_DIR)) {
    throw new Error("Refusing to use an unexpected E2E build directory.")
  }
  nextConfig.distDir = process.env.E2E_NEXT_DIST_DIR
}

// Fail closed: a production bundle must never carry the E2E mock flag unless a
// server-only acknowledgement was explicitly set for an approved test build.
if (
  process.env.NODE_ENV === "production" &&
  process.env.NEXT_PUBLIC_E2E_MOCK_API === "1" &&
  process.env.ADMIN_E2E_ALLOW_PRODUCTION !== "1"
) {
  throw new Error(
    "Refusing to build a production bundle with NEXT_PUBLIC_E2E_MOCK_API=1. " +
      "Unset the flag, or set ADMIN_E2E_ALLOW_PRODUCTION=1 for an approved test build.",
  )
}

module.exports = nextConfig
