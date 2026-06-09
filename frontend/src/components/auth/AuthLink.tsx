"use client"

import { useEffect, useRef } from "react"
import Link from "next/link"
import type { Route } from "next"
import { useAuthStore } from "@/lib/stores/authStore"
import { authApi } from "@/lib/api/auth"

interface AuthLinkProps {
  href: "/login" | "/register"
  children: React.ReactNode
  className?: string
}

/**
 * A smart navigation link for auth pages that validates the session before navigation.
 * If there's a cached user but the session is invalid, it clears the stale data and
 * sets the session_dead marker to prevent middleware redirect loops.
 */
export function AuthLink({ href, children, className }: AuthLinkProps) {
  const user = useAuthStore((s) => s.user)
  const validating = useRef(false)

  // Pre-validate session when the component mounts if there's a cached user
  useEffect(() => {
    if (user && !validating.current) {
      validating.current = true
      authApi.me()
        .then((validUser) => {
          if (!validUser) {
            // Session expired, clear stale user and set marker for middleware
            document.cookie = "lorevia_session_dead=1; Max-Age=30; Path=/; Secure; SameSite=Lax"
            useAuthStore.getState().logout()
          }
        })
        .catch(() => {
          // Session invalid, clear stale user and set marker for middleware
          document.cookie = "lorevia_session_dead=1; Max-Age=30; Path=/; Secure; SameSite=Lax"
          useAuthStore.getState().logout()
        })
        .finally(() => {
          validating.current = false
        })
    }
  }, [user])

  const handleClick = async (e: React.MouseEvent) => {
    // If there's a user in the store, validate the session before navigating
    const currentUser = useAuthStore.getState().user
    if (currentUser) {
      e.preventDefault()
      
      try {
        const validUser = await authApi.me()
        if (!validUser) {
          // Session expired, clear stale data and set marker
          document.cookie = "lorevia_session_dead=1; Max-Age=30; Path=/; Secure; SameSite=Lax"
          useAuthStore.getState().logout()
          
          // Small delay to ensure cookie is set before navigation
          await new Promise(resolve => setTimeout(resolve, 50))
        }
      } catch {
        // Session invalid, clear stale data and set marker
        document.cookie = "lorevia_session_dead=1; Max-Age=30; Path=/; Secure; SameSite=Lax"
        useAuthStore.getState().logout()
        
        // Small delay to ensure cookie is set before navigation
        await new Promise(resolve => setTimeout(resolve, 50))
      }
      
      // Now navigate
      window.location.href = href
    }
  }

  return (
    <Link href={href as Route} className={className} onClick={handleClick}>
      {children}
    </Link>
  )
}
