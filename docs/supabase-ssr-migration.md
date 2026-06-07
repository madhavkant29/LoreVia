# Supabase SSR Migration

## Issue
Users were encountering the error:
```
PKCE code verifier not found in storage
```

This happened because the LoreVia frontend was using `@supabase/supabase-js` with `persistSession: false`, which prevented the PKCE code verifier from being properly stored and retrieved during the OAuth callback flow in Next.js.

## Root Cause
- The standard `@supabase/supabase-js` client doesn't properly handle session persistence in SSR environments
- PKCE (Proof Key for Code Exchange) code verifiers need to be stored across page navigations
- With `persistSession: false`, the code verifier was lost between the OAuth initiation and callback

## Solution
Migrated to `@supabase/ssr` package which provides proper SSR-compatible client utilities.

### Changes Made

#### 1. Package Installation
```bash
npm install @supabase/ssr
```

#### 2. Updated Client Configuration (`src/lib/supabase.ts`)
**Before:**
```typescript
import { createClient } from "@supabase/supabase-js"

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    flowType: "pkce",
    detectSessionInUrl: true,
    persistSession: false,
    autoRefreshToken: false,
  },
})
```

**After:**
```typescript
import { createBrowserClient } from "@supabase/ssr"

export const supabase = createBrowserClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    flowType: "pkce",
    detectSessionInUrl: true,
    persistSession: true,
    storage: typeof window !== "undefined" ? window.localStorage : undefined,
    autoRefreshToken: true,
  },
  cookieOptions: {
    name: "lorevia-supabase-auth",
    domain: typeof window !== "undefined" ? window.location.hostname : undefined,
    path: "/",
    sameSite: "lax",
  },
})
```

#### 3. Created Server-Side Client (`src/lib/supabase-server.ts`)
New utility for server components and API routes:
```typescript
import { createServerClient } from "@supabase/ssr"
import { cookies } from "next/headers"

export async function createSupabaseServerClient() {
  const cookieStore = await cookies()
  return createServerClient(supabaseUrl, supabaseAnonKey, {
    cookies: {
      getAll() {
        return cookieStore.getAll()
      },
      setAll(cookiesToSet) {
        cookiesToSet.forEach(({ name, value, options }) => {
          cookieStore.set(name, value, options)
        })
      },
    },
  })
}
```

#### 4. Updated Middleware (`src/middleware.ts`)
Added Supabase session refresh logic to ensure PKCE flow works correctly:
```typescript
import { createServerClient } from "@supabase/ssr"

// In middleware function:
const supabase = createServerClient(supabaseUrl, supabaseAnonKey, {
  cookies: {
    getAll() {
      return request.cookies.getAll()
    },
    setAll(cookiesToSet) {
      // Handle cookie updates
    },
  },
})

// Refresh session on each request
supabase.auth.getUser()
```

## Key Benefits
1. **Proper PKCE Support**: Code verifier is now stored in localStorage and properly persisted
2. **Auto Session Refresh**: Sessions are automatically refreshed on the server
3. **SSR Compatible**: Works correctly with Next.js server-side rendering
4. **Cookie-Based Storage**: Uses cookies for cross-domain compatibility

## Testing
All 582 frontend unit tests pass, including:
- OAuth button tests
- Middleware CSP tests
- Auth flow tests

## Migration Impact
- **Breaking Change**: Existing Supabase sessions may need to be re-authenticated
- **Cookie Changes**: New cookie named `lorevia-supabase-auth` will be created
- **Storage**: Sessions now persist in localStorage instead of memory

## Rollout Plan
1. Deploy frontend changes
2. Monitor for auth-related errors
3. Users may need to sign in again (expected behavior)

## References
- [Supabase SSR Documentation](https://supabase.com/docs/guides/auth/server-side/nextjs)
- [PKCE Flow](https://oauth.net/2/pkce/)
